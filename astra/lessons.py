"""Step 3 - Lessons: teacher findings -> general rules for the student.

1. One teacher call turns its findings into general rules (prompts/lessons.md).
2. Leak filter: drop any lesson that names something from this app
   (class names, package, file paths), so lessons stay general.
"""
from astra.llm import LLM
from astra.schemas import App, Finding


def make_lessons(findings: list[Finding], teacher: LLM, max_lessons: int) -> list[str]:
    raise NotImplementedError


def remove_leaky_lessons(lessons: list[str], app: App) -> list[str]:
    raise NotImplementedError
