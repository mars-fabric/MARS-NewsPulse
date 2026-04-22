"""
Backend services for MARS NewsPulse.

Minimal service layer — WebSocket connection management, session lifecycle,
and PDF extraction. Provider-specific services (workflow/execution) live in
cmbagent_infosys and are imported on demand.
"""

from services.connection_manager import ConnectionManager, connection_manager
from services.session_manager import (
    SessionManager,
    get_session_manager,
    create_session_manager,
)

__all__ = [
    "ConnectionManager",
    "connection_manager",
    "SessionManager",
    "get_session_manager",
    "create_session_manager",
]
