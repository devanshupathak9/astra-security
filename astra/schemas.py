"""Data shapes passed between pipeline steps."""
from dataclasses import dataclass, field


@dataclass
class Component:
    """One manifest entry: activity, service, receiver or provider."""
    kind: str
    name: str
    exported: bool
    permission: str | None = None
    intent_filters: list[str] = field(default_factory=list)   # e.g. "action=VIEW scheme=myapp"


@dataclass
class App:
    """Everything ingest produces: the input to every scan."""
    package: str
    manifest_xml: str
    components: list[Component]
    sources: dict[str, str]       # relative file path -> decompiled Java (app code only)
    resources: dict[str, str]     # relative file path -> text (xml configs, strings)
    libraries: list[str]          # third-party packages / versions found in the APK


@dataclass
class Chunk:
    """One piece of the app that fits in a single model request."""
    id: int
    files: list[str]
    text: str


@dataclass
class Finding:
    category: str                 # one of config.yaml `categories`
    title: str
    file: str
    location: str                 # class / method / component
    severity: str                 # low | medium | high | critical
    evidence: str                 # exact code quote
    rationale: str = ""
    line: int | None = None       # filled in when the evidence is found in the file


@dataclass
class GroundTruth:
    id: int
    title: str
    categories: list[str]
    location: str = ""
