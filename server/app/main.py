"""Aplicação FastAPI: rotas, WebSocket, páginas estáticas e o laço do relógio do jogo.

Estado do processo (em `app.state`):
- game: instância de Game (ou o objeto criado por game_factory, nos testes);
- map_data: dict do map.json ({} se o mapa não existir e houver game_factory);
- lock: asyncio.Lock que serializa toda operação que muda o jogo;
- hub: Hub de WebSocket;
- commit(events): salva o snapshot (e o arquivo do turno, se houve resolução) e publica os eventos.
  Deve ser chamado com o lock tomado;
- new_game(**kwargs) e game.from_dict: usados pelas rotas do árbitro.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import auth
from app.config import settings
from app.hub import Hub
from app.persistence import load_snapshot, save_snapshot, save_turn_archive
from app.routes_admin import router as admin_router
from app.routes_faction import router as faction_router
from app.routes_public import router as public_router
from app.routes_tools import router as tools_router

logger = logging.getLogger("estado_maior")

TICK_SECONDS = 1.0
WS_CLOSE_UNAUTHORIZED = 4401
PAGES = {"/teatro": "teatro.html", "/qg": "qg.html", "/arbitro": "arbitro.html"}


class NoCacheStaticFiles(StaticFiles):
    """Estáticos com Cache-Control: no-cache, para que os PCs do evento não usem JS antigo."""

    async def get_response(self, path: str, scope: Any):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def _now_ms() -> int:
    return int(time.time() * 1000)


def _read_map(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _detail_of(exc: Exception) -> str:
    if exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return str(exc) or "Requisição inválida."


async def _commit(app: FastAPI, events: Iterable[dict[str, Any]] = ()) -> None:
    events = list(events or [])
    game = app.state.game
    snapshot = game.to_dict()
    save_snapshot(snapshot)
    for event in events:
        if event.get("type") == "resolution":
            # O relatório do turno traz o número do turno resolvido; sem ele, usa o turno atual.
            turn = (event.get("data") or {}).get("turn", snapshot.get("turn"))
            if turn is not None:
                save_turn_archive(turn, snapshot)
    for event in events:
        await app.state.hub.publish(event)


async def _clock(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            async with app.state.lock:
                events = app.state.game.tick(_now_ms()) or []
                if events:
                    await app.state.commit(events)
        except Exception:
            logger.exception("Falha no relógio do jogo; nova tentativa no próximo segundo.")


def create_app(game_factory: Callable[[dict[str, Any]], Any] | None = None) -> FastAPI:
    """Cria a aplicação.

    game_factory: opcional, recebe map_data e devolve o objeto de jogo. Usado nos testes;
    nesse modo o snapshot de disco não é carregado na inicialização.
    """

    def _load_game(app: FastAPI) -> Any:
        map_data = _read_map(Path(settings.MAP_PATH))
        if game_factory is not None:
            app.state.map_data = map_data or {}
            return game_factory(app.state.map_data)
        if map_data is None:
            raise RuntimeError(
                f"Mapa não encontrado em {settings.MAP_PATH}. Gere-o com tools/gen_map.py."
            )
        app.state.map_data = map_data
        from app.game.game import Game  # import preguiçoso: o núcleo pode não existir nos testes

        snapshot = load_snapshot()
        if snapshot is not None:
            return Game.from_dict(snapshot, map_data)
        game = Game.new(
            map_data,
            n_factions=settings.N_FACTIONS,
            turn_minutes=settings.TURN_MINUTES,
            max_turns=settings.MAX_TURNS,
            seed=settings.SEED,
        )
        save_snapshot(game.to_dict())
        return game

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.game = _load_game(app)
        app.state.lock = asyncio.Lock()
        clock = asyncio.create_task(_clock(app), name="relogio-do-jogo")
        try:
            yield
        finally:
            clock.cancel()
            with suppress(asyncio.CancelledError):
                await clock

    app = FastAPI(title="Estado-Maior", lifespan=lifespan)
    hub = Hub()
    app.state.hub = hub
    app.state.map_data = None
    app.state.commit = lambda events=(): _commit(app, events)

    def _new_game(**kwargs: Any) -> Any:
        if game_factory is not None:
            return game_factory(app.state.map_data)
        from app.game.game import Game

        return Game.new(app.state.map_data, **kwargs)

    app.state.new_game = _new_game

    @app.exception_handler(ValueError)
    @app.exception_handler(KeyError)
    async def _game_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": _detail_of(exc)})

    app.include_router(public_router)
    app.include_router(faction_router)
    app.include_router(admin_router)
    app.include_router(tools_router)

    @app.get("/api/server_time", include_in_schema=False)
    async def server_time() -> dict[str, int]:
        return {"now_ms": _now_ms()}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket, ch: str = "public") -> None:
        session = auth.current_session(ws) or {}
        await ws.accept()
        fid: str | None = None
        if ch == "public":
            pass
        elif ch == "faction":
            fid = session.get("fid")
            if not isinstance(fid, str) or not fid:
                await ws.close(code=WS_CLOSE_UNAUTHORIZED)
                return
        elif ch == "admin":
            if session.get("admin") is not True:
                await ws.close(code=WS_CLOSE_UNAUTHORIZED)
                return
        else:
            await ws.close(code=WS_CLOSE_UNAUTHORIZED)
            return

        hub.register(ws, ch, fid)
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
        finally:
            hub.unregister(ws)

    def _page(name: str) -> Callable[[], Any]:
        async def page() -> FileResponse:
            path = Path(settings.WEB_DIR) / name
            if not path.is_file():
                raise HTTPException(status_code=404, detail="Página ainda não disponível.")
            return FileResponse(path, headers={"Cache-Control": "no-cache"})

        return page

    for route, name in PAGES.items():
        app.add_api_route(route, _page(name), methods=["GET"], include_in_schema=False)

    # Montado por último: tudo que não é API nem página explícita cai nos estáticos.
    if Path(settings.WEB_DIR).is_dir():
        app.mount("/", NoCacheStaticFiles(directory=settings.WEB_DIR, html=True), name="web")

    return app


app = create_app()
