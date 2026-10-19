"""Step 3 - Lessons: teacher findings -> general rules for the student.

1. One teacher call turns all its findings into general rules (prompts/lessons.md).
2. Leak filter: drop any lesson that names something from this app (class names,
   package, custom intent actions), so lessons stay general and the lift is honest.
3. Placebo: generic advice with the same number and length of items as the lessons
   (prompts/placebo.md). Used as a control: if the student improves as much with the
   placebo as with the lessons, the lift came from a longer prompt, not from the lessons.
"""
import json
import re
from pathlib import Path

from astra.llm import LLM
from astra.schemas import App, Finding

MIN_TERM_LEN = 5    # shorter names ("Cart", "Util") are ordinary words, not leaks


def make_lessons(findings: list[Finding], teacher: LLM, max_lessons: int) -> list[str]:
    system = Path("prompts/lessons.md").read_text().format(max_lessons=max_lessons)
    fields = ("category", "title", "severity", "evidence", "rationale")
    user = json.dumps([{k: getattr(f, k) for k in fields} for f in findings], indent=1)
    reply = teacher.ask_json(system, user)
    lessons = [str(l).strip() for l in reply.get("lessons", []) if str(l).strip()]
    return lessons[:max_lessons]


def split_leaky(lessons: list[str], app: App) -> tuple[list[str], list[dict]]:
    """Returns (clean lessons, rejected lessons with the app terms they mention)."""
    terms = app_terms(app)
    clean, rejected = [], []
    for lesson in lessons:
        hits = [t for t in terms if re.search(rf"\b{re.escape(t)}\b", lesson, re.IGNORECASE)]
        if hits:
            rejected.append({"lesson": lesson, "mentions": hits})
        else:
            clean.append(lesson)
    return clean, rejected


def app_terms(app: App) -> set[str]:
    """Names that only make sense for this app."""
    terms = {Path(p).stem for p in app.sources}                      # class names
    terms |= {app.package, app.package.split(".")[-1]}              # package
    for c in app.components:                                        # custom intent actions
        for f in c.intent_filters:
            terms |= {a for a in re.findall(r"action=(\S+)", f) if a.startswith(app.package)}
    return {t for t in terms if len(t) >= MIN_TERM_LEN}


def make_placebo(lessons: list[str]) -> list[str]:
    """Same number of items as `lessons`, each about as long, with no security knowledge."""
    lines = Path("prompts/placebo.md").read_text().split("\n")
    lines = [l.strip() for l in lines if l.strip()]
    placebo, i = [], 0
    for lesson in lessons:
        item = ""
        while len(item) < len(lesson):
            item = (item + " " + lines[i % len(lines)]).strip()
            i += 1
        placebo.append(item)
    return placebo
