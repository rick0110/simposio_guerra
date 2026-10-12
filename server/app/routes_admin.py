"""Rotas do árbitro. Exigem cookie `em_session` com {"admin": true}, obtido em /api/admin/login."""

from __future__ import annotations

import hmac
import time
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import require_admin, set_session
from app.config import settings
from app.persistence import load_turn_archive

router = APIRouter()


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Corpo da requisição deve ser JSON válido.")
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Corpo da requisição deve ser um objeto JSON.")
    return body


def _state_event() -> dict[str, Any]:
    """Pede que todos os clientes refaçam os GETs (o estado mudou de forma geral)."""
    return {"channel": "public", "type": "state", "data": {}}


async def _apply(request: Request, action: Callable[[Any], Any]) -> dict[str, Any]:
    """Executa uma ação do jogo que devolve list[Event], salva e publica."""
    app = request.app
    async with app.state.lock:
        events = action(app.state.game) or []
        await app.state.commit(events)
    return {"ok": True}


@router.post("/api/admin/login")
async def admin_login(request: Request):
    body = await _json_body(request)
    password = body.get("password")
    if not isinstance(password, str):
        password = ""
    if not hmac.compare_digest(password.encode("utf-8"), settings.ADMIN_PASSWORD.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Senha do árbitro incorreta.")
    response = JSONResponse({"ok": True})
    set_session(response, {"admin": True})
    return response


@router.get("/api/admin/state")
async def admin_state(request: Request):
    require_admin(request)
    return request.app.state.game.admin_view(_now_ms())


@router.get("/api/admin/credentials")
async def admin_credentials(request: Request):
    require_admin(request)
    return request.app.state.game.credentials()


@router.get("/api/admin/events")
async def admin_events(request: Request):
    require_admin(request)
    try:
        from app.game import events as game_events
    except ImportError:
        return []
    listing = getattr(game_events, "list_events", None)
    return listing() if callable(listing) else []


def _seed_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


@router.post("/api/admin/new_game")
async def admin_new_game(request: Request):
    require_admin(request)
    body = await _json_body(request)
    try:
        params = {
            "n_factions": int(body.get("n_factions", settings.N_FACTIONS)),
            "turn_minutes": float(body.get("turn_minutes", settings.TURN_MINUTES)),
            "max_turns": int(body.get("max_turns", settings.MAX_TURNS)),
            "seed": _seed_or_none(body.get("seed", settings.SEED)),
        }
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Parâmetros da partida devem ser numéricos.")
    app = request.app
    async with app.state.lock:
        app.state.game = app.state.new_game(**params)
        await app.state.commit([_state_event()])
    return {"ok": True}


@router.post("/api/admin/start")
async def admin_start(request: Request):
    require_admin(request)
    return await _apply(request, lambda g: g.start(_now_ms()))


@router.post("/api/admin/pause")
async def admin_pause(request: Request):
    require_admin(request)
    return await _apply(request, lambda g: g.pause(_now_ms()))


@router.post("/api/admin/resume")
async def admin_resume(request: Request):
    require_admin(request)
    return await _apply(request, lambda g: g.resume(_now_ms()))


@router.post("/api/admin/extend")
async def admin_extend(request: Request):
    require_admin(request)
    body = await _json_body(request)
    try:
        minutes = float(body.get("minutes"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Informe 'minutes' como número.")
    return await _apply(request, lambda g: g.extend(_now_ms(), minutes))


@router.post("/api/admin/resolve_now")
async def admin_resolve_now(request: Request):
    require_admin(request)
    return await _apply(request, lambda g: g.resolve_turn(_now_ms()))


@router.post("/api/admin/rollback")
async def admin_rollback(request: Request):
    require_admin(request)
    body = await _json_body(request)
    try:
        turn = int(body.get("turn"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Informe o turno como número inteiro em 'turn'.")
    snapshot = load_turn_archive(turn)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Não há arquivo salvo para o turno {turn}.")
    app = request.app
    async with app.state.lock:
        app.state.game = type(app.state.game).from_dict(snapshot, app.state.map_data)
        await app.state.commit([_state_event()])
    return {"ok": True, "turn": turn}


@router.post("/api/admin/broadcast")
async def admin_broadcast(request: Request):
    require_admin(request)
    body = await _json_body(request)
    text = body.get("text")
    to = body.get("to", "all")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail="Informe o texto do aviso em 'text'.")
    if not isinstance(to, str):
        raise HTTPException(status_code=400, detail="Destinatário inválido em 'to'.")
    return await _apply(request, lambda g: g.admin_broadcast(text, to, _now_ms()))


@router.post("/api/admin/edit_faction")
async def admin_edit_faction(request: Request):
    require_admin(request)
    body = await _json_body(request)
    faction_id = body.get("faction_id")
    patch = body.get("patch")
    if not isinstance(faction_id, str) or not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="Informe 'faction_id' (texto) e 'patch' (objeto).")
    return await _apply(request, lambda g: g.admin_edit_faction(faction_id, patch, _now_ms()))


@router.post("/api/admin/event")
async def admin_event(request: Request):
    require_admin(request)
    body = await _json_body(request)
    event_id = body.get("event_id")
    if not isinstance(event_id, str):
        raise HTTPException(status_code=400, detail="Informe 'event_id' como texto.")
    return await _apply(request, lambda g: g.admin_trigger_event(event_id, _now_ms()))
