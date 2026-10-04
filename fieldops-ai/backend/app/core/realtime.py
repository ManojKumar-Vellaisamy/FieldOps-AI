"""
FieldOps AI Real-Time Operational Synchronization Layer.

Provides in-process WebSocket connection management, authenticated session tracking,
role-based event scoping, and broadcast utilities for operational events.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Optional
import uuid

from fastapi import WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger(__name__)

# Standard Operational Event Types
EVENT_JOB_ASSIGNED = "JOB_ASSIGNED"
EVENT_JOB_UNASSIGNED = "JOB_UNASSIGNED"
EVENT_JOB_STATUS_CHANGED = "JOB_STATUS_CHANGED"
EVENT_JOB_COMPLETED = "JOB_COMPLETED"
EVENT_JOB_CANCELLED = "JOB_CANCELLED"
EVENT_TECHNICIAN_LOCATION_UPDATED = "TECHNICIAN_LOCATION_UPDATED"
EVENT_TECHNICIAN_AVAILABILITY_CHANGED = "TECHNICIAN_AVAILABILITY_CHANGED"
EVENT_ETA_UPDATED = "ETA_UPDATED"
EVENT_DISPATCH_PLAN_CHANGED = "DISPATCH_PLAN_CHANGED"


class WebSocketUserSession:
    """Represents an active, authenticated WebSocket client session."""

    def __init__(self, websocket: WebSocket, user_id: uuid.UUID, role: str) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.role = role.upper() if role else ""
        self.connected_at = datetime.now(timezone.utc)

    @property
    def is_dispatcher_or_admin(self) -> bool:
        return self.role in ("ADMINISTRATOR", "DISPATCHER")

    @property
    def is_technician(self) -> bool:
        return self.role == "TECHNICIAN"


class WebSocketConnectionManager:
    """
    Central in-memory connection manager for FieldOps real-time event distribution.
    Maintains active WebSocket sessions and routes operational events by role and identity.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: list[WebSocketUserSession] = []

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID, role: str) -> WebSocketUserSession:
        """Accept WebSocket connection and register authenticated user session."""
        await websocket.accept()
        session = WebSocketUserSession(websocket=websocket, user_id=user_id, role=role)
        async with self._lock:
            self._sessions.append(session)
        logger.info(
            "ws_client_connected",
            user_id=str(user_id),
            role=role,
            total_connections=len(self._sessions),
        )
        return session

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket session upon disconnect."""
        async with self._lock:
            self._sessions = [s for s in self._sessions if s.websocket != websocket]
        logger.info("ws_client_disconnected", remaining_connections=len(self._sessions))

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def _build_payload(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    async def _send_to_session(self, session: WebSocketUserSession, payload: dict[str, Any]) -> bool:
        """Send JSON payload to a session with error handling and stale cleanup."""
        try:
            await session.websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError, Exception) as err:
            logger.debug("ws_send_failed", user_id=str(session.user_id), error=str(err))
            return False

    async def broadcast_to_dispatchers(self, event_type: str, data: dict[str, Any]) -> int:
        """Deliver event to all connected Administrators and Dispatchers."""
        payload = self._build_payload(event_type, data)
        async with self._lock:
            targets = [s for s in self._sessions if s.is_dispatcher_or_admin]

        sent_count = 0
        dead_sessions: list[WebSocket] = []
        for session in targets:
            success = await self._send_to_session(session, payload)
            if success:
                sent_count += 1
            else:
                dead_sessions.append(session.websocket)

        if dead_sessions:
            async with self._lock:
                self._sessions = [s for s in self._sessions if s.websocket not in dead_sessions]

        return sent_count

    async def broadcast_to_technician(
        self, technician_user_id: uuid.UUID, event_type: str, data: dict[str, Any]
    ) -> int:
        """Deliver event strictly to the specific technician user ID."""
        payload = self._build_payload(event_type, data)
        async with self._lock:
            targets = [s for s in self._sessions if s.user_id == technician_user_id]

        sent_count = 0
        dead_sessions: list[WebSocket] = []
        for session in targets:
            success = await self._send_to_session(session, payload)
            if success:
                sent_count += 1
            else:
                dead_sessions.append(session.websocket)

        if dead_sessions:
            async with self._lock:
                self._sessions = [s for s in self._sessions if s.websocket not in dead_sessions]

        return sent_count

    async def broadcast_operational_event(
        self,
        event_type: str,
        data: dict[str, Any],
        technician_user_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Deliver operational event:
        1. Always to Dispatchers & Administrators.
        2. To the specific technician if technician_user_id is provided.
        3. Never leaks across other technicians.
        """
        payload = self._build_payload(event_type, data)
        async with self._lock:
            targets: list[WebSocketUserSession] = []
            for s in self._sessions:
                if s.is_dispatcher_or_admin:
                    targets.append(s)
                elif technician_user_id and s.user_id == technician_user_id:
                    targets.append(s)

        sent_count = 0
        dead_sessions: list[WebSocket] = []
        for session in targets:
            success = await self._send_to_session(session, payload)
            if success:
                sent_count += 1
            else:
                dead_sessions.append(session.websocket)

        if dead_sessions:
            async with self._lock:
                self._sessions = [s for s in self._sessions if s.websocket not in dead_sessions]

        return sent_count


# Global singleton instance
ws_manager = WebSocketConnectionManager()
