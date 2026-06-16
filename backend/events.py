"""
EventManager - Singleton SSE event streaming for TaxFlow Pro.

Provides per-user asyncio.Queue-based event delivery with graceful
disconnect handling.  Used by the /api/events endpoint and published
from routers across the application.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EventManager:
    """Singleton event manager with per-user queues for SSE delivery."""

    _instance: Optional["EventManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "EventManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queues: Dict[int, asyncio.Queue] = {}
            cls._instance._initialized = True
        return cls._instance

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def _get_or_create_queue(self, user_id: int) -> asyncio.Queue:
        """Return the asyncio.Queue for *user_id*, creating it if absent."""
        if user_id not in self._queues:
            self._queues[user_id] = asyncio.Queue(maxsize=1000)
        return self._queues[user_id]

    def _drop_queue(self, user_id: int) -> None:
        """Remove a user's queue (called on disconnect)."""
        self._queues.pop(user_id, None)

    # ------------------------------------------------------------------
    # Publishing helpers
    # ------------------------------------------------------------------

    def _publish(self, user_id: int, event_type: str, payload: dict) -> None:
        """Enqueue an event for *user_id*.  Drops silently if queue full."""
        queue = self._get_or_create_queue(user_id)
        message = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Event queue full for user %s, dropping %s", user_id, event_type)

    # ------------------------------------------------------------------
    # Typed public publishers
    # ------------------------------------------------------------------

    def publish_import_complete(self, user_id: int, statement_id: int, count: int) -> None:
        """Notify that a statement import has finished."""
        self._publish(
            user_id,
            "import_complete",
            {"statement_id": statement_id, "transactions_imported": count},
        )

    def publish_backup_created(self, user_id: int, path: str) -> None:
        """Notify that a database backup was created successfully."""
        self._publish(user_id, "backup_created", {"path": path})

    def publish_training_complete(self, user_id: int, version: str) -> None:
        """Notify that an ML model training run has completed."""
        self._publish(user_id, "training_complete", {"model_version": version})

    def publish_period_locked(self, user_id: int, period_id: int) -> None:
        """Notify that an accounting period was locked."""
        self._publish(user_id, "period_locked", {"period_id": period_id})

    # ------------------------------------------------------------------
    # SSE async generator
    # ------------------------------------------------------------------

    async def get_event_stream(self, user_id: int):
        """
        Async generator yielding SSE-formatted strings for *user_id*.

        Yields:
            str: SSE formatted event strings (``data: {...}\n\n``).

        Handles disconnects gracefully by catching CancelledError and
        cleaning up the user's queue.
        """
        queue = self._get_or_create_queue(user_id)
        logger.info("SSE stream started for user %s", user_id)

        # Send an initial connected event
        connected_msg = {
            "type": "connected",
            "payload": {"user_id": user_id},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield f"data: {json.dumps(connected_msg)}\n\n"

        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat = {
                        "type": "heartbeat",
                        "payload": {},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
                    continue

                yield f"data: {json.dumps(message)}\n\n"
                queue.task_done()

        except asyncio.CancelledError:
            logger.info("SSE stream cancelled for user %s (client disconnected)", user_id)
            self._drop_queue(user_id)
            raise
        except Exception:
            logger.exception("SSE stream error for user %s", user_id)
            self._drop_queue(user_id)
            raise
        finally:
            self._drop_queue(user_id)


# Module-level singleton accessor
event_manager = EventManager()
