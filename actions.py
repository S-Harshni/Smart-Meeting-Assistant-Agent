"""Action items as data: extract them from meeting notes, validate them, and work out the deadlines in code.

The agents in main.py write free text. This module is the checked path: a model lists the action items as
JSON, every item is validated against the notes, and relative deadlines ("next Friday") are turned into
dates by `resolve_due`, a deterministic tool, because small language models are unreliable at calendar arithmetic.
"""
import calendar
import datetime as dt
import json
import os
import re
from dataclasses import asdict, dataclass

import httpx

DEFAULT_BASE_URL = "http://localhost:11434/v1"       # a local Ollama server; Nebius and others speak the same API
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS |= {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10}

SYSTEM = """You extract action items from meeting notes.

An action item is a task that a named person agreed to do or was asked to do. Do not list ideas nobody took,
tasks that were cancelled later in the meeting, or things that are already done.

Reply with JSON only: {"action_items": [{"task": "...", "owner": "...", "due": "..."}]}
- task: a short imperative phrase, e.g. "Send the pricing proposal to the client".
- owner: the first name of the person who will do it, as written in the notes.
- due: __DUE__
If there are no action items, reply {"action_items": []}."""
DUE_PHRASE = 'the deadline in the speaker\'s own words, e.g. "next Friday", "tomorrow", "March 14"; null if none was given.'
DUE_DATE = "the deadline as a calendar date in YYYY-MM-DD format, worked out from the meeting date; null if none was given."


@dataclass
class ActionItem:
    task: str
    owner: str | None
    due: str | None          # ISO date
    due_text: str | None = None


def resolve_due(phrase: str | None, meeting_date: dt.date) -> dt.date | None:
    """Turn a deadline phrase into a date. Returns None when there is no deadline or it cannot be read."""
    if not phrase:
        return None
    if re.fullmatch(r"\s*(by |before )?(this (morning|afternoon|evening)|end of (the )?day|eod|close of business)\s*", phrase.lower()):
        return meeting_date
    text = re.sub(r"\b(by|on|before|the|until|due|within|eod|end of day|morning|afternoon|evening|this)\b", " ", phrase.lower())
    text = re.sub(r"[.,]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if iso := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        try:
            return dt.date(*map(int, iso.groups()))
        except ValueError:
            return None
    if text in ("today", "tonight"):
        return meeting_date
    if text == "tomorrow":
        return meeting_date + dt.timedelta(days=1)
    if text == "end of week":
        return meeting_date + dt.timedelta(days=(4 - meeting_date.weekday()) % 7)
    if text == "end of next week":
        return meeting_date + dt.timedelta(days=(4 - meeting_date.weekday()) % 7 + 7)
    if text == "end of month":
        return meeting_date.replace(day=calendar.monthrange(meeting_date.year, meeting_date.month)[1])
    if span := re.fullmatch(r"(?:in )?(\w+) (day|week)s?(?: time)?", text):
        count = NUMBERS.get(span.group(1)) or (int(span.group(1)) if span.group(1).isdigit() else None)
        return meeting_date + dt.timedelta(days=count * (7 if span.group(2) == "week" else 1)) if count else None
    if day := re.fullmatch(r"(next )?(" + "|".join(WEEKDAYS) + ")", text):
        ahead = (WEEKDAYS.index(day.group(2)) - meeting_date.weekday()) % 7 or 7      # the coming one, never today
        if day.group(1):                                                              # "next Friday": Friday of next week
            monday_next_week = meeting_date + dt.timedelta(days=7 - meeting_date.weekday())
            return monday_next_week + dt.timedelta(days=WEEKDAYS.index(day.group(2)))
        return meeting_date + dt.timedelta(days=ahead)
    month_day = re.fullmatch(r"([a-z]+) (\d{1,2})(?:st|nd|rd|th)?", text) or re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)? (?:of )?([a-z]+)", text)
    if month_day:
        a, b = month_day.groups()
        month, number = (MONTHS.get(a), b) if a.isalpha() else (MONTHS.get(b), a)
        if month:
            try:
                date = dt.date(meeting_date.year, month, int(number))
            except ValueError:
                return None
            return date if date >= meeting_date else date.replace(year=date.year + 1)     # the next such date
    if nth := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)", text):                            # "the 20th": this month or next
        number = int(nth.group(1))
        year, month = meeting_date.year, meeting_date.month
        if number < meeting_date.day:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        try:
            return dt.date(year, month, number)
        except ValueError:
            return None
    return None


PHRASE = re.compile(
    r"\b(today|tonight|tomorrow|end of (?:the )?(?:next )?(?:week|month)|in (?:\w+) (?:days?|weeks?)"
    r"|(?:next )?(?:" + "|".join(WEEKDAYS) + r")|(?:" + "|".join(MONTHS) + r")\.? \d{1,2}(?:st|nd|rd|th)?|the \d{1,2}(?:st|nd|rd|th))\b", re.I)


def deadline_in(text: str, meeting_date: dt.date) -> tuple[str, dt.date] | None:
    """The last deadline phrase written in `text` that the date tool can read, with its date."""
    for found in reversed(PHRASE.findall(text)):
        if date := resolve_due(found, meeting_date):
            return found, date
    return None


def build_messages(notes: str, meeting_date: dt.date, dates_by_model: bool = False) -> list[dict]:
    system = SYSTEM.replace("__DUE__", DUE_DATE if dates_by_model else DUE_PHRASE)
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"Meeting date: {meeting_date.isoformat()} ({meeting_date.strftime('%A')})\n\nNotes:\n{notes}"}]


def parse_items(reply: str, notes: str, meeting_date: dt.date, dates_by_model: bool = False) -> list[ActionItem] | None:
    """Validate the model's JSON. Returns None if it is not usable; drops items that fail a check."""
    found = re.search(r"\{.*\}", reply, flags=re.S)
    try:
        raw = json.loads(found.group(0))["action_items"] if found else None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    if not isinstance(raw, list):
        return None
    items = []
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("task"), str) or not entry["task"].strip():
            continue
        owner = entry.get("owner") if isinstance(entry.get("owner"), str) and entry["owner"].strip() else None
        if owner and owner.split()[0].lower() not in notes.lower():       # an owner the notes never mention is made up
            owner = None
        due_text = entry.get("due") if isinstance(entry.get("due"), str) and entry["due"].strip().lower() not in ("", "null", "none") else None
        if dates_by_model:
            try:
                due = dt.date.fromisoformat(due_text) if due_text else None
            except ValueError:
                due = None
        else:
            computed_by_model = bool(due_text) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_text.strip()) and due_text.strip() not in notes
            due = None if computed_by_model else resolve_due(due_text, meeting_date)
            if due is None and (found := deadline_in(entry["task"], meeting_date)):     # the phrase is often inside the task text
                due_text, due = found
        items.append(ActionItem(entry["task"].strip(), owner.split()[0] if owner else None, due.isoformat() if due else None, due_text))
    return items


class ChatModel:
    """Any OpenAI-compatible endpoint: Ollama locally, or Nebius with LLM_BASE_URL and LLM_API_KEY set."""

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "local")
        self.client = httpx.Client(timeout=180)

    def chat(self, messages: list[dict]) -> str:
        response = self.client.post(
            f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0, "seed": 0, "max_tokens": 600,
                  "response_format": {"type": "json_object"}})
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def extract(notes: str, meeting_date: dt.date, llm, dates_by_model: bool = False) -> list[ActionItem] | None:
    return parse_items(llm.chat(build_messages(notes, meeting_date, dates_by_model)), notes, meeting_date, dates_by_model)


def as_markdown(items: list[ActionItem]) -> str:
    rows = ["| Task | Owner | Due |", "|---|---|---|"]
    rows += [f"| {i.task} | {i.owner or 'unassigned'} | {i.due or 'no deadline'} |" for i in items]
    return "\n".join(rows)


# ---- scoring ---------------------------------------------------------------------------------------------------------

STOP = set("a an the to of for and with in on by from our their his her up it that this be is all".split())


def words(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP}       # crude stemming: first six letters


def overlap(a: str, b: str) -> float:
    x, y = words(a), words(b)
    common = len(x & y)
    return 2 * common / (len(x) + len(y)) if common else 0.0


def match(expected: list[dict], found: list[ActionItem], threshold: float = 0.4) -> list[tuple[dict, ActionItem]]:
    """Pair each expected item with at most one extracted item describing the same task, best matches first."""
    scored = sorted(((overlap(e["task"], f.task), i, j) for i, e in enumerate(expected) for j, f in enumerate(found)), reverse=True)
    used_e, used_f, pairs = set(), set(), []
    for score, i, j in scored:
        if score >= threshold and i not in used_e and j not in used_f:
            used_e.add(i)
            used_f.add(j)
            pairs.append((expected[i], found[j]))
    return pairs


def score(meetings: list[dict], outputs: list[list[ActionItem] | None]) -> dict:
    expected_total = found_total = matched = owners = dues = with_due = invented_due = no_due = 0
    for meeting, items in zip(meetings, outputs, strict=True):
        items = items or []
        pairs = match(meeting["action_items"], items)
        expected_total += len(meeting["action_items"])
        found_total += len(items)
        matched += len(pairs)
        for gold, got in pairs:
            owners += (got.owner or "").lower() == gold["owner"].lower()
            if gold["due"]:
                with_due += 1
                dues += got.due == gold["due"]
            else:
                no_due += 1
                invented_due += got.due is not None
    precision, recall = matched / max(found_total, 1), matched / max(expected_total, 1)
    return {
        "valid_json": round(sum(o is not None for o in outputs) / len(outputs), 4),
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(2 * precision * recall / max(precision + recall, 1e-12), 4),
        "owner_accuracy": round(owners / max(matched, 1), 4),
        "deadline_accuracy": round(dues / max(with_due, 1), 4),
        "deadline_invented": round(invented_due / max(no_due, 1), 4),
        "items_expected": expected_total, "items_extracted": found_total, "items_matched": matched,
    }


def to_dicts(items: list[ActionItem] | None) -> list[dict]:
    return [asdict(i) for i in items or []]
