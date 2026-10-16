"""Step 1 - Ingest: APK (or decompiled folder) -> App.

1. Decompile the APK with jadx. jadx gives both Java sources and the decoded
   manifest + resources, so one tool is enough.
2. Parse AndroidManifest.xml into Components (exported? permission? intent-filters?).
3. Keep only app code (classes under the manifest package), skip build-generated files.
4. List third-party libraries instead of scanning them.
"""
import fnmatch
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from astra.schemas import App, Component

ANDROID = "{http://schemas.android.com/apk/res/android}"
COMPONENT_TAGS = ["activity", "activity-alias", "service", "receiver", "provider"]
PACKAGE_RE = re.compile(r"^package\s+([\w.]+);", re.MULTILINE)


def decompile(apk_path: str, out_dir: str, jadx: str = "jadx") -> Path:
    """Run jadx once; reuse the output if it already exists."""
    out = Path(out_dir)
    if not (out / "sources").is_dir():
        print(f"Decompiling {apk_path} -> {out} (takes a minute)...")
        # jadx exits non-zero when a few classes fail to decompile, which is normal
        subprocess.run([jadx, "-q", "-d", str(out), apk_path], check=False)
    if not (out / "sources").is_dir():
        raise RuntimeError(f"jadx produced no sources in {out}")
    return out


def parse_manifest(manifest_xml: str) -> tuple[str, str | None, list[Component]]:
    """Returns (package, application class, components)."""
    root = ET.fromstring(manifest_xml)
    package = root.get("package", "")
    app = root.find("application")
    app_class = _full_name(app.get(f"{ANDROID}name"), package) if app is not None else None

    components = []
    for tag in COMPONENT_TAGS:
        for el in root.iter(tag):
            filters = [_describe_filter(f) for f in el.findall("intent-filter")]
            exported = el.get(f"{ANDROID}exported")
            components.append(Component(
                kind=tag,
                name=_full_name(el.get(f"{ANDROID}name"), package),
                # No explicit value: components with an intent-filter are exported by default
                exported=(exported == "true") if exported is not None else bool(filters),
                permission=el.get(f"{ANDROID}permission") or el.get(f"{ANDROID}readPermission"),
                intent_filters=filters,
            ))
    return package, app_class, components


def load_app(app_path: str, config: dict) -> App:
    """Entry point: accepts an .apk or an already-decompiled folder."""
    path = Path(app_path)
    if path.suffix == ".apk":
        root = decompile(app_path, f"{config['output_dir']}/decompiled/{path.stem}", config["tools"]["jadx"])
    else:
        root = path

    manifest_file = min(root.rglob("AndroidManifest.xml"), key=lambda p: len(p.parts))
    manifest_xml = manifest_file.read_text(errors="ignore")
    package, app_class, components = parse_manifest(manifest_xml)

    cfg = config["ingest"]
    app_prefixes = [package] + cfg["extra_app_prefixes"]
    if app_class and not _starts_with_any(app_class, cfg["platform_prefixes"]):
        app_prefixes.append(app_class.rsplit(".", 1)[0])

    sources, libraries = {}, set()
    for java in root.rglob("*.java"):
        rel = str(java.relative_to(root))
        code = java.read_text(errors="ignore")
        match = PACKAGE_RE.search(code)
        pkg = match.group(1) if match else ""
        if not _starts_with_any(pkg, app_prefixes):
            if pkg and not _starts_with_any(pkg, cfg["platform_prefixes"]):
                libraries.add(".".join(pkg.split(".")[:3]))
        elif not any(fnmatch.fnmatch(rel, p) for p in cfg["skip_files"]):
            sources[rel] = code

    resources = {}
    for pattern in cfg["resource_globs"]:
        for f in root.glob(pattern):
            resources[str(f.relative_to(root))] = f.read_text(errors="ignore")

    # Gradle libraries ship a META-INF/<group>_<artifact>.version file with their version
    versions = [f"{f.stem} {f.read_text(errors='ignore').strip()}" for f in root.rglob("META-INF/*.version")]

    return App(
        package=package,
        manifest_xml=manifest_xml,
        components=components,
        sources=dict(sorted(sources.items())),
        resources=resources,
        libraries=_collapse(libraries) + sorted(versions),
    )


def summary(app: App) -> str:
    exported = [c for c in app.components if c.exported]
    lines = [
        f"package:    {app.package}",
        f"components: {len(app.components)} ({len(exported)} exported)",
        f"app files:  {len(app.sources)} ({sum(map(len, app.sources.values())):,} chars)",
        f"resources:  {len(app.resources)}",
        f"libraries:  {len(app.libraries)}",
        "exported components:",
    ]
    lines += [f"  - {c.kind:9} {c.name}" + (f"  [perm: {c.permission}]" if c.permission else "") for c in exported]
    return "\n".join(lines)


def _full_name(name: str | None, package: str) -> str:
    if not name:
        return ""
    return package + name if name.startswith(".") else name


def _starts_with_any(name: str, prefixes: list[str]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def _collapse(packages: set[str]) -> list[str]:
    """Keep only top-level packages: drop com.foo.bar if com.foo is present."""
    return sorted(p for p in packages if not any(p != q and p.startswith(q + ".") for q in packages))


def _describe_filter(f: ET.Element) -> str:
    parts = [f"action={a.get(ANDROID + 'name')}" for a in f.findall("action")]
    parts += [f"category={c.get(ANDROID + 'name')}" for c in f.findall("category")]
    for d in f.findall("data"):
        parts += [f"{k}={d.get(ANDROID + k)}" for k in ("scheme", "host", "path", "mimeType") if d.get(ANDROID + k)]
    return " ".join(parts)
