"""Clima como cadeia de Markov oculta (estados: limpo, chuva, tempestade)."""

from __future__ import annotations

import numpy as np

STATES = ["limpo", "chuva", "tempestade"]


def random_transition_matrix(
    rng: np.random.Generator,
    n: int = 3,
    persistence: tuple = (0.45, 0.8),
) -> np.ndarray:
    """Matriz estocástica por linhas com diagonal sorteada em `persistence` (diagonal dominante)."""
    lo, hi = float(persistence[0]), float(persistence[1])
    if not 0 < lo <= hi < 1:
        raise ValueError("A persistência deve estar em (0, 1) com lo ≤ hi")
    if n < 2:
        raise ValueError("A cadeia precisa de pelo menos 2 estados")
    P = np.zeros((n, n))
    for i in range(n):
        d = rng.uniform(lo, hi)
        off_mass = 1.0 - d
        off = np.full(n - 1, off_mass / (n - 1))  # fallback: distribuição uniforme
        for _ in range(100):
            cand = off_mass * rng.dirichlet(np.ones(n - 1))
            if cand.max() < d:
                off = cand
                break
        row = np.insert(off, i, d)
        P[i] = row
    return P


def simulate(P, start: int, steps: int, rng: np.random.Generator) -> list[int]:
    """Simula `steps` transições a partir de `start`; retorna os estados seguintes (sem `start`)."""
    M = np.asarray(P, dtype=float)
    n = M.shape[0]
    if M.shape != (n, n):
        raise ValueError("P deve ser quadrada")
    if not 0 <= start < n:
        raise ValueError("Estado inicial fora do intervalo")
    cum = np.cumsum(M, axis=1)
    out: list[int] = []
    state = int(start)
    for _ in range(int(steps)):
        u = rng.random()
        state = int(min(np.searchsorted(cum[state], u, side="right"), n - 1))
        out.append(state)
    return out


def estimate_P(seq: list[int], n: int = 3) -> np.ndarray:
    """Estima P por contagem de transições consecutivas; linhas sem dados viram uniformes."""
    counts = np.zeros((n, n))
    values = [int(s) for s in seq]
    for s in values:
        if not 0 <= s < n:
            raise ValueError("Estado fora do intervalo na sequência")
    for a, b in zip(values[:-1], values[1:]):
        counts[a, b] += 1
    P = np.empty((n, n))
    for i in range(n):
        total = counts[i].sum()
        P[i] = counts[i] / total if total > 0 else 1.0 / n
    return P


def forecast(P, state: int, k: int = 1) -> np.ndarray:
    """Distribuição após k passos a partir de `state`: linha `state` de P^k."""
    M = np.asarray(P, dtype=float)
    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise ValueError("P deve ser quadrada")
    if not 0 <= state < M.shape[0]:
        raise ValueError("Estado fora do intervalo")
    if k < 0:
        raise ValueError("k deve ser ≥ 0")
    return np.linalg.matrix_power(M, int(k))[int(state)]
