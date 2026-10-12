"""Moral: modelo linear oculto (Δmoral) e regressão por equações normais."""

from __future__ import annotations

import numpy as np

FEATURES = ["racao", "propaganda", "horas_extra", "baixas", "saldo_territorial"]
# Ordem de β: [β0 (intercepto), β_racao, β_propaganda, β_horas, β_baixas, β_saldo]


def random_betas(rng: np.random.Generator) -> np.ndarray:
    """Coeficientes culturais de uma nação, com os sinais do design."""
    b0 = rng.uniform(1.0, 3.0)
    b_racao = rng.uniform(-4.0, -2.0)
    b_prop = rng.uniform(0.8, 2.0)
    b_horas = rng.uniform(-1.2, -0.5)
    b_baixas = rng.uniform(-3.0, -1.5)
    b_saldo = rng.uniform(1.5, 3.5)
    return np.array([b0, b_racao, b_prop, b_horas, b_baixas, b_saldo])


def survey(betas, rng: np.random.Generator, n: int = 25, noise: float = 1.5) -> list[dict]:
    """Pesquisa de opinião: `n` observações com FEATURES e delta_moral = X·β + ruído."""
    B = np.asarray(betas, dtype=float).reshape(-1)
    if B.size != len(FEATURES) + 1:
        raise ValueError(f"betas deve ter {len(FEATURES) + 1} valores (β0 + {len(FEATURES)} fatores)")
    rows: list[dict] = []
    for _ in range(int(n)):
        racao = int(rng.integers(0, 3))            # 0, 1, 2
        propaganda = int(rng.integers(0, 6))       # 0..5
        horas_extra = int(rng.choice([0, 2, 4]))   # horas acima de 8
        baixas = round(float(rng.uniform(0.0, 3.0)), 2)  # em dezenas de batalhões
        saldo = int(rng.integers(-2, 3))           # −2..2
        x = np.array([1.0, racao, propaganda, horas_extra, baixas, saldo])
        delta = float(x @ B + rng.normal(0.0, noise))
        rows.append({
            "racao": racao,
            "propaganda": propaganda,
            "horas_extra": horas_extra,
            "baixas": baixas,
            "saldo_territorial": saldo,
            "delta_moral": round(delta, 2),
        })
    return rows


def ols(rows, features=FEATURES, target: str = "delta_moral") -> np.ndarray:
    """Estimativa [β0..βk] por equações normais: (XᵀX) β = Xᵀy, com intercepto."""
    features = list(features)
    if not rows:
        raise ValueError("Não há observações para a regressão")
    try:
        X = np.array([[1.0] + [float(r[f]) for f in features] for r in rows], dtype=float)
        y = np.array([float(r[target]) for r in rows], dtype=float)
    except KeyError as exc:
        raise ValueError(f"Campo ausente nas observações: {exc.args[0]!r}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("Todas as observações devem ter valores numéricos") from exc
    if X.shape[0] <= X.shape[1]:
        raise ValueError("São necessárias mais observações do que variáveis")
    XtX = X.T @ X
    Xty = X.T @ y
    try:
        return np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Equações normais singulares: variáveis colineares ou constantes") from exc


def delta_morale(betas, feats: dict, rng: np.random.Generator | None = None, noise: float = 1.0) -> float:
    """Δmoral previsto para as variáveis `feats`; com `rng`, soma ruído normal(0, noise)."""
    B = np.asarray(betas, dtype=float).reshape(-1)
    if B.size != len(FEATURES) + 1:
        raise ValueError(f"betas deve ter {len(FEATURES) + 1} valores")
    try:
        x = np.array([1.0] + [float(feats[f]) for f in FEATURES], dtype=float)
    except KeyError as exc:
        raise ValueError(f"Variável ausente: {exc.args[0]!r}") from exc
    value = float(x @ B)
    if rng is not None:
        value += float(rng.normal(0.0, noise))
    return value
