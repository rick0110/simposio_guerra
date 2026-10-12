"""Testes unitários do motor matemático (app/engine)."""

import math

import numpy as np
import pytest

from app.engine import cipher, combat, economy, geo, linalg, morale, weather


# ============================================================ linalg

def test_det_inv_solve_2x2():
    A = [[2.0, 1.0], [1.0, 3.0]]
    assert linalg.det(A) == pytest.approx(5.0)
    assert np.allclose(linalg.inv(A) @ np.array(A), np.eye(2))
    x = linalg.solve(A, [3.0, 5.0])
    assert np.allclose(x, [0.8, 1.4])


def test_singular_matrix_errors_in_portuguese():
    S = [[1.0, 2.0], [2.0, 4.0]]
    with pytest.raises(ValueError, match="singular"):
        linalg.inv(S)
    with pytest.raises(ValueError, match="singular"):
        linalg.solve(S, [1.0, 1.0])


def test_non_square_is_rejected():
    with pytest.raises(ValueError, match="não é quadrada"):
        linalg.det([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])


def test_lstsq_exact_line_and_residual():
    A = [[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]]
    x, rss = linalg.lstsq(A, [1.0, 3.0, 5.0])  # y = 1 + 2t
    assert np.allclose(x, [1.0, 2.0])
    assert rss == pytest.approx(0.0, abs=1e-12)

    x2, rss2 = linalg.lstsq(A, [1.0, 4.0, 4.0])
    assert rss2 > 0
    # equações normais dão a mesma solução
    AtA = np.array(A).T @ np.array(A)
    assert np.allclose(x2, np.linalg.solve(AtA, np.array(A).T @ [1.0, 4.0, 4.0]))


def test_eig_real_and_complex():
    vals, vecs = linalg.eig([[2.0, 0.0], [0.0, 3.0]])
    assert sorted(vals) == pytest.approx([2.0, 3.0])
    assert all(isinstance(v, float) for v in vals)

    vals, _ = linalg.eig([[0.0, -1.0], [1.0, 0.0]])
    assert all(isinstance(v, complex) for v in vals)
    assert sorted(v.imag for v in vals) == pytest.approx([-1.0, 1.0])
    assert np.allclose(sorted(v.real for v in vals), [0.0, 0.0])


def test_mat_pow_positive_and_negative():
    A = [[1.0, 1.0], [0.0, 1.0]]
    assert np.allclose(linalg.mat_pow(A, 3), [[1.0, 3.0], [0.0, 1.0]])
    assert np.allclose(linalg.mat_pow(A, 0), np.eye(2))
    assert np.allclose(linalg.mat_pow(A, -2), [[1.0, -2.0], [0.0, 1.0]])


def test_stationary_two_state_chain():
    P = [[0.9, 0.1], [0.5, 0.5]]
    pi = linalg.stationary(P)
    assert np.allclose(pi, [5 / 6, 1 / 6])
    assert pi.sum() == pytest.approx(1.0)
    assert np.allclose(pi @ np.array(P), pi)


def test_stationary_rejects_non_stochastic():
    with pytest.raises(ValueError, match="estocástica"):
        linalg.stationary([[0.5, 0.4], [0.5, 0.5]])


def test_matmul_shapes():
    assert np.allclose(linalg.matmul([[1, 2]], [[3], [4]]), [[11.0]])
    with pytest.raises(ValueError, match="Dimensões incompatíveis"):
        linalg.matmul([[1, 2]], [[1, 2]])


def test_mod_inv_int():
    assert linalg.mod_inv_int(3, 37) == 25  # 3·25 = 75 ≡ 1
    assert (linalg.mod_inv_int(-3, 37) * -3) % 37 == 1
    with pytest.raises(ValueError, match="não é invertível"):
        linalg.mod_inv_int(2, 4)


def test_mod_inv_matrix_2x2_known_example():
    K = np.array([[3, 3], [2, 5]])
    Kinv = linalg.mod_inv_matrix(K, 26)
    assert np.array_equal((K @ Kinv) % 26, np.eye(2, dtype=int))


@pytest.mark.parametrize("seed", range(20))
def test_mod_inv_matrix_3x3_random_mod_37(seed):
    rng = np.random.default_rng(seed)
    while True:
        K = rng.integers(0, 37, size=(3, 3))
        try:
            Kinv = linalg.mod_inv_matrix(K, 37)
            break
        except ValueError:
            continue
    assert np.array_equal((K @ Kinv) % 37, np.eye(3, dtype=int))


def test_mod_inv_matrix_singular_message():
    with pytest.raises(ValueError, match=r"Determinante ≡ 0 mod 37: chave não invertível"):
        linalg.mod_inv_matrix([[1, 2], [2, 4]], 37)


# ============================================================ cipher

def test_normalize_accents_cedilla_and_symbols():
    assert cipher.normalize("Ação, Ç!") == "ACAO C "
    assert cipher.normalize("olá   mundo") == "OLA MUNDO"
    assert cipher.normalize("URGENTE ") == "URGENTE "  # espaço final é preservado
    assert set(cipher.normalize("x@y#z-9")) <= set(cipher.ALPHABET)


def test_alphabet_and_numbers():
    assert len(cipher.ALPHABET) == 37 == cipher.M
    assert cipher.to_nums("AZ 09") == [0, 25, 36, 26, 35]
    assert cipher.to_text([0, 25, 36, 26, 35]) == "AZ 09"


def test_encrypt_known_example():
    K = np.array([[3, 3], [2, 5]])
    # H=7, I=8 → (3·7+3·8, 2·7+5·8) mod 37 = (8, 17) = I, R
    assert cipher.encrypt("HI", K) == "IR"
    assert cipher.decrypt("IR", K) == "HI"


def test_ciphertext_double_space_is_not_collapsed():
    """No criptograma o espaço é símbolo: dois espaços seguidos não podem virar um."""
    K = np.array([[3, 3], [2, 5]])
    Kinv = linalg.mod_inv_matrix(K, 37)
    block = (Kinv @ np.array([36, 36])) % 37          # bloco claro que cifra em "  "
    plain = cipher.to_text(block)
    assert cipher.encrypt(plain, K) == "  "
    assert cipher.decrypt("  ", K) == plain
    assert cipher.decrypt(cipher.encrypt("OI", K), K) == "OI"


def test_encrypt_padding_after_trailing_space():
    """Texto que termina em espaço e recebe preenchimento não pode colapsar o espaço."""
    K = np.array([[3, 3], [2, 5]])
    c = cipher.encrypt("HI ", K)           # 3 símbolos → 4 com preenchimento
    assert len(c) == 4
    assert cipher.decrypt(c, K) == "HI  "


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", range(10))
def test_encrypt_decrypt_roundtrip(n, seed):
    rng = np.random.default_rng(seed)
    K = cipher.random_key(rng, n)
    msg = "Tropas avançando pela Ponte 7 às 14h"
    c = cipher.encrypt(msg, K)
    assert len(c) % n == 0 and len(c) >= len(cipher.normalize(msg))
    back = cipher.decrypt(c, K)
    assert back.rstrip() == cipher.normalize(msg).rstrip()
    assert len(back) == len(c)


def test_random_key_is_invertible_and_reproducible():
    K1 = cipher.random_key(np.random.default_rng(7), 2)
    K2 = cipher.random_key(np.random.default_rng(7), 2)
    assert np.array_equal(K1, K2)
    assert K1.shape == (2, 2)
    linalg.mod_inv_matrix(K1, 37)  # não levanta


def test_decrypt_with_noninvertible_key_fails():
    with pytest.raises(ValueError, match="chave não invertível"):
        cipher.decrypt("ABCD", [[1, 2], [2, 4]])


def test_decrypt_wrong_length_fails():
    with pytest.raises(ValueError, match="múltiplo de 2"):
        cipher.decrypt("ABC", [[3, 3], [2, 5]])


@pytest.mark.parametrize("seed", range(50))
def test_recover_key_from_urgente_crib(seed):
    rng = np.random.default_rng(seed)
    K = cipher.random_key(rng, 2)
    crib_cipher = cipher.encrypt("URGENTE ", K)
    recovered = cipher.recover_key("URGENTE ", crib_cipher, 2)
    assert np.array_equal(recovered, K)


def test_recover_key_rejects_inconsistent_crib():
    with pytest.raises(ValueError, match="Não foi possível recuperar a chave"):
        cipher.recover_key("URGENTE ", "QWERTYUI", 2)


def test_recover_key_rejects_singular_crib_blocks():
    # todos os blocos "AA" são iguais → nenhuma combinação é invertível
    with pytest.raises(ValueError):
        cipher.recover_key("AAAA", "ABCD", 2)


def test_recover_key_requires_same_length():
    with pytest.raises(ValueError, match="mesmo comprimento"):
        cipher.recover_key("URGENTE ", "ABC", 2)


# ============================================================ economy

@pytest.mark.parametrize("seed", range(30))
def test_random_A_is_productive_and_bounded(seed):
    A = economy.random_A(np.random.default_rng(seed))
    assert A.shape == (3, 3)
    assert np.all(A >= 0.05 - 1e-12) and np.all(A <= 0.30 + 1e-12)
    assert np.all(A.sum(axis=0) < 0.6)
    assert max(abs(np.linalg.eigvals(A))) < 1


def test_perturb_A_keeps_productive_and_applies_damage():
    rng = np.random.default_rng(3)
    A = economy.random_A(rng)
    B = economy.perturb_A(A, np.random.default_rng(4), scale=0.02, damage=0.0)
    assert np.all(B >= 0.02 - 1e-12) and np.all(B <= 0.45 + 1e-12)
    assert np.all(B.sum(axis=0) < 1.0)

    damaged = economy.perturb_A(A, np.random.default_rng(4), scale=0.0, damage=0.2)
    assert np.all(damaged.sum(axis=0) <= 0.85 + 1e-9)
    assert max(abs(np.linalg.eigvals(damaged))) < 1


def test_perturb_A_damage_increases_diagonal_when_unscaled():
    A = np.full((3, 3), 0.1)
    out = economy.perturb_A(A, np.random.default_rng(0), scale=0.0, damage=0.05)
    assert np.allclose(out, A + 0.05 * np.eye(3))


def test_transactions_and_back_to_A():
    A = np.array([[0.1, 0.2, 0.1], [0.3, 0.1, 0.2], [0.1, 0.1, 0.2]])
    x = np.array([10.0, 20.0, 30.0])
    Z = economy.transactions(A, x)
    assert np.allclose(Z, A * x[None, :])
    assert np.allclose(economy.A_from_transactions(Z, x), A)
    with pytest.raises(ValueError, match="zeros"):
        economy.A_from_transactions(Z, [1.0, 0.0, 1.0])


def test_leontief_required_production_and_net_output():
    A = np.array([[0.1, 0.2, 0.1], [0.3, 0.1, 0.2], [0.1, 0.1, 0.2]])
    d = np.array([50.0, 30.0, 20.0])
    x = economy.required_production(A, d)
    assert np.allclose(economy.net_output(A, x), d)
    assert np.allclose(x, np.linalg.solve(np.eye(3) - A, d))


def test_labor_used_is_dot_product():
    assert economy.labor_used([1.0, 1.5, 1.2], [10.0, 4.0, 5.0]) == pytest.approx(10 + 6 + 6)
    with pytest.raises(ValueError):
        economy.labor_used([1.0, 2.0], [1.0, 2.0, 3.0])


# ============================================================ combat

def test_effectiveness_base_and_modifiers():
    assert combat.effectiveness(70) == pytest.approx(1.2)
    assert combat.effectiveness(0) == pytest.approx(0.5)
    assert combat.effectiveness(70, terrain="montanha", role="defense") == pytest.approx(1.2 * 1.5)
    assert combat.effectiveness(70, weather=2, role="attack") == pytest.approx(1.2 * 0.65)
    # clima não afeta defensor; terreno não afeta atacante
    assert combat.effectiveness(70, weather=2, role="defense") == pytest.approx(1.2)
    assert combat.effectiveness(70, terrain="floresta", role="attack") == pytest.approx(1.2)
    with pytest.raises(ValueError):
        combat.effectiveness(70, terrain="deserto", role="defense")
    with pytest.raises(ValueError):
        combat.effectiveness(70, role="flanco")
    with pytest.raises(ValueError):
        combat.effectiveness(120)


def test_lanchester_attacker_wins_with_closed_form():
    r = combat.lanchester(2.0, 1.0, 1.0, 1.0, T=0.9)
    assert r["winner"] == "attacker"
    assert r["b_final"] == 0.0
    assert r["a_final"] == pytest.approx(math.sqrt(3), rel=1e-9)
    assert r["t_end"] == pytest.approx(math.atanh(0.5), rel=1e-9)


def test_lanchester_equal_forces_none_and_exponential_decay():
    r = combat.lanchester(1.0, 1.0, 1.0, 1.0, T=0.9)
    assert r["winner"] == "none"
    assert r["t_end"] == pytest.approx(0.9)
    assert r["a_final"] == pytest.approx(math.exp(-0.9), rel=1e-9)
    assert r["b_final"] == pytest.approx(math.exp(-0.9), rel=1e-9)


def test_lanchester_defender_wins():
    r = combat.lanchester(1.0, 2.0, 1.0, 1.0, T=0.9)
    assert r["winner"] == "defender"
    assert r["a_final"] == 0.0
    assert r["b_final"] == pytest.approx(math.sqrt(3), rel=1e-9)


def test_lanchester_trajectory_shape_and_monotonic():
    r = combat.lanchester(3.0, 2.0, 0.9, 1.1, T=0.9, steps=25)
    traj = r["trajectory"]
    assert len(traj) == 25
    assert traj[0] == pytest.approx([0.0, 3.0, 2.0])
    assert traj[-1][0] == pytest.approx(r["t_end"])
    assert traj[-1][1] == pytest.approx(r["a_final"])
    assert traj[-1][2] == pytest.approx(r["b_final"])
    arr = np.array(traj)
    assert np.all(np.diff(arr[:, 1]) <= 1e-12)
    assert np.all(np.diff(arr[:, 2]) <= 1e-12)
    assert np.all(arr[:, 1:] >= 0)


@pytest.mark.parametrize("A0,B0,alpha,beta", [(1.0, 1.0, 0.5, 0.5), (2.0, 1.5, 1.0, 2.0), (3.0, 2.0, 0.3, 0.3)])
def test_lanchester_matches_numerical_ode_when_no_zero_crossing(A0, B0, alpha, beta):
    """Compara a solução fechada com integração RK4 quando nenhum lado zera antes de T."""
    T = 0.9
    r = combat.lanchester(A0, B0, alpha, beta, T=T)
    if r["winner"] != "none":
        pytest.skip("lado zerou antes de T; coberto pelos outros testes")
    A, B, h = A0, B0, T / 20000

    def f(a, b):
        return -beta * b, -alpha * a

    for _ in range(20000):
        k1 = f(A, B)
        k2 = f(A + h / 2 * k1[0], B + h / 2 * k1[1])
        k3 = f(A + h / 2 * k2[0], B + h / 2 * k2[1])
        k4 = f(A + h * k3[0], B + h * k3[1])
        A += h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        B += h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
    assert r["a_final"] == pytest.approx(A, rel=1e-6)
    assert r["b_final"] == pytest.approx(B, rel=1e-6)


def test_lanchester_never_negative_random_inputs():
    rng = np.random.default_rng(11)
    for _ in range(200):
        r = combat.lanchester(*rng.uniform(0.1, 5, size=2), *rng.uniform(0.2, 3, size=2), T=0.9, steps=10)
        assert r["a_final"] >= 0 and r["b_final"] >= 0
        assert r["winner"] in {"attacker", "defender", "none"}


def test_lanchester_zero_start_and_validation():
    r = combat.lanchester(2.0, 0.0, 1.0, 1.0)
    assert r["winner"] == "attacker" and r["t_end"] == 0.0
    with pytest.raises(ValueError):
        combat.lanchester(1.0, 1.0, 0.0, 1.0)
    with pytest.raises(ValueError):
        combat.lanchester(-1.0, 1.0, 1.0, 1.0)


# ============================================================ weather

def test_random_transition_matrix_is_stochastic_and_dominant():
    for seed in range(30):
        P = weather.random_transition_matrix(np.random.default_rng(seed), 3, (0.45, 0.8))
        assert P.shape == (3, 3)
        assert np.all(P >= 0)
        assert np.allclose(P.sum(axis=1), 1.0)
        for i in range(3):
            assert 0.45 - 1e-12 <= P[i, i] <= 0.8 + 1e-12
            assert P[i, i] == P[i].max()


def test_simulate_deterministic_cycle_and_length():
    cycle = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)
    seq = weather.simulate(cycle, start=0, steps=7, rng=np.random.default_rng(0))
    assert seq == [1, 2, 0, 1, 2, 0, 1]
    assert len(weather.simulate(weather.random_transition_matrix(np.random.default_rng(1)), 0, 40, np.random.default_rng(2))) == 40


def test_estimate_P_counts_and_uniform_fallback():
    seq = [0, 0, 1, 1, 1, 0]
    P = weather.estimate_P(seq, 3)
    assert np.allclose(P[0], [0.5, 0.5, 0.0])
    assert np.allclose(P[1], [1 / 3, 2 / 3, 0.0])
    assert np.allclose(P[2], [1 / 3, 1 / 3, 1 / 3])  # sem dados → uniforme
    with pytest.raises(ValueError):
        weather.estimate_P([0, 5], 3)


def test_estimate_P_recovers_true_matrix_from_long_simulation():
    rng = np.random.default_rng(42)
    P_true = np.array([[0.7, 0.2, 0.1], [0.3, 0.5, 0.2], [0.2, 0.3, 0.5]])
    seq = [0] + weather.simulate(P_true, 0, 20000, rng)
    P_hat = weather.estimate_P(seq, 3)
    assert np.max(np.abs(P_hat - P_true)) < 0.02


def test_forecast_is_row_of_power():
    P = np.array([[0.9, 0.1, 0.0], [0.2, 0.8, 0.0], [0.0, 0.5, 0.5]])
    assert np.allclose(weather.forecast(P, 0, 1), P[0])
    assert np.allclose(weather.forecast(P, 2, 3), np.linalg.matrix_power(P, 3)[2])
    assert np.allclose(weather.forecast(P, 1, 0), [0.0, 1.0, 0.0])
    assert weather.forecast(P, 0, 5).sum() == pytest.approx(1.0)
    assert weather.STATES == ["limpo", "chuva", "tempestade"]


# ============================================================ geo

def test_grid_label_examples_and_clipping():
    assert geo.grid_label(525, 310) == "K7"
    assert geo.grid_label(0, 0) == "A1"
    assert geo.grid_label(1199, 799) == "X16"
    assert geo.grid_label(-30, -5) == "A1"       # recorta para dentro
    assert geo.grid_label(5000, 5000) == "X16"


def test_grid_center_roundtrip():
    assert geo.grid_center("K7") == (525.0, 325.0)
    for label in ["A1", "M9", "X16"]:
        x, y = geo.grid_center(label)
        assert geo.grid_label(x, y) == label
    with pytest.raises(ValueError):
        geo.grid_center("Z99Z")


def test_point_in_polygon_square_and_concave():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert geo.point_in_polygon((5, 5), square)
    assert not geo.point_in_polygon((15, 5), square)
    # forma em "L"
    L = [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10]]
    assert geo.point_in_polygon((2, 8), L)
    assert not geo.point_in_polygon((8, 8), L)


def test_random_point_in_polygon_is_inside():
    tri = [[0, 0], [100, 0], [50, 80]]
    rng = np.random.default_rng(5)
    for _ in range(200):
        x, y = geo.random_point_in_polygon(tri, rng)
        assert geo.point_in_polygon((x, y), tri)


def test_station_readings_noiseless_are_exact():
    stations = [[0, 0], [100, 0], [0, 100]]
    d = geo.station_readings((30, 40), stations, np.random.default_rng(0), noise=0.0)
    assert d == pytest.approx([50.0, math.hypot(70, 40), math.hypot(30, 60)])


def test_trilaterate_exact_four_stations():
    stations = [[100, 100], [900, 150], [700, 700], [200, 650]]
    target = (525.0, 310.0)
    d = geo.station_readings(target, stations, np.random.default_rng(0), noise=0.0)
    x, y = geo.trilaterate(stations, d)
    assert x == pytest.approx(target[0], abs=1e-6)
    assert y == pytest.approx(target[1], abs=1e-6)


def test_trilaterate_with_noise_is_close():
    stations = [[100, 100], [900, 150], [700, 700], [200, 650]]
    target = (525.0, 310.0)
    errs = []
    for seed in range(30):
        d = geo.station_readings(target, stations, np.random.default_rng(seed), noise=8.0)
        x, y = geo.trilaterate(stations, d)
        errs.append(math.hypot(x - target[0], y - target[1]))
    assert np.median(errs) < 15


def test_trilaterate_requires_three_noncollinear_stations():
    with pytest.raises(ValueError, match="pelo menos 3"):
        geo.trilaterate([[0, 0], [1, 1]], [1.0, 1.0])
    with pytest.raises(ValueError, match="colineares"):
        geo.trilaterate([[0, 0], [1, 0], [2, 0]], [1.0, 1.0, 1.0])


# ============================================================ morale

def test_random_betas_signs_and_ranges():
    for seed in range(50):
        b = morale.random_betas(np.random.default_rng(seed))
        b0, b_racao, b_prop, b_horas, b_baixas, b_saldo = b
        assert 1.0 <= b0 <= 3.0
        assert -4.0 <= b_racao <= -2.0
        assert 0.8 <= b_prop <= 2.0
        assert -1.2 <= b_horas <= -0.5
        assert -3.0 <= b_baixas <= -1.5
        assert 1.5 <= b_saldo <= 3.5


def test_survey_rows_have_expected_domains():
    betas = morale.random_betas(np.random.default_rng(1))
    rows = morale.survey(betas, np.random.default_rng(2), n=200, noise=1.5)
    assert len(rows) == 200
    for r in rows:
        assert set(r) == set(morale.FEATURES) | {"delta_moral"}
        assert r["racao"] in (0, 1, 2)
        assert 0 <= r["propaganda"] <= 5
        assert r["horas_extra"] in (0, 2, 4)
        assert 0.0 <= r["baixas"] <= 3.0
        assert -2 <= r["saldo_territorial"] <= 2


def test_ols_recovers_betas_from_large_low_noise_survey():
    betas = morale.random_betas(np.random.default_rng(10))
    rows = morale.survey(betas, np.random.default_rng(11), n=2000, noise=0.01)
    est = morale.ols(rows)
    assert est.shape == (6,)
    assert np.max(np.abs(est - betas)) < 0.1


def test_ols_on_exact_linear_data():
    rng = np.random.default_rng(99)
    coef = np.array([2.0, 0.5, -1.0, 3.0, 0.25, 1.5])
    rows = []
    for _ in range(60):
        feats = {
            "racao": int(rng.integers(0, 3)),
            "propaganda": int(rng.integers(0, 6)),
            "horas_extra": float(rng.choice([0, 2, 4])),
            "baixas": float(rng.uniform(0, 3)),
            "saldo_territorial": int(rng.integers(-2, 3)),
        }
        x = np.array([1.0] + [feats[f] for f in morale.FEATURES])
        rows.append({**feats, "delta_moral": float(x @ coef)})
    est = morale.ols(rows)
    assert np.allclose(est, coef)


def test_ols_errors():
    with pytest.raises(ValueError, match="observações"):
        morale.ols([])
    with pytest.raises(ValueError, match="Campo ausente"):
        morale.ols([{"racao": 1}], features=["racao"])
    with pytest.raises(ValueError, match="mais observações"):
        morale.ols([{"racao": 1, "delta_moral": 2.0}], features=["racao"])


def test_delta_morale_linear_and_noise():
    betas = np.array([2.0, -3.0, 1.0, -1.0, -2.0, 2.0])
    feats = {"racao": 1, "propaganda": 2, "horas_extra": 2, "baixas": 1.0, "saldo_territorial": -1}
    expected = 2 - 3 * 1 + 1 * 2 - 1 * 2 - 2 * 1.0 + 2 * (-1)
    assert morale.delta_morale(betas, feats) == pytest.approx(expected)
    noisy = morale.delta_morale(betas, feats, np.random.default_rng(0), noise=1.0)
    assert noisy != pytest.approx(expected)
    with pytest.raises(ValueError):
        morale.delta_morale(betas, {"racao": 1})
