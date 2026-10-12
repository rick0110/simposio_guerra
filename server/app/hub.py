"""Hub de WebSocket com os canais `public`, `faction:<FID>` e `admin`.

Cada socket se inscreve com `ch` ("public", "faction" ou "admin") e, para facção, com o fid.
Regras de entrega, conforme o canal do evento:
- "public": todos os sockets (públicos, facções e admin);
- "faction:X": sockets da facção X e do admin;
- "admin": só o admin;
- qualquer outro canal: só o admin (falha fechada).

Mensagem enviada ao cliente: {"type", "data"} (sem o campo channel).
Sockets que falham no envio (ou não respondem a tempo) são removidos sem derrubar o servidor.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("estado_maior.hub")

SEND_TIMEOUT_S = 5.0


@dataclass(eq=False)
class _Client:
    ws: Any
    ch: str
    fid: str | None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _accepts(client: _Client, channel: str | None) -> bool:
    if client.ch == "admin":
        return True
    if channel == "public":
        return True
    return client.ch == "faction" and client.fid is not None and channel == f"faction:{client.fid}"


class Hub:
    def __init__(self) -> None:
        self._clients: list[_Client] = []

    def __len__(self) -> int:
        return len(self._clients)

    def register(self, ws: Any, ch: str, fid: str | None = None) -> None:
        # Substitui a lista (em vez de mutar) para que publish() itere sobre um instantâneo.
        self._clients = [*self._clients, _Client(ws=ws, ch=ch, fid=fid)]

    def unregister(self, ws: Any) -> None:
        self._clients = [c for c in self._clients if c.ws is not ws]

    async def publish(self, event: dict[str, Any]) -> None:
        channel = event.get("channel")
        message = {"type": event.get("type"), "data": event.get("data", {})}
        targets = [c for c in self._clients if _accepts(c, channel)]
        if not targets:
            return
        results = await asyncio.gather(
            *(self._send(client, message) for client in targets),
            return_exceptions=True,
        )
        for client, result in zip(targets, results):
            if isinstance(result, BaseException):
                logger.info("Removendo conexão WebSocket após falha de envio: %r", result)
                self.unregister(client.ws)

    async def _send(self, client: _Client, message: dict[str, Any]) -> None:
        async with client.lock:
            await asyncio.wait_for(client.ws.send_json(message), timeout=SEND_TIMEOUT_S)
