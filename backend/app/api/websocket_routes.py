from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.session_service import session_service
from ..services.websocket_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def session_updates(websocket: WebSocket, session_id: str) -> None:
    session = session_service.sessions.get_session(session_id)
    if session is None:
        await websocket.close(code=1008, reason="Session not found")
        return

    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
