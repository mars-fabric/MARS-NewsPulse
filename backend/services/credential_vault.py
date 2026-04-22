"""
Encrypted credential storage with file-based persistence.

Credentials are encrypted at rest using AES-256-GCM.
The encryption key is derived from MARS_CREDENTIAL_KEY env var.
If no key is set, falls back to a machine-specific key derived
from hostname + install path (less secure, but works out of box).

Storage: JSON file at {CMBAGENT_DEFAULT_WORK_DIR}/config/credentials.enc
"""

import os
import json
import hashlib
import logging
import threading
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

_CREDENTIAL_KEY_ENV = "MARS_CREDENTIAL_KEY"


class CredentialVault:
    """
    Thread-safe singleton encrypted credential store.

    Stores provider credentials as:
    {
        "openai": {"api_key": "sk-..."},
        "azure": {"api_key": "...", "endpoint": "...", ...},
        "aws_bedrock": {"aws_access_key_id": "...", ...},
        ...
    }
    """

    _instance: Optional["CredentialVault"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        # Double-checked locking: fast path skips the lock when already initialized.
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self, base_dir: str = None):
        if self._initialized:
            return
        self._initialized = True
        self._base_dir = base_dir or os.getenv(
            "CMBAGENT_DEFAULT_WORK_DIR",
            os.path.expanduser("~/Desktop/cmbdir"),
        )
        self._config_dir = os.path.join(self._base_dir, "config")
        self._cred_file = os.path.join(self._config_dir, "credentials.enc")
        self._credentials: Dict[str, Dict[str, str]] = {}
        # Guards read-modify-write of _credentials + disk I/O in _save().
        self._write_lock = threading.Lock()
        self._load()

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing only)."""
        with cls._singleton_lock:
            cls._instance = None

    def _get_encryption_key(self) -> bytes:
        """Get or derive the 32-byte encryption key."""
        explicit_key = os.getenv(_CREDENTIAL_KEY_ENV)
        if explicit_key:
            return hashlib.sha256(explicit_key.encode()).digest()
        # Fallback: machine-specific derivation
        import socket
        seed = f"{socket.gethostname()}:{os.path.abspath(self._base_dir)}"
        return hashlib.sha256(seed.encode()).digest()

    def _encrypt(self, data: bytes) -> bytes:
        """AES-256-GCM encrypt."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = self._get_encryption_key()
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, data, None)
        return nonce + ct  # prepend nonce

    def _decrypt(self, data: bytes) -> bytes:
        """AES-256-GCM decrypt."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = self._get_encryption_key()
        nonce = data[:12]
        ct = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None)

    def _load(self) -> None:
        """Load credentials from encrypted file."""
        if not os.path.exists(self._cred_file):
            self._credentials = {}
            return
        try:
            with open(self._cred_file, "rb") as f:
                encrypted = f.read()
            decrypted = self._decrypt(encrypted)
            self._credentials = json.loads(decrypted.decode())
            logger.info(
                "Loaded credentials for %d providers", len(self._credentials)
            )
        except Exception as e:
            logger.warning("Failed to load credentials: %s", e)
            self._credentials = {}

    def _save(self) -> None:
        """Persist credentials to encrypted file."""
        os.makedirs(self._config_dir, exist_ok=True)
        data = json.dumps(self._credentials).encode()
        encrypted = self._encrypt(data)
        # Atomic write
        tmp_file = self._cred_file + ".tmp"
        with open(tmp_file, "wb") as f:
            f.write(encrypted)
        os.replace(tmp_file, self._cred_file)
        # Restrict file permissions
        try:
            os.chmod(self._cred_file, 0o600)
        except OSError:
            pass  # Windows doesn't support POSIX permissions

    def get(self, provider_id: str) -> Dict[str, str]:
        """Get credentials for a provider."""
        return self._credentials.get(provider_id, {})

    def set(self, provider_id: str, credentials: Dict[str, str]) -> None:
        """Store credentials for a provider and persist."""
        with self._write_lock:
            self._credentials[provider_id] = credentials
            self._save()

    def remove(self, provider_id: str) -> None:
        """Remove credentials for a provider."""
        with self._write_lock:
            self._credentials.pop(provider_id, None)
            self._save()

    def list_configured(self) -> Dict[str, bool]:
        """Return which providers have stored credentials."""
        return {pid: bool(creds) for pid, creds in self._credentials.items()}

    def get_all(self) -> Dict[str, Dict[str, str]]:
        """Get all credentials (for syncing to registry)."""
        return dict(self._credentials)
