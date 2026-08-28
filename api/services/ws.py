# api/services/ws.py — B6. Connection hub + broadcast for WS /api/stream
# (docs/backend/09-PHASE-B6-events-materiality-ws.md section 5 / FINAL.md section 10).
#
# Deliberately minimal — exactly the skeleton in the phase doc. It knows nothing about the
# DB or the engine; it only tracks live sockets and fans a frame out to them. The on-connect
# snapshot (current sim / newest metrics / newest forecast) needs DB and engine access, so it
# is built in api/routers/events.py's websocket handler, not here (services stay one layer
# below routers — 00-BACKEND-OVERVIEW.md section 3).
from __future__ import annotations

import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class Hub:
    def __init__(self) -> None:
        self._conns: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._conns.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._conns.discard(ws)

    async def send(self, channel: str, sim_day: int, data: dict) -> None:
        """Fire-and-forget broadcast. A dead socket never raises into a request handler —
        collect failures and drop those sockets instead (section 5 rule)."""
        frame = {"channel": channel, "sim_day": sim_day, "data": data}
        dead = []
        for ws in list(self._conns):
            try:
                await ws.send_json(frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = Hub()
