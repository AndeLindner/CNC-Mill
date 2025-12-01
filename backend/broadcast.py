import asyncio
from typing import Dict, Set

from fastapi import WebSocket


class Broadcaster:
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def register(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.connections.add(ws)

    async def unregister(self, ws: WebSocket):
        async with self.lock:
            if ws in self.connections:
                self.connections.remove(ws)
        try:
            await ws.close()
        except Exception:
            pass

    async def broadcast(self, payload: Dict):
        async with self.lock:
            conns = list(self.connections)
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                await self.unregister(ws)
