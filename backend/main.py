"""
MARS NewsPulse Backend API - Main Entry Point

This module assembles all components and starts the FastAPI application.
Standalone extraction of the NewsPulse feature from MARS.
"""

import sys
from pathlib import Path

# Add the backend directory to the path to import local modules (task_framework, core, routers, etc.)
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket

# Import core app factory
from core.app import create_app

# Import routers
from routers import register_routers

# Import WebSocket components
from websocket.events import send_ws_event

# Create the FastAPI application
app = create_app()

# Register all REST API routers
register_routers(app)


# WebSocket endpoint for News Pulse stage execution
@app.websocket("/ws/newspulse/{task_id}/{stage_num}")
async def newspulse_websocket_endpoint(websocket: WebSocket, task_id: str, stage_num: int):
    """WebSocket endpoint for streaming News Pulse stage execution output."""
    import asyncio
    from routers.newspulse import _get_console_lines, _clear_console_buffer

    await websocket.accept()

    buf_key = f"np:{task_id}:{stage_num}"
    line_index = 0

    try:
        await send_ws_event(websocket, "status", {
            "message": f"Connected to stage {stage_num}",
            "stage_num": stage_num,
        }, run_id=task_id)

        while True:
            await asyncio.sleep(1)

            new_lines = _get_console_lines(buf_key, since_index=line_index)
            for line in new_lines:
                await send_ws_event(websocket, "console_output", {
                    "text": line,
                    "stage_num": stage_num,
                }, run_id=task_id)
            line_index += len(new_lines)

            try:
                from cmbagent.database.base import get_db_session
                db = get_db_session()
                try:
                    from routers.newspulse import _get_session_id_for_task, _get_stage_repo
                    session_id = _get_session_id_for_task(task_id, db)
                    repo = _get_stage_repo(db, session_id=session_id)
                    stages = repo.list_stages(parent_run_id=task_id)
                    stage = next((s for s in stages if s.stage_number == stage_num), None)
                    if stage:
                        if stage.status == "completed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_completed", {
                                "stage_num": stage_num,
                                "stage_name": stage.stage_name,
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                        elif stage.status == "failed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_failed", {
                                "stage_num": stage_num,
                                "error": stage.error_message or "Stage failed",
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                finally:
                    db.close()
            except Exception:
                pass
    except Exception:
        pass
