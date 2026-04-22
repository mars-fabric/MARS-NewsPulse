"""
WebSocket helpers for NewsPulse.

Only the thin event emitter is exported; the NewsPulse pipeline manages its
own WebSocket endpoint directly in ``main.py``.
"""

from websocket.events import send_ws_event

__all__ = [
    "send_ws_event",
]
