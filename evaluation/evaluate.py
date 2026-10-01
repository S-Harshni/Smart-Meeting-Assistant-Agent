"""Measure action-item extraction on the labelled meetings, with open-source models running locally.

    ollama pull qwen2.5:3b llama3.2:3b gemma2:2b
    python evaluation/evaluate.py          # writes evaluation/results.json

Two set-ups are compared for each model: the model works out each deadline's date itself, or it copies the
deadline phrase and `resolve_due` (code) does the calendar arithmetic.
"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import actions  # noqa: E402

MODELS = ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b"]


def main() -> None:
    meetings = json.loads((HERE / "meetings.json").read_text())
    runs, shown = [], {}
    for model in MODELS:
        llm = actions.ChatModel(model)
        for dates_by_model in (True, False):
            outputs = []
            for m in meetings:
                try:
                    outputs.append(actions.extract(m["notes"], dt.date.fromisoformat(m["date"]), llm, dates_by_model))
                except Exception:                      # a failed call counts as an unusable answer
                    outputs.append(None)
            row = {"model": model, "deadlines": "model" if dates_by_model else "tool", **actions.score(meetings, outputs)}
            runs.append(row)
            print(row, flush=True)
            shown[(model, row["deadlines"])] = [actions.to_dicts(o) for o in outputs]
    best = max((r for r in runs if r["deadlines"] == "tool"), key=lambda r: (r["f1"], r["deadline_accuracy"]))
    out = {"meetings": len(meetings), "action_items": sum(len(m["action_items"]) for m in meetings), "runs": runs,
           "best_model": best["model"],
           "examples": [{"id": m["id"], "date": m["date"], "notes": m["notes"], "expected": m["action_items"],
                         "extracted": shown[(best["model"], "tool")][i], "by_model_dates": shown[(best["model"], "model")][i]}
                        for i, m in enumerate(meetings)]}
    (HERE / "results.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
