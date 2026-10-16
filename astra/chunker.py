"""Splits an App into chunks that fit one model request.

Every chunk starts with the same short header (package, exported components),
so the model always knows the app's attack surface even when it only sees a few files.
  chunk 0     : full manifest + resources + library list (configuration bugs)
  chunk 1..n  : app source files, packed together up to `max_chars`
                (a file bigger than the budget is split by lines)
"""
from astra.schemas import App, Chunk


def make_chunks(app: App, max_chars: int) -> list[Chunk]:
    header = _header(app)
    budget = max(max_chars - len(header), 2000)

    # Chunk 0: configuration (manifest, resources, libraries)
    config_parts = [("AndroidManifest.xml", app.manifest_xml)]
    config_parts += list(app.resources.items())
    config_parts.append(("third-party libraries", "\n".join(app.libraries)))

    # Remaining chunks: source code
    code_parts = []
    for path, code in app.sources.items():
        code_parts += _split(path, code, budget)

    chunks = []
    for parts in _pack(config_parts, budget) + _pack(code_parts, budget):
        files = [name for name, _ in parts]
        body = "\n\n".join(f"### FILE: {name}\n{text}" for name, text in parts)
        chunks.append(Chunk(id=len(chunks), files=files, text=header + body))
    return chunks


def _header(app: App) -> str:
    lines = [f"## App: {app.package}", "## Exported components (reachable by other apps):"]
    for c in app.components:
        if c.exported:
            perm = f" [permission: {c.permission}]" if c.permission else ""
            filters = f" filters: {' | '.join(c.intent_filters)}" if c.intent_filters else ""
            lines.append(f"- {c.kind} {c.name}{perm}{filters}")
    return "\n".join(lines) + "\n\n"


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
