"""Simulações de partidas completas com bots simples: invariantes e números de balanceamento.

Os bots só usam o que um aluno veria (faction_view e dossier_view) e resolvem os desafios com a
mesma matemática da Mesa de Cálculo, a partir dos DADOS ENTREGUES.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

from app.engine import economy, geo, morale, weather
from app.game import balance as B
from app.game import events as EV
from app.game.game import Game

MAP = json.loads((Path(__file__).resolve().parents[1] / "app" / "data" / "map.json").read_text(encoding="utf-8"))
T0 = 1_760_000_000_000
SEC = B.SECTORS
RANGE_MID = {"0": 0, "1–5": 3, "6–10": 8, "11–20": 15, "21+": 26}


def br(x: float) -> str:
    return f"{x:.4f}".replace(".", ",")


# ------------------------------------------------------------------------ "alunos"
def solve_challenges(g: Game, fid: str, now: int, only=None) -> dict:
    """Resolve os 4 desafios como um aluno faria, usando só os dossiês."""
    out = {}
    for section in B.SECTIONS:
        if only and section not in only:
            continue
        d = g.dossier_view(fid, section)
        if not d["challenges"]:
            continue
        ch = d["challenges"][0]
        ds = {x["id"]: x for x in d["datasets"]}
        if section == "intendencia":
            rows = ds["transacoes"]["rows"]
            Z = np.array([r[1:] for r in rows[:3]], float)
            X = np.array(rows[3][1:], float)
            A = economy.A_from_transactions(Z, X)
            dstar = [float(v) for v in re.findall(r"(\d+) (?:ALI|ACO|COM)", ch["prompt"])]
            x = economy.required_production(A, dstar)
            ans = "; ".join(br(v) for v in x)
        elif section == "operacoes":
            m = re.search(r"região (\w+) o tempo está agora em «(\w+)»", ch["prompt"])
            region, state = m.group(1).lower(), B.WEATHER_NAMES.index(m.group(2))
            col = {"norte": 1, "centro": 2, "sul": 3}[region]
            seq = [B.WEATHER_NAMES.index(r[col]) for r in ds["diario_clima"]["rows"]]
            ans = br(weather.estimate_P(seq)[state, 2])
        elif section == "inteligencia":
            rows = ds["leituras"]["rows"]
            if not rows:
                continue
            st = [[r[1], r[2]] for r in rows]
            dist = [r[3] for r in rows]
            x, y = geo.trilaterate(st, dist)
            ans = f"{x:.1f}; {y:.1f}".replace(".", ",")
        else:
            rows = [dict(zip(["obs", "racao", "propaganda", "horas_extra", "baixas", "saldo_territorial",
                              "delta_moral"], r)) for r in ds["pesquisa"]["rows"]]
            ans = br(morale.ols(rows)[2])
        out[section] = g.answer_challenge(fid, ch["id"], ans, now)
    return out


class Bot:
    """style: 'builder' (produz e recruta, sem atacar), 'warrior' (ataca com vantagem), 'idle' (nada)."""

    def __init__(self, fid: str, style: str = "warrior", ratio: float = 1.8, recruit: int = 3,
                 answer: bool = True):
        self.fid, self.style, self.ratio, self.recruit, self.answer = fid, style, ratio, recruit, answer

    def play(self, g: Game, now: int) -> None:
        fid = self.fid
        if g.factions[fid].capitulated or self.style == "idle":
            return
        if self.answer:
            solve_challenges(g, fid, now)
        view = g.faction_view(fid, now)
        me = view["faction"]
        tr = {t["id"]: t for t in view["territories"]}
        d = g.dossier_view(fid, "intendencia")
        rows = d["datasets"][0]["rows"]
        Z = np.array([r[1:] for r in rows[:3]], float)
        X = np.array(rows[3][1:], float)
        A = economy.A_from_transactions(Z, X)

        # operações
        moves, com_need = [], 0
        if self.style == "warrior":
            moves, com_need = self._plan_moves(g, view, tr)
        upkeep = 0.5 * me["troops_total"] + B.CIVIL_ALI[0]
        r = self.recruit
        dnet = np.array([upkeep + 2 * r + 2, 2 * r + 3, r + com_need + 2], float)
        x = economy.required_production(A, dnet)
        cap = np.array([me["capacity"][s] for s in SEC])
        x = np.minimum(x, cap)
        need = float(np.dot([B.LABOR[s] for s in SEC], x))
        if need > me["workforce"]:
            x = x * me["workforce"] / need
        res = g.submit_orders(fid, "intendencia", {"production": {s: float(x[i]) for i, s in enumerate(SEC)},
                                                   "recruit": r}, now)
        assert res["ok"], res
        if moves:
            res = g.submit_orders(fid, "operacoes", {"moves": moves}, now)
            assert res["ok"], res
        res = g.submit_orders(fid, "governo", {"racao": 0, "propaganda": 2, "horas": 8}, now)
        assert res["ok"], res

    def _plan_moves(self, g, view, tr):
        fid = self.fid
        me = view["faction"]
        pacts = {p["with"] for p in me["pacts"]}
        moves, used = [], {}
        com = me["stock"]["COM"]
        cost = 0
        for t in sorted(tr, key=lambda t: -(tr[t]["troops"] or 0)):
            if tr[t]["owner"] != fid:
                continue
            avail = tr[t]["troops"] - 1
            if avail < 2:
                continue
            best = None
            for u in g.adjacent(t):
                tu = tr[u]
                if tu["owner"] == fid or tu["owner"] in pacts:
                    continue
                if tu["visibility"] == "revealed":
                    est = tu["troops"]
                else:
                    est = RANGE_MID.get(tu["troops_range"], 8) if tu["troops_range"] else 8
                if avail >= self.ratio * max(est, 1):
                    score = (est, u)
                    if best is None or score < best[0]:
                        best = (score, u)
            if best:
                u = best[1]
                n = avail
                c = n * (2 if g.is_sea_move(t, u) else 1)
                if cost + c <= com + 6:
                    moves.append({"from": t, "to": u, "troops": n})
                    cost += c
        return moves, cost


def check_invariants(g: Game) -> None:
    ids = set(g.factions)
    for t in g.order_tids:
        assert g.owner[t] is None or g.owner[t] in ids
        assert isinstance(g.troops[t], int) and g.troops[t] >= 0, (t, g.troops[t])
    for f in g.factions.values():
        for s in SEC:
            assert f.stock[s] >= -1e-9, (f.id, s, f.stock)
        assert 0 <= f.morale <= 100
        if f.capitulated:
            assert g.n_territories(f.id) == 0
    n_terr = sum(g.n_territories(f) for f in g.order)
    n_neutral = sum(1 for t in g.order_tids if g.owner[t] is None)
    assert n_terr + n_neutral == len(g.order_tids)
    for r in g.standings():
        assert r["vp"] >= 0


def play_game(n: int, seed: int, styles=None, turns: int = 8, answer: bool = True, hook=None):
    g = Game.new(MAP, n_factions=n, turn_minutes=12, max_turns=turns, seed=seed)
    bots = []
    for i, fid in enumerate(g.order):
        st = (styles or ["warrior"] * n)[i % len(styles or [1])] if styles else "warrior"
        bots.append(Bot(fid, st, answer=answer))
    now = T0
    g.start(now)
    stats = []
    while g.status == "running":
        for b in bots:
            b.play(g, now)
        if hook:
            hook(g, now)
        now += g.turn_ms
        g.resolve_turn(now)
        check_invariants(g)
        h = g.history[-1]
        stats.append(h)
    return g, stats


@pytest.mark.parametrize("n,seed", [(2, 1), (4, 2), (6, 3)])
def test_partida_completa_sem_erros(n, seed):
    g, stats = play_game(n, seed)
    assert g.status == "finished"
    assert len(stats) == 8
    assert g.winner in g.factions
    assert g.news[-1]["kind"] == "event" and "Classificação final" in g.news[-1]["body"]


@pytest.mark.parametrize("n,seed", [(3, 5), (5, 6)])
def test_guerra_agressiva_mantem_invariantes(n, seed):
    """Bots que atacam com vantagem pequena (1,2:1): muita batalha, nenhum erro, ninguém some no turno 2."""
    g = Game.new(MAP, n_factions=n, turn_minutes=12, max_turns=8, seed=seed)
    bots = [Bot(f, "warrior", ratio=1.2, recruit=4) for f in g.order]
    now = T0
    g.start(now)
    battles = 0
    while g.status == "running":
        for b in bots:
            b.play(g, now)
        now += g.turn_ms
        g.resolve_turn(now)
        check_invariants(g)
        battles += g.history[-1]["battles"]
        if g.turn <= 3:
            assert not any(f.capitulated for f in g.factions.values())
    assert battles >= 4


def test_passivo_sensato_nao_passa_fome_e_inativo_entra_em_crise():
    """Uma nação que produz o suficiente não passa fome; uma que não produz nada entra em crise em ~3 turnos."""
    styles = ["builder", "idle", "builder", "idle"]
    g, stats = play_game(4, 7, styles=styles)
    assert not any("GAU" in h["starved"] or "HIL" in h["starved"] for h in stats), [h["starved"] for h in stats]
    first = [h["turn"] for h in stats if "EUL" in h["starved"]]
    assert first and 2 <= first[0] <= 4, first


def test_numeros_de_balanceamento(capsys):
    rows = []
    for n, seeds in ((2, [11, 12, 13]), (4, [21, 22, 23, 24]), (6, [31, 32, 33])):
        for seed in seeds:
            g, stats = play_game(n, seed)
            rows.append((n, seed, stats, g))
    for n, seed, stats, g in rows:
        assert sum(h["captures"] for h in stats) >= 3, (n, seed)          # a guerra anda
        assert all(h["territories"][f] > 0 for h in stats[:2] for f in g.order)   # ninguém some no turno 2
    if not os.environ.get("SIM_VERBOSE"):
        return
    with capsys.disabled():
        print()
        for n, seed, stats, g in rows:
            caps = [h["captures"] for h in stats]
            troops = [sum(h["troops"].values()) for h in stats]
            ali = [np.mean([h["stock"][f]["ALI"] for f in g.order]) for h in stats]
            print(f"n={n} seed={seed} capturas/turno={caps} tropas totais={troops} "
                  f"ALI médio={[round(float(a), 1) for a in ali]} fome={sum(len(h['starved']) for h in stats)} "
                  f"capituladas={[f for f in g.order if g.factions[f].capitulated]}")


# ------------------------------------------------------------------------------ fuzz
def _random_orders(g: Game, rng: np.random.Generator, fid: str, now: int) -> None:
    v = g.faction_view(fid, now)
    mine = [t["id"] for t in v["territories"] if t["owner"] == fid]
    others = [f for f in g.order if f != fid]
    big = lambda: float(rng.choice([0, 3, 10, 40, 500]))  # noqa: E731
    g.submit_orders(fid, "intendencia", {"production": {s: big() for s in SEC},
                                         "recruit": int(rng.choice([0, 2, 9, 40]))}, now)
    moves = []
    for _ in range(int(rng.integers(0, 6))):
        if not mine:
            break
        a = str(rng.choice(mine))
        nb = sorted(g.adjacent(a))
        moves.append({"from": a, "to": str(rng.choice(nb)), "troops": int(rng.integers(1, 12))})
    g.submit_orders(fid, "operacoes", {"moves": moves}, now)
    g.submit_orders(fid, "governo", {
        "racao": int(rng.integers(0, 3)), "propaganda": int(rng.integers(0, 6)),
        "horas": int(rng.choice([8, 10, 12])),
        "transfers": [{"to": str(rng.choice(others)), "ALI": big(), "ACO": big(), "COM": 0}] if others else [],
        "pact_propose": [str(rng.choice(others))] if others and rng.random() < 0.5 else [],
        "pact_denounce": [str(rng.choice(others))] if others and rng.random() < 0.2 else [],
    }, now)
    if rng.random() < 0.5:
        solve_challenges(g, fid, now)
    if rng.random() < 0.3:
        loc = g.faction_view(fid, now)["faction"]["bonuses"]["depot_located"]
        if loc:
            g.submit_orders(fid, "inteligencia", {"bombard": loc["territory"]}, now)


@pytest.mark.parametrize("seed", range(6))
def test_fuzz_ordens_aleatorias_nunca_quebram(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 7))
    g = Game.new(MAP, n_factions=n, turn_minutes=5, max_turns=8, seed=seed)
    now = T0
    g.start(now)
    while g.status == "running":
        for fid in g.order:
            if not g.factions[fid].capitulated:
                _random_orders(g, rng, fid, now)
        if rng.random() < 0.3:
            g.admin_trigger_event(str(rng.choice([e["id"] for e in EV.list_events()])), now)
        if rng.random() < 0.2:
            g.pause(now)
            g.resume(now + 1000)
        if rng.random() < 0.3:
            g.send_message(g.order[0], g.order[1], "teste", now)
        if rng.random() < 0.3:
            g.tick(now + g.turn_ms // 2 + 1)
        now += g.turn_ms
        g.tick(now)
        check_invariants(g)
        json.dumps(g.admin_view(now), allow_nan=False)
        for fid in g.order:
            json.dumps(g.faction_view(fid, now), allow_nan=False)
    assert g.status == "finished" or g.turn <= 8
    # após o fim, a visão pública traz a classificação
    pv = g.public_view(now)
    assert pv["standings"][0]["rank"] == 1
