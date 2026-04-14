"""
Pydantic models for API request and response validation.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# Task Models
# =============================================================================

class TaskType(str, Enum):
    STANDARD = "standard"
    DEEPRESEARCH_RESEARCH = "deepresearch-research"


class TaskRequest(BaseModel):
    """Request model for task submission."""
    task: str
    config: Dict[str, Any] = {
        "model": "gpt-4o",
        "maxRounds": 25,
        "maxAttempts": 6,
        "agent": "engineer",
        "workDir": "~/Desktop/cmbdir"
    }
    task_type: TaskType = Field(default=TaskType.STANDARD, description="Task type")
    data_description: Optional[str] = Field(None, description="Data description for Deepresearch tasks")


class TaskResponse(BaseModel):
    """Response model for task submission."""
    task_id: str
    status: str
    message: str


class StageInfo(BaseModel):
    """Stage information within a multi-stage task."""
    stage_number: int
    stage_name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Extended task status including stage information."""
    task_id: str
    status: str
    task_type: str = "standard"
    mode: Optional[str] = None
    created_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    updated_at: Optional[str] = None
    # Stage fields (only for deepresearch tasks)
    stages: Optional[List[StageInfo]] = None
    current_stage: Optional[int] = None
    progress_percent: Optional[float] = None
    total_cost_usd: Optional[float] = None


# =============================================================================
# File Models
# =============================================================================

class FileItem(BaseModel):
    """Model representing a file or directory item."""
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: Optional[int] = None
    modified: Optional[float] = None
    mime_type: Optional[str] = None


class DirectoryListing(BaseModel):
    """Model representing a directory listing response."""
    path: str
    items: List[FileItem]
    parent: Optional[str] = None


# =============================================================================
# ArXiv Models
# =============================================================================

class ArxivFilterRequest(BaseModel):
    """Request model for arXiv URL filtering."""
    input_text: str
    work_dir: Optional[str] = None


class ArxivFilterResponse(BaseModel):
    """Response model for arXiv URL filtering."""
    status: str
    result: Dict[str, Any]
    message: str


# =============================================================================
# Enhance Input Models
# =============================================================================

class EnhanceInputRequest(BaseModel):
    """Request model for input text enhancement."""
    input_text: str
    work_dir: Optional[str] = None
    max_workers: Optional[int] = 2
    max_depth: Optional[int] = 10


class EnhanceInputResponse(BaseModel):
    """Response model for input text enhancement."""
    status: str
    enhanced_text: str
    processing_summary: Dict[str, Any]
    cost_breakdown: Dict[str, Any]
    message: str


# =============================================================================
# Branching Models
# =============================================================================

class BranchRequest(BaseModel):
    """Request model for creating a workflow branch."""
    node_id: str  # DAG node ID (e.g., "step_1", "planning")
    branch_name: str
    hypothesis: Optional[str] = None
    new_instructions: Optional[str] = None  # New instructions for branch planning
    modifications: Optional[Dict[str, Any]] = None
    execute_immediately: bool = False  # Whether to start execution right away


class BranchExecuteRequest(BaseModel):
    """Request model for executing a branch."""
    config_overrides: Optional[Dict[str, Any]] = None


class PlayFromNodeRequest(BaseModel):
    """Request model for resuming execution from a node."""
    node_id: str
    context_override: Optional[Dict[str, Any]] = None
