# app/harness/models.py
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, Enum, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.store.db import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="project")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)  # local path or object store key
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="documents")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    skill_name: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "bidgaps"
    document_ids: Mapped[list] = mapped_column(JSON, default=list)  # scoped doc set for this task
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.QUEUED, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    result: Mapped["Result | None"] = relationship(back_populates="task", uselist=False)


class Result(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, unique=True)
    skill_version: Mapped[str] = mapped_column(String, nullable=False)
    model_used: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="result")
    findings: Mapped[list["Finding"]] = relationship(back_populates="result")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    result_id: Mapped[str] = mapped_column(ForeignKey("results.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    risk_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0–1.0

    # citation / evidence integrity fields (TR-02, TR-03)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    highlight_bbox: Mapped[dict] = mapped_column(JSON, nullable=False)  # {x0,y0,x1,y1}

    rejected: Mapped[bool] = mapped_column(default=False)  # true if evidence check failed (TR-04)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped["Result"] = relationship(back_populates="findings")