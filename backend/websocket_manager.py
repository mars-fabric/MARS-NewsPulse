"""
DEPRECATED: WebSocketManager

This module is deprecated. Use backend/services/connection_manager.py instead.

The ConnectionManager provides:
- Thread-safe operations with async locks
- Connection limits
- Proper event queue integration
- No duplicate websocket.accept() calls

Migration:
    # Old:
    from websocket_manager import ws_manager
    await ws_manager.connect(websocket, run_id)

    # New:
    from services.connection_manager import connection_manager
    await connection_manager.connect(websocket, task_id)
"""

import warnings
warnings.warn(
    "websocket_manager.py is deprecated. Use services/connection_manager.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Keep old implementation for backward compatibility but redirect
from services.connection_manager import connection_manager as _cm


class WebSocketManager:
    """DEPRECATED: Use ConnectionManager from services/connection_manager.py"""

    def __init__(self):
        warnings.warn("WebSocketManager is deprecated", DeprecationWarning)
        self.active_connections = _cm._connections

    async def connect(self, websocket, run_id):
        warnings.warn("Use connection_manager.connect() instead", DeprecationWarning)
        # NOTE: Do NOT call websocket.accept() here - it's already called by handler
        return await _cm.connect(websocket, run_id)

    async def disconnect(self, run_id):
        return await _cm.disconnect(run_id)

    async def send_event(self, run_id, event):
        return await _cm.send_event(run_id, event)


# Deprecated global instance
ws_manager = WebSocketManager()
