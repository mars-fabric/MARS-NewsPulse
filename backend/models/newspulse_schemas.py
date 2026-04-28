"""
Pydantic schemas for the Industry News & Sentiment Pulse wizard endpoints.

4-stage pipeline:
  1 — Setup & Configuration (no AI)
  2 — News Discovery & Collection (AI research)
  3 — Deep Sentiment & Analysis (AI research)
  4 — Final Report + PDF (AI compilation)
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class NewsPulseStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Requests
# =============================================================================

class NewsPulseCreateRequest(BaseModel):
    """POST /api/newspulse/create"""
    industry: str = Field(..., description="Industry or sector to research (e.g. 'AI/ML', 'Fintech')")
    companies: Optional[str] = Field(None, description="Comma-separated company names (optional)")
    region: Optional[str] = Field("Global", description="Geography/region focus")
    time_window: Optional[str] = Field("7d", description="Time window: 1d, 7d, 30d, 90d")
    config: Optional[Dict[str, Any]] = Field(None, description="Model configuration overrides")
    work_dir: Optional[str] = Field(None, description="Base work directory")


class NewsPulseExecuteRequest(BaseModel):
    """POST /api/newspulse/{task_id}/stages/{num}/execute"""
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Per-stage overrides")


class NewsPulseContentUpdateRequest(BaseModel):
    """PUT /api/newspulse/{task_id}/stages/{num}/content"""
    content: str = Field(..., description="Updated markdown content")
    field: str = Field("draft_report", description="shared_state key to update")


class NewsPulseRefineChatMessage(BaseModel):
    """Single message in refinement conversation history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class NewsPulseRefineRequest(BaseModel):
    """POST /api/newspulse/{task_id}/stages/{num}/refine"""
    message: str = Field(..., description="User instruction for the LLM")
    content: str = Field(..., description="Current editor content to refine")
    history: list[NewsPulseRefineChatMessage] = Field(
        default_factory=list,
        description="Previous refinement conversation messages for context",
    )


# =============================================================================
# Responses
# =============================================================================

class NewsPulseStageResponse(BaseModel):
    """Single stage info in responses."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class NewsPulseCreateResponse(BaseModel):
    """Response for POST /api/newspulse/create"""
    task_id: str
    work_dir: str
    stages: List[NewsPulseStageResponse]


class NewsPulseStageContentResponse(BaseModel):
    """Response for GET /api/newspulse/{task_id}/stages/{num}/content"""
    stage_number: int
    stage_name: str
    status: str
    content: Optional[str] = None
    shared_state: Optional[Dict[str, Any]] = None
    output_files: Optional[List[str]] = None


class NewsPulseRefineResponse(BaseModel):
    """Response for POST /api/newspulse/{task_id}/stages/{num}/refine"""
    refined_content: str
    message: str = "Content refined successfully"
    method: Optional[str] = None  # "diff" or "fallback"
    edits_applied: Optional[int] = None
    edits_failed: Optional[int] = None


class NewsPulseTaskStateResponse(BaseModel):
    """Response for GET /api/newspulse/{task_id}"""
    task_id: str
    task: str
    status: str
    work_dir: Optional[str] = None
    created_at: Optional[str] = None
    stages: List[NewsPulseStageResponse]
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
    total_cost_usd: Optional[float] = None


class NewsPulseRecentTaskResponse(BaseModel):
    """Single item in GET /api/newspulse/recent"""
    task_id: str
    task: str
    status: str
    created_at: Optional[str] = None
    current_stage: Optional[int] = None
    progress_percent: float = 0.0
