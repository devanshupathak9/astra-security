"""Step 4 - Match & score: findings vs labels -> recall / precision.

A finding matches a label when its category is in the label's `categories`
(and its location agrees, when the label has one). Matching is one-to-one:
each label can be claimed by at most one finding, so duplicates don't inflate recall.
"""
from astra.schemas import Finding, GroundTruth


def is_match(finding: Finding, label: GroundTruth) -> bool:
    raise NotImplementedError


def score(findings: list[Finding], labels: list[GroundTruth]) -> dict:
    """Returns {recall, precision, matched_ids, missed_ids, n_findings}."""
    raise NotImplementedError
