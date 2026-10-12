"""Validação das ordens, preparação do turno e resolução (DESIGN §4, na ordem prescrita).

Ordem da resolução: (1) congela as ordens; (2) Governo: transferências, pactos, política;
(3) Intendência: produção; (4) recrutamento; (5) bombardeios; (6) movimentos e batalhas;
(7) manutenção; (8) moral; (9) capitulação, PV, fim de jogo; (10) manchetes e preparo do próximo turno.
"""

from __future__ import annotations

import math

import numpy as np

from app.engine import cipher, combat, economy, geo, morale, weather
from app.game import balance as B
from app.game import dossiers, events as EV
from app.game import news as N
from app.game.model import deep, ev, num, signed

SEC = B.SECTORS


# =============================================================================================
# Validação das ordens (no envio)
# =============================================================================================
def _as_number(v, name, errors, minimum=0.0):
    if isinstance(v, bool):
        errors.append(f"{name}: valor inválido.")
        return None
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        try:
            v = float(s)
        except ValueError:
            errors.append(f"{name}: «{v}» não é um número.")
            return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        errors.append(f"{name}: valor inválido.")
        return None
    if not math.isfinite(x):
        errors.append(f"{name}: valor inválido.")
        return None
    if x < minimum:
        errors.append(f"{name}: não pode ser negativo.")
        return None
    return x


def _as_int(v, name, errors, minimum=0, maximum=None):
    x = _as_number(v, name, errors, minimum=float(minimum))
    if x is None:
        return None
    if abs(x - round(x)) > 1e-9:
        errors.append(f"{name}: deve ser um número inteiro.")
        return None
    x = int(round(x))
    if maximum is not None and x > maximum:
        errors.append(f"{name}: no máximo {maximum}.")
        return None
    return x


def validate_orders(game, fid: str, section: str, payload) -> tuple[list, list, dict | None]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ["A ordem deve ser um objeto JSON."], [], None
    f = game.factions[fid]
    fn = {"intendencia": _v_intendencia, "operacoes": _v_operacoes,
          "inteligencia": _v_inteligencia, "governo": _v_governo}[section]
    norm = fn(game, f, payload, errors, warnings)
    if errors:
        return errors, warnings, None
    return errors, warnings, norm


def _v_intendencia(game, f, payload, errors, warnings):
    prod_in = payload.get("production")
    if prod_in is None:
        prod_in = {}
    if not isinstance(prod_in, dict):
        errors.append("production deve ser um objeto {ALI, ACO, COM}.")
        prod_in = {}
    prod = {}
    cap = game.capacity(f.id)
    for s in SEC:
        v = _as_number(prod_in.get(s, 0), f"Produção de {s}", errors)
        prod[s] = 0.0 if v is None else round(v, 2)
        if v is not None and v > cap[s] + 1e-9:
            errors.append(f"Produção de {s} ({num(v)}) excede a capacidade ({num(cap[s])}).")
    recruit = _as_int(payload.get("recruit", 0) or 0, "Recrutamento", errors)
    recruit = 0 if recruit is None else recruit
    if errors:
        return None
    x = np.array([prod[s] for s in SEC])
    need = float(np.dot([B.LABOR[s] for s in SEC], x))
    W = game.workforce(f.id)
    if need > W + 1e-9:
        warnings.append(f"Mão de obra insuficiente: a produção usa {num(need)} de {num(W)} disponíveis; "
                        f"será reduzida a {num(100 * W / need, 0)}% na resolução (a jornada do Governo pode mudar W).")
    if x.sum() <= 0:
        warnings.append("Nenhuma produção ordenada: o estoque de Alimento será consumido e a nação pode entrar em crise.")
    if recruit:
        A = np.array(f.A_prev, float)
        net = economy.net_output(A, x)
        est = {s: f.stock[s] + float(net[i]) for i, s in enumerate(SEC)}
        short = [s for s in SEC if est[s] < recruit * B.RECRUIT_COST[s] - 1e-9]
        if short:
            warnings.append("Estoque estimado insuficiente para recrutar " + str(recruit) + " batalhões (falta "
                            + ", ".join(short) + "): o recrutamento será reduzido proporcionalmente.")
    return {"production": prod, "recruit": recruit}


def _v_operacoes(game, f, payload, errors, warnings):
    moves_in = payload.get("moves")
    if moves_in is None:
        moves_in = []
    if not isinstance(moves_in, list):
        return errors.append("moves deve ser uma lista de ordens {from, to, troops}.") or None
    if len(moves_in) > B.MAX_MOVES:
        errors.append(f"No máximo {B.MAX_MOVES} ordens de movimento por turno.")
        return None
    out = []
    used: dict[str, int] = {}
    com_cost = 0.0
    for i, mv in enumerate(moves_in, 1):
        tag = f"Movimento {i}"
        if not isinstance(mv, dict):
            errors.append(f"{tag}: formato inválido.")
            continue
        a, b = str(mv.get("from", "")).strip().upper(), str(mv.get("to", "")).strip().upper()
        n = _as_int(mv.get("troops", 0), f"{tag}: batalhões", errors, minimum=1)
        if a not in game.TER or b not in game.TER:
            errors.append(f"{tag}: território inexistente ({a or '?'} → {b or '?'}).")
            continue
        if a == b:
            errors.append(f"{tag}: origem e destino são o mesmo território.")
            continue
        if game.owner[a] != f.id:
            errors.append(f"{tag}: {a} ({game.tname(a)}) não é um território seu.")
            continue
        if b not in game.adjacent(a):
            errors.append(f"{tag}: {b} ({game.tname(b)}) não é vizinho de {a} ({game.tname(a)}).")
            continue
        if n is None:
            continue
        used[a] = used.get(a, 0) + n
        if used[a] > game.troops[a]:
            errors.append(f"{tag}: {a} tem apenas {game.troops[a]} batalhões (pedidos {used[a]} no total).")
            continue
        target_owner = game.owner[b]
        if target_owner and target_owner != f.id and f.has_pact_with(target_owner, game.turn):
            errors.append(f"{tag}: pacto de não agressão com {game.factions[target_owner].short} impede o ataque a {b}.")
            continue
        sea = game.is_sea_move(a, b)
        com_cost += n * (B.SEA_MOVE_COM if sea else B.MOVE_COM)
        if sea:
            warnings.append(f"{tag}: rota marítima ({a} → {b}) custa {B.SEA_MOVE_COM} COM por batalhão e é "
                            "cancelada em caso de tempestade.")
        out.append({"from": a, "to": b, "troops": n})
    if errors:
        return None
    for t, n in used.items():
        if n >= game.troops[t]:
            warnings.append(f"{t} ({game.tname(t)}) ficará sem guarnição.")
    if com_cost > f.stock["COM"] + 1e-9:
        warnings.append(f"Custo estimado de {num(com_cost)} COM excede o estoque ({num(f.stock['COM'])}): os "
                        "movimentos serão reduzidos proporcionalmente (a produção do turno pode ajudar).")
    return {"moves": out}


def _v_inteligencia(game, f, payload, errors, warnings):
    b = payload.get("bombard")
    if b in (None, "", False):
        return {"bombard": None}
    b = str(b).strip().upper()
    loc = f.bonuses.get("depot_located")
    if b not in game.TER:
        errors.append(f"Território inexistente: {b}.")
        return None
    if not loc or loc.get("territory") != b:
        errors.append(f"Nenhum depósito localizado em {b} neste turno. Resolva o desafio de radiogoniometria primeiro.")
        return None
    own = game.owner[b]
    if own == f.id:
        errors.append("O depósito localizado pertence à sua própria nação.")
        return None
    if own and f.has_pact_with(own, game.turn):
        errors.append(f"Pacto de não agressão com {game.factions[own].short} impede o bombardeio.")
        return None
    if f.stock["COM"] < B.BOMBARD_COM:
        warnings.append(f"Combustível insuficiente ({num(f.stock['COM'])} COM) para o bombardeio ({B.BOMBARD_COM} COM).")
    return {"bombard": b}


def _v_governo(game, f, payload, errors, warnings):
    pol = f.policy
    racao = _as_int(payload.get("racao", pol["racao"]), "Ração", errors, 0, 2)
    prop = _as_int(payload.get("propaganda", 0) or 0, "Propaganda", errors, 0, B.PROPAGANDA_MAX)
    horas = _as_int(payload.get("horas", pol["horas"]), "Jornada", errors, 0)
    if horas is not None and horas not in B.HOURS_MULT:
        errors.append("Jornada: use 8, 10 ou 12 horas.")
        horas = None
    transfers_in = payload.get("transfers") or []
    if not isinstance(transfers_in, list):
        errors.append("transfers deve ser uma lista.")
        transfers_in = []
    transfers = []
    totals = {s: 0.0 for s in SEC}
    for i, t in enumerate(transfers_in, 1):
        tag = f"Transferência {i}"
        if not isinstance(t, dict):
            errors.append(f"{tag}: formato inválido.")
            continue
        to = str(t.get("to", "")).strip().upper()
        if to not in game.factions or to == f.id:
            errors.append(f"{tag}: nação destinatária inválida ({to or '?'}).")
            continue
        if game.factions[to].capitulated:
            errors.append(f"{tag}: {game.factions[to].short} já capitulou.")
            continue
        amt = {}
        for s in SEC:
            v = _as_number(t.get(s, 0) or 0, f"{tag}: {s}", errors)
            amt[s] = 0.0 if v is None else round(v, 2)
            totals[s] += amt[s]
        if sum(amt.values()) > 0:
            transfers.append({"to": to, **amt})
    propose = _fid_list(game, f, payload.get("pact_propose"), "Pacto proposto", errors)
    denounce = _fid_list(game, f, payload.get("pact_denounce"), "Pacto denunciado", errors)
    for g in denounce:
        if not f.has_pact_with(g, game.turn):
            errors.append(f"Não há pacto ativo com {game.factions[g].short} para denunciar.")
    if errors:
        return None
    for s in SEC:
        if totals[s] > f.stock[s] + 1e-9:
            warnings.append(f"Transferência de {s} ({num(totals[s])}) excede o estoque ({num(f.stock[s])}): será reduzida.")
    if prop and prop > f.stock["ACO"]:
        warnings.append(f"Propaganda custa {prop} ACO e o estoque é {num(f.stock['ACO'])}: o nível será reduzido se faltar.")
    keep = []
    for g in propose:
        if f.has_pact_with(g, game.turn):
            warnings.append(f"Já existe pacto com {game.factions[g].short}.")
        else:
            keep.append(g)
    return {"racao": racao, "propaganda": prop, "horas": horas, "transfers": transfers,
            "pact_propose": keep, "pact_denounce": denounce}


def _fid_list(game, f, raw, tag, errors) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append(f"{tag}: deve ser uma lista de siglas de nações.")
        return []
    out = []
    for g in raw:
        g = str(g).strip().upper()
        if g not in game.factions or g == f.id:
            errors.append(f"{tag}: nação inválida ({g or '?'}).")
        elif game.factions[g].capitulated:
            errors.append(f"{tag}: {game.factions[g].short} já capitulou.")
        elif g not in out:
            out.append(g)
    return out


# =============================================================================================
# Preparação de um turno
# =============================================================================================
def new_cipher_key(rng) -> list:
    while True:
        K = cipher.random_key(rng, 2)
        if not cipher.encrypt("URGENTE ", K).startswith(" "):
            return [[int(v) for v in row] for row in K]


def _turn_matrix(A_clean, damage: float) -> list:
    A = np.array(A_clean, float)
    if damage:
        A = A.copy()
        A[np.diag_indices_from(A)] += damage
        sums = A.sum(axis=0)
        for j in range(A.shape[1]):
            if sums[j] > 0.85:
                A[:, j] *= 0.85 / sums[j]
    return A.tolist()


def prepare_turn(game, now_ms: int) -> list[dict]:
    """Sorteia o que é oculto no turno `game.turn` (chaves, clima, A, depósitos), roda o evento e gera dossiês."""
    rng = game.rng
    turn = game.turn
    # chaves de cifra (trocam a cada CIPHER_KEY_TURNS turnos)
    gen = (turn - 1) // B.CIPHER_KEY_TURNS
    for fid in game.order:
        f = game.factions[fid]
        if f.cipher_gen != gen:
            f.cipher_key = new_cipher_key(rng)
            f.cipher_gen = gen
    # clima pré-sorteado
    for r in B.REGIONS:
        c = game.climate[r]
        c["next"] = int(weather.simulate(c["P"], int(game.weather[r]), 1, rng)[0])
    # matrizes técnicas
    for fid in game.order:
        f = game.factions[fid]
        f.A_prev = deep(f.A_turn) if f.A_turn else deep(f.A_clean)
        f.A_clean = economy.perturb_A(f.A_clean, rng, scale=B.A_PERTURB_SCALE).tolist()
        f.A_turn = _turn_matrix(f.A_clean, f.a_damage_next)
        f.a_damage_next = 0.0
        f.orders = {s: None for s in B.SECTIONS}
        f.orders_at = {}
        f.bonuses = {"productivity": False, "weather_revealed": False, "depot_located": None}
    # depósitos de suprimentos (realocados a cada turno)
    game.depots = {}
    for fid in game.order:
        owned = [t for t in game.order_tids if game.owner[t] == fid]
        if game.factions[fid].capitulated or not owned:
            continue
        t = owned[int(rng.integers(0, len(owned)))]
        x, y = geo.random_point_in_polygon(game.TER[t]["polygon"], rng)
        game.depots[fid] = {"territory": t, "point": [round(float(x), 1), round(float(y), 1)]}
    out = []
    # evento global (a partir do turno 2)
    item = EV.roll_event(game)
    if item:
        game.add_news(item)
        out.append(ev("public", "news", item))
    out.extend(dossiers.build_all(game, now_ms))
    return out


# =============================================================================================
# Resolução
# =============================================================================================
def _largest_remainder(total: int, weights: dict[str, int]) -> dict[str, int]:
    s = sum(weights.values())
    if s <= 0 or total <= 0:
        return {k: 0 for k in weights}
    raw = {k: total * w / s for k, w in weights.items()}
    out = {k: int(math.floor(v)) for k, v in raw.items()}
    rest = total - sum(out.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - out[k]), k))[:rest]:
        out[k] += 1
    return out


def resolve(game, now_ms: int) -> list[dict]:
    T = game.turn
    rng = game.rng
    F = game.factions
    order = list(game.order)
    alive = [f for f in order if not F[f].capitulated]
    rep: dict[str, list[str]] = {f: [] for f in order}
    news: list[dict] = []
    owner0 = dict(game.owner)
    troops0 = dict(game.troops)
    stock0 = {f: dict(F[f].stock) for f in order}
    morale0 = {f: F[f].morale for f in order}
    battle_losses = {f: 0 for f in order}
    gained = {f: 0 for f in order}
    lost = {f: 0 for f in order}
    starved = {f: False for f in order}
    denounced = {f: [] for f in order}
    battles: list[dict] = []
    moves_pub: list[dict] = []
    captures: list[dict] = []

    # --- clima desta resolução (pré-sorteado no preparo do turno) -------------------------------
    wx = {r: int(game.climate[r]["next"]) for r in B.REGIONS}
    for r in B.REGIONS:
        game.weather[r] = wx[r]
        game.climate[r]["diary"].append(wx[r])
    wline = "Clima: " + ", ".join(f"{dossiers.region_name(game, r)} {B.WEATHER_NAMES[wx[r]]}" for r in B.REGIONS) + "."
    for f in alive:
        rep[f].append(wline)
    severe = [r for r in B.REGIONS if wx[r] == 2]
    rainy = [r for r in B.REGIONS if wx[r] == 1]
    wn = N.weather(rng, T, severe, rainy)
    if wn:
        news.append(wn)

    # eventos ativos neste turno
    for fid, lines in game.event_lines.items():
        rep.setdefault(fid, []).extend(lines)
    game.event_lines = {}

    # --- 1. congela as ordens ------------------------------------------------------------------
    orders = {f: deep(F[f].orders) for f in alive}

    # --- 2. Governo ------------------------------------------------------------------------------
    pol_prev = {f: dict(F[f].policy) for f in alive}
    for fid in alive:
        o = orders[fid].get("governo")
        pol = F[fid].policy
        if o:
            F[fid].policy = {"racao": o["racao"], "propaganda": o["propaganda"], "horas": o["horas"]}
        else:
            F[fid].policy = {"racao": pol["racao"], "propaganda": 0, "horas": pol["horas"]}
            rep[fid].append("Nenhuma ordem do Governo: ração e jornada mantidas, sem propaganda.")
    # racionamento (notícia quando agrava)
    for fid in alive:
        if F[fid].policy["racao"] > pol_prev[fid]["racao"]:
            news.append(N.rationing(rng, T, F[fid].short, F[fid].policy["racao"]))
    # pactos expirados
    for fid in order:
        F[fid].pacts = [p for p in F[fid].pacts if p["until_turn"] >= T]
    # transferências (simultâneas, escaladas pelo estoque)
    sent = {f: {s: 0.0 for s in SEC} for f in alive}
    plan = []
    for fid in alive:
        o = orders[fid].get("governo") or {}
        tr = o.get("transfers") or []
        totals = {s: sum(t[s] for t in tr) for s in SEC}
        scale = {s: (min(1.0, F[fid].stock[s] / totals[s]) if totals[s] > 1e-12 else 1.0) for s in SEC}
        for t in tr:
            amt = {s: math.floor(t[s] * scale[s] * 100 + 1e-9) / 100 for s in SEC}
            if F[t["to"]].capitulated:
                continue
            plan.append((fid, t["to"], amt))
            for s in SEC:
                sent[fid][s] += amt[s]
        if any(scale[s] < 1.0 for s in SEC if totals[s] > 0):
            rep[fid].append("Transferências reduzidas: estoque insuficiente.")
    for fid, to, amt in plan:
        if sum(amt.values()) <= 0:
            continue
        for s in SEC:
            F[fid].stock[s] -= amt[s]
            F[to].stock[s] += amt[s]
        txt = ", ".join(f"{s} {num(v)}" for s, v in amt.items() if v > 0)
        rep[fid].append(f"Transferência a {F[to].short}: {txt}.")
        rep[to].append(f"Recebido de {F[fid].short}: {txt}.")
    # denúncias de pacto (o pacto vale até o fim do turno)
    for fid in alive:
        o = orders[fid].get("governo") or {}
        for g in o.get("pact_denounce") or []:
            if F[fid].has_pact_with(g, T):
                denounced[fid].append(g)
                rep[fid].append(f"Pacto com {F[g].short} denunciado (encerra ao fim do turno; moral {B.DENOUNCE_MORALE}).")
                rep[g].append(f"{F[fid].short} denunciou o pacto de não agressão (encerra ao fim do turno).")
                news.append(N.pact_denounced(rng, T, F[fid].short, F[g].short))
    # propostas de pacto
    game.proposals = [p for p in game.proposals if p["turn"] >= T - 1]
    now_prop = set()
    for fid in alive:
        o = orders[fid].get("governo") or {}
        for g in o.get("pact_propose") or []:
            now_prop.add((fid, g))
    for fid, g in sorted(now_prop, key=lambda p: (order.index(p[0]), order.index(p[1]))):
        if F[g].capitulated or F[fid].has_pact_with(g, T):
            continue
        pending = any(p["from"] == g and p["to"] == fid for p in game.proposals)
        if (g, fid) in now_prop or pending:
            until = T + B.PACT_TURNS - 1
            F[fid].pacts.append({"with": g, "until_turn": until})
            F[g].pacts.append({"with": fid, "until_turn": until})
            game.proposals = [p for p in game.proposals
                              if not ({p["from"], p["to"]} == {fid, g})]
            now_prop.discard((g, fid))
            rep[fid].append(f"Pacto de não agressão com {F[g].short} firmado até o turno {until}.")
            rep[g].append(f"Pacto de não agressão com {F[fid].short} firmado até o turno {until}.")
            news.append(N.pact_formed(rng, T, F[fid].short, F[g].short, until))
        elif not any(p["from"] == fid and p["to"] == g for p in game.proposals):
            game.proposals.append({"from": fid, "to": g, "turn": T})
            rep[fid].append(f"Proposta de pacto enviada a {F[g].short}.")

    # --- 3. Intendência: produção -----------------------------------------------------------------
    A_of = {f: np.array(F[f].A_turn, float) for f in alive}
    gross = {}
    for fid in alive:
        f = F[fid]
        o = orders[fid].get("intendencia")
        x = np.array([(o or {}).get("production", {}).get(s, 0.0) for s in SEC], float) if o else np.zeros(3)
        if not o:
            rep[fid].append("Nenhuma ordem da Intendência: nada foi produzido.")
        cap = game.capacity(fid)
        for i, s in enumerate(SEC):
            if x[i] > cap[s] + 1e-9:
                rep[fid].append(f"Capacidade excedida em {s}: produção limitada a {num(cap[s])}.")
                x[i] = cap[s]
        W = game.workforce(fid)
        need = float(np.dot([B.LABOR[s] for s in SEC], x))
        if need > W + 1e-9:
            k = W / need
            x = x * k
            rep[fid].append(f"Mão de obra insuficiente ({num(need)} necessários, {num(W)} disponíveis): produção "
                            f"reduzida a {num(100 * k, 0)}%.")
        for i, s in enumerate(SEC):
            m = game.effect_mult(fid, "prod_" + s)
            if abs(m - 1) > 1e-9:
                x[i] *= m
        if f.bonuses.get("productivity"):
            x = x * B.PRODUCTIVITY_BONUS
            rep[fid].append("Plano aprovado: produtividade +10% nesta jornada.")
        y = (np.eye(3) - A_of[fid]) @ x
        for i, s in enumerate(SEC):
            f.stock[s] += float(y[i])
            if f.stock[s] < 0:
                rep[fid].append(f"Insumos insuficientes em {s}: o estoque foi zerado (produção desbalanceada).")
                f.stock[s] = 0.0
        f.last_x = [float(v) for v in x]
        gross[fid] = x
        if x.sum() > 0:
            rep[fid].append("Produção bruta: " + ", ".join(f"{s} {num(x[i])}" for i, s in enumerate(SEC))
                            + ". Líquida: " + ", ".join(f"{s} {signed(y[i])}" for i, s in enumerate(SEC)) + ".")
    # propaganda (custa ACO; reduz se faltar)
    prop_eff = {}
    for fid in alive:
        want = F[fid].policy["propaganda"]
        eff = int(min(want, math.floor(F[fid].stock["ACO"] + 1e-9)))
        F[fid].stock["ACO"] -= eff
        prop_eff[fid] = eff
        if want and eff < want:
            rep[fid].append(f"Propaganda reduzida de {want} para {eff} por falta de Aço.")
        elif eff:
            rep[fid].append(f"Propaganda nível {eff} (custo {eff} ACO).")

    # --- 4. Recrutamento --------------------------------------------------------------------------
    for fid in alive:
        o = orders[fid].get("intendencia") or {}
        want = int(o.get("recruit", 0) or 0)
        if want <= 0:
            continue
        f = F[fid]
        cap_res = int(math.floor(min(f.stock[s] / B.RECRUIT_COST[s] for s in SEC) + 1e-9))
        n = max(0, min(want, cap_res))
        if n < want:
            lim = min(SEC, key=lambda s: f.stock[s] / B.RECRUIT_COST[s])
            rep[fid].append(f"Recrutamento reduzido de {want} para {n} batalhões (falta {lim}).")
        if n > 0:
            for s in SEC:
                f.stock[s] -= n * B.RECRUIT_COST[s]
            where = game.recruit_site(fid)
            if where:
                game.troops[where] += n
                rep[fid].append(f"Recrutamento: +{n} batalhões em {game.tname(where)} "
                                f"(custo {B.RECRUIT_COST['ALI'] * n} ALI, {B.RECRUIT_COST['ACO'] * n} ACO, "
                                f"{B.RECRUIT_COST['COM'] * n} COM).")
            else:
                rep[fid].append("Recrutamento cancelado: nenhum território para receber os batalhões.")
                for s in SEC:
                    f.stock[s] += n * B.RECRUIT_COST[s]

    # --- 5. Inteligência: bombardeios ---------------------------------------------------------------
    for fid in alive:
        o = orders[fid].get("inteligencia") or {}
        tgt = o.get("bombard")
        if not tgt:
            continue
        f = F[fid]
        loc = f.bonuses.get("depot_located")
        victim = game.owner.get(tgt)
        if not loc or loc.get("territory") != tgt:
            rep[fid].append(f"Bombardeio em {tgt} cancelado: depósito não localizado.")
            continue
        if f.stock["COM"] < B.BOMBARD_COM:
            rep[fid].append(f"Bombardeio em {tgt} cancelado: Combustível insuficiente.")
            continue
        if victim is None or victim == fid or F[victim].capitulated or F[fid].has_pact_with(victim, T):
            rep[fid].append(f"Bombardeio em {tgt} cancelado: alvo inválido (sem dono inimigo ou pacto vigente).")
            continue
        f.stock["COM"] -= B.BOMBARD_COM
        v = F[victim]
        big = max(SEC, key=lambda s: (v.stock[s], s))
        loss = round(v.stock[big] * B.BOMBARD_STOCK_LOSS, 2)
        v.stock[big] -= loss
        v.a_damage_next += B.BOMBARD_A_DAMAGE
        rep[fid].append(f"Bombardeio em {game.tname(tgt)}: {F[victim].short} perdeu {num(loss)} de {big}.")
        rep[victim].append(f"Bombardeio inimigo atingiu nosso depósito: −{num(loss)} de {big}; a matriz técnica piorará.")
        news.append(N.bombard(rng, T, F[fid].short, F[victim].short, game.tname(tgt)))

    # --- 6. Operações: movimentos e batalhas -----------------------------------------------------
    avail = dict(game.troops)
    valid_moves: list[dict] = []
    for fid in alive:
        o = orders[fid].get("operacoes") or {}
        mvs = o.get("moves") or []
        f = F[fid]
        cand = []
        for mv in mvs:
            a, b, n = mv["from"], mv["to"], int(mv["troops"])
            if game.owner.get(a) != fid:
                rep[fid].append(f"Ordem {a}→{b} ignorada: {a} já não é nosso território.")
                continue
            n = min(n, avail[a])
            if n <= 0:
                rep[fid].append(f"Ordem {a}→{b} ignorada: não há batalhões disponíveis em {a}.")
                continue
            if b not in game.adjacent(a):
                rep[fid].append(f"Ordem {a}→{b} ignorada: territórios não são vizinhos.")
                continue
            tgt_owner = game.owner[b]
            if tgt_owner and tgt_owner != fid and F[fid].has_pact_with(tgt_owner, T):
                rep[fid].append(f"Ordem {a}→{b} cancelada: pacto de não agressão com {F[tgt_owner].short}.")
                continue
            sea = game.is_sea_move(a, b)
            if sea and (wx[game.TER[a]["climate"]] == 2 or wx[game.TER[b]["climate"]] == 2):
                rep[fid].append(f"Travessia {a}→{b} cancelada: tempestade fechou o mar.")
                continue
            avail[a] -= n
            cand.append({"from": a, "to": b, "troops": n, "sea": sea, "faction": fid})
        if not cand:
            continue
        mult = game.effect_mult(fid, "move_cost")
        cost = sum(m["troops"] * (B.SEA_MOVE_COM if m["sea"] else B.MOVE_COM) * mult for m in cand)
        if cost > f.stock["COM"] + 1e-9:
            k = f.stock["COM"] / cost
            newc = []
            for m in cand:
                cut = int(math.floor(m["troops"] * k + 1e-9))
                avail[m["from"]] += m["troops"] - cut
                if cut > 0:
                    m = dict(m, troops=cut)
                    newc.append(m)
            rep[fid].append(f"Combustível insuficiente: movimentos reduzidos a {num(100 * k, 0)}%.")
            cand = newc
            cost = sum(m["troops"] * (B.SEA_MOVE_COM if m["sea"] else B.MOVE_COM) * mult for m in cand)
        f.stock["COM"] = max(0.0, f.stock["COM"] - cost)
        if cand:
            rep[fid].append(f"Movimentos executados: {sum(m['troops'] for m in cand)} batalhões (custo {num(cost)} COM).")
        valid_moves.extend(cand)

    # tira as tropas das origens; reforços chegam antes das batalhas
    groups: dict[str, dict[str, dict]] = {}
    for m in valid_moves:
        game.troops[m["from"]] -= m["troops"]
    for m in valid_moves:
        moves_pub.append({"from": m["from"], "to": m["to"], "faction": m["faction"], "troops": m["troops"]})
        if game.owner[m["to"]] == m["faction"]:
            game.troops[m["to"]] += m["troops"]
        else:
            g = groups.setdefault(m["to"], {}).setdefault(m["faction"], {"origins": {}, "total": 0})
            g["origins"][m["from"]] = g["origins"].get(m["from"], 0) + m["troops"]
            g["total"] += m["troops"]

    retreats: list[tuple[str, str, int]] = []
    for tid in sorted(groups):
        holder = game.owner[tid]
        htroops = game.troops[tid]
        glist = sorted(groups[tid].items(), key=lambda kv: (-kv[1]["total"], order.index(kv[0])))
        for afid, g in glist:
            origins = g["origins"]
            A0 = g["total"]
            if holder == afid:
                for o_, n_ in origins.items():
                    retreats.append((afid, o_, n_))
                continue
            if holder and F[afid].has_pact_with(holder, T):
                rep[afid].append(f"Ataque a {tid} cancelado: pacto de não agressão com {F[holder].short}.")
                for o_, n_ in origins.items():
                    retreats.append((afid, o_, n_))
                continue
            main_origin = max(origins, key=lambda k: (origins[k], k))
            B0 = htroops
            holder_short = F[holder].short if holder else "milícia neutra"
            if B0 <= 0:
                res, att_after, def_after = "captured", A0, 0
            else:
                w_mult = sum(n * combat.WEATHER_ATTACK[wx[game.TER[o_]["climate"]]] for o_, n in origins.items()) / A0
                alpha = (combat.effectiveness(F[afid].morale, role="attack") * w_mult
                         * game.effect_mult(afid, "attack"))
                hm = F[holder].morale if holder else B.NEUTRAL_MORALE
                beta = combat.effectiveness(hm, terrain=game.TER[tid]["terrain"], role="defense")
                alpha *= math.exp(B.BATTLE_NOISE_SIGMA * float(rng.normal()))
                beta *= math.exp(B.BATTLE_NOISE_SIGMA * float(rng.normal()))
                r = combat.lanchester(float(A0), float(B0), alpha, beta, T=B.BATTLE_T)
                if r["winner"] == "attacker":
                    res, att_after, def_after = "captured", max(1, int(round(r["a_final"]))), 0
                elif r["winner"] == "defender":
                    res, att_after, def_after = "repelled", 0, max(1, int(round(r["b_final"])))
                else:
                    res = "stalemate"
                    att_after = int(round(r["a_final"]))
                    def_after = max(1, int(round(r["b_final"])))
            battles.append({
                "from": main_origin, "to": tid, "attacker": afid, "defender": holder,
                "att_before": A0, "def_before": B0, "att_after": att_after, "def_after": def_after,
                "result": res, "terrain": game.TER[tid]["terrain"],
                "origins": dict(origins),
            })
            battle_losses[afid] += A0 - att_after
            if holder:
                battle_losses[holder] += B0 - def_after
            a_short = F[afid].short
            tn = game.tname(tid)
            if res == "captured":
                captures.append({"tid": tid, "by": afid, "from": holder})
                is_cap = game.is_capital_of_someone(tid)
                news.append(N.capture(rng, T, a_short, F[holder].short if holder else None, tn, bool(is_cap),
                                      A0, B0, att_after, (A0 - att_after) + (B0 - 0)))
                rep[afid].append(f"VITÓRIA em {tn} ({tid}): {A0} atacantes contra {B0} defensores; sobraram "
                                 f"{att_after}. Território conquistado.")
                if holder:
                    rep[holder].append(f"DERROTA em {tn} ({tid}): {B0} defensores contra {A0} atacantes de {a_short}. "
                                       "Território perdido.")
                gained[afid] += 1
                if holder:
                    lost[holder] += 1
                holder, htroops = afid, att_after
            elif res == "repelled":
                news.append(N.repelled(rng, T, a_short, F[holder].short if holder else None, tn, A0, B0, def_after))
                rep[afid].append(f"DERROTA em {tn} ({tid}): {A0} atacantes contra {B0} defensores; ataque repelido, "
                                 "todos os atacantes perdidos.")
                if holder:
                    rep[holder].append(f"Defesa de {tn} ({tid}) bem-sucedida contra {a_short}: restam {def_after} de {B0}.")
                htroops = def_after
            else:
                news.append(N.stalemate(rng, T, a_short, F[holder].short if holder else None, tn, att_after, def_after))
                rep[afid].append(f"Combate indeciso em {tn} ({tid}): recuamos com {att_after} de {A0}.")
                if holder:
                    rep[holder].append(f"Combate indeciso em {tn} ({tid}) contra {a_short}: restam {def_after} de {B0}.")
                htroops = def_after
                for o_, n_ in _largest_remainder(att_after, origins).items():
                    retreats.append((afid, o_, n_))
        game.owner[tid] = holder
        game.troops[tid] = htroops
    for afid, o_, n_ in retreats:
        if n_ <= 0:
            continue
        if game.owner.get(o_) == afid:
            game.troops[o_] += n_
        else:
            rep[afid].append(f"{n_} batalhões em retirada perderam-se: {o_} já não é nosso.")
            battle_losses[afid] += n_

    # --- 7. Manutenção --------------------------------------------------------------------------
    for fid in alive:
        f = F[fid]
        tr = game.troops_total(fid)
        mil = B.UPKEEP_ALI_PER_BATTALION * tr
        civil = B.CIVIL_ALI[f.policy["racao"]] + game.effect_add(fid, "civil_ali")
        need = mil + civil
        if f.stock["ALI"] + 1e-9 >= need:
            f.stock["ALI"] = max(0.0, f.stock["ALI"] - need)
            rep[fid].append(f"Manutenção: −{num(mil)} ALI (tropas) −{num(civil)} ALI (civil).")
        else:
            f.stock["ALI"] = 0.0
            starved[fid] = True
            loss = int(math.ceil(B.STARVATION_ATTRITION * tr))
            removed = game.attrition(fid, loss)
            battle_stub = removed
            rep[fid].append(f"FOME: faltou Alimento (precisávamos de {num(need)}). Moral {B.STARVATION_MORALE} e "
                            f"{battle_stub} batalhões desertaram.")
            news.append(N.starvation(rng, T, F[fid].short))

    # --- 8. Moral ---------------------------------------------------------------------------------
    for fid in alive:
        f = F[fid]
        pol = f.policy
        saldo = max(-3, min(3, gained[fid] - lost[fid]))
        feats = {"racao": pol["racao"], "propaganda": prop_eff[fid], "horas_extra": pol["horas"] - 8,
                 "baixas": battle_losses[fid] / 10.0, "saldo_territorial": saldo}
        d = morale.delta_morale(f.betas, feats, rng, noise=1.0)
        reasons = []
        if pol["racao"] == 1:
            reasons.append("ração reduzida")
        elif pol["racao"] == 2:
            reasons.append("ração severa")
        if prop_eff[fid]:
            reasons.append(f"propaganda {prop_eff[fid]}")
        if pol["horas"] > 8:
            reasons.append(f"jornada de {pol['horas']} h")
        if battle_losses[fid] > 0:
            reasons.append(f"{battle_losses[fid]} baixas")
        if saldo > 0:
            reasons.append("territórios conquistados")
        elif saldo < 0:
            reasons.append("territórios perdidos")
        extra = 0.0
        cap = game.capital_tid(fid)
        if owner0.get(cap) == fid and game.owner.get(cap) != fid:
            extra += B.CAPITAL_LOST_MORALE
            reasons.append(f"capital perdida ({B.CAPITAL_LOST_MORALE})")
            rep[fid].append("A CAPITAL CAIU: moral −15.")
        if starved[fid]:
            extra += B.STARVATION_MORALE
            reasons.append(f"fome ({B.STARVATION_MORALE})")
        if denounced[fid]:
            extra += B.DENOUNCE_MORALE * len(denounced[fid])
            reasons.append(f"pacto denunciado ({B.DENOUNCE_MORALE * len(denounced[fid])})")
        f.morale = float(min(100.0, max(0.0, f.morale + d + extra)))
        rep[fid].append(f"Moral: {num(morale0[fid])} → {num(f.morale)} ({signed(f.morale - morale0[fid])})"
                        + (": " + ", ".join(reasons) + "." if reasons else "."))
    # denúncias efetivam-se: pactos encerrados
    for fid in alive:
        for g in denounced[fid]:
            F[fid].pacts = [p for p in F[fid].pacts if p["with"] != g]
            F[g].pacts = [p for p in F[g].pacts if p["with"] != fid]

    # --- 9. Capitulação ----------------------------------------------------------------------------
    for fid in alive:
        f = F[fid]
        n_t = game.n_territories(fid)
        cap = game.capital_tid(fid)
        no_cap = game.owner.get(cap) != fid
        total_stock = sum(f.stock.values())
        if n_t == 0 or (no_cap and game.troops_total(fid) < B.CAPITULATION_TROOPS
                        and total_stock < B.CAPITULATION_STOCK):
            f.capitulated = True
            for t in game.order_tids:
                if game.owner[t] == fid:
                    game.owner[t] = None
            f.pacts = []
            for g in order:
                F[g].pacts = [p for p in F[g].pacts if p["with"] != fid]
            rep[fid].append("CAPITULAÇÃO: a nação não tem mais meios de continuar a guerra.")
            news.append(N.capitulation(rng, T, f.short, game.tname(cap)))

    # arredonda estoques
    for fid in order:
        for s in SEC:
            F[fid].stock[s] = round(max(0.0, F[fid].stock[s]), 2)
        F[fid].morale = round(F[fid].morale, 2)

    # relatórios
    for fid in alive:
        f = F[fid]
        rep[fid].append("Estoque: " + ", ".join(f"{s} {num(f.stock[s])}" for s in SEC)
                        + f". Tropas: {game.troops_total(fid)} batalhões em {game.n_territories(fid)} territórios.")
        f.last_report = {"turn": T, "lines": rep[fid]}

    # --- fim de jogo? ---------------------------------------------------------------------------------
    survivors = [f for f in order if not F[f].capitulated]
    total_terr = len(game.order_tids)
    thresh = int(math.ceil(B.DOMINATION * total_terr - 1e-9))
    winner, reason = None, None
    dom = [f for f in survivors if game.n_territories(f) >= thresh]
    if dom:
        winner, reason = dom[0], "domination"
    elif len(survivors) <= 1 and len(order) >= 2:
        winner = survivors[0] if survivors else None
        reason = "last_standing"
    elif T >= game.max_turns:
        reason = "turns"
    finished = reason is not None
    standings = game.standings()
    if finished and winner is None:
        winner = standings[0]["id"]

    # placar / líder
    if len(standings) > 1 and not finished:
        top, sec = standings[0], standings[1]
        if top["vp"] > sec["vp"]:
            if game.leader != top["id"]:
                news.append(N.leader(rng, T, F[top["id"]].short, top["vp"], F[sec["id"]].short, sec["vp"]))
            game.leader = top["id"]
    if not battles:
        news.append(N.calm(rng, T))
    # prioridade: capturas por último (aparecem primeiro, "mais recentes primeiro")
    news.sort(key=lambda n: {"weather": 0, "politics": 1, "battle": 2, "event": 3, "capture": 4}.get(n["kind"], 2))
    if len(news) > 8:                       # o jornal não cabe tudo: ficam as notícias mais importantes
        news = news[-8:]
    if finished:
        sl = [(F[s["id"]].short, s["vp"]) for s in standings]
        news.append(N.final(rng, T, F[winner].short, next(s["vp"] for s in standings if s["id"] == winner), sl, reason))
    for item in news:
        game.add_news(item)

    # estatísticas por turno (balanceamento e painel do árbitro)
    game.history.append({
        "turn": T, "battles": len(battles), "captures": len(captures),
        "troops": {f: game.troops_total(f) for f in order},
        "stock": {f: dict(F[f].stock) for f in order},
        "morale": {f: F[f].morale for f in order},
        "territories": {f: game.n_territories(f) for f in order},
        "starved": [f for f in order if starved[f]],
    })

    res_data = {"turn": T, "battles": deep(battles), "moves": moves_pub, "weather": wx}
    game.last_resolution = res_data

    # efeitos que acabaram
    EV.expire(game, T)

    events: list[dict] = [ev("public", "resolution", deep(res_data))]
    for item in news:
        events.append(ev("public", "news", deep(item)))

    if finished:
        game.status = "finished"
        game.winner = winner
        game.end_reason = reason
        game.deadline_ms = 0
        game.paused_remaining_ms = 0
        events.append(ev("public", "phase", game.phase_data(now_ms)))
        events.append(ev("public", "state", {}))
        return events

    # --- 10. prepara o próximo turno -----------------------------------------------------------------
    game.turn = T + 1
    game.turn_started_ms = now_ms
    game.flash_sent = False
    if game.status == "paused":
        game.paused_remaining_ms = game.turn_ms
        game.deadline_ms = 0
    else:
        game.deadline_ms = now_ms + game.turn_ms
    events.extend(prepare_turn(game, now_ms))
    events.append(ev("public", "phase", game.phase_data(now_ms)))
    events.append(ev("public", "state", {}))
    return events
