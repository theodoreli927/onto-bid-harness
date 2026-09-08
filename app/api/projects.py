# app/api/projects.py
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.store.db import get_db
from app.harness.models import Project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str


@router.post("")
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(id=str(uuid.uuid4()), name=body.name)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": project.id, "name": project.name}