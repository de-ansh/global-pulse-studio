"""Models for intelligence sources and raw ingested articles."""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class Source(Base):
    """Monitored publication, wire service, or think-tank feed."""
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    homepage_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="wire")  # wire, think_tank, gov, independent
    region: Mapped[str] = mapped_column(String(64), default="Global")
    bias_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.85)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    articles: Mapped[List["Article"]] = relationship("Article", back_populates="source", cascade="all, delete-orphan")


class Article(Base):
    """Raw intelligence report or article ingested from a feed."""
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("event_clusters.id", ondelete="SET NULL"), nullable=True)
    
    canonical_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clean_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    entities: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    topics: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    source: Mapped["Source"] = relationship("Source", back_populates="articles")
    cluster: Mapped[Optional["EventCluster"]] = relationship("EventCluster", back_populates="articles")  # type: ignore # noqa: F821

    __table_args__ = (
        Index("idx_articles_published", "published_at"),
        Index("idx_articles_source", "source_id"),
    )
