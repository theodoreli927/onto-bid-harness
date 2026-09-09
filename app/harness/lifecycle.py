# app/harness/lifecycle.py
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.harness.models import Task, TaskStatus, Document, Result, Finding
from app.skills.base import SkillContext
from app.skills.bidgaps.skill import BidGapsSkill
from app.docproc.extract import extract_document, find_evidence_bbox

MAX_RETRIES = 2

SKILL_REGISTRY = {
    "bidgaps": BidGapsSkill,
}


async def claim_next_queued_task(db: AsyncSession) -> Task | None:
    """Pick one queued task and atomically mark it running, so two workers
    can't both grab the same task."""
    result = await db.execute(
        select(Task).where(Task.status == TaskStatus.QUEUED).limit(1).with_for_update(skip_locked=True)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


async def execute_task(db: AsyncSession, task: Task) -> None:
    try:
        skill_cls = SKILL_REGISTRY.get(task.skill_name)
        if skill_cls is None:
            raise ValueError(f"Unknown skill: {task.skill_name}")

        # Load documents scoped to this task (TR-06 — only docs in document_ids, already
        # validated as belonging to this project at task-creation time)
        result = await db.execute(
            select(Document).where(Document.id.in_(task.document_ids))
        )
        documents = {d.id: d for d in result.scalars().all()}

        # Extraction is sync/CPU-bound — run off the event loop
        document_texts = {}
        page_lookup = {}  # doc_id -> extracted DocumentContent, kept for evidence validation
        for doc_id, doc in documents.items():
            extracted = await asyncio.to_thread(extract_document, doc.storage_path)
            document_texts[doc_id] = [p.text for p in extracted.pages]
            page_lookup[doc_id] = extracted

        skill = skill_cls()
        context = SkillContext(
            task_id=task.id,
            project_id=task.project_id,
            objective=task.objective,
            document_ids=task.document_ids,
            document_texts=document_texts,
        )
        skill_result = await skill.execute(context)

        # Persist Result
        result_row = Result(
            id=str(__import__("uuid").uuid4()),
            task_id=task.id,
            skill_version=skill_result.skill_version,
            model_used=skill_result.model_used,
        )
        db.add(result_row)
        await db.flush()  # get result_row.id without committing yet

        # Validate + persist each finding — this is the TR-02/03/04 enforcement point
        for f in skill_result.findings:
            rejected = False
            rejection_reason = None
            bbox = {}

            if f.document_id not in page_lookup:
                rejected = True
                rejection_reason = "cited document_id not in task's document set"
            else:
                doc_content = page_lookup[f.document_id]
                page = next(
                    (p for p in doc_content.pages if p.page_number == f.page_number), None
                )
                if page is None:
                    rejected = True
                    rejection_reason = "cited page_number does not exist in document"
                else:
                    found_bbox = find_evidence_bbox(page, f.evidence_quote)
                    if found_bbox is None:
                        rejected = True
                        rejection_reason = "evidence_quote not found verbatim on cited page"
                    else:
                        bbox = found_bbox

            finding_row = Finding(
                id=str(__import__("uuid").uuid4()),
                result_id=result_row.id,
                title=f.title,
                risk_explanation=f.risk_explanation,
                recommended_action=f.recommended_action,
                confidence=f.confidence,
                document_id=f.document_id if f.document_id in page_lookup else list(documents.keys())[0],
                page_number=f.page_number,
                evidence_quote=f.evidence_quote,
                highlight_bbox=bbox,
                rejected=rejected,
                rejection_reason=rejection_reason,
            )
            db.add(finding_row)

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        await db.commit()

    except Exception as e:
        task.retry_count += 1
        task.error_message = str(e)[:500]  # cap length, avoid dumping huge tracebacks with doc content
        if task.retry_count >= MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.QUEUED  # will be picked up again
        await db.commit()