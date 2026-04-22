"""
Bridges the CredentialVault (backend persistence) with
cmbagent's ProviderRegistry (runtime provider resolution).

Called:
  1. On server startup (lifespan)
  2. After any credential store/update/delete via API
  3. Explicitly via POST /api/providers/sync
"""

import logging
from typing import Dict, Any

from services.credential_vault import CredentialVault

logger = logging.getLogger(__name__)


class ConfigBridge:
    """Syncs credentials from multiple sources into cmbagent's ProviderRegistry."""

    @staticmethod
    def sync_all() -> Dict[str, str]:
        """
        Full sync: .env -> vault -> registry -> os.environ.

        Priority (highest wins):
        1. CredentialVault (user set via UI)
        2. os.environ / .env file (admin set)

        Returns dict of {provider_id: status}
        """
        try:
            from cmbagent.providers.registry import ProviderRegistry
        except ImportError:
            logger.warning("cmbagent.providers not available — skipping credential sync")
            return {"error": "cmbagent.providers not importable"}

        registry = ProviderRegistry.instance()
        vault = CredentialVault()
        results: Dict[str, str] = {}

        # Step 1: Load from .env / os.environ (base layer)
        registry.refresh_from_env()

        # Step 2: Override with vault credentials (UI layer — takes priority)
        for provider_id, creds in vault.get_all().items():
            if creds:
                try:
                    registry.set_credentials(provider_id, creds)
                    results[provider_id] = "synced_from_vault"
                except ValueError:
                    logger.warning("Provider '%s' in vault but not in registry, skipping", provider_id)
                    results[provider_id] = "provider_not_in_registry"
            else:
                results[provider_id] = "empty_in_vault"

        # Step 3: Refresh the legacy LLMProviderConfig singleton
        try:
            from cmbagent.llm_provider import get_provider_config
            get_provider_config().refresh()
        except Exception as e:
            logger.warning("Failed to refresh legacy LLMProviderConfig: %s", e)

        logger.info("Config sync complete: %s", results)
        return results

    @staticmethod
    async def sync_and_validate(provider_id: str) -> Dict[str, Any]:
        """
        Sync a single provider and validate its credentials.
        Called after UI stores new credentials.
        """
        try:
            from cmbagent.providers.registry import ProviderRegistry
        except ImportError:
            return {"status": "error", "message": "cmbagent.providers not importable"}

        registry = ProviderRegistry.instance()
        vault = CredentialVault()

        # Get credentials from vault
        creds = vault.get(provider_id)
        if not creds:
            return {"status": "not_configured", "message": "No credentials stored"}

        # Inject into registry
        registry.set_credentials(provider_id, creds)

        # Validate
        result = await registry.validate_provider(provider_id)

        # Refresh legacy singleton
        try:
            from cmbagent.llm_provider import get_provider_config
            get_provider_config().refresh()
        except Exception:
            pass

        return {
            "status": "validated" if result.success else "invalid",
            "message": result.message,
            "latency_ms": result.latency_ms,
            "error_details": result.error_details,
        }
