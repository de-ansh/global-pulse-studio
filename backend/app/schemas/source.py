"""Pydantic schemas for sources and articles."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceBase(BaseModel):
    name: str
    feed_url: str
    homepage_url: Optional[str] = None
    source_type: str = "wire"
    governance_type: str = "commercial_wire"
    region: str = "Global"
    bias_category: Optional[str] = None
    reliability_score: float = 0.85
    is_active: bool = True


def _require_web_url(v: Optional[str]) -> Optional[str]:
    # URLs are fetched by the server and rendered as hrefs; allow only http(s).
    if v is not None and not v.lower().startswith(("http://", "https://")):
        raise ValueError("must be an http:// or https:// URL")
    return v


class SourceCreate(SourceBase):
    id: str
    reliability_score: float = Field(0.85, ge=0.0, le=1.0)

    _check_urls = field_validator("feed_url", "homepage_url")(_require_web_url)


class SourceUpdate(BaseModel):
    """Partial update: only fields sent are changed."""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    feed_url: Optional[str] = None
    homepage_url: Optional[str] = None
    source_type: Optional[str] = None
    governance_type: Optional[str] = None
    region: Optional[str] = None
    bias_category: Optional[str] = None
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None

    _check_urls = field_validator("feed_url", "homepage_url")(_require_web_url)


class SourceResponse(SourceBase):
    id: str
    last_fetched_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleResponse(BaseModel):
    id: str
    source_id: str
    cluster_id: Optional[str] = None
    title: str
    url: str
    author: Optional[str] = None
    summary: Optional[str] = None
    published_at: datetime
    ingested_at: datetime
    topics: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class ScanSummary(BaseModel):
    sources_scanned: int
    new_articles_ingested: int
    duplicate_articles_skipped: int
    clusters_created_or_updated: int
    errors: List[Dict[str, str]] = []
