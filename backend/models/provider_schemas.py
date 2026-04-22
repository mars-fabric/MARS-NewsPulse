"""
Pydantic schemas for the Provider Management API endpoints.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class ProviderCredentialInput(BaseModel):
    """Input for storing/testing credentials."""
    credentials: Dict[str, str] = Field(
        ..., description="Map of credential field name to value"
    )


class ProviderTestResponse(BaseModel):
    """Response for credential test operations."""
    success: bool
    message: str
    latency_ms: Optional[float] = None
    error_details: Optional[str] = None
    models_available: Optional[List[str]] = None


class ProviderStatusResponse(BaseModel):
    """Single provider status."""
    provider_id: str
    display_name: str
    status: str
    models_count: int = 0


class ProviderCredentialFieldSchema(BaseModel):
    """Schema for a single credential field (sent to frontend)."""
    name: str
    display_name: str
    description: str
    required: bool = True
    field_type: str = "password"
    placeholder: str = ""
    validation_pattern: str = ""
    options: List[Dict[str, str]] = []
    has_value: bool = False
    masked_value: str = ""


class ProviderModelSchema(BaseModel):
    """Schema for a single model (sent to frontend)."""
    model_id: str
    display_name: str
    context_window: int = 128000
    max_output_tokens: int = 4096
    supports_vision: bool = False
    category: str = "chat"


class ProviderDetailResponse(BaseModel):
    """Full detail for a single provider."""
    provider_id: str
    display_name: str
    status: str
    credential_fields: List[ProviderCredentialFieldSchema] = []
    models: List[ProviderModelSchema] = []


class ProvidersListResponse(BaseModel):
    """Response for GET /api/providers."""
    providers: List[Dict[str, Any]]
    active_provider: Optional[str] = None
    total_models: int = 0
    timestamp: float = 0


class ProviderStoreResponse(BaseModel):
    """Response for POST /api/providers/{id}/credentials."""
    status: str
    provider: Dict[str, Any]
    models_added: int = 0
    timestamp: float = 0


class AvailableModelsResponse(BaseModel):
    """Response for GET /api/providers/models/available."""
    models: List[Dict[str, Any]]
    provider_count: int = 0
    timestamp: float = 0


class SyncResponse(BaseModel):
    """Response for POST /api/providers/sync."""
    status: str
    results: Dict[str, str]
    timestamp: float = 0


class RemoveCredentialsResponse(BaseModel):
    """Response for DELETE /api/providers/{id}/credentials."""
    status: str
    message: str
    timestamp: float = 0
