"""Step 1 - Ingest: APK -> App.

1. Decompile with jadx (Java sources) and apktool (decoded manifest + resources).
2. Parse AndroidManifest.xml into Components (exported? permission? intent-filters?).
3. Keep only app code: drop files under config `library_prefixes`.
"""
from astra.schemas import App


def decompile(apk_path: str, out_dir: str) -> str:
    raise NotImplementedError


def parse_manifest(manifest_xml: str):
    raise NotImplementedError


def load_app(apk_path: str, config: dict) -> App:
    raise NotImplementedError
