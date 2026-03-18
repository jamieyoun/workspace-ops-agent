"""Pydantic v2 schemas for Notion-like workspace."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Workspace ---
class WorkspaceBase(BaseModel):
    name: str


class WorkspaceResponse(WorkspaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class WorkspaceStats(BaseModel):
    page_count: int
    issue_count: int
    open_issue_count: int
    recommendation_count: int
    proposed_recommendation_count: int


class WorkspaceWithStats(WorkspaceResponse):
    stats: WorkspaceStats


# --- Page ---
class PageBase(BaseModel):
    title: str
    content_markdown: Optional[str] = None
    owner: Optional[str] = None


class PageResponse(PageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    last_updated_at: datetime
    created_at: datetime
    archived_at: Optional[datetime] = None


# --- PageMetric ---
class PageMetricBase(BaseModel):
    word_count: int = 0
    block_count: int = 0
    embed_count: int = 0
    database_refs_count: int = 0


class PageMetricResponse(PageMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    computed_at: datetime


# --- Issue ---
class IssueBase(BaseModel):
    type: str
    severity: int = Field(ge=1, le=5)
    summary: str
    details_json: Optional[str] = None


class IssueResponse(IssueBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    page_id: Optional[int] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


# --- Recommendation ---
class RecommendationStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    applied = "applied"
    dismissed = "dismissed"


class RecommendationBase(BaseModel):
    type: str
    priority: int = Field(ge=1, le=5)
    title: str
    rationale: Optional[str] = None
    proposed_changes_json: Optional[str] = None
    status: RecommendationStatus = RecommendationStatus.proposed


class RecommendationResponse(RecommendationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    page_id: Optional[int] = None
    why_this_matters: Optional[str] = None
    risk_tradeoff: Optional[str] = None
    expected_impact: Optional[str] = None
    created_at: datetime


# --- AgentAction ---
class AgentActionBase(BaseModel):
    action_type: str
    actor: str = Field(pattern="^(agent|user)$")
    payload_json: Optional[str] = None


class AgentActionResponse(AgentActionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    recommendation_id: Optional[int] = None
    created_at: datetime


# --- Analysis / Scoring ---
class SubscoreResponse(BaseModel):
    name: str
    score: float
    weight: float
    explanation: str


class WorkspaceScoreResponse(BaseModel):
    overall: float
    subscores: List[SubscoreResponse]
    issue_count: int
    open_issue_count: int
    last_analysis_at: Optional[datetime] = None


class AnalyzeResponse(BaseModel):
    pages_processed: int
    metrics_updated: int
    issues_upserted: int


class GenerateRecommendationsResponse(BaseModel):
    count: int
    source: str  # "openai" | "heuristic"


class RecommendationExplainResponse(BaseModel):
    why_this_matters: str
    risk_tradeoff: str
    expected_impact: str
    source: str  # "openai" | "heuristic"


class ApplyRecommendationRequest(BaseModel):
    owner: Optional[str] = None
    summary_text: Optional[str] = None
    section_text: Optional[str] = None
    new_title: Optional[str] = None


class ApplyRecommendationResponse(BaseModel):
    applied: bool
    reason: Optional[str] = None
    idempotent: Optional[bool] = None
    new_page_id: Optional[int] = None


class RecommendationStatusResponse(BaseModel):
    id: int
    status: str


class AuditActionResponse(BaseModel):
    id: int
    action_type: str
    actor: str
    recommendation_id: Optional[int] = None
    payload_json: Optional[str] = None
    created_at: datetime
