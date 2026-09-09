# app/api/tasks.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.store.db import get_db
from app.harness.models import Task, TaskStatus, Document, Project, Result, Finding

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    objective: str
    skill_name: str
    document_ids: list[str]


@router.post("")
async def create_task(
    project_id: str,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Document.id).where(
            Document.project_id == project_id,
            Document.id.in_(body.document_ids),
        )
    )
    valid_doc_ids = {row[0] for row in result.all()}
    invalid = set(body.document_ids) - valid_doc_ids
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Documents not found in this project: {invalid}",
        )

    task = Task(
        id=str(uuid.uuid4()),
        project_id=project_id,
        objective=body.objective,
        skill_name=body.skill_name,
        document_ids=body.document_ids,
        status=TaskStatus.QUEUED,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return {"id": task.id, "status": task.status.value}


@router.get("/{task_id}")
async def get_task(project_id: str, task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "status": task.status.value,
        "objective": task.objective,
        "skill_name": task.skill_name,
        "error_message": task.error_message,
        "retry_count": task.retry_count,
    }


@router.get("/{task_id}/result")
async def get_task_result(project_id: str, task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(select(Result).where(Result.task_id == task_id))
    result_row = result.scalar_one_or_none()
    if result_row is None:
        raise HTTPException(status_code=404, detail="No result yet for this task")

    findings_result = await db.execute(
        select(Finding).where(Finding.result_id == result_row.id, Finding.rejected == False)
    )
    findings = findings_result.scalars().all()

    return {
        "skill_version": result_row.skill_version,
        "model_used": result_row.model_used,
        "findings": [
            {
                "title": f.title,
                "risk_explanation": f.risk_explanation,
                "recommended_action": f.recommended_action,
                "confidence": f.confidence,
                "document_id": f.document_id,
                "page_number": f.page_number,
                "evidence_quote": f.evidence_quote,
                "highlight_bbox": f.highlight_bbox,
            }
            for f in findings
        ],
    }
