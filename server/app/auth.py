"""Cookies de sessão assinados (HMAC-SHA256).

Valor do cookie `em_session`: base64url(json) + "." + base64url(HMAC-SHA256(SECRET_KEY, parte_json)).
O payload recebe "exp" (epoch em segundos); a validade é de 12 h.
Payloads usados: {"fid": "GAU"} para facções e {"admin": true} para o árbitro.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response
from starlette.requests import HTTPConnection

from app.config import settings

COOKIE_NAME = "em_session"
MAX_AGE = 12 * 60 * 60  # segundos

SESSION_EXPIRED = "Sessão expirada: faça login novamente"
ADMIN_REQUIRED = "Acesso restrito ao árbitro: faça login como árbitro."


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(mac)


def make_cookie(payload: dict[str, Any]) -> str:
    """Gera o valor assinado do cookie de sessão a partir do payload."""
    data = dict(payload)
    data["exp"] = int(time.time()) + MAX_AGE
    body = _b64encode(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def read_cookie(value: str | None) -> dict[str, Any] | None:
    """Valida assinatura e validade; devolve o payload original ou None."""
    if not value or "." not in value:
        return None
    body, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(signature.encode("utf-8"), _sign(body).encode("ascii")):
        return None
    try:
        data = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    exp = data.pop("exp", None)
    if not isinstance(exp, int) or isinstance(exp, bool) or exp < time.time():
        return None
    return data


def current_session(conn: HTTPConnection) -> dict[str, Any] | None:
    """Sessão do cookie de uma requisição HTTP ou de um WebSocket."""
    return read_cookie(conn.cookies.get(COOKIE_NAME))


def require_faction(request: Request) -> str:
    """Devolve o fid da facção logada; 401 se não houver sessão de facção."""
    fid = (current_session(request) or {}).get("fid")
    if not isinstance(fid, str) or not fid:
        raise HTTPException(status_code=401, detail=SESSION_EXPIRED)
    return fid


def require_admin(request: Request) -> None:
    """Exige sessão de árbitro; 401 caso contrário."""
    if (current_session(request) or {}).get("admin") is not True:
        raise HTTPException(status_code=401, detail=ADMIN_REQUIRED)


def set_session(response: Response, payload: dict[str, Any]) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_cookie(payload),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
