"""Configuração do servidor, lida de variáveis de ambiente.

Todas as variáveis são opcionais; os padrões servem para rodar no PC do árbitro
(com ou sem Docker). Caminhos padrão são resolvidos a partir deste arquivo.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

# server/app/config.py -> app -> server -> <repo>
_PKG_DIR = Path(__file__).resolve().parent            # server/app
_SERVER_DIR = _PKG_DIR.parent                          # server
_REPO_DIR = _SERVER_DIR.parent                         # raiz do repositório

_DOCKER_DATA_DIR = Path("/data")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Variável {name} deve ser um número inteiro (recebido: {value!r})") from exc


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Variável {name} deve ser um número (recebido: {value!r})") from exc


def _default_data_dir() -> Path:
    # No contêiner o volume fica em /data; em desenvolvimento usa <repo>/data.
    if _DOCKER_DATA_DIR.is_dir():
        return _DOCKER_DATA_DIR
    return _REPO_DIR / "data"


def _load_or_create_secret(path: Path) -> str:
    """Lê a chave de assinatura de cookies; cria e persiste uma nova se não existir."""
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(key, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass  # Windows e alguns sistemas de arquivos ignoram permissões POSIX
    os.replace(tmp, path)
    return key


class Settings:
    def __init__(self) -> None:
        # Senha do árbitro (painel /arbitro). Trocar antes do evento.
        self.ADMIN_PASSWORD: str = _env("ADMIN_PASSWORD", "arbitro")

        # Diretórios de dados e do front-end.
        self.DATA_DIR: Path = Path(_env("DATA_DIR", str(_default_data_dir()))).expanduser()
        self.WEB_DIR: Path = Path(_env("WEB_DIR", str(_REPO_DIR / "web"))).expanduser()
        self.MAP_PATH: Path = Path(_env("MAP_PATH", str(_PKG_DIR / "data" / "map.json"))).expanduser()

        # Rede.
        self.HOST: str = _env("HOST", "0.0.0.0")
        self.PORT: int = _env_int("PORT", 8000)

        # Regras da partida.
        self.N_FACTIONS: int = _env_int("N_FACTIONS", 4)
        self.TURN_MINUTES: float = _env_float("TURN_MINUTES", 12)
        self.MAX_TURNS: int = _env_int("MAX_TURNS", 8)
        seed = _env("SEED")
        self.SEED: int | None = int(seed) if seed is not None else None

        # Diretório de dados precisa existir antes de qualquer snapshot.
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Chave de cookies: fixa se vier do ambiente; senão persistida em DATA_DIR
        # para que as sessões sobrevivam a reinícios do contêiner.
        env_key = _env("SECRET_KEY")
        self.SECRET_KEY: str = env_key if env_key else _load_or_create_secret(self.DATA_DIR / "secret.key")

    def __repr__(self) -> str:
        shown = {k: v for k, v in vars(self).items() if k not in ("ADMIN_PASSWORD", "SECRET_KEY")}
        return f"Settings({shown})"


settings = Settings()
