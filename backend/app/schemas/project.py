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
    governance_risk: str = "none"  # "none" | "low" | "mixed" | "high"
    governance_warning: Optional[str] = None
    state_controlled_sources: int = 0
    governance_penalty: int = 0
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
    governance_risk: str = "none"  # "none" | "low" | "mixed" | "high"
    governance_warning: Optional[str] = None
    state_controlled_sources: int = 0
    citations: List[SourceSheetCitation] = []
    sources: List[Dict[str, Any]] = []
    markdown: str


class ClusterCrossCheckArticle(BaseModel):
    id: str
    title: str
    outlet: str
    origin: Optional[str] = None
    governance_type: Optional[str] = None
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
    independent_origins: int = 0
    supporting_outlets: int = 0
    disputing_origins: int = 0
    silent_count: int
    total_checked: int
    governance_risk: str = "none"  # "none" | "low" | "mixed" | "high"
    governance_warning: Optional[str] = None
    auto_confirmed: bool = False
    recommendation: Optional[str] = None
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


class MediaVerificationRequest(BaseModel):
    media_url: str
    claimed_date: Optional[datetime] = None


class MediaVerificationResponse(BaseModel):
    media_url: str
    verdict: str  # "Likely Original / Authentic", "Recycled Footage Warning", "Synthetic / Video Game Footage", "Inconclusive"
    risk_level: str  # "low", "medium", "high"
    is_recycled_footage: bool = False
    is_synthetic_or_game: bool = False
    earliest_seen_year: Optional[int] = None
    best_guess_label: Optional[str] = None
    web_entities: List[str] = []
    matching_domains: List[str] = []
    explanation: str


class ProductionCitation(BaseModel):
    """One resolved (or unresolved) citation attached to a shot."""
    id: str
    found: bool = True
    kind: Optional[str] = None  # "article" | "claim" | "unknown"
    title: Optional[str] = None
    outlet: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    status: Optional[str] = None
    governance_type: Optional[str] = None
    text: Optional[str] = None


class ProductionShot(BaseModel):
    """One beat as an editor-ready shot, with timings only when it is not blocked on a source."""
    shot_number: int
    act_index: int
    act_title: str
    act_timecode: str = ""
    beat_index: int
    kind: str
    narration: str
    broll: Optional[str] = None
    citations: List[ProductionCitation] = []
    needs_source: bool
    included_in_timeline: bool
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    start_timecode: Optional[str] = None
    end_timecode: Optional[str] = None


class ProductionNarrationPlan(BaseModel):
    voice: Optional[str] = None
    words_per_minute: int
    word_count: int
    estimated_runtime_seconds: float
    estimated_runtime_timecode: str


class ProductionToolchainStatus(BaseModel):
    available: bool = True
    ffmpeg: Optional[str] = None
    pillow: bool = True
    missing: List[str] = []


class ProjectProductionPackageResponse(BaseModel):
    """Deterministic shot list, timings, captions and manifest for the stored script."""
    project_id: Optional[str] = None
    title: str
    logline: str = ""
    generated_at: str
    narration: ProductionNarrationPlan
    shots: List[ProductionShot] = []
    total_shots: int
    included_shots: int
    skipped_shots: int
    needs_source_shots: int
    warnings: List[str] = []
    captions_srt: str = ""
    captions_vtt: str = ""
    shotlist_markdown: str = ""
    shotlist_csv: str = ""
    render_toolchain: Optional[ProductionToolchainStatus] = None





