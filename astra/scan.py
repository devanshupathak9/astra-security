"""Step 2 - Scan: App + model (+ optional lessons) -> list[Finding].

1. Split the app into chunks that fit the model (chunker.py).
2. Ask the model for findings as JSON, one request per chunk (prompts/scan.md).
3. Grounding check: keep only findings whose evidence quote is really in the code.
4. De-duplicate.
"""
import re
from pathlib import Path

from astra.chunker import make_chunks
from astra.llm import LLM
from astra.schemas import App, Finding

SEVERITIES = {"low", "medium", "high", "critical"}


def scan(app: App, llm: LLM, categories: list[str], lessons: list[str] | None = None,
         drop_unverified: bool = True) -> list[Finding]:
    system = Path("prompts/scan.md").read_text().format(categories=", ".join(categories))
    if lessons:
        system += "\n\nLessons from an expert reviewer. Apply them:\n" + "\n".join(f"- {l}" for l in lessons)

    chunks = make_chunks(app, llm.max_chunk_chars)
    all_files = {"AndroidManifest.xml": app.manifest_xml, **app.resources, **app.sources}

    findings, dropped = [], 0
    for chunk in chunks:
        print(f"  chunk {chunk.id + 1}/{len(chunks)}: {len(chunk.files)} files, {len(chunk.text):,} chars")
        try:
            reply = llm.ask_json(system, chunk.text)
        except Exception as e:  # one bad chunk shouldn't kill the whole scan
            print(f"    failed: {e}")
            continue
        for raw in reply.get("findings", []):
            finding = _to_finding(raw, categories)
            if _locate(finding, all_files) or not drop_unverified:
                findings.append(finding)
            else:
                dropped += 1

    findings = _dedupe(findings)
    print(f"  {len(findings)} findings ({dropped} dropped: evidence not found in code)")
    return findings


def _to_finding(raw: dict, categories: list[str]) -> Finding:
    category = str(raw.get("category", "other")).strip().lower()
    severity = str(raw.get("severity", "medium")).strip().lower()
    return Finding(
        category=category if category in categories else "other",
        title=str(raw.get("title", "")),
        file=re.sub(r" \(part \d+/\d+\)$", "", str(raw.get("file", ""))),
        location=str(raw.get("location", "")),
        severity=severity if severity in SEVERITIES else "medium",
        evidence=str(raw.get("evidence", "")),
        rationale=str(raw.get("rationale", "")),
    )


def _locate(finding: Finding, files: dict[str, str]) -> bool:
    """Grounding check. If the evidence is found, fix up `file` and set `line`.

    Lenient on purpose: any evidence line of 10+ chars found verbatim
    (ignoring whitespace) counts, since models often trim or join lines.
    """
    needles = [_norm(l) for l in finding.evidence.splitlines() if len(_norm(l)) >= 10]
    if not needles:
        return False
    # Look in the file the model named first, then everywhere else
    named = finding.file.lstrip("/")
    order = sorted(files, key=lambda path: not (path == named or path.endswith("/" + named)))
    for path in order:
        for i, line in enumerate(files[path].splitlines(), start=1):
            code = _norm(line)
            if any(n in code or (len(code) >= 10 and code in n) for n in needles):
                finding.file, finding.line = path, i
                return True
    return False


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen, unique = set(), []
    for f in findings:
        key = (f.category, f.file, f.line)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique
