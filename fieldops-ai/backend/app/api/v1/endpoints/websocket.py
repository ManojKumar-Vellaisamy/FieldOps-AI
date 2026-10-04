"""
WebSocket endpoint for real-time operational event streaming.
Authenticates client on handshake using JWT access token and streams live events.
"""

from datetime import datetime, timezone
import json
from typing import Optional
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
import structlog

from app.core.realtime import ws_manager
from app.core.security import decode_access_token

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Real-Time Synchronization"])


@router.websocket("/ws")
async def websocket_operational_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
) -> None:
    """
    Live WebSocket operational stream endpoint.

    Handshake Security:
    - Requires valid JWT access token passed via query parameter '?token=<jwt>'.
    - Validates token signature, expiration, and role claims.
    - Rejects unauthorized or expired connections with WebSocket code 1008 (Policy Violation).

    Connection Lifecycle:
    - Registers session in ws_manager upon connection.
    - Sends an initial 'CONNECTED' event confirming authenticated session details.
    - Responds to 'ping' keepalive frames with 'pong'.
    - Cleans up session from active registry on disconnect.
    """
    if not token or not token.strip():
        logger.warning("ws_auth_failed_missing_token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token is missing.")
        return

    try:
        token_payload = decode_access_token(token.strip())
        user_id = uuid.UUID(str(token_payload.sub))
        role = token_payload.role
    except Exception as err:
        logger.warning("ws_auth_failed_invalid_token", error=str(err))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired authentication token.")
        return

    session = await ws_manager.connect(websocket, user_id=user_id, role=role)

    try:
        # Initial greeting and handshake confirmation
        await websocket.send_json(
            {
                "event": "CONNECTED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "user_id": str(user_id),
                    "role": role,
                    "connected_at": session.connected_at.isoformat(),
                    "message": "FieldOps AI authenticated real-time operational stream connected.",
                },
            }
        )

        while True:
            message_text = await websocket.receive_text()
            try:
                client_msg = json.loads(message_text)
                msg_type = client_msg.get("type", "").lower()
                if msg_type == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as err:
        logger.error("ws_session_error", user_id=str(user_id), error=str(err))
        await ws_manager.disconnect(websocket)
