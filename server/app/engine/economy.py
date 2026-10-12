"""Modelo de Leontief (entrada-produto) para a Intendência."""

from __future__ import annotations

import numpy as np

from app.engine import linalg

SECTORS = ["ALI", "ACO", "COM"]

_COL_SUM_MAX = 0.6        # somas de coluna de A_base ficam abaixo disso
_ENTRY_LO, _ENTRY_HI = 0.05, 0.30
_CLIP_LO, _CLIP_HI = 0.02, 0.45
_COL_SUM_CAP = 0.85       # colunas com soma ≥ 0.85 são reescaladas para 0.85


def random_A(rng: np.random.Generator) -> np.ndarray:
    """Matriz técnica 3×3 produtiva: entradas em [0.05, 0.30] e somas de coluna < 0.6.

    Colunas que violam a soma são reamostradas (rejeição), assim as entradas
    permanecem dentro do intervalo.
    """
    n = len(SECTORS)
    A = np.empty((n, n))
    for j in range(n):
        while True:
            col = rng.uniform(_ENTRY_LO, _ENTRY_HI, size=n)
            if col.sum() < _COL_SUM_MAX:
                break
        A[:, j] = col
    return A


def _rescale_columns(A: np.ndarray, cap: float, target: float) -> np.ndarray:
    A = A.copy()
    sums = A.sum(axis=0)
    for j in range(A.shape[1]):
        if sums[j] >= cap:
            A[:, j] *= target / sums[j]
    return A


def perturb_A(A, rng: np.random.Generator, scale: float = 0.02, damage: float = 0.0) -> np.ndarray:
    """Pequena variação de A (ruído normal), dano somado à diagonal e produtividade preservada."""
    B = np.array(A, dtype=float)
    if B.ndim != 2 or B.shape[0] != B.shape[1]:
        raise ValueError("A matriz técnica deve ser quadrada")
    B = B + rng.normal(0.0, scale, size=B.shape)
    B = np.clip(B, _CLIP_LO, _CLIP_HI)
    B[np.diag_indices_from(B)] += damage
    return _rescale_columns(B, _COL_SUM_CAP, _COL_SUM_CAP)


def transactions(A, x) -> np.ndarray:
    """Z = A·diag(x): fluxo intersetorial de insumos."""
    Am = np.array(A, dtype=float)
    xv = np.array(x, dtype=float).reshape(-1)
    if Am.shape != (xv.size, xv.size):
        raise ValueError("Dimensões incompatíveis: A deve ser n×n e x ter n entradas")
    return Am * xv[np.newaxis, :]


def A_from_transactions(Z, X) -> np.ndarray:
    """A = Z·diag(X)⁻¹: coeficientes técnicos a partir das transações e da produção total."""
    Zm = np.array(Z, dtype=float)
    Xv = np.array(X, dtype=float).reshape(-1)
    if Zm.shape != (Xv.size, Xv.size):
        raise ValueError("Dimensões incompatíveis: Z deve ser n×n e X ter n entradas")
    if np.any(Xv == 0):
        raise ValueError("Produção total X não pode ter zeros")
    return Zm / Xv[np.newaxis, :]


def net_output(A, x) -> np.ndarray:
    """Produção líquida y = (I − A)·x."""
    Am = np.array(A, dtype=float)
    xv = np.array(x, dtype=float).reshape(-1)
    if Am.shape != (xv.size, xv.size):
        raise ValueError("Dimensões incompatíveis: A deve ser n×n e x ter n entradas")
    return (np.eye(xv.size) - Am) @ xv


def required_production(A, d) -> np.ndarray:
    """Produção bruta x que atende à demanda final d: resolve (I − A)·x = d."""
    Am = np.array(A, dtype=float)
    dv = np.array(d, dtype=float).reshape(-1)
    if Am.shape != (dv.size, dv.size):
        raise ValueError("Dimensões incompatíveis: A deve ser n×n e d ter n entradas")
    return linalg.solve(np.eye(dv.size) - Am, dv)


def labor_used(L, x) -> float:
    """Mão de obra usada: L·x (L = coeficientes de mão de obra por unidade)."""
    Lv = np.array(L, dtype=float).reshape(-1)
    xv = np.array(x, dtype=float).reshape(-1)
    if Lv.size != xv.size:
        raise ValueError("Dimensões incompatíveis: L e x devem ter o mesmo número de setores")
    return float(Lv @ xv)
