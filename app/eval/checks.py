# app/eval/checks.py
from dataclasses import dataclass
from app.harness.models import Finding


@dataclass
class DeterministicCheckResult:
    passed: bool
    reasons: list[str]


def run_deterministic_checks(findings: list[Finding]) -> DeterministicCheckResult:
    """Cheap, exact checks — no LLM judgment. These mirror the TR-02/03/04
    integrity rules already enforced at persistence time, re-verified here
    so the eval report catches any drift between the two."""
    reasons = []

    for f in findings:
        if f.rejected:
            continue  # rejected findings are expected to exist sometimes; not a failure by itself

        if not f.title or not f.risk_explanation or not f.recommended_action:
            reasons.append(f"Finding '{f.id}' missing required text fields")

        if not (0.0 <= f.confidence <= 1.0):
            reasons.append(f"Finding '{f.id}' confidence out of range: {f.confidence}")

        if not f.document_id or f.page_number is None or f.page_number < 1:
            reasons.append(f"Finding '{f.id}' has invalid document/page reference")

        if not f.highlight_bbox or not all(
            k in f.highlight_bbox for k in ("x0", "y0", "x1", "y1")
        ):
            reasons.append(f"Finding '{f.id}' has invalid or missing highlight bbox")

    return DeterministicCheckResult(passed=len(reasons) == 0, reasons=reasons)