"""Combate: eficácia (moral, terreno, clima) e lei quadrática de Lanchester."""

from __future__ import annotations

import math

TERRAIN_DEFENSE = {"planicie": 1.0, "floresta": 1.25, "montanha": 1.5, "pantano": 1.2, "urbano": 1.3}
WEATHER_ATTACK = {0: 1.0, 1: 0.85, 2: 0.65}


def effectiveness(
    morale: float,
    terrain: str | None = None,
    weather: int | None = None,
    role: str = "attack",
) -> float:
    """Eficácia de combate: (0.5 + moral/100), × terreno (defensor) ou × clima (atacante)."""
    if not 0 <= morale <= 100:
        raise ValueError("A moral deve estar entre 0 e 100")
    base = 0.5 + morale / 100.0
    if role == "defense":
        if terrain is not None:
            if terrain not in TERRAIN_DEFENSE:
                raise ValueError(f"Terreno desconhecido: {terrain!r}")
            base *= TERRAIN_DEFENSE[terrain]
    elif role == "attack":
        if weather is not None:
            if weather not in WEATHER_ATTACK:
                raise ValueError(f"Clima desconhecido: {weather!r} (use 0, 1 ou 2)")
            base *= WEATHER_ATTACK[weather]
    else:
        raise ValueError("O papel deve ser 'attack' ou 'defense'")
    return base


def _zero_time(x: float, w: float) -> float:
    """Instante em que um lado zera, dado x = tanh(wt*) (math.inf se nunca zera)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return math.inf
    return math.atanh(x) / w


def lanchester(
    A0: float,
    B0: float,
    alpha: float,
    beta: float,
    T: float = 0.9,
    steps: int = 60,
) -> dict:
    """Lei quadrática de Lanchester: A' = −β·B, B' = −α·A (alpha = atacante A, beta = defensor B).

    Solução fechada, w = sqrt(αβ):
        A(t) = A0·cosh(wt) − sqrt(β/α)·B0·sinh(wt)
        B(t) = B0·cosh(wt) − sqrt(α/β)·A0·sinh(wt)
    Para no primeiro instante em que um lado zera, ou em T. Valores finais nunca são negativos.
    Com A0, B0, α, β > 0 no máximo um lado zera (as duas condições são mutuamente exclusivas);
    se ambos começam em zero, o resultado é "none" com t_end = 0.
    """
    if A0 < 0 or B0 < 0:
        raise ValueError("As forças iniciais não podem ser negativas")
    if alpha <= 0 or beta <= 0:
        raise ValueError("As eficácias alpha e beta devem ser positivas")
    if T < 0:
        raise ValueError("O tempo T não pode ser negativo")
    if steps < 2:
        raise ValueError("steps deve ser ≥ 2")

    w = math.sqrt(alpha * beta)
    if A0 <= 0 and B0 <= 0:
        return {"a_final": 0.0, "b_final": 0.0, "t_end": 0.0, "winner": "none",
                "trajectory": [[0.0, 0.0, 0.0] for _ in range(steps)]}
    # B zera quando tanh(wt) = B0 / (sqrt(α/β)·A0); A zera quando tanh(wt) = A0 / (sqrt(β/α)·B0)
    t_B = 0.0 if B0 <= 0 else (math.inf if A0 <= 0 else _zero_time(B0 / (math.sqrt(alpha / beta) * A0), w))
    t_A = 0.0 if A0 <= 0 else (math.inf if B0 <= 0 else _zero_time(A0 / (math.sqrt(beta / alpha) * B0), w))

    if t_B <= T and t_B <= t_A:
        winner, t_end = "attacker", t_B
    elif t_A <= T and t_A < t_B:
        winner, t_end = "defender", t_A
    else:
        winner, t_end = "none", T

    def state_at(t: float) -> tuple[float, float]:
        if t_end == 0.0:
            return A0, B0
        ch, sh = math.cosh(w * t), math.sinh(w * t)
        a = A0 * ch - math.sqrt(beta / alpha) * B0 * sh
        b = B0 * ch - math.sqrt(alpha / beta) * A0 * sh
        return a, b

    a_final, b_final = state_at(t_end)
    if winner == "attacker":
        b_final = 0.0
    elif winner == "defender":
        a_final = 0.0
    a_final = max(0.0, a_final)
    b_final = max(0.0, b_final)

    trajectory = []
    for i in range(steps):
        t = t_end * i / (steps - 1)
        if i == steps - 1:
            a, b = a_final, b_final
        else:
            a, b = state_at(t)
        trajectory.append([t, max(0.0, a), max(0.0, b)])

    return {
        "a_final": a_final,
        "b_final": b_final,
        "t_end": t_end,
        "winner": winner,
        "trajectory": trajectory,
    }
