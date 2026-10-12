"""Estado serializável do jogo: a classe `Faction` e utilitários de JSON puro."""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass, field, fields
from typing import Any

import numpy as np

from app.game import balance as B

Event = dict  # {"channel": "public" | "faction:GAU" | "admin", "type": str, "data": dict}


def ev(channel: str, type_: str, data: dict | None = None) -> dict:
    return {"channel": channel, "type": type_, "data": data if data is not None else {}}


def clean(obj: Any) -> Any:
    """Converte recursivamente para JSON puro: numpy → tipos nativos, tuplas → listas, chaves → str."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return clean(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return clean(float(obj))
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    return obj


def deep(obj: Any) -> Any:
    return copy.deepcopy(obj)


def num(x: float, digits: int = 1) -> str:
    """Formata com vírgula decimal brasileira; inteiros saem sem casas."""
    x = float(x)
    if abs(x - round(x)) < 0.5 * 10 ** (-digits):
        return str(int(round(x)))
    return f"{x:.{digits}f}".replace(".", ",")


def signed(x: float, digits: int = 1) -> str:
    s = num(x, digits)
    return s if s.startswith("-") or s == "0" else "+" + s


def upper_ascii(text: str) -> str:
    from app.engine import cipher
    return cipher.normalize(text).strip()


def troops_range(n: int) -> str:
    n = int(n)
    if n <= 0:
        return "0"
    if n <= 5:
        return "1–5"
    if n <= 10:
        return "6–10"
    if n <= 20:
        return "11–20"
    return "21+"


def _default_stock() -> dict:
    return dict(B.START_STOCK)


def _default_policy() -> dict:
    return {"racao": 0, "propaganda": 0, "horas": 8}


def _default_bonuses() -> dict:
    return {"productivity": False, "weather_revealed": False, "depot_located": None}


def _default_orders() -> dict:
    return {s: None for s in B.SECTIONS}


@dataclass
class Faction:
    id: str
    slot: int
    password: str = ""
    stock: dict = field(default_factory=_default_stock)
    morale: float = B.START_MORALE
    policy: dict = field(default_factory=_default_policy)
    betas: list = field(default_factory=list)            # SEGREDO: coeficientes culturais da moral
    A_clean: list = field(default_factory=list)          # SEGREDO: matriz técnica "de base"
    A_prev: list = field(default_factory=list)           # matriz usada no turno anterior (aparece nos dossiês)
    A_turn: list = field(default_factory=list)           # SEGREDO: matriz do turno em curso
    a_damage_next: float = 0.0
    cipher_key: list = field(default_factory=list)       # SEGREDO: chave de Hill 2x2
    cipher_gen: int = -1
    capitulated: bool = False
    challenges_solved: int = 0
    pacts: list = field(default_factory=list)            # [{"with": fid, "until_turn": n}]
    bonuses: dict = field(default_factory=_default_bonuses)
    last_x: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    last_report: Any = None
    orders: dict = field(default_factory=_default_orders)
    orders_at: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    telegrams: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return clean(asdict(self))

    @classmethod
    def from_dict(cls, d: dict) -> "Faction":
        names = {f.name for f in fields(cls)}
        return cls(**{k: copy.deepcopy(v) for k, v in d.items() if k in names})

    # -- atalhos -------------------------------------------------------------------
    @property
    def nation(self) -> dict:
        return B.NATION_BY_ID[self.id]

    @property
    def name(self) -> str:
        return self.nation["name"]

    @property
    def short(self) -> str:
        return self.nation["short"]

    def has_pact_with(self, other: str, turn: int) -> bool:
        return any(p["with"] == other and p["until_turn"] >= turn for p in self.pacts)
