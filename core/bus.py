"""
core/bus.py — Agent-to-agent message bus
Pub/Sub system for asynchronous agent communication.
"""
from core.logger import logger
import asyncio
from collections import defaultdict

class EventBus:
    def __init__(self):
        self.subscribers = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, callback):
        async with self._lock:
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)

    async def unsubscribe(self, event_type: str, callback):
        async with self._lock:
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)

    async def publish(self, event_type: str, data: dict):
        # We don't lock while invoking callbacks to avoid deadlocks
        subs = []
        async with self._lock:
            subs = list(self.subscribers.get(event_type, []))
        
        # Fire and forget / parallelize handling
        for callback in subs:
            asyncio.create_task(self._safe_invoke(callback, data))

    async def _safe_invoke(self, callback, data):
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            logger.error(f"[BUS] Error handling event: {e}")

# Global singleton bus
bus = EventBus()
