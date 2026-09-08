# app/api/documents.py
import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.store.db import get_db
from app.harness.models import Document, Project
from app.docproc.extract import extract_document
import asyncio

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])

UPLOAD_DIR = "/app/data/uploads"


@router.post("")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # confirm project exists and scope the upload to it (WF-01: documents stay project-scoped)
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    doc_id = str(uuid.uuid4())
    storage_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")

    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    # PyMuPDF is sync — offload to a thread so we don't block the event loop
    extracted = await asyncio.to_thread(extract_document, storage_path)

    document = Document(
        id=doc_id,
        project_id=project_id,
        filename=file.filename,
        storage_path=storage_path,
        page_count=extracted.page_count,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return {
        "id": document.id,
        "filename": document.filename,
        "page_count": document.page_count,
    }


@router.get("")
async def list_documents(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.project_id == project_id))
    docs = result.scalars().all()
    return [
        {"id": d.id, "filename": d.filename, "page_count": d.page_count}
        for d in docs
    ]