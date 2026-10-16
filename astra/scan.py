"""Step 2 - Scan: App + model (+ optional lessons) -> list[Finding].

1. Split the app into chunks that fit the model's `max_chunk_chars`
   (manifest summary + one or more source files each).
2. Ask the model for findings as JSON (prompts/scan.md).
3. Drop findings whose evidence quote is not actually in the source (anti-hallucination).
4. De-duplicate.
"""
from astra.llm import LLM
from astra.schemas import App, Finding


def make_chunks(app: App, max_chars: int) -> list[str]:
    raise NotImplementedError


def scan(app: App, llm: LLM, categories: list[str], lessons: list[str] | None = None) -> list[Finding]:
    raise NotImplementedError
