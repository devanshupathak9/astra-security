"""Splits an App into chunks that each fit one model request.

Every chunk starts with the same short header (package + exported components),
so the model always knows the attack surface even when it sees only a few files.
Chunk 0 is always configuration: manifest + resources + library list.

How source code is grouped is the `strategy`:
  packed   - files in path order, packed together up to `max_chars`
  per_file - one file per chunk
  slices   - one chunk per manifest component: the component's own file plus the
             app files it references (following class names `depth` hops).
             Related files are seen together, so bugs that span files are visible.
             Files no slice reached are packed at the end, so nothing is skipped.
"""
import re
from pathlib import Path

from astra.schemas import App, Chunk

STRATEGIES = ["packed", "per_file", "slices"]


def make_chunks(app: App, max_chars: int, strategy: str = "packed", depth: int = 2) -> list[Chunk]:
    header = _header(app)
    budget = max(max_chars - len(header), 2000)

    config_parts = [("AndroidManifest.xml", app.manifest_xml), *app.resources.items(),
                    ("third-party libraries", "\n".join(app.libraries))]
    groups = _pack(config_parts, budget)

    if strategy == "packed":
        groups += _pack(_split_all(app, list(app.sources), budget), budget)
    elif strategy == "per_file":
        groups += [[part] for part in _split_all(app, list(app.sources), budget)]
    elif strategy == "slices":
        groups += _slices(app, budget, depth)
    else:
        raise ValueError(f"unknown strategy {strategy!r}, expected one of {STRATEGIES}")

    chunks = []
    for parts in groups:
        body = "\n\n".join(f"### FILE: {name}\n{text}" for name, text in parts)
        chunks.append(Chunk(id=len(chunks), files=[name for name, _ in parts], text=header + body))
    return chunks


def _slices(app: App, budget: int, depth: int) -> list[list[tuple[str, str]]]:
    refs = _references(app)
    # Entry points: manifest components that are app code, exported ones first
    components = sorted(app.components, key=lambda c: not c.exported)
    entries = [app.classes[c.name] for c in components if c.name in app.classes]

    groups, covered = [], set()
    for entry in dict.fromkeys(entries):              # unique, order kept
        if len(app.sources[entry]) > budget:          # entry alone is too big: its parts are the slice
            groups += [[part] for part in _split_all(app, [entry], budget)]
            covered.add(entry)
            continue
        group, size = [], 0
        for path in _reachable(entry, refs, depth):   # nearest files first
            text = app.sources[path]
            if size + len(text) > budget:
                continue
            group.append((path, text))
            size += len(text)
            covered.add(path)
        groups.append(group)

    leftover = [p for p in app.sources if p not in covered]
    return groups + _pack(_split_all(app, leftover, budget), budget)


def _references(app: App) -> dict[str, list[str]]:
    """File -> other app files it mentions by class name."""
    by_name = {Path(p).stem: p for p in app.sources}
    refs = {}
    for path, code in app.sources.items():
        words = set(re.findall(r"\b[A-Z]\w+\b", code))
        refs[path] = sorted(by_name[w] for w in words if w in by_name and by_name[w] != path)
    return refs


def _reachable(start: str, refs: dict[str, list[str]], depth: int) -> list[str]:
    """Breadth-first: start, then files it references, then theirs, up to `depth` hops."""
    order, frontier = [start], [start]
    for _ in range(depth):
        frontier = [r for f in frontier for r in refs[f] if r not in order]
        frontier = list(dict.fromkeys(frontier))
        order += frontier
    return order


def _header(app: App) -> str:
    lines = [f"## App: {app.package}", "## Exported components (reachable by other apps):"]
    for c in app.components:
        if c.exported:
            perm = f" [permission: {c.permission}]" if c.permission else ""
            filters = f" filters: {' | '.join(c.intent_filters)}" if c.intent_filters else ""
            lines.append(f"- {c.kind} {c.name}{perm}{filters}")
    return "\n".join(lines) + "\n\n"


def _split_all(app: App, paths: list[str], budget: int) -> list[tuple[str, str]]:
    return [part for p in paths for part in _split(p, app.sources[p], budget)]


def _split(path: str, text: str, budget: int) -> list[tuple[str, str]]:
    """Split one file into pieces of at most `budget` chars, on line boundaries."""
    if len(text) <= budget:
        return [(path, text)]
    pieces, current = [], ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > budget:
            pieces.append(current)
            current = ""
        current += line[:budget]
    pieces.append(current)
    return [(f"{path} (part {i + 1}/{len(pieces)})", p) for i, p in enumerate(pieces)]


def _pack(parts: list[tuple[str, str]], budget: int) -> list[list[tuple[str, str]]]:
    """Greedily group parts so each group stays under `budget` chars."""
    groups, current, size = [], [], 0
    for name, text in parts:
        text = text[:budget]
        if current and size + len(text) > budget:
            groups.append(current)
            current, size = [], 0
        current.append((name, text))
        size += len(text)
    if current:
        groups.append(current)
    return groups
