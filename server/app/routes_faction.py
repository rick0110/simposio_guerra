"""Rotas da facção. Exigem cookie `em_session` com fid; tudo é filtrado pelo fid do cookie."""

from __future__ import annotations

import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.auth import require_faction

router = APIRouter()

SECTIONS = ("intendencia", "operacoes", "inteligencia", "governo")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _check_section(section: str) -> None:
    if section not in SECTIONS:
        raise HTTPException(status_code=404, detail=f"Seção desconhecida: {section}")


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


@router.get("/api/faction/state")
async def faction_state(request: Request):
    fid = require_faction(request)
    return request.app.state.game.faction_view(fid, _now_ms())


@router.get("/api/faction/dossier/{section}")
async def faction_dossier(section: str, request: Request):
    fid = require_faction(request)
    _check_section(section)
    return request.app.state.game.dossier_view(fid, section)


@router.get("/api/faction/dossier/{section}/{dataset_id}.csv")
async def faction_dataset_csv(section: str, dataset_id: str, request: Request):
    fid = require_faction(request)
    _check_section(section)
    text = request.app.state.game.dataset_csv(fid, section, dataset_id)
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", f"{section}-{dataset_id}")
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'},
    )


@router.post("/api/faction/orders/{section}")
async def faction_orders(section: str, request: Request):
    fid = require_faction(request)
    _check_section(section)
    payload = await _json_body(request)
    app = request.app
    async with app.state.lock:
        result = app.state.game.submit_orders(fid, section, payload, _now_ms())
        await app.state.commit([])
    return result


@router.post("/api/faction/challenge/{challenge_id}")
async def faction_challenge(challenge_id: str, request: Request):
    fid = require_faction(request)
    body = await _json_body(request)
    answer = body.get("answer")
    if not isinstance(answer, str):
        raise HTTPException(status_code=400, detail="Informe a resposta como texto em 'answer'.")
    app = request.app
    async with app.state.lock:
        result = app.state.game.answer_challenge(fid, challenge_id, answer, _now_ms())
        await app.state.commit([])
    return result


@router.post("/api/faction/message")
async def faction_message(request: Request):
    fid = require_faction(request)
    body = await _json_body(request)
    to_faction = body.get("to_faction")
    text = body.get("text")
    if not isinstance(to_faction, str) or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Informe 'to_faction' e 'text' como texto.")
    app = request.app
    async with app.state.lock:
        events = app.state.game.send_message(fid, to_faction, text, _now_ms())
        await app.state.commit(events or [])
    return {"ok": True}
