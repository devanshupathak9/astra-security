"""Step 4 - Match & score: findings vs labels -> recall / precision.

A finding matches a label when:
  - its file is one of the label's files (path suffix), and
  - strict mode: its category is one of the label's categories.
    lenient mode: any category (right place, possibly wrong label).
Strict is a lower bound, lenient an upper bound; we report both.

Matching is one-to-one (maximum bipartite matching): each label is claimed by at most
one finding and each finding claims at most one label, so duplicates can't inflate recall.
"""
import yaml

from astra.schemas import Finding, GroundTruth


def load_groundtruth(path: str) -> list[GroundTruth]:
    with open(path) as f:
        return [GroundTruth(**entry) for entry in yaml.safe_load(f)]


def is_match(finding: Finding, label: GroundTruth, strict: bool = True) -> bool:
    file_ok = not label.files or any(finding.file.endswith(f) for f in label.files)
    return file_ok and (finding.category in label.categories or not strict)


def score(findings: list[Finding], labels: list[GroundTruth], strict: bool = True) -> dict:
    pairs = _max_matching(findings, labels, strict)          # label index -> finding index
    matched = len(pairs)
    return {
        "recall": matched / len(labels) if labels else 0.0,
        "precision": matched / len(findings) if findings else 0.0,
        "matched": {labels[l].id: findings[f].title for l, f in sorted(pairs.items())},
        "missed": [lab.id for i, lab in enumerate(labels) if i not in pairs],
        "n_findings": len(findings),
    }


def report(findings: list[Finding], labels: list[GroundTruth]) -> str:
    strict, lenient = score(findings, labels, True), score(findings, labels, False)
    lines = []
    for lab in labels:
        mark = "✓" if lab.id in strict["matched"] else ("~" if lab.id in lenient["matched"] else "✗")
        lines.append(f"  {mark} {lab.id:2}. {lab.title}")
    lines.append(f"  (✓ strict match, ~ right file but different category, ✗ missed)")
    lines.append(f"Recall  strict {strict['recall']:.0%} ({len(strict['matched'])}/{len(labels)})"
                 f"   lenient {lenient['recall']:.0%} ({len(lenient['matched'])}/{len(labels)})")
    lines.append(f"Precision strict {strict['precision']:.0%}   findings: {len(findings)}")
    return "\n".join(lines)


def _max_matching(findings, labels, strict) -> dict[int, int]:
    """Kuhn's algorithm: try to give every label its own finding, re-assigning when needed."""
    owner = {}                                               # finding index -> label index

    def assign(l, seen):
        for f, finding in enumerate(findings):
            if f not in seen and is_match(finding, labels[l], strict):
                seen.add(f)
                if f not in owner or assign(owner[f], seen):
                    owner[f] = l
                    return True
        return False

    for l in range(len(labels)):
        assign(l, set())
    return {l: f for f, l in owner.items()}
