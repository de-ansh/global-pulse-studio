"""Model for clustered geopolitical events and crises."""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    DateTime,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class EventCluster(Base):
    """A cluster of multi-source reports describing a unified geopolitical event."""
    __tablename__ = "event_clusters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    headline: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[str] = mapped_column(String(64), default="Global", index=True)
    severity: Mapped[str] = mapped_column(String(32), default="routine", index=True)  # routine, escalating, crisis
    status: Mapped[str] = mapped_column(String(32), default="emerging")  # emerging, active, archived
    
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    
    article_count: Mapped[int] = mapped_column(Integer, default=1)
    explainer_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    
    key_actors: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    chokepoints: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    strategic_keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    articles: Mapped[List["Article"]] = relationship("Article", back_populates="cluster")  # type: ignore # noqa: F821

    __table_args__ = (
        Index("idx_clusters_score", "explainer_score"),
        Index("idx_clusters_region_severity", "region", "severity"),
    )
