import asyncio
from app.docproc.extract import extract_document
from app.skills.bidgaps.skill import BidGapsSkill
from app.skills.base import SkillContext


async def main():
    doc = extract_document("data/construction_contract.pdf")
    document_texts = {"contract-1": [p.text for p in doc.pages]}

    skill = BidGapsSkill()
    ctx = SkillContext(
        task_id="smoke-test-2",
        project_id="smoke-test-2",
        objective="Identify potential scope gaps that could lead to change orders.",
        document_ids=["contract-1"],
        document_texts=document_texts,
    )

    result = await skill.execute(ctx)
    print(f"Findings: {len(result.findings)}")
    for f in result.findings:
        print(f"\n- {f.title} (confidence: {f.confidence})")
        print(f"  Evidence: {f.evidence_quote!r}")
        print(f"  Page: {f.page_number}")

    print("\n--- RAW OUTPUT ---")
    print(result.raw_metadata["raw_model_output"])


if __name__ == "__main__":
    asyncio.run(main())
