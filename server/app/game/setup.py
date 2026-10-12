"""Criação de uma partida nova: slots, nações, territórios, segredos e clima inicial."""

from __future__ import annotations

import numpy as np

from app.engine import economy, morale, weather
from app.game import balance as B
from app.game.model import Faction


def make_password(rng, taken: set[str]) -> str:
    words = B.PASSWORD_WORDS
    while True:
        a = words[int(rng.integers(0, len(words)))]
        b = words[int(rng.integers(0, len(words)))]
        if a == b:
            continue
        pw = f"{a}-{b}-{int(rng.integers(10, 100))}"
        if pw not in taken:
            taken.add(pw)
            return pw


def init_new(game, n_factions: int, turn_minutes: float, max_turns: int, seed: int | None) -> None:
    n_factions = int(n_factions)
    if n_factions not in B.ACTIVE_SLOTS:
        raise ValueError("O número de nações deve estar entre 2 e 6.")
    if not turn_minutes or float(turn_minutes) <= 0:
        raise ValueError("A duração do turno deve ser positiva (em minutos).")
    if int(max_turns) < 1:
        raise ValueError("O número de turnos deve ser pelo menos 1.")
    if seed is None:
        seed = int(np.random.SeedSequence().entropy % (2 ** 63))
    game.seed = int(seed)
    game.rng = np.random.Generator(np.random.PCG64(game.seed))
    rng = game.rng

    game.n_factions = n_factions
    game.turn_ms = int(round(float(turn_minutes) * 60000))
    game.max_turns = int(max_turns)
    game.status = "lobby"
    game.turn = 0

    slots = B.ACTIVE_SLOTS[n_factions]
    home = {h["slot"]: h for h in game.map["home_slots"]}
    game.order = [B.NATIONS[i]["id"] for i in range(n_factions)]
    game.slot_fid = {}
    for i, slot in enumerate(slots):
        game.slot_fid[str(slot)] = game.order[i]

    # território: dono e tropas
    game.owner = {t: None for t in game.order_tids}
    game.troops = {t: 0 for t in game.order_tids}
    for slot, fid in ((int(s), f) for s, f in game.slot_fid.items()):
        h = home[slot]
        for t in h["territories"]:
            game.owner[t] = fid
            game.troops[t] = B.START_TROOPS_CAPITAL if t == h["capital"] else B.START_TROOPS_OTHER
    lo, hi = B.NEUTRAL_MILITIA
    for t in game.order_tids:
        if game.owner[t] is None:
            game.troops[t] = int(rng.integers(lo, hi + 1))

    # nações
    taken: set[str] = set()
    game.factions = {}
    for i, fid in enumerate(game.order):
        f = Faction(id=fid, slot=slots[i])
        f.password = make_password(rng, taken)
        f.stock = dict(B.START_STOCK)
        f.morale = float(B.START_MORALE)
        betas = [float(v) for v in morale.random_betas(rng)]
        # o intercepto sorteado pelo motor (+1 a +3) saturaria a moral em 100 em poucos turnos;
        # aqui ele é rebaixado para que a moral dependa das decisões do Governo
        betas[0] = float(rng.uniform(B.BETA0_RANGE[0], B.BETA0_RANGE[1]))
        f.betas = betas
        f.A_clean = (B.A_SCALE * economy.random_A(rng)).tolist()
        game.factions[fid] = f
    for fid in game.order:
        f = game.factions[fid]
        nominal = game.nominal_x(fid)
        jitter = rng.uniform(0.92, 1.08, size=3)
        f.last_x = [float(v) for v in nominal * jitter]

    # clima: uma cadeia de Markov oculta por região, com histórico de 44 observações
    game.climate = {}
    game.weather = {}
    for r in B.REGIONS:
        P = weather.random_transition_matrix(rng)
        diary = weather.simulate(P, int(rng.integers(0, 3)), B.DIARY_LENGTH, rng)
        game.climate[r] = {"P": P.tolist(), "diary": [int(v) for v in diary], "next": int(diary[-1])}
        game.weather[r] = int(diary[-1])
