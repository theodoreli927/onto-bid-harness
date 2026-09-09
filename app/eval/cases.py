# app/eval/cases.py
from dataclasses import dataclass


@dataclass
class ExpectedFinding:
    """A ground-truth finding a reviewer expects the skill to surface.
    Matched loosely (semantically) against actual findings, not by exact title string,
    since the same real issue can be phrased many ways by the model."""
    description: str  # plain-language description of the real issue, used for matching
    expected_document: str  # filename, matched against the doc uploaded for this case
    expected_page: int


@dataclass
class EvalCase:
    id: str
    description: str
    objective: str
    document_paths: list[str]  # local paths to fixed test PDFs
    expected_findings: list[ExpectedFinding]


# Versioned, fixed test cases — separate from production code/prompts.
# Add new cases here as you discover more ground truth in the Royal Oak package.
EVAL_CASES: list[EvalCase] = [
    EvalCase(
        id="contract-001",
        description="Royal Oak construction contract — known scope exclusions and date mismatch",
        objective="Identify potential scope gaps that could lead to change orders.",
        document_paths=["data/construction_contract.pdf"],
        expected_findings=[
            ExpectedFinding(
                description="Surveys and footer pinning are excluded from the estimate",
                expected_document="construction_contract.pdf",
                expected_page=11,
            ),
            ExpectedFinding(
                description="Window and sliding door screens are excluded from the estimate",
                expected_document="construction_contract.pdf",
                expected_page=11,
            ),
            ExpectedFinding(
                description="Rock, poor soil, or water in excavation may incur additional charges",
                expected_document="construction_contract.pdf",
                expected_page=11,
            ),
            ExpectedFinding(
                description="The proposal's stated validity date (Jan 20, 2024) predates the actual signing date (Jan 2025)",
                expected_document="construction_contract.pdf",
                expected_page=7,
            ),
        ],
    ),
    # app/eval/cases.py — add this case to EVAL_CASES
    EvalCase(
        id="contract-addenda-001",
        description="Contract + both addenda together — tests cross-document scope gap detection",
        objective="Identify potential scope gaps that could lead to change orders.",
        document_paths=[
            "data/construction_contract.pdf",
            "data/utility_allowance_addendum.pdf",
            "data/soft_draw_addendum.pdf",
        ],
        expected_findings=[
            ExpectedFinding(
                description="The Septic, Well, and Utilities Allowance was reduced from $60,000 to $40,000, with the client responsible for any overage beyond the new cap",
                expected_document="utility_allowance_addendum.pdf",
                expected_page=1,
            ),
            ExpectedFinding(
                description="The Soft Draw payment due at loan closing was revised from $25,187.50 to $18,000.00",
                expected_document="soft_draw_addendum.pdf",
                expected_page=1,
            ),
        ],
    ),
]