"""
Pure helpers for the compound-task planner (no network), so they are unit-testable.

The orchestrator uses `looks_compound` as a cheap gate (skip the planner LLM call
for simple goals), `build_plan_prompt` to ask Gemini for a decomposition, and
`normalize_steps` to coerce the model output into a clean ordered list of strings.
"""
import re
from typing import List, Any

_COMPOUND_MARKERS = (
    " then ", " and then ", "; ", " after that ", " followed by ",
    " next ", " also ", " finally ", " lastly ",
)

MAX_STEPS = 8


def looks_compound(goal: str) -> bool:
    """Cheap heuristic: does this goal plausibly contain multiple chained tasks?"""
    g = (goal or "").lower()
    if any(m in g for m in _COMPOUND_MARKERS):
        return True
    if len(re.findall(r"\b\d[\.\)]", g)) >= 2:  # "1." "2)" enumerations
        return True
    return g.count(" and ") >= 2


def build_plan_prompt(goal: str) -> str:
    """Instruction for Gemini to decompose a goal into ordered atomic sub-tasks."""
    return (
        "Decompose the user's request into an ordered list of atomic, independently "
        "executable sub-tasks. Preserve order. If a later sub-task needs the result of "
        "an earlier one (e.g. a summary or a draft), phrase it so it can consume that "
        "result. Keep each sub-task to a single action. If the request is genuinely a "
        "single task, return exactly one item.\n\n"
        f"Request: {goal}"
    )


def normalize_steps(raw_steps: List[Any]) -> List[str]:
    """Coerce model output (list of strings or {task:...} dicts) into clean strings."""
    out: List[str] = []
    for s in raw_steps or []:
        if isinstance(s, dict):
            text = (s.get("task") or s.get("step") or s.get("description") or "").strip()
        else:
            text = str(s).strip()
        if text:
            out.append(text)
    return out[:MAX_STEPS]
