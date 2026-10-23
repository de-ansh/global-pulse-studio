"""Models for creator video projects, research dossiers, and script outlines."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class Project(Base):
    """A creator's video essay project."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    working_slug: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    target_duration_mins: Mapped[int] = mapped_column(Integer, default=15)
    status: Mapped[str] = mapped_column(String(32), default="concept")  # concept, researching, scripting, archived
    selected_angle: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    dossier: Mapped[Optional["Dossier"]] = relationship("Dossier", back_populates="project", uselist=False, cascade="all, delete-orphan")
    script_outline: Mapped[Optional["ScriptOutline"]] = relationship("ScriptOutline", back_populates="project", uselist=False, cascade="all, delete-orphan")
    script: Mapped[Optional["Script"]] = relationship("Script", back_populates="project", uselist=False, cascade="all, delete-orphan")


class Dossier(Base):
    """Synthesized geopolitical research dossier backing the video project."""
    __tablename__ = "dossiers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)

    timeline_events: Mapped[list] = mapped_column(JSON, default=list)
    stakeholders: Mapped[list] = mapped_column(JSON, default=list)
    geography: Mapped[dict] = mapped_column(JSON, default=dict)
    contradictions: Mapped[list] = mapped_column(JSON, default=list)
    citations: Mapped[list] = mapped_column(JSON, default=list)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="dossier")


class ScriptOutline(Base):
    """5-Act documentary narrative structure with B-roll visual cues and hooks."""
    __tablename__ = "script_outlines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)

    acts: Mapped[list] = mapped_column(JSON, default=list)
    hook_variants: Mapped[list] = mapped_column(JSON, default=list)
    visual_prompts: Mapped[list] = mapped_column(JSON, default=list)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="script_outline")


class Claim(Base):
    """A factual claim the script relies on, with evidence and the creator's verdict."""
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="unverified")  # unverified, confirmed, disputed, false
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # [{"url": ..., "label": ...}]

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Latest AI evidence check, eager-loaded so every claim response can include it.
    ai_check: Mapped[Optional["ClaimCheck"]] = relationship(
        "ClaimCheck", uselist=False, lazy="selectin", cascade="all, delete-orphan", passive_deletes=True
    )


class ClaimCheck(Base):
    """AI comparison of a claim against the event's reports and its attached evidence (a suggestion, never a verdict)."""
    __tablename__ = "claim_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(64), ForeignKey("claims.id", ondelete="CASCADE"), unique=True, nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)  # the wording that was checked; stale if the claim was edited since
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    quotes: Mapped[list] = mapped_column(JSON, default=list)  # [{source_id, quote}], each verified verbatim
    sources: Mapped[list] = mapped_column(JSON, default=list)  # [{id, title, outlet, url}] the check was run against
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Script(Base):
    """LLM-written narration script; every beat cites numbered sources from the project's coverage and claims."""
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)

    content: Mapped[dict] = mapped_column(JSON, default=dict)  # {title, logline, acts: [{title, timecode, beats: [...]}], open_questions}
    sources: Mapped[list] = mapped_column(JSON, default=list)  # the numbered sources the model was given: [{id: "S1", ...}]
    stats: Mapped[dict] = mapped_column(JSON, default=dict)  # verification counts
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="script")
