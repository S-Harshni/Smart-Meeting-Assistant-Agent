"""Linear and Slack, called by code rather than by a language model.

The model decides *what* the tasks are; creating them is ordinary, checkable code. Without a key each
client runs in dry-run mode and reports what it would have sent, so the app can be tried with no accounts.
"""
from dataclasses import dataclass, field

import httpx

from actions import ActionItem

LINEAR_URL = "https://api.linear.app/graphql"
SLACK_URL = "https://slack.com/api/chat.postMessage"


class IntegrationError(RuntimeError):
    """The service rejected the request (bad key, unknown channel, ...)."""


@dataclass
class Linear:
    api_key: str | None = None
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=30))

    def _call(self, query: str, variables: dict | None = None) -> dict:
        response = self.client.post(LINEAR_URL, json={"query": query, "variables": variables or {}},
                                    headers={"Authorization": self.api_key})
        body = response.json() if response.content else {}
        if response.status_code != 200 or body.get("errors"):
            raise IntegrationError(f"Linear: {(body.get('errors') or [{'message': response.status_code}])[0]['message']}")
        return body["data"]

    def create_tasks(self, items: list[ActionItem], meeting_title: str) -> list[dict]:
        """One issue per action item, assigned to the owner when a workspace member's name matches."""
        if not self.api_key:
            return [{"title": i.task, "owner": i.owner, "due": i.due, "status": "dry run"} for i in items]
        data = self._call("{ teams(first: 1) { nodes { id } } users { nodes { id name displayName } } }")
        if not data["teams"]["nodes"]:
            raise IntegrationError("Linear: the workspace has no team to file issues in")
        team = data["teams"]["nodes"][0]["id"]
        members = {(u.get("displayName") or u["name"]).split()[0].lower(): u["id"] for u in data["users"]["nodes"]}
        created = []
        for item in items:
            fields = {"teamId": team, "title": item.task, "description": f"From meeting: {meeting_title}"
                      + (f"\nOwner named in the notes: {item.owner}" if item.owner else "")}
            if item.due:
                fields["dueDate"] = item.due
            if item.owner and item.owner.lower() in members:
                fields["assigneeId"] = members[item.owner.lower()]
            issue = self._call("mutation($input: IssueCreateInput!) { issueCreate(input: $input) { issue { identifier url } } }",
                               {"input": fields})["issueCreate"]["issue"]
            created.append({"title": item.task, "owner": item.owner, "due": item.due, "status": issue["identifier"], "url": issue["url"]})
        return created


@dataclass
class Slack:
    token: str | None = None
    channel: str = "#general"
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=30))

    def post(self, text: str) -> dict:
        if not self.token:
            return {"status": "dry run", "channel": self.channel, "text": text}
        response = self.client.post(SLACK_URL, json={"channel": self.channel, "text": text},
                                    headers={"Authorization": f"Bearer {self.token}"})
        body = response.json()
        if not body.get("ok"):
            raise IntegrationError(f"Slack: {body.get('error', response.status_code)}")
        return {"status": "posted", "channel": self.channel, "text": text}
