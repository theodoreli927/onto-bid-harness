# app/skills/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillFinding:
    """A single finding produced by a skill, before persistence or validation."""
    title: str
    risk_explanation: str
    recommended_action: str
    confidence: float
    document_id: str
    page_number: int
    evidence_quote: str
    highlight_bbox: dict[str, float] = field(default_factory=dict)  # {x0,y0,x1,y1}


@dataclass
class SkillResult:
    """What a skill returns after running — harness persists this, skill doesn't touch the DB."""
    skill_version: str
    model_used: str
    findings: list[SkillFinding]
    raw_metadata: dict[str, Any] = field(default_factory=dict)  # for debugging/eval, not shown to user


@dataclass
class SkillContext:
    """Everything a skill needs to run, assembled by the harness before invocation."""
    task_id: str
    project_id: str
    objective: str
    document_ids: list[str]
    # populated by the harness from docproc — skill never touches storage/DB directly
    document_texts: dict[str, list[str]]  # document_id -> list of page texts


class Skill(ABC):
    """
    Base interface every analysis skill implements.
    The harness only ever calls `execute` — it never imports or knows about
    a specific skill's internals. This is the boundary that lets a new skill
    be added without touching harness/task/persistence code.
    """

    name: str  # e.g. "bidgaps" — must match Task.skill_name

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        ...