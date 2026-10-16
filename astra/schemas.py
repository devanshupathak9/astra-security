"""Data shapes passed between pipeline steps."""
from dataclasses import dataclass, field


@dataclass
class Component:
    """One manifest entry: activity, service, receiver or provider."""
    kind: str
    name: str
    exported: bool
    permission: str | None = None
    intent_filters: list[str] = field(default_factory=list)


@dataclass
class App:
    """Everything ingest produces: the input to every scan."""
    package: str
    manifest_xml: str
    components: list[Component]
    sources: dict[str, str]       # relative file path -> decompiled Java (app code only)
    resources: dict[str, str]     # relative file path -> xml (e.g. res/xml/file_paths.xml)


@dataclass
class Finding:
    category: str                 # one of config.yaml `categories`
    title: str
    file: str
    location: str                 # class / method / component
    severity: str                 # low | medium | high | critical
    evidence: str                 # exact code quote
    rationale: str = ""


@dataclass
class GroundTruth:
    id: int
    title: str
    categories: list[str]
    location: str = ""
