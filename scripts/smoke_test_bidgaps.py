import asyncio
from app.docproc.extract import extract_document
from app.skills.bidgaps.skill import BidGapsSkill
from app.skills.base import SkillContext


async def main():
    doc = extract_document("data/steel_column_over_concrete_piers.pdf")
    document_texts = {"test-doc-1": [p.text for p in doc.pages]}

    skill = BidGapsSkill()
    ctx = SkillContext(
        task_id="smoke-test",
        project_id="smoke-test",
        objective="Identify potential scope gaps that could lead to change orders.",
        document_ids=["test-doc-1"],
        document_texts=document_texts,
    )

    result = await skill.execute(ctx)
    print(f"Model used: {result.model_used}")
    print(f"Findings: {len(result.findings)}")
    for f in result.findings:
        print(f"\n- {f.title} (confidence: {f.confidence})")
        print(f"  Evidence: {f.evidence_quote!r}")
        print(f"  Page: {f.page_number}")


if __name__ == "__main__":
    asyncio.run(main())
