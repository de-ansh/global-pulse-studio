"""Pydantic schemas for event clusters and radar filters."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.schemas.source import ArticleResponse


class VerificationChecklistItem(BaseModel):
    id: str
    label: str
    passed: bool
    detail: str


class FactCheckResponse(BaseModel):
    claim: str
    claimant: Optional[str] = None
    claim_date: Optional[str] = None
    publisher: str
    rating: str
    title: Optional[str] = None
    url: str
    review_date: Optional[str] = None


class EventClusterResponse(BaseModel):
    id: str
    headline: str
    summary: Optional[str] = None
    region: str
    severity: str
    status: str
    first_seen: datetime
    last_updated: datetime
    article_count: int
    explainer_score: float
    key_actors: List[str] = []
    chokepoints: List[str] = []
    strategic_keywords: List[str] = []
    
    # Multi-source triangulation metrics
    source_count: int = 1
    source_names: List[str] = []
    triangulation_level: str = "unverified"  # 'triangulated' | 'corroborated' | 'unverified'
    confidence_score: float = 0.50
    independent_origin_count: int = 1
    verification_label: str = "Unconfirmed claim — single origin"
    is_india_relevant: bool = False
    has_domestic_source: bool = False
    has_international_source: bool = False
    verification_checklist: List[VerificationChecklistItem] = []

    model_config = ConfigDict(from_attributes=True)


class EventClusterDetail(EventClusterResponse):
    articles: List[ArticleResponse] = []


class ClusterFilterParams(BaseModel):
    region: Optional[str] = None
    severity: Optional[str] = None
    min_score: Optional[float] = None
    limit: int = 50
    offset: int = 0
