"""Geometria: quadrícula do mapa, pontos em polígonos e triangulação por mínimos quadrados."""

from __future__ import annotations

import math
import re

import numpy as np

from app.engine import linalg

_LABEL_RE = re.compile(r"^\s*([A-Za-z])\s*(\d+)\s*$")


def grid_label(
    x: float,
    y: float,
    cell: float = 50,
    cols: str = "ABCDEFGHIJKLMNOPQRSTUVWX",
    rows: int = 16,
) -> str:
    """Rótulo da quadrícula: coluna por letra (floor(x/cell)), linha 1-based (floor(y/cell)+1).

    Coordenadas fora da grade são recortadas para dentro dela. (525, 310) → "K7".
    """
    c = int(math.floor(float(x) / cell))
    r = int(math.floor(float(y) / cell)) + 1
    c = min(max(c, 0), len(cols) - 1)
    r = min(max(r, 1), rows)
    return f"{cols[c]}{r}"


def grid_center(label: str, cell: float = 50, cols: str = "ABCDEFGHIJKLMNOPQRSTUVWX") -> tuple[float, float]:
    """Centro (x, y) da quadrícula 'K7' → (525.0, 325.0)."""
    m = _LABEL_RE.match(label or "")
    if not m:
        raise ValueError(f"Quadrícula inválida: {label!r} (use algo como 'K7')")
    letter, number = m.group(1).upper(), int(m.group(2))
    c = cols.find(letter)
    if c < 0 or number < 1:
        raise ValueError(f"Quadrícula inválida: {label!r}")
    return ((c + 0.5) * cell, (number - 0.5) * cell)


def point_in_polygon(pt, polygon) -> bool:
    """Teste de raio (ray casting). Polígono é anel fechado implícito."""
    x, y = float(pt[0]), float(pt[1])
    poly = np.asarray(polygon, dtype=float)
    if poly.ndim != 2 or poly.shape[0] < 3 or poly.shape[1] != 2:
        raise ValueError("O polígono precisa de ao menos 3 vértices [x, y]")
    inside = False
    n = poly.shape[0]
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def random_point_in_polygon(polygon, rng: np.random.Generator, max_tries: int = 10000) -> tuple[float, float]:
    """Ponto uniforme dentro do polígono (rejeição sobre a caixa envolvente)."""
    poly = np.asarray(polygon, dtype=float)
    if poly.ndim != 2 or poly.shape[0] < 3 or poly.shape[1] != 2:
        raise ValueError("O polígono precisa de ao menos 3 vértices [x, y]")
    (xmin, ymin), (xmax, ymax) = poly.min(axis=0), poly.max(axis=0)
    for _ in range(max_tries):
        x = rng.uniform(xmin, xmax)
        y = rng.uniform(ymin, ymax)
        if point_in_polygon((x, y), poly):
            return (float(x), float(y))
    raise ValueError("Não foi possível sortear ponto dentro do polígono")


def station_readings(target, stations, rng: np.random.Generator, noise: float = 8.0) -> list[float]:
    """Distância de cada estação ao alvo, com ruído gaussiano (desvio `noise`), sem valores negativos."""
    tx, ty = float(target[0]), float(target[1])
    out = []
    for s in stations:
        d = math.hypot(tx - float(s[0]), ty - float(s[1]))
        d += float(rng.normal(0.0, noise))
        out.append(max(0.0, d))
    return out


def trilaterate(stations, distances) -> tuple[float, float]:
    """Posição (x, y) a partir de ≥ 3 estações e distâncias, por mínimos quadrados.

    Subtrai a 1ª equação de cada outra:
        2(xi−x1)·x + 2(yi−y1)·y = r1² − ri² + xi² − x1² + yi² − y1²
    """
    S = np.asarray(stations, dtype=float)
    r = np.asarray(distances, dtype=float).reshape(-1)
    if S.ndim != 2 or S.shape[1] != 2:
        raise ValueError("Cada estação deve ser [x, y]")
    if S.shape[0] < 3:
        raise ValueError("São necessárias pelo menos 3 estações de escuta")
    if r.size != S.shape[0]:
        raise ValueError("Há que informar uma distância para cada estação")
    if not np.all(np.isfinite(S)) or not np.all(np.isfinite(r)):
        raise ValueError("Coordenadas e distâncias devem ser finitas")
    x1, y1 = S[0]
    r1 = r[0]
    A = 2.0 * (S[1:] - S[0])
    b = (r1 ** 2 - r[1:] ** 2
         + (S[1:, 0] ** 2 - x1 ** 2)
         + (S[1:, 1] ** 2 - y1 ** 2))
    if np.linalg.matrix_rank(A) < 2:
        raise ValueError("Estações colineares: a triangulação não tem solução única")
    sol, _ = linalg.lstsq(A, b)
    return float(sol[0]), float(sol[1])
