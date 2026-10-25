"""Pydantic schemas for video essay projects, dossiers, and narrative outlines."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints


# Projects created from a cluster take its headline as title (EventCluster.headline allows 512), and generated
# angle titles embed that topic, so both must accept 512 even though the (unenforced) SQLite columns say less.
ProjectTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
AngleTitle = Annotated[str, StringConstraints(max_length=1024)]
DurationMins = Annotated[int, Field(ge=1, le=240)]
ProjectStatus = Literal["concept", "researching", "scripting", "storyboarding", "ready", "archived"]


class ProjectCreate(BaseModel):
    title: ProjectTitle
    target_duration_mins: DurationMins = 15
    selected_angle: Optional[AngleTitle] = None
    cluster_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[ProjectTitle] = None
    target_duration_mins: Optional[DurationMins] = None
    status: Optional[ProjectStatus] = None
    selected_angle: Optional[AngleTitle] = None


ClaimStatus = Literal["unverified", "confirmed", "disputed", "false"]


class ClaimEvidence(BaseModel):
    # HttpUrl rejects javascript:/data: links that would otherwise be rendered as clickable hrefs.
    url: HttpUrl
    label: str = Field("", max_length=200)
    archive_url: Optional[HttpUrl] = None


class ClaimCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    evidence: List[ClaimEvidence] = []
    epistemic_level: Optional[str] = None
    attributed_to: Optional[str] = None


class ClaimUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=1000)
    status: Optional[ClaimStatus] = None
    epistemic_level: Optional[str] = None
    attributed_to: Optional[str] = None
    note: Optional[str] = Field(None, max_length=4000)
    evidence: Optional[List[ClaimEvidence]] = None


class ClaimCheckResponse(BaseModel):
    verdict: str  # supported | partly_supported | contradicted | not_addressed | unverifiable | not_checked
    explanation: str = ""
    quotes: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    claim_text: str
    model: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    id: str
    project_id: str
    text: str
    status: ClaimStatus
    epistemic_level: Optional[str] = "empirical_event"
    attributed_to: Optional[str] = None
    note: Optional[str] = None
    evidence: List[Dict[str, Any]] = []
    created_at: datetime
    status_changed_at: Optional[datetime] = None
    ai_check: Optional[ClaimCheckResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DossierResponse(BaseModel):
    id: str
    project_id: str
    timeline_events: List[Dict[str, Any]] = []
    stakeholders: List[Dict[str, Any]] = []
    geography: Dict[str, Any] = {}
    contradictions: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScriptOutlineResponse(BaseModel):
    id: str
    project_id: str
    acts: List[Dict[str, Any]] = []
    hook_variants: List[Dict[str, Any]] = []
    visual_prompts: List[Dict[str, Any]] = []
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScriptResponse(BaseModel):
    id: str
    project_id: str
    content: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {}
    model: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NarrativeAngleOption(BaseModel):
    angle_type: str  # e.g., 'resource_economic', 'historical_grievance', 'deterrence_game_theory'
    title: str
    thesis: str
    core_question: str
    target_emotion: str
    id: Optional[str] = None
    premise: Optional[str] = None
    tone: Optional[str] = None
    key_tension: Optional[str] = None
    hook: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    working_slug: str
    target_duration_mins: int
    status: str
    selected_angle: Optional[str] = None
    cluster_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(ProjectResponse):
    dossier: Optional[DossierResponse] = None
    script_outline: Optional[ScriptOutlineResponse] = None


class ReadinessChecklistItem(BaseModel):
    id: str
    label: str
    passed: bool
    detail: str


class ProjectReadinessResponse(BaseModel):
    project_id: str
    score: int  # 0-100
    status: str  # "ready" | "needs_review" | "unverified"
    total_claims: int
    confirmed_claims: int
    unverified_claims: int
    disputed_claims: int
    false_claims: int
    total_sources: int
    independent_origins: int
    script_support_checked: bool
    script_verdict_summary: Dict[str, int] = {}
    checklist: List[ReadinessChecklistItem] = []
    warnings: List[str] = []


class SourceSheetCitation(BaseModel):
    type: str  # "claim" | "script_statement"
    id: str
    text: str
    status: str
    evidence_urls: List[str] = []
    archive_urls: List[str] = []
    verbatim_quotes: List[str] = []
    outlet: Optional[str] = None


class ProjectSourceSheetResponse(BaseModel):
    project_id: str
    title: str
    generated_at: datetime
    readiness_score: int
    citations: List[SourceSheetCitation] = []
    sources: List[Dict[str, Any]] = []
    markdown: str


class ClusterCrossCheckArticle(BaseModel):
    id: str
    title: str
    outlet: str
    url: Optional[str] = None
    overlap_ratio: float = 0.0
    matched_terms: List[str] = []
    reason: Optional[str] = None


class ClusterCrossCheckResponse(BaseModel):
    claim_id: Optional[str] = None
    claim_text: str
    cluster_id: Optional[str] = None
    status: str  # "broad_consensus" | "corroborated" | "disputed" | "isolated_claim" | "unaddressed"
    summary: str
    supporting: List[ClusterCrossCheckArticle] = []
    disputing: List[ClusterCrossCheckArticle] = []
    silent_count: int
    total_checked: int
    superseded_warning: Optional[str] = None


class ClaimCacheMatchResponse(BaseModel):
    has_match: bool
    canonical_hash: Optional[str] = None
    claim_text: Optional[str] = None
    status: Optional[str] = None
    epistemic_level: Optional[str] = None
    attributed_to: Optional[str] = None
    evidence: List[Dict[str, Any]] = []
    verified_in_project_id: Optional[str] = None
    message: Optional[str] = None



