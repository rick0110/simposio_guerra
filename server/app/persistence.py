"""Persistência em disco: snapshot atual e arquivos por turno.

Layout em settings.DATA_DIR:
    state.json              snapshot do jogo (escrito a cada mudança)
    turns/turn_XX.json      estado após a resolução de cada turno (usado pelo rollback)

Escrita atômica: grava em "<arquivo>.tmp" no mesmo diretório, faz fsync e troca com os.replace.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.config import settings

SNAPSHOT_NAME = "state.json"
TURNS_DIR_NAME = "turns"
_TURN_FILE = re.compile(r"^turn_(\d+)\.json$")


def _data_dir() -> Path:
    return Path(settings.DATA_DIR)


def _snapshot_path() -> Path:
    return _data_dir() / SNAPSHOT_NAME


def _turn_path(turn: int) -> Path:
    return _data_dir() / TURNS_DIR_NAME / f"turn_{turn:02d}.json"


def _write_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(data, ensure_ascii=False)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            # Não recomeçar um jogo em silêncio por cima de um arquivo corrompido.
            raise ValueError(f"Arquivo de estado corrompido: {path} ({exc})") from exc


def save_snapshot(game_dict: dict[str, Any]) -> None:
    _write_atomic(_snapshot_path(), game_dict)


def load_snapshot() -> dict[str, Any] | None:
    return _read(_snapshot_path())


def save_turn_archive(turn: int, game_dict: dict[str, Any]) -> None:
    _write_atomic(_turn_path(int(turn)), game_dict)


def load_turn_archive(turn: int) -> dict[str, Any] | None:
    try:
        number = int(turn)
    except (TypeError, ValueError):
        return None
    return _read(_turn_path(number))


def list_turn_archives() -> list[int]:
    folder = _data_dir() / TURNS_DIR_NAME
    if not folder.is_dir():
        return []
    turns = []
    for entry in folder.iterdir():
        match = _TURN_FILE.match(entry.name)
        if match:
            turns.append(int(match.group(1)))
    return sorted(turns)


def clear_turn_archives() -> None:
    """Apaga os arquivos de turno (usado ao criar uma nova partida)."""
    d = _turn_path(0).parent
    if d.exists():
        for f in d.glob("turn_*.json"):
            f.unlink()
