"""Testes HTTP da Mesa de Cálculo: POST /api/tools/{tool}."""

import math

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine import cipher, geo
from app.routes_tools import router


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def post(client, tool, body):
    return client.post(f"/api/tools/{tool}", json=body)


def ok(client, tool, body):
    r = post(client, tool, body)
    assert r.status_code == 200, r.text
    return r.json()


def bad(client, tool, body, fragment=None):
    r = post(client, tool, body)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, str) and detail
    if fragment is not None:
        assert fragment in detail, detail
    return detail


# ---------------------------------------------------------------- roteamento

def test_unknown_tool_is_404(client):
    r = post(client, "magia", {})
    assert r.status_code == 404


def test_body_must_be_json_object(client):
    r = client.post("/api/tools/matrix", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert "JSON" in r.json()["detail"]
    r = client.post("/api/tools/matrix", json=[1, 2, 3])
    assert r.status_code == 400
    assert "objeto JSON" in r.json()["detail"]


# ---------------------------------------------------------------- matrix

def test_matrix_det_and_inv(client):
    assert ok(client, "matrix", {"op": "det", "A": [[1, 2], [3, 4]]})["result"] == pytest.approx(-2.0)
    inv = ok(client, "matrix", {"op": "inv", "A": [[1, 2], [3, 4]]})["result"]
    assert np.allclose(inv, [[-2.0, 1.0], [1.5, -0.5]])


def test_matrix_rounds_to_six_decimals(client):
    res = ok(client, "matrix", {"op": "pow", "A": [[3]], "k": -1})["result"]
    assert res == [[0.333333]]


def test_matrix_non_square_det_is_400(client):
    bad(client, "matrix", {"op": "det", "A": [[1, 2, 3], [4, 5, 6]]}, "A matriz não é quadrada")


def test_matrix_singular_inv_is_400(client):
    bad(client, "matrix", {"op": "inv", "A": [[1, 2], [2, 4]]}, "singular")


def test_matrix_solve_and_lstsq(client):
    x = ok(client, "matrix", {"op": "solve", "A": [[2, 1], [1, 3]], "b": [3, 5]})["result"]
    assert x == pytest.approx([0.8, 1.4])
    out = ok(client, "matrix", {"op": "lstsq", "A": [[1, 0], [1, 1], [1, 2]], "b": [1, 3, 5]})
    assert out["result"] == pytest.approx([1.0, 2.0])
    assert out["residuo_quadratico"] == pytest.approx(0.0, abs=1e-9)
    bad(client, "matrix", {"op": "solve", "A": [[1, 2], [2, 4]], "b": [1, 1]}, "singular")
    bad(client, "matrix", {"op": "solve", "A": [[2, 1], [1, 3]]}, "Campo obrigatório ausente: 'b'")


def test_matrix_eig_real_and_complex_as_pairs(client):
    out = ok(client, "matrix", {"op": "eig", "A": [[2, 0], [0, 3]]})
    assert sorted(out["result"]) == pytest.approx([2.0, 3.0])
    out = ok(client, "matrix", {"op": "eig", "A": [[0, -1], [1, 0]]})
    # autovalores complexos saem como [re, im]
    assert all(isinstance(v, list) and len(v) == 2 for v in out["result"])
    assert sorted(v[1] for v in out["result"]) == pytest.approx([-1.0, 1.0])
    assert len(out["vectors"]) == 2 and all(isinstance(e, list) for row in out["vectors"] for e in row)


def test_matrix_pow_mul_transpose_stationary(client):
    assert ok(client, "matrix", {"op": "pow", "A": [[1, 1], [0, 1]], "k": 3})["result"] == [[1.0, 3.0], [0.0, 1.0]]
    assert ok(client, "matrix", {"op": "mul", "A": [[1, 2]], "B": [[3], [4]]})["result"] == [[11.0]]
    bad(client, "matrix", {"op": "mul", "A": [[1, 2]], "B": [[1, 2]]}, "Dimensões incompatíveis")
    assert ok(client, "matrix", {"op": "transpose", "A": [[1, 2, 3]]})["result"] == [[1.0], [2.0], [3.0]]
    pi = ok(client, "matrix", {"op": "stationary", "A": [[0.9, 0.1], [0.5, 0.5]]})["result"]
    assert pi == pytest.approx([0.833333, 0.166667], abs=1e-6)
    bad(client, "matrix", {"op": "stationary", "A": [[0.5, 0.4], [0.5, 0.5]]}, "estocástica")


def test_matrix_invalid_inputs_are_400(client):
    bad(client, "matrix", {"op": "soma", "A": [[1]]}, "Operação desconhecida")
    bad(client, "matrix", {"op": "det"}, "Campo obrigatório ausente: 'A'")
    bad(client, "matrix", {"op": "det", "A": [1, 2, 3]}, "deve ser uma matriz")
    bad(client, "matrix", {"op": "det", "A": [[1, 2], [3]]}, "tamanhos diferentes")
    bad(client, "matrix", {"op": "det", "A": [[1, "x"], [3, 4]]}, "numérico")
    bad(client, "matrix", {"op": "pow", "A": [[1, 1], [0, 1]], "k": 1.5}, "inteiro")


# ---------------------------------------------------------------- modinv

def test_modinv_scalar_and_matrix(client):
    assert ok(client, "modinv", {"K": 3})["result"] == 25
    assert ok(client, "modinv", {"K": 3, "m": 26})["result"] == 9
    inv = np.array(ok(client, "modinv", {"K": [[3, 3], [2, 5]], "m": 26})["result"])
    assert np.array_equal((np.array([[3, 3], [2, 5]]) @ inv) % 26, np.eye(2, dtype=int))


def test_modinv_errors(client):
    bad(client, "modinv", {"K": 2, "m": 4}, "não é invertível")
    bad(client, "modinv", {"K": [[1, 2], [2, 4]]}, "Determinante ≡ 0 mod 37: chave não invertível")
    bad(client, "modinv", {"K": [[1.5, 0], [0, 2]]}, "apenas inteiros")
    bad(client, "modinv", {}, "Campo obrigatório ausente: 'K'")


# ---------------------------------------------------------------- Hill

def test_hill_encrypt_decrypt_known_example(client):
    key = [[3, 3], [2, 5]]
    assert ok(client, "hill_encrypt", {"plain": "HI", "key": key}) == {"cipher": "IR"}
    assert ok(client, "hill_decrypt", {"cipher": "IR", "key": key})["plain"] == "HI"


def test_hill_encrypt_normalizes_accents(client):
    key = [[3, 3], [2, 5]]
    c = ok(client, "hill_encrypt", {"plain": "hi!", "key": key})["cipher"]
    assert c == cipher.encrypt("HI ", np.array(key))


def test_hill_decrypt_singular_key_is_400(client):
    bad(client, "hill_decrypt", {"cipher": "ABCD", "key": [[1, 2], [2, 4]]},
        "Determinante ≡ 0 mod 37: chave não invertível")


def test_hill_recover_roundtrip_urgente(client):
    rng = np.random.default_rng(2024)
    K = cipher.random_key(rng, 2)
    crib_cipher = cipher.encrypt("URGENTE ", K)
    out = ok(client, "hill_recover", {"plain": "URGENTE ", "cipher": crib_cipher, "n": 2})
    assert np.array_equal(np.array(out["key"]), K)
    # e a chave recuperada decifra mensagens reais
    msg = "AVANCAR PELA PONTE 7"
    c = ok(client, "hill_encrypt", {"plain": msg, "key": out["key"]})["cipher"]
    assert ok(client, "hill_decrypt", {"cipher": c, "key": out["key"]})["plain"].rstrip() == msg


def test_hill_recover_failure_is_400(client):
    bad(client, "hill_recover", {"plain": "URGENTE ", "cipher": "QWERTYUI"}, "Não foi possível recuperar")
    bad(client, "hill_recover", {"plain": "URGENTE ", "cipher": "ABC"}, "mesmo comprimento")
    bad(client, "hill_recover", {"plain": "URGENTE "}, "Campo obrigatório ausente: 'cipher'")


def test_hill_encrypt_requires_square_key(client):
    bad(client, "hill_encrypt", {"plain": "HI", "key": [[1, 2, 3]]}, "quadrada")


# ---------------------------------------------------------------- leontief

def test_leontief_from_transactions(client):
    Z = [[1.0, 2.0], [3.0, 4.0]]
    X = [10.0, 20.0]
    out = ok(client, "leontief", {"Z": Z, "X": X})
    assert np.allclose(out["A"], [[0.1, 0.1], [0.3, 0.2]])
    assert set(out) == {"A"}


def test_leontief_required_net_labor(client):
    A = [[0.2, 0.1, 0.1], [0.3, 0.2, 0.1], [0.1, 0.2, 0.2]]
    d = [50.0, 30.0, 20.0]
    x = ok(client, "leontief", {"A": A, "d": d})["x_required"]
    assert np.allclose((np.eye(3) - np.array(A)) @ np.array(x), d, atol=1e-5)

    net = ok(client, "leontief", {"A": A, "x": x})["net"]
    assert np.allclose(net, d, atol=1e-5)

    labor = ok(client, "leontief", {"L": [1.0, 1.5, 1.2], "x": [10, 4, 5]})
    assert labor == {"labor": pytest.approx(22.0)}


def test_leontief_does_what_it_can(client):
    Z = [[1.0, 2.0], [3.0, 4.0]]
    X = [10.0, 20.0]
    out = ok(client, "leontief", {"Z": Z, "X": X, "d": [1.0, 1.0]})
    assert "A" in out and "x_required" in out and "net" not in out


def test_leontief_errors(client):
    bad(client, "leontief", {"Z": [[1.0]]}, "Nada a calcular")
    bad(client, "leontief", {"A": [[0.1, 0.1], [0.3, 0.2]], "d": [1.0, 1.0, 1.0]}, "Dimensões incompatíveis")
    bad(client, "leontief", {"Z": [[1.0, 2.0], [3.0, 4.0]], "X": [1.0, 0.0]}, "zeros")


# ---------------------------------------------------------------- markov

def test_markov_names_and_ints_are_equivalent(client):
    seq_names = ["limpo", "limpo", "chuva", "tempestade", "chuva", "limpo", "limpo", "chuva"]
    seq_ints = [0, 0, 1, 2, 1, 0, 0, 1]
    a = ok(client, "markov", {"sequence": seq_names})
    b = ok(client, "markov", {"sequence": seq_ints})
    assert a == b
    P = np.array(a["P_estimated"])
    assert P.shape == (3, 3) and np.allclose(P.sum(axis=1), 1.0)
    assert np.sum(a["stationary"]) == pytest.approx(1.0, abs=1e-6)


def test_markov_forecast_with_state_name(client):
    P = [[0.9, 0.1, 0.0], [0.2, 0.8, 0.0], [0.0, 0.5, 0.5]]
    out = ok(client, "markov", {"P": P, "state": "chuva", "k": 2})
    expected = np.linalg.matrix_power(np.array(P), 2)[1]
    assert out["forecast"] == pytest.approx(expected.tolist(), abs=1e-6)
    assert "P_estimated" not in out
    assert "stationary" in out


def test_markov_sequence_and_state_accents(client):
    seq = ["Limpo", "Tempestade", "Limpo", "Chuva"]
    out = ok(client, "markov", {"sequence": seq, "state": "limpo"})
    assert len(out["forecast"]) == 3 and abs(sum(out["forecast"]) - 1) < 1e-6


def test_markov_errors(client):
    bad(client, "markov", {"sequence": ["limpo", "neve"]}, "Estado desconhecido")
    bad(client, "markov", {"sequence": [0, 7]}, "fora do intervalo")
    bad(client, "markov", {"sequence": ["limpo"]}, "pelo menos 2")
    bad(client, "markov", {"P": [[0.5, 0.4], [0.5, 0.5]]}, "estocástica")
    bad(client, "markov", {}, "Informe 'sequence'")


# ---------------------------------------------------------------- trilaterate

def test_trilaterate_exact_and_grid(client):
    stations = [[100, 100], [900, 150], [700, 700], [200, 650]]
    target = (525.0, 310.0)
    d = geo.station_readings(target, stations, np.random.default_rng(0), noise=0.0)
    out = ok(client, "trilaterate", {"stations": stations, "distances": d})
    assert out["x"] == pytest.approx(525.0, abs=1e-4)
    assert out["y"] == pytest.approx(310.0, abs=1e-4)
    assert out["grid"] == "K7"


def test_trilaterate_outside_grid_is_clipped_label(client):
    stations = [[0, 0], [1000, 0], [0, 700]]
    d = [math.hypot(1300, 900), math.hypot(300, 900), math.hypot(1300, 200)]
    out = ok(client, "trilaterate", {"stations": stations, "distances": d})
    assert out["grid"] == "X16"


def test_trilaterate_errors(client):
    bad(client, "trilaterate", {"stations": [[0, 0], [1, 1]], "distances": [1, 1]}, "pelo menos 3")
    bad(client, "trilaterate", {"stations": [[0, 0], [1, 0], [2, 0]], "distances": [1, 1, 1]}, "colineares")
    bad(client, "trilaterate", {"stations": [[0, 0, 1], [1, 0], [0, 1]], "distances": [1, 1, 1]}, "par [x, y]")
    bad(client, "trilaterate", {"stations": [[0, 0], [1, 0], [0, 1]], "distances": [1, 1]}, "uma distância")


# ---------------------------------------------------------------- regression

def _linear_rows(n=40, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        a = float(rng.uniform(0, 10))
        b = float(rng.uniform(-5, 5))
        rows.append({"a": round(a, 4), "b": round(b, 4), "y": round(1 + 2 * a - 3 * b, 4)})
    return rows


def test_regression_rows_recovers_coefficients(client):
    out = ok(client, "regression", {"rows": _linear_rows(), "features": ["a", "b"], "target": "y"})
    c = out["coefficients"]
    assert c["intercepto"] == pytest.approx(1.0, abs=1e-3)
    assert c["a"] == pytest.approx(2.0, abs=1e-3)
    assert c["b"] == pytest.approx(-3.0, abs=1e-3)
    assert out["r2"] == pytest.approx(1.0, abs=1e-6)


def test_regression_csv_semicolon_and_decimal_comma(client):
    lines = ["tempo;a;b;y"]
    for row in _linear_rows(20, seed=3):
        lines.append(f"x;{str(row['a']).replace('.', ',')};{str(row['b']).replace('.', ',')};"
                     f"{str(row['y']).replace('.', ',')}")
    csv_text = "\n".join(lines)
    out = ok(client, "regression", {"csv": csv_text, "target": "y", "features": ["a", "b"]})
    assert out["coefficients"]["a"] == pytest.approx(2.0, abs=1e-3)
    assert out["coefficients"]["b"] == pytest.approx(-3.0, abs=1e-3)


def test_regression_csv_comma_and_default_features(client):
    csv_text = "a,b,y\n1,2,8\n2,1,6\n3,5,4\n4,0,9\n5,3,7\n"
    out = ok(client, "regression", {"csv": csv_text, "target": "y"})
    assert set(out["coefficients"]) == {"intercepto", "a", "b"}
    assert 0.0 <= out["r2"] <= 1.0


def test_regression_errors(client):
    rows = _linear_rows(10)
    bad(client, "regression", {"rows": rows, "features": ["a", "b"], "target": "zeta"}, "Coluna 'zeta' não encontrada")
    bad(client, "regression", {"rows": rows, "features": ["a", "b"], "target": "a"}, "não pode estar entre")
    bad(client, "regression", {"csv": "a,b,y\n1,2\n3,4,5\n", "target": "y"}, "colunas")
    bad(client, "regression", {"target": "y"}, "Informe 'rows'")
    bad(client, "regression", {"csv": "a,y\n1,2\n", "target": "y"}, "mais observações")
    # colunas idênticas → equações normais singulares
    dup = [{"a": v, "a2": v, "y": 2 * v + 1} for v in range(1, 8)]
    bad(client, "regression", {"rows": dup, "features": ["a", "a2"], "target": "y"}, "singulares")


# ---------------------------------------------------------------- lanchester

def test_lanchester_tool_matches_closed_form(client):
    out = ok(client, "lanchester", {"A0": 2, "B0": 1, "alpha": 1, "beta": 1, "T": 0.9})
    assert out["winner"] == "attacker"
    assert out["a_final"] == pytest.approx(math.sqrt(3), abs=1e-6)
    assert out["b_final"] == 0.0
    assert len(out["trajectory"]) == 60
    assert out["trajectory"][0] == pytest.approx([0.0, 2.0, 1.0])


def test_lanchester_tool_none_and_steps(client):
    out = ok(client, "lanchester", {"A0": 1, "B0": 1, "alpha": 1, "beta": 1, "steps": 5})
    assert out["winner"] == "none"
    assert out["a_final"] == pytest.approx(math.exp(-0.9), abs=1e-6)
    assert len(out["trajectory"]) == 5


def test_lanchester_tool_errors(client):
    bad(client, "lanchester", {"A0": 1, "B0": 1, "alpha": 0, "beta": 1}, "positivas")
    bad(client, "lanchester", {"A0": 1, "B0": 1, "alpha": 1, "beta": 1, "steps": 1}, "entre 2 e")
    bad(client, "lanchester", {"A0": 1, "B0": 1, "alpha": 1}, "Campo obrigatório ausente: 'beta'")
    bad(client, "lanchester", {"A0": "forte", "B0": 1, "alpha": 1, "beta": 1}, "numérico")


def test_all_responses_are_plain_json(client):
    """Nenhuma resposta pode conter NaN/Infinity ou tipos numpy."""
    responses = [
        post(client, "matrix", {"op": "eig", "A": [[0, -1], [1, 0]]}),
        post(client, "lanchester", {"A0": 2, "B0": 1, "alpha": 1, "beta": 1}),
        post(client, "modinv", {"K": [[3, 3], [2, 5]]}),
    ]
    for r in responses:
        assert r.status_code == 200
        assert "NaN" not in r.text and "Infinity" not in r.text
        r.json()
