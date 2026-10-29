"""Paired review requires verifiable quotes from both independent answers."""
from pydantic import Field

from stylist.models import Model


class PreferenceComparison(Model):
    meaningful_difference: bool
    persona_preserved: bool
    requirements_preserved: bool
    evidence_a: str = Field(min_length=1)
    evidence_b: str = Field(min_length=1)
    reason: str = Field(min_length=1)


def comparison_status(review, a, b):
    if not review.evidence_a.strip() or not review.evidence_b.strip():
        return "invalid_evidence"
    if review.evidence_a not in a or review.evidence_b not in b:
        return "invalid_evidence"
    return "passed" if all([review.meaningful_difference, review.persona_preserved,
                            review.requirements_preserved]) else "failed"
