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


class ClaimCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    evidence: List[ClaimEvidence] = []


class ClaimUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=1000)
    status: Optional[ClaimStatus] = None
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
