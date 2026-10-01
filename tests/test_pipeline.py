import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import actions  # noqa: E402
from integrations import IntegrationError, Linear, Slack  # noqa: E402

ITEMS = [actions.ActionItem("Send the report", "Asha", "2025-03-07"), actions.ActionItem("Book a room", None, None)]


def linear_with(handler) -> Linear:
    return Linear("key", httpx.Client(transport=httpx.MockTransport(handler)))


def test_integrations_are_dry_runs_without_keys():
    tasks = Linear().create_tasks(ITEMS, "Sync")
    assert [t["status"] for t in tasks] == ["dry run", "dry run"] and tasks[0]["due"] == "2025-03-07"
    assert Slack(channel="#team").post("hello") == {"status": "dry run", "channel": "#team", "text": "hello"}


def test_linear_creates_one_issue_per_item_and_assigns_known_owners():
    sent = []

    def handler(request):
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "key"
        if "teams" in body["query"]:
            return httpx.Response(200, json={"data": {"teams": {"nodes": [{"id": "T1"}]},
                                                      "users": {"nodes": [{"id": "U1", "name": "Asha Rao", "displayName": "asha"}]}}})
        sent.append(body["variables"]["input"])
        return httpx.Response(200, json={"data": {"issueCreate": {"issue": {"identifier": f"ENG-{len(sent)}", "url": "https://linear.app/x"}}}})

    tasks = linear_with(handler).create_tasks(ITEMS, "Sync")
    assert [t["status"] for t in tasks] == ["ENG-1", "ENG-2"]
    assert sent[0] == {"teamId": "T1", "title": "Send the report", "description": "From meeting: Sync\nOwner named in the notes: Asha",
                       "dueDate": "2025-03-07", "assigneeId": "U1"}
    assert "dueDate" not in sent[1] and "assigneeId" not in sent[1]


def test_linear_and_slack_report_rejections():
    with pytest.raises(IntegrationError, match="Authentication"):
        linear_with(lambda r: httpx.Response(200, json={"errors": [{"message": "Authentication required"}]})).create_tasks(ITEMS, "x")
    slack = Slack("token", "#team", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": False, "error": "channel_not_found"}))))
    with pytest.raises(IntegrationError, match="channel_not_found"):
        slack.post("hi")
    ok = Slack("token", "#team", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))))
    assert ok.post("hi")["status"] == "posted"


def test_pipeline_end_to_end_with_a_scripted_model(monkeypatch):
    pipeline = pytest.importorskip("pipeline")          # needs agno; skipped where it is not installed
    notes = "Asha: I'll send the report by Friday.\nBen: Should we repaint the office? Asha: Not now."

    class FakeChat:
        def __init__(self, *args):
            pass

        def chat(self, messages):
            return json.dumps({"action_items": [{"task": "Send the report", "owner": "Asha", "due": "Friday"},
                                                {"task": "Repaint the office", "owner": "Zed", "due": "2025-13-99"}]})

    seen = []

    def fake_writer(name, instructions, model, base_url, api_key):
        async def arun(context):
            seen.append((name, context))
            return SimpleNamespace(content=f" {name} output ")
        return SimpleNamespace(arun=arun)

    monkeypatch.setattr(pipeline.actions, "ChatModel", FakeChat)
    monkeypatch.setattr(pipeline, "writer", fake_writer)

    class BrokenSlack(Slack):
        def post(self, text):
            raise IntegrationError("Slack: channel_not_found")

    steps = []
    result = asyncio.run(pipeline.run(notes, dt.date(2025, 3, 3), "m", "http://x", slack=BrokenSlack(), on_step=steps.append))
    assert [(i.task, i.owner, i.due) for i in result.items] == [("Send the report", "Asha", "2025-03-07"), ("Repaint the office", None, None)]
    assert result.recap == "Recap writer output" and result.summary == "Summary writer output"
    assert {name for name, _ in seen} == {"Recap writer", "Summary writer"}
    assert "owner: Asha | due: 2025-03-07" in seen[0][1] and "unassigned" in seen[0][1]      # agents get the checked items
    assert [t["status"] for t in result.tasks] == ["dry run", "dry run"]
    assert result.warnings == ["Slack: channel_not_found"] and result.slack == {}             # tasks survive a Slack failure
    assert len(steps) == 3
