"""Panele giden olaylar: geçmiş + canlı abonelik (WebSocket başına bir kuyruk)."""
import asyncio
import time


class EventBus:
    def __init__(self, keep: int = 500):
        self.history: list[dict] = []
        self.keep = keep
        self._subs: set[asyncio.Queue] = set()

    def publish(self, event: dict) -> None:
        event.setdefault("t", time.time())
        self.history.append(event)
        del self.history[:-self.keep]
        for q in list(self._subs):
            q.put_nowait(event)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)
