"""Mesa de Cálculo (sem login): POST /api/tools/{tool}.

Cada ferramenta recebe um objeto JSON e devolve JSON. Entradas inválidas → 400 com `detail`
em português. Ferramenta desconhecida → 404.
"""

from __future__ import annotations

import csv
import io
import math
import unicodedata
from typing import Any, Callable

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from app.engine import cipher as _cipher
from app.engine import combat, economy, geo, linalg, morale, weather

router = APIRouter(prefix="/api/tools", tags=["tools"])

MATRIX_OPS = ("det", "inv", "solve", "lstsq", "eig", "pow", "mul", "transpose", "stationary")
MAX_STEPS = 2000


# ---------------------------------------------------------------- conversão de entrada

def _need(body: dict, key: str) -> Any:
    if body.get(key) is None:
        raise ValueError(f"Campo obrigatório ausente: '{key}'")
    return body[key]


def _num(v: Any, name: str) -> float:
    if isinstance(v, bool):
        raise ValueError(f"'{name}' deve ser numérico")
    if isinstance(v, str):
        s = v.strip()
        if "." not in s:
            s = s.replace(",", ".")  # aceita decimal com vírgula
        v = s
    try:
        f = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{name}' deve ser numérico (valor recebido: {v!r})") from exc
    if not math.isfinite(f):
        raise ValueError(f"'{name}' deve ser um número finito")
    return f


def _int(v: Any, name: str) -> int:
    if isinstance(v, bool):
        raise ValueError(f"'{name}' deve ser um inteiro")
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-+").isdigit():
        return int(v.strip())
    raise ValueError(f"'{name}' deve ser um inteiro")


def _text(v: Any, name: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"'{name}' deve ser um texto")
    return v


def _vector(v: Any, name: str) -> list[float]:
    if not isinstance(v, list) or not v:
        raise ValueError(f"'{name}' deve ser uma lista de números")
    return [_num(x, name) for x in v]


def _matrix(v: Any, name: str) -> list[list[float]]:
    if not isinstance(v, list) or not v or not all(isinstance(r, list) for r in v):
        raise ValueError(f"'{name}' deve ser uma matriz (lista de linhas)")
    width = len(v[0])
    if width == 0 or any(len(r) != width for r in v):
        raise ValueError(f"As linhas de '{name}' têm tamanhos diferentes ou estão vazias")
    return [[_num(x, name) for x in r] for r in v]


def _int_matrix(v: Any, name: str) -> list[list[int]]:
    M = _matrix(v, name)
    out = []
    for row in M:
        if any(not float(x).is_integer() for x in row):
            raise ValueError(f"A chave deve conter apenas inteiros ('{name}')")
        out.append([int(x) for x in row])
    return out


_STATE_INDEX = {name: i for i, name in enumerate(weather.STATES)}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _state_index(v: Any, n: int = 3) -> int:
    """Aceita índice (0..n-1), número em texto, ou nome de estado (limpo/chuva/tempestade)."""
    if isinstance(v, str) and not v.strip().lstrip("-+").isdigit():
        key = _strip_accents(v.strip().lower())
        if key not in _STATE_INDEX:
            raise ValueError(
                f"Estado desconhecido: {v!r}. Use limpo, chuva ou tempestade (ou 0, 1, 2)."
            )
        idx = _STATE_INDEX[key]
    else:
        idx = _int(v, "estado")
    if not 0 <= idx < n:
        raise ValueError(f"Estado fora do intervalo: {idx} (use 0 a {n - 1})")
    return idx


ID_COLUMNS = {"obs", "id", "observacao", "observação", "linha", "provincia", "província"}


def _parse_csv(text: str) -> tuple[list[dict], list[str]]:
    text = text.lstrip(chr(0xFEFF))  # CSV baixado do jogo vem com BOM UTF-8
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError("O CSV precisa de cabeçalho e ao menos uma linha de dados")
    sep = ";" if ";" in lines[0] else ","
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=sep)
    header = [h.strip() for h in next(reader)]
    if len(set(header)) != len(header) or any(not h for h in header):
        raise ValueError("Cabeçalho do CSV vazio ou com nomes repetidos")
    rows: list[dict] = []
    for parts in reader:
        if len(parts) != len(header):
            raise ValueError(
                f"Linha {reader.line_num} do CSV tem {len(parts)} colunas; o cabeçalho tem {len(header)}"
            )
        rows.append({h: p.strip() for h, p in zip(header, parts)})
    return rows, header


# ---------------------------------------------------------------- saída JSON

def _round(f: float) -> float | None:
    if not math.isfinite(f):
        return None
    r = round(f, 6)
    return 0.0 if r == 0 else r


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (complex, np.complexfloating)):
        return [_round(float(obj.real)), _round(float(obj.imag))]
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return _round(float(obj))
    if obj is None or isinstance(obj, str):
        return obj
    raise TypeError(f"Tipo não serializável: {type(obj).__name__}")


# ---------------------------------------------------------------- ferramentas

def _tool_matrix(body: dict) -> dict:
    op = body.get("op")
    if op not in MATRIX_OPS:
        raise ValueError(f"Operação desconhecida: {op!r}. Use uma de: {', '.join(MATRIX_OPS)}")
    A = _matrix(_need(body, "A"), "A")
    if op == "det":
        return {"result": linalg.det(A)}
    if op == "inv":
        return {"result": linalg.inv(A)}
    if op == "solve":
        return {"result": linalg.solve(A, _vector(_need(body, "b"), "b"))}
    if op == "lstsq":
        x, rss = linalg.lstsq(A, _vector(_need(body, "b"), "b"))
        return {"result": x, "residuo_quadratico": rss}
    if op == "eig":
        values, vectors = linalg.eig(A)
        return {"result": values, "vectors": vectors}
    if op == "pow":
        return {"result": linalg.mat_pow(A, _int(_need(body, "k"), "k"))}
    if op == "mul":
        return {"result": linalg.matmul(A, _matrix(_need(body, "B"), "B"))}
    if op == "transpose":
        return {"result": np.array(A, dtype=float).T}
    # stationary
    return {"result": linalg.stationary(A)}


def _tool_modinv(body: dict) -> dict:
    m = _int(body.get("m", 37), "m")
    K = _need(body, "K")
    if isinstance(K, list):
        return {"result": linalg.mod_inv_matrix(_int_matrix(K, "K"), m)}
    return {"result": linalg.mod_inv_int(_int(K, "K"), m)}


def _tool_hill_recover(body: dict) -> dict:
    plain = _text(_need(body, "plain"), "plain")
    cipher = _text(_need(body, "cipher"), "cipher")
    n = _int(body.get("n", 2), "n")
    return {"key": _cipher.recover_key(plain, cipher, n)}


def _tool_hill_decrypt(body: dict) -> dict:
    cipher = _text(_need(body, "cipher"), "cipher")
    key = _int_matrix(_need(body, "key"), "key")
    return {"plain": _cipher.decrypt(cipher, key)}


def _tool_hill_encrypt(body: dict) -> dict:
    plain = _text(_need(body, "plain"), "plain")
    key = _int_matrix(_need(body, "key"), "key")
    return {"cipher": _cipher.encrypt(plain, key)}


def _tool_leontief(body: dict) -> dict:
    out: dict = {}
    Z = body.get("Z")
    X = body.get("X")
    A = body.get("A")
    d = body.get("d")
    x = body.get("x")
    L = body.get("L")

    A_mat = None
    if A is not None:
        A_mat = _matrix(A, "A")
    elif Z is not None and X is not None:
        A_mat = economy.A_from_transactions(_matrix(Z, "Z"), _vector(X, "X"))
        out["A"] = A_mat

    if A_mat is not None and d is not None:
        out["x_required"] = economy.required_production(A_mat, _vector(d, "d"))
    if A_mat is not None and x is not None:
        out["net"] = economy.net_output(A_mat, _vector(x, "x"))
    if L is not None and x is not None:
        out["labor"] = economy.labor_used(_vector(L, "L"), _vector(x, "x"))
    if not out:
        raise ValueError(
            "Nada a calcular com estes campos. Informe (Z e X), (A e d), (A e x) ou (L e x)."
        )
    return out


def _tool_markov(body: dict) -> dict:
    out: dict = {}
    P_est = None
    seq_in = body.get("sequence")
    if seq_in is not None:
        if not isinstance(seq_in, list):
            raise ValueError("'sequence' deve ser uma lista de estados")
        seq = [_state_index(s) for s in seq_in]
        if len(seq) < 2:
            raise ValueError("A sequência precisa de pelo menos 2 observações")
        P_est = weather.estimate_P(seq, len(weather.STATES))
        out["P_estimated"] = P_est

    P_use = P_est
    if body.get("P") is not None:
        P_mat = np.array(_matrix(body["P"], "P"), dtype=float)
        if P_mat.shape[0] != P_mat.shape[1]:
            raise ValueError("A matriz não é quadrada: P deve ser n×n")
        if np.any(P_mat < 0) or not np.allclose(P_mat.sum(axis=1), 1.0, atol=1e-6):
            raise ValueError("P não é estocástica por linhas (entradas ≥ 0 e cada linha soma 1)")
        P_use = P_mat

    if P_use is not None:
        n = P_use.shape[0]
        if body.get("state") is not None:
            state = _state_index(body["state"], n)
            k = _int(body.get("k", 1), "k")
            if k < 0:
                raise ValueError("'k' deve ser ≥ 0")
            out["forecast"] = weather.forecast(P_use, state, k)
        try:
            out["stationary"] = linalg.stationary(P_use)
        except ValueError:
            out["stationary"] = None  # cadeia sem distribuição estacionária única

    if not out:
        raise ValueError("Informe 'sequence' (observações do clima) ou 'P' (matriz de transição)")
    return out


def _tool_trilaterate(body: dict) -> dict:
    st_in = _need(body, "stations")
    if not isinstance(st_in, list):
        raise ValueError("'stations' deve ser uma lista de pares [x, y]")
    stations = []
    for s in st_in:
        if not isinstance(s, list) or len(s) != 2:
            raise ValueError("Cada estação deve ser um par [x, y]")
        stations.append([_num(s[0], "stations"), _num(s[1], "stations")])
    distances = _vector(_need(body, "distances"), "distances")
    x, y = geo.trilaterate(stations, distances)
    return {"x": x, "y": y, "grid": geo.grid_label(x, y)}


def _r2(rows: list[dict], betas: np.ndarray, features: list[str], target: str) -> float:
    X = np.array([[1.0] + [r[f] for f in features] for r in rows], dtype=float)
    y = np.array([r[target] for r in rows], dtype=float)
    ss_res = float(np.sum((y - X @ betas) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    if ss_tot == 0:
        return 1.0 if ss_res < 1e-12 else 0.0
    return 1.0 - ss_res / ss_tot


def _tool_regression(body: dict) -> dict:
    target = _text(_need(body, "target"), "target")
    feats_in = body.get("features")
    if body.get("rows") is not None:
        raw = body["rows"]
        if not isinstance(raw, list) or not raw or not all(isinstance(r, dict) for r in raw):
            raise ValueError("'rows' deve ser uma lista de objetos (um por observação)")
        columns = list(raw[0].keys())
        records = raw
    elif body.get("csv") is not None:
        records, columns = _parse_csv(_text(body["csv"], "csv"))
    else:
        raise ValueError("Informe 'rows' (lista de objetos) ou 'csv' (texto com cabeçalho)")

    if feats_in is None:
        # colunas de identificação (ex.: "obs") não são variáveis explicativas
        features = [c for c in columns if c != target and c.lower() not in ID_COLUMNS]
    else:
        if not isinstance(feats_in, list) or not all(isinstance(f, str) for f in feats_in):
            raise ValueError("'features' deve ser uma lista de nomes de colunas")
        features = list(feats_in)
    if not features:
        raise ValueError("Nenhuma variável explicativa informada")
    if target in features:
        raise ValueError("A variável alvo não pode estar entre as explicativas")

    needed = features + [target]
    for name in needed:
        if not all(name in r for r in records):
            raise ValueError(f"Coluna '{name}' não encontrada nos dados")
    rows = [{k: _num(r[k], k) for k in needed} for r in records]

    betas = morale.ols(rows, features, target)
    names = ["intercepto"] + features
    return {
        "coefficients": {nm: float(b) for nm, b in zip(names, betas)},
        "r2": _r2(rows, betas, features, target),
    }


def _tool_lanchester(body: dict) -> dict:
    A0 = _num(_need(body, "A0"), "A0")
    B0 = _num(_need(body, "B0"), "B0")
    alpha = _num(_need(body, "alpha"), "alpha")
    beta = _num(_need(body, "beta"), "beta")
    T = _num(body.get("T", 0.9), "T")
    steps = _int(body.get("steps", 60), "steps")
    if not 2 <= steps <= MAX_STEPS:
        raise ValueError(f"'steps' deve estar entre 2 e {MAX_STEPS}")
    return combat.lanchester(A0, B0, alpha, beta, T=T, steps=steps)


_HANDLERS: dict[str, Callable[[dict], dict]] = {
    "matrix": _tool_matrix,
    "modinv": _tool_modinv,
    "hill_recover": _tool_hill_recover,
    "hill_decrypt": _tool_hill_decrypt,
    "hill_encrypt": _tool_hill_encrypt,
    "leontief": _tool_leontief,
    "markov": _tool_markov,
    "trilaterate": _tool_trilaterate,
    "regression": _tool_regression,
    "lanchester": _tool_lanchester,
}


def _error_message(exc: Exception) -> str:
    if isinstance(exc, np.linalg.LinAlgError):
        return "Matriz singular ou mal condicionada: a operação não tem resultado único"
    if isinstance(exc, ValueError):
        return str(exc)
    return "Entrada inválida: confira os campos da ferramenta"


@router.post("/{tool}")
async def run_tool(tool: str, request: Request) -> dict:
    handler = _HANDLERS.get(tool)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"Ferramenta desconhecida: '{tool}'")
    try:
        body = await request.json()
    except Exception:  # corpo ausente ou não é JSON
        raise HTTPException(status_code=400, detail="O corpo da requisição deve ser JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="O corpo da requisição deve ser um objeto JSON")
    try:
        result = handler(body)
        return _jsonable(result)
    except (ValueError, np.linalg.LinAlgError, ArithmeticError, TypeError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=_error_message(exc))
