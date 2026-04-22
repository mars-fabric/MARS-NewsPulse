"""
Provider Management API — multi-provider LLM credential management.

Endpoints:
  GET    /api/providers                     — List all registered providers
  GET    /api/providers/{id}                — Get single provider details
  POST   /api/providers/{id}/credentials    — Store credentials for a provider
  POST   /api/providers/{id}/test           — Test credentials without storing
  DELETE /api/providers/{id}/credentials    — Remove stored credentials
  GET    /api/providers/models/available    — Models from all configured providers
  POST   /api/providers/sync               — Force re-sync .env + vault -> registry
"""

import time
import logging

from fastapi import APIRouter, HTTPException
from models.provider_schemas import ProviderCredentialInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["Providers"])


def _get_registry():
    """Lazy-import the ProviderRegistry to avoid import-time failures."""
    try:
        from cmbagent.providers.registry import ProviderRegistry
        return ProviderRegistry.instance()
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Provider system not available: {e}",
        )


def _get_vault():
    """Lazy-import the CredentialVault."""
    from services.credential_vault import CredentialVault
    return CredentialVault()


def _get_bridge():
    """Lazy-import the ConfigBridge."""
    from services.config_bridge import ConfigBridge
    return ConfigBridge


# ─── List / Detail ─────────────────────────────────────────────────────

@router.get("")
async def list_providers():
    """List all registered providers with status, credential schema, and models."""
    registry = _get_registry()
    providers = registry.list_providers()
    active = registry.get_active_provider()

    total_models = sum(len(p.get("models", [])) for p in providers)

    return {
        "providers": providers,
        "active_provider": active.provider_id if active else None,
        "total_models": total_models,
        "timestamp": time.time(),
    }


@router.get("/models/available")
async def get_available_models():
    """Get models from ALL configured providers (for UI dropdowns)."""
    registry = _get_registry()
    models = registry.get_available_models_for_configured_providers()

    # Count unique providers
    providers_seen = set()
    for m in models:
        providers_seen.add(m.get("provider", ""))

    return {
        "models": models,
        "provider_count": len(providers_seen),
        "timestamp": time.time(),
    }


@router.get("/{provider_id}")
async def get_provider_detail(provider_id: str):
    """Get details for a single provider."""
    registry = _get_registry()
    providers = registry.list_providers()

    for p in providers:
        if p["provider_id"] == provider_id:
            return p

    raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")


# ─── Credential Operations ─────────────────────────────────────────────

@router.post("/{provider_id}/credentials")
async def store_provider_credentials(
    provider_id: str, body: ProviderCredentialInput
):
    """Store credentials for a provider, persist to vault, sync to registry.

    If registry sync fails with an unexpected error (not an invalid-credentials
    result), roll back the vault write so we don't persist orphaned credentials
    that fail to sync at every startup.
    """
    vault = _get_vault()
    bridge = _get_bridge()
    registry = _get_registry()

    # Verify provider exists before touching vault
    known_providers = {p["provider_id"] for p in registry.list_providers()}
    if provider_id not in known_providers:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_id}' not found"
        )

    # Capture prior credentials for rollback
    had_prior = bool(vault.get(provider_id))
    prior_creds = vault.get(provider_id) if had_prior else None

    # Store in vault (encrypted persistence)
    vault.set(provider_id, body.credentials)

    # Sync to registry + validate. Rollback on unexpected exceptions.
    try:
        result = await bridge.sync_and_validate(provider_id)
    except Exception as exc:
        logger.exception("sync_and_validate failed for %s; rolling back vault write", provider_id)
        if had_prior and prior_creds is not None:
            vault.set(provider_id, prior_creds)
        else:
            vault.remove(provider_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync credentials: {exc}",
        )

    # Count models from this provider
    models_added = 0
    for p in registry.list_providers():
        if p["provider_id"] == provider_id:
            models_added = len(p.get("models", []))
            break

    return {
        "status": "success",
        "provider": {
            "provider_id": provider_id,
            "status": result.get("status", "unknown"),
            "message": result.get("message", ""),
            "latency_ms": result.get("latency_ms"),
        },
        "models_added": models_added,
        "timestamp": time.time(),
    }


@router.post("/{provider_id}/test")
async def test_provider_credentials(
    provider_id: str, body: ProviderCredentialInput
):
    """Test credentials without storing them."""
    registry = _get_registry()
    providers = {p["provider_id"]: p for p in registry.list_providers()}

    if provider_id not in providers:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_id}' not found"
        )

    # Access the adapter. `_adapters` is private but the registry exposes no
    # public "test arbitrary credentials without persisting" method. Guard the
    # access so a registry refactor surfaces a clear error instead of AttributeError.
    adapters = getattr(registry, "_adapters", None)
    adapter = adapters.get(provider_id) if adapters else None
    if not adapter:
        raise HTTPException(
            status_code=404, detail=f"Provider adapter '{provider_id}' not found"
        )

    try:
        result = await adapter.test_credentials(body.credentials)
    except Exception as exc:
        logger.exception("Adapter test_credentials raised for %s", provider_id)
        return {
            "success": False,
            "message": f"Test failed: {exc}",
            "latency_ms": None,
            "error_details": str(exc),
            "models_available": None,
            "timestamp": time.time(),
        }

    return {
        "success": result.success,
        "message": result.message,
        "latency_ms": result.latency_ms,
        "error_details": result.error_details,
        "models_available": result.models_available,
        "timestamp": time.time(),
    }


@router.delete("/{provider_id}/credentials")
async def remove_provider_credentials(provider_id: str):
    """Remove stored credentials for a provider."""
    vault = _get_vault()
    registry = _get_registry()

    vault.remove(provider_id)

    # Explicitly clear from registry (clears internal state + env vars)
    try:
        registry.remove_credentials(provider_id)
    except ValueError:
        pass  # provider not in registry — already clean

    return {
        "status": "success",
        "message": f"Credentials for '{provider_id}' removed",
        "timestamp": time.time(),
    }


# ─── Sync ───────────────────────────────────────────────────────────────

@router.post("/sync")
async def force_sync():
    """Force re-sync .env + vault -> registry. Called after manual .env edits."""
    bridge = _get_bridge()
    results = bridge.sync_all()

    return {
        "status": "success",
        "results": results,
        "timestamp": time.time(),
    }
