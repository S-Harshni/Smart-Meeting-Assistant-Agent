import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import actions  # noqa: E402

MONDAY = dt.date(2025, 3, 3)


@pytest.mark.parametrize("phrase, expected", [
    ("today", "2025-03-03"), ("tomorrow", "2025-03-04"), ("by Friday", "2025-03-07"), ("Wednesday", "2025-03-05"),
    ("Monday", "2025-03-10"),                 # a weekday named on that same weekday means the coming one
    ("next Friday", "2025-03-14"), ("next Monday", "2025-03-10"),
    ("end of week", "2025-03-07"), ("by the end of the week", "2025-03-07"), ("end of month", "2025-03-31"),
    ("in two weeks", "2025-03-17"), ("in 3 days", "2025-03-06"), ("two days", "2025-03-05"), ("within a week", "2025-03-10"),
    ("this afternoon", "2025-03-03"), ("by end of day", "2025-03-03"),
    ("March 14", "2025-03-14"), ("14th of March", "2025-03-14"), ("Mar 14", "2025-03-14"),
    ("January 10", "2026-01-10"),             # already past this year, so next year
    ("the 20th", "2025-03-20"), ("the 1st", "2025-04-01"), ("2025-04-01", "2025-04-01"),
])
def test_resolve_due(phrase, expected):
    assert actions.resolve_due(phrase, MONDAY) == dt.date.fromisoformat(expected)


@pytest.mark.parametrize("phrase", [None, "", "soon", "when the sandbox is ready", "February 30", "2025-13-40"])
def test_resolve_due_returns_none_when_there_is_no_readable_deadline(phrase):
    assert actions.resolve_due(phrase, MONDAY) is None


def test_end_of_week_on_a_friday_is_that_friday():
    assert actions.resolve_due("end of week", dt.date(2025, 3, 7)) == dt.date(2025, 3, 7)


NOTES = "Asha: I'll send the report by Friday.\nBen: I'll review it."


def test_parse_items_validates_and_resolves():
    reply = json.dumps({"action_items": [
        {"task": "Send the report", "owner": "Asha", "due": "Friday"},
        {"task": "Review the report", "owner": "Ben", "due": None},
        {"task": "Buy cake", "owner": "Zed", "due": "soon"},          # Zed is not in the notes; "soon" is not a date
        {"task": "", "owner": "Ben"}, "not an item",
    ]})
    items = actions.parse_items("Sure! " + reply, NOTES, MONDAY)
    assert [(i.task, i.owner, i.due) for i in items] == [
        ("Send the report", "Asha", "2025-03-07"), ("Review the report", "Ben", None), ("Buy cake", None, None)]


@pytest.mark.parametrize("reply", ["", "no json here", '{"items": []}', '{"action_items": "none"}', "{broken"])
def test_parse_items_rejects_unusable_replies(reply):
    assert actions.parse_items(reply, NOTES, MONDAY) is None


def test_dates_by_model_are_taken_as_given_and_bad_ones_dropped():
    reply = json.dumps({"action_items": [{"task": "A", "owner": "Asha", "due": "2025-03-08"}, {"task": "B", "owner": "Ben", "due": "Friday"}]})
    assert [i.due for i in actions.parse_items(reply, NOTES, MONDAY, dates_by_model=True)] == ["2025-03-08", None]


def test_extract_sends_the_meeting_date_and_weekday():
    class Fake:
        def chat(self, messages):
            self.messages = messages
            return '{"action_items": []}'
    llm = Fake()
    assert actions.extract(NOTES, MONDAY, llm) == []
    assert "2025-03-03 (Monday)" in llm.messages[1]["content"]


def test_matching_is_one_to_one_and_tolerates_rewording():
    expected = [{"task": "Send the pricing proposal to the client", "owner": "Asha", "due": "2025-03-07"},
                {"task": "Book the meeting room", "owner": "Ben", "due": None}]
    found = [actions.ActionItem("Send pricing proposal", "Asha", "2025-03-07"), actions.ActionItem("Send pricing proposal to client", "Asha", None),
             actions.ActionItem("Order lunch", "Ben", None)]
    pairs = actions.match(expected, found)
    assert len(pairs) == 1 and pairs[0][0] is expected[0]


def test_score_on_a_hand_worked_case():
    meetings = [{"action_items": [{"task": "Send the report", "owner": "Asha", "due": "2025-03-07"},
                                  {"task": "Review the report", "owner": "Ben", "due": None}]}]
    perfect = [[actions.ActionItem("Send the report", "Asha", "2025-03-07"), actions.ActionItem("Review the report", "Ben", None)]]
    assert actions.score(meetings, perfect) | {} == actions.score(meetings, perfect)
    s = actions.score(meetings, perfect)
    assert (s["precision"], s["recall"], s["owner_accuracy"], s["deadline_accuracy"], s["deadline_invented"]) == (1, 1, 1, 1, 0)
    flawed = [[actions.ActionItem("Send the report", "Ben", "2025-03-08"), actions.ActionItem("Review the report", "Ben", "2025-03-09"),
               actions.ActionItem("Plan the party", "Asha", None)]]
    s = actions.score(meetings, flawed)
    assert (s["precision"], s["recall"], s["owner_accuracy"], s["deadline_accuracy"], s["deadline_invented"]) == (0.6667, 1, 0.5, 0, 1)
    assert actions.score(meetings, [None])["valid_json"] == 0


def test_labelled_meetings_are_consistent():
    meetings = json.loads((ROOT / "evaluation" / "meetings.json").read_text())
    assert len(meetings) == 18 and sum(len(m["action_items"]) for m in meetings) == 49
    for m in meetings:
        day = dt.date.fromisoformat(m["date"])
        for item in m["action_items"]:
            assert item["owner"] in m["notes"]
            due = actions.resolve_due(item["due_text"], day)
            assert (due.isoformat() if due else None) == item["due"]
            assert item["due"] is None or item["due"] >= m["date"]


def test_a_date_the_model_computed_itself_is_not_trusted():
    notes = "Asha: I'll send the report by next Friday. Ben: I'll book the room on 2025-03-20. Cy: I'll tidy up."
    reply = json.dumps({"action_items": [
        {"task": "Send the report by next Friday", "owner": "Asha", "due": "2025-03-09"},      # wrong arithmetic by the model
        {"task": "Book the room", "owner": "Ben", "due": "2025-03-20"},                        # a date that is written in the notes
        {"task": "Tidy up", "owner": "Cy", "due": "2025-03-05"},                               # invented: nothing to fall back on
    ]})
    items = actions.parse_items(reply, notes, MONDAY)
    assert [(i.due, i.due_text) for i in items] == [("2025-03-14", "next Friday"), ("2025-03-20", "2025-03-20"), (None, "2025-03-05")]


def test_deadline_in_finds_the_last_readable_phrase():
    assert actions.deadline_in("Finish the export button by Thursday", MONDAY) == ("Thursday", dt.date(2025, 3, 6))
    assert actions.deadline_in("Get sign-off by the 20th", MONDAY)[1] == dt.date(2025, 3, 20)
    assert actions.deadline_in("Review March numbers", MONDAY) is None
