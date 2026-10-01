"""Meeting notes in; validated action items, tasks, a team recap and a summary out.

    notes ──► Extractor ──► validation + deadline tool ──┬──► Linear: one task per item      (code)
              (LLM, JSON)    (code, actions.py)          ├──► Recap agent ──► Slack message  (LLM writes, code posts)
                                                          └──► Summary agent ──► Markdown     (LLM)

The language model is used where judgement is needed (reading the notes, writing prose). Everything
that has a right answer (dates, who exists in the notes, creating tasks, posting) is done by code.
The two writing agents run at the same time.
"""
import asyncio
import datetime as dt
from dataclasses import dataclass, field

from agno.agent import Agent
from agno.models.openai.like import OpenAILike

import actions
from integrations import Linear, Slack

PROVIDERS = {
    "Local (Ollama)": {"base_url": "http://localhost:11434/v1", "model": "llama3.2:3b", "needs_key": False},
    "Nebius AI Studio": {"base_url": "https://api.studio.nebius.com/v1", "model": "moonshotai/Kimi-K2-Instruct", "needs_key": True},
}

RECAP = """You write a short Slack message for a team after a meeting.
Use only the action items and notes you are given; never add tasks, owners or dates.
Format: one opening line, then one bullet per action item as "• task — owner, due date", then one line on what happens next.
Plain text, at most 120 words, no headings."""

SUMMARY = """You summarise a meeting for people who were not there.
Write Markdown with exactly these sections: "## What was discussed" (3 to 5 bullets), "## Decisions" (bullets; write
"None recorded" if there were none) and "## Open questions" (bullets; "None" if there were none).
Use only what the notes say. Do not list action items; they are shown separately."""


@dataclass
class Result:
    items: list[actions.ActionItem]
    tasks: list[dict] = field(default_factory=list)
    recap: str = ""
    slack: dict = field(default_factory=dict)
    summary: str = ""
    warnings: list[str] = field(default_factory=list)


def writer(name: str, instructions: str, model: str, base_url: str, api_key: str) -> Agent:
    return Agent(name=name, model=OpenAILike(id=model, base_url=base_url, api_key=api_key, temperature=0.2), instructions=instructions)


def brief(notes: str, items: list[actions.ActionItem]) -> str:
    listed = "\n".join(f"- {i.task} | owner: {i.owner or 'unassigned'} | due: {i.due or 'no deadline'}" for i in items) or "(none)"
    return f"Action items (already checked):\n{listed}\n\nMeeting notes:\n{notes}"


async def run(notes: str, meeting_date: dt.date, model: str, base_url: str, api_key: str = "local", title: str = "Team meeting",
              linear: Linear | None = None, slack: Slack | None = None, on_step=lambda text: None) -> Result:
    on_step("Reading the notes and extracting action items")
    llm = actions.ChatModel(model, base_url, api_key)
    items = await asyncio.to_thread(actions.extract, notes, meeting_date, llm)
    result = Result(items or [])
    if items is None:
        result.warnings.append("The model did not return a usable list of action items.")

    on_step("Writing the summary and the team recap")
    context = brief(notes, result.items)
    recap, summary = await asyncio.gather(
        writer("Recap writer", RECAP, model, base_url, api_key).arun(context),
        writer("Summary writer", SUMMARY, model, base_url, api_key).arun(context),
    )
    result.recap, result.summary = (recap.content or "").strip(), (summary.content or "").strip()

    on_step("Creating tasks and posting the recap")
    for name, call in (("tasks", lambda: (linear or Linear()).create_tasks(result.items, title)),
                       ("slack", lambda: (slack or Slack()).post(result.recap))):
        try:
            setattr(result, name, await asyncio.to_thread(call))
        except Exception as exc:                       # one integration failing must not lose the rest of the result
            result.warnings.append(str(exc))
    return result
