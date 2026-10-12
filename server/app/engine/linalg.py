"""Álgebra linear sobre reais e inteiros módulo m. Só NumPy."""

from __future__ import annotations

import numpy as np

_TOL = 1e-9


def _as_matrix(A, name: str = "A") -> np.ndarray:
    try:
        M = np.array(A, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: entradas devem ser numéricas") from exc
    if M.ndim == 1:
        M = M.reshape(-1, 1) if M.size else M.reshape(0, 0)
    if M.ndim != 2 or M.size == 0:
        raise ValueError(f"{name}: a matriz não pode ser vazia")
    if not np.all(np.isfinite(M)):
        raise ValueError(f"{name}: entradas devem ser finitas")
    return M


def _as_square(A, name: str = "A") -> np.ndarray:
    M = _as_matrix(A, name)
    if M.shape[0] != M.shape[1]:
        raise ValueError(f"A matriz não é quadrada ({name} é {M.shape[0]}×{M.shape[1]})")
    return M


def _as_vector(b, name: str = "b") -> np.ndarray:
    try:
        v = np.array(b, dtype=float).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: entradas devem ser numéricas") from exc
    if v.size == 0 or not np.all(np.isfinite(v)):
        raise ValueError(f"{name}: vetor vazio ou com valores não finitos")
    return v


def det(A) -> float:
    M = _as_square(A)
    return float(np.linalg.det(M))


def inv(A) -> np.ndarray:
    M = _as_square(A)
    if abs(np.linalg.det(M)) < _TOL:
        raise ValueError("Matriz singular: não possui inversa")
    return np.linalg.inv(M)


def solve(A, b) -> np.ndarray:
    M = _as_square(A)
    v = _as_vector(b)
    if v.shape[0] != M.shape[0]:
        raise ValueError(
            f"Dimensões incompatíveis: A é {M.shape[0]}×{M.shape[0]} e b tem {v.shape[0]} entradas"
        )
    if abs(np.linalg.det(M)) < _TOL:
        raise ValueError("Matriz singular: o sistema não tem solução única")
    return np.linalg.solve(M, v)


def lstsq(A, b) -> tuple[np.ndarray, float]:
    """Mínimos quadrados: retorna (x, soma dos resíduos²)."""
    M = _as_matrix(A)
    v = _as_vector(b)
    if v.shape[0] != M.shape[0]:
        raise ValueError(
            f"Dimensões incompatíveis: A tem {M.shape[0]} linhas e b tem {v.shape[0]} entradas"
        )
    x = np.linalg.lstsq(M, v, rcond=None)[0]
    rss = float(np.sum((M @ x - v) ** 2))
    return x, rss


def eig(A) -> tuple[list, np.ndarray]:
    """Autovalores (floats se reais, complexos caso contrário) e autovetores (colunas)."""
    M = _as_square(A)
    vals, vecs = np.linalg.eig(M)
    if np.all(np.abs(np.imag(vals)) < _TOL):
        values: list = [float(np.real(v)) for v in vals]
    else:
        values = [complex(v) for v in vals]
    return values, vecs


def mat_pow(A, k: int) -> np.ndarray:
    M = _as_square(A)
    if int(k) != k:
        raise ValueError("O expoente k deve ser inteiro")
    k = int(k)
    if k >= 0:
        return np.linalg.matrix_power(M, k)
    if abs(np.linalg.det(M)) < _TOL:
        raise ValueError("Matriz singular: potência negativa não existe")
    return np.linalg.matrix_power(np.linalg.inv(M), -k)


def stationary(P) -> np.ndarray:
    """Vetor estacionário π (soma 1) com π·P = π, para P estocástica por linhas."""
    M = _as_square(P, "P")
    if np.any(M < -_TOL) or not np.allclose(M.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("A matriz não é estocástica por linhas (entradas ≥ 0 e linhas somam 1)")
    n = M.shape[0]
    S = M.T - np.eye(n)
    S[-1, :] = 1.0
    rhs = np.zeros(n)
    rhs[-1] = 1.0
    try:
        pi = np.linalg.solve(S, rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError("A cadeia não tem distribuição estacionária única") from exc
    pi = np.where(np.abs(pi) < _TOL, 0.0, pi)
    if np.any(pi < -1e-6):
        raise ValueError("A cadeia não tem distribuição estacionária válida")
    pi = np.clip(pi, 0.0, None)
    return pi / pi.sum()


def matmul(A, B) -> np.ndarray:
    MA = _as_matrix(A, "A")
    MB = _as_matrix(B, "B")
    if MA.shape[1] != MB.shape[0]:
        raise ValueError(
            f"Dimensões incompatíveis para multiplicação: {MA.shape[0]}×{MA.shape[1]} · "
            f"{MB.shape[0]}×{MB.shape[1]}"
        )
    return MA @ MB


def mod_inv_int(a: int, m: int) -> int:
    """Inverso de `a` módulo `m`. ValueError se mdc(a, m) ≠ 1."""
    if m < 2:
        raise ValueError("O módulo deve ser ≥ 2")
    a_mod = int(a) % m
    try:
        return pow(a_mod, -1, m)
    except ValueError as exc:
        raise ValueError(f"{a} não é invertível módulo {m}") from exc


def _int_det(M: list[list[int]]) -> int:
    """Determinante exato com inteiros (expansão por cofatores; n pequeno)."""
    n = len(M)
    if n == 1:
        return M[0][0]
    if n == 2:
        return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    total = 0
    for j in range(n):
        minor = [row[:j] + row[j + 1:] for row in M[1:]]
        total += ((-1) ** j) * M[0][j] * _int_det(minor)
    return total


def mod_inv_matrix(K, m: int = 37) -> np.ndarray:
    """Inversa inteira de K módulo m: K⁻¹ = det(K)⁻¹ · adj(K) (mod m).

    Funciona para qualquer n pequeno (2x2, 3x3, ...). ValueError se det ≡ 0 mod m.
    """
    if m < 2:
        raise ValueError("O módulo deve ser ≥ 2")
    M = _as_square(K, "K")
    if not np.allclose(M, np.rint(M)):
        raise ValueError("A chave deve conter apenas inteiros")
    Ki = [[int(round(v)) for v in row] for row in M]
    n = len(Ki)
    d = _int_det(Ki) % m
    if d == 0:
        raise ValueError(f"Determinante ≡ 0 mod {m}: chave não invertível")
    d_inv = mod_inv_int(d, m)
    adj = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            minor = [row[:j] + row[j + 1:] for k, row in enumerate(Ki) if k != i]
            cof = ((-1) ** (i + j)) * _int_det(minor) if n > 1 else 1
            adj[j][i] = cof  # transposta dos cofatores = adjunta
    return np.array([[(d_inv * adj[i][j]) % m for j in range(n)] for i in range(n)], dtype=np.int64)
