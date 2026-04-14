"""
Pydantic models and schemas for API request/response validation.
"""

from models.schemas import (
    # Task models
    TaskType,
    TaskRequest,
    TaskResponse,
    StageInfo,
    TaskStatusResponse,
    # File models
    FileItem,
    DirectoryListing,
    # ArXiv models
    ArxivFilterRequest,
    ArxivFilterResponse,
    # Enhance input models
    EnhanceInputRequest,
    EnhanceInputResponse,
    # Branching models
    BranchRequest,
    PlayFromNodeRequest,
)

from models.copilot_schemas import (
    # Copilot configuration
    CopilotConfig,
    CopilotTaskRequest,
    CopilotTaskResponse,
    # Copilot session
    CopilotSessionInfo,
    CopilotTurnResult,
    CopilotConversationHistory,
    CopilotResult,
    # Copilot feedback
    CopilotFeedback,
    CopilotNextTaskRequest,
    # Copilot info
    CopilotWorkflowInfo,
    CopilotAgentInfo,
    AvailableAgentsResponse,
)

__all__ = [
    # Task models
    "TaskType",
    "TaskRequest",
    "TaskResponse",
    "StageInfo",
    "TaskStatusResponse",
    # File models
    "FileItem",
    "DirectoryListing",
    # ArXiv models
    "ArxivFilterRequest",
    "ArxivFilterResponse",
    # Enhance input models
    "EnhanceInputRequest",
    "EnhanceInputResponse",
    # Branching models
    "BranchRequest",
    "PlayFromNodeRequest",
    # Copilot models
    "CopilotConfig",
    "CopilotTaskRequest",
    "CopilotTaskResponse",
    "CopilotSessionInfo",
    "CopilotTurnResult",
    "CopilotConversationHistory",
    "CopilotResult",
    "CopilotFeedback",
    "CopilotNextTaskRequest",
    "CopilotWorkflowInfo",
    "CopilotAgentInfo",
    "AvailableAgentsResponse",
]
