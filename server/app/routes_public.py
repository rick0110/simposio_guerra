"""Rotas públicas e de sessão (login/logout/me, estado público, mapa)."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app import auth

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


@router.get("/api/public/map")
async def public_map(request: Request):
    app = request.app
    game = app.state.game
    if hasattr(game, "public_map"):
        return game.public_map()
    if not app.state.map_data:
        raise HTTPException(status_code=404, detail="Mapa ainda não foi gerado (tools/gen_map.py).")
    return app.state.map_data


@router.get("/api/public/state")
async def public_state(request: Request):
    return request.app.state.game.public_view(_now_ms())


@router.post("/api/login")
async def login(request: Request):
    body = await _json_body(request)
    fid = str(body.get("faction_id") or "").strip().upper()
    password = str(body.get("password") or "")
    game = request.app.state.game
    try:
        ok = bool(fid) and bool(game.check_password(fid, password))
    except (ValueError, KeyError):
        ok = False  # facção desconhecida recebe a mesma resposta que senha errada
    if not ok:
        raise HTTPException(status_code=401, detail="Facção ou senha incorretos.")
    response = JSONResponse({"ok": True, "faction_id": fid})
    auth.set_session(response, {"fid": fid})
    return response


@router.post("/api/logout")
async def logout():
    response = JSONResponse({"ok": True})
    auth.clear_session(response)
    return response


@router.get("/api/me")
async def me(request: Request):
    session = auth.current_session(request) or {}
    fid = session.get("fid")
    return {
        "faction_id": fid if isinstance(fid, str) and fid else None,
        "admin": session.get("admin") is True,
    }
