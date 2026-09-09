import asyncio
import json
from datetime import datetime

from app.docproc.extract import extract_document, find_evidence_bbox
from app.skills.bidgaps.skill import BidGapsSkill
from app.skills.base import SkillContext
from app.eval.cases import EVAL_CASES
from app.eval.checks import run_deterministic_checks
from app.eval.judge import judge_matches


class FakeFinding:
    def __init__(self, skill_finding, rejected, rejection_reason):
        self.id = skill_finding.title[:20]
        self.title = skill_finding.title
        self.risk_explanation = skill_finding.risk_explanation
        self.recommended_action = skill_finding.recommended_action
        self.confidence = skill_finding.confidence
        self.document_id = skill_finding.document_id
        self.page_number = skill_finding.page_number
        self.highlight_bbox = skill_finding.highlight_bbox
        self.rejected = rejected
        self.rejection_reason = rejection_reason


async def run_case(case) -> dict:
    document_texts = {}
    page_lookups = {}
    for path in case.document_paths:
        doc_id = path
        extracted = await asyncio.to_thread(extract_document, path)
        document_texts[doc_id] = [p.text for p in extracted.pages]
        page_lookups[doc_id] = extracted

    skill = BidGapsSkill()
    context = SkillContext(
        task_id=f"eval-{case.id}",
        project_id="eval",
        objective=case.objective,
        document_ids=list(document_texts.keys()),
        document_texts=document_texts,
    )

    max_attempts = 3
    skill_result = None
    last_error = None
    for attempt in range(max_attempts):
        try:
            skill_result = await skill.execute(context)
            break
        except Exception as e:
            last_error = e
            print(f"  [{case.id}] attempt {attempt + 1} failed: {e}")
            if attempt < max_attempts - 1:
                wait = 5 * (attempt + 1)
                print(f"  retrying in {wait}s...")
                await asyncio.sleep(wait)

    if skill_result is None:
        return {
            "case_id": case.id,
            "error": f"Skill failed after {max_attempts} attempts: {last_error}",
            "deterministic_checks_passed": False,
            "expected_count": len(case.expected_findings),
            "matched_count": 0,
            "missed_count": len(case.expected_findings),
            "total_findings_returned": 0,
            "rejected_findings_count": 0,
            "match_details": [],
        }

    fake_findings = []
    for f in skill_result.findings:
        rejected, reason, bbox = False, None, {}
        doc_content = page_lookups.get(f.document_id)
        if doc_content is None:
            rejected, reason = True, "document_id not in case document set"
        else:
            page = next((p for p in doc_content.pages if p.page_number == f.page_number), None)
            if page is None:
                rejected, reason = True, "page_number does not exist"
            else:
                found_bbox = find_evidence_bbox(page, f.evidence_quote)
                if found_bbox is None:
                    rejected, reason = True, "evidence_quote not found verbatim"
                else:
                    bbox = found_bbox
        f.highlight_bbox = bbox
        fake_findings.append(FakeFinding(f, rejected, reason))

    det_result = run_deterministic_checks(fake_findings)

    matches = []
    for attempt in range(max_attempts):
        try:
            matches = judge_matches(case.expected_findings, fake_findings)
            break
        except Exception as e:
            print(f"  [{case.id}] judge attempt {attempt + 1} failed: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(5 * (attempt + 1))

    matched_count = sum(1 for m in matches if m.get("matched"))
    unsupported_count = sum(1 for f in fake_findings if f.rejected)

    return {
        "case_id": case.id,
        "skill_version": skill_result.skill_version,
        "model_used": skill_result.model_used,
        "deterministic_checks_passed": det_result.passed,
        "deterministic_reasons": det_result.reasons,
        "expected_count": len(case.expected_findings),
        "matched_count": matched_count,
        "missed_count": len(case.expected_findings) - matched_count,
        "total_findings_returned": len(fake_findings),
        "rejected_findings_count": unsupported_count,
        "match_details": matches,
    }


async def run_all() -> dict:
    results = []
    for case in EVAL_CASES:
        print(f"Running case: {case.id}")
        results.append(await run_case(case))

    valid_results = [r for r in results if "error" not in r]
    return {
        "run_at": datetime.utcnow().isoformat(),
        "cases": results,
        "summary": {
            "total_cases": len(results),
            "failed_cases": len(results) - len(valid_results),
            "deterministic_pass_rate": (
                sum(1 for r in valid_results if r["deterministic_checks_passed"]) / len(valid_results)
                if valid_results else 0
            ),
            "avg_recall": (
                sum(r["matched_count"] / r["expected_count"] for r in valid_results if r["expected_count"])
                / len(valid_results)
                if valid_results else 0
            ),
        },
    }


if __name__ == "__main__":
    report = asyncio.run(run_all())
    print(json.dumps(report, indent=2))

    with open("data/eval_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nReport written to data/eval_report.json")
