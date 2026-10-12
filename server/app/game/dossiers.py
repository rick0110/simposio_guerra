"""Dossiês, desafios, telegramas de interceptação e correção de respostas.

Os desafios são corrigidos contra os DADOS ENTREGUES ao aluno (tabelas arredondadas, diário,
leituras e pesquisa que ele vê), nunca contra o segredo do servidor. Os gabaritos ficam em
`game.keys[fid][challenge_id]` e jamais aparecem nas visões não-administrativas.
"""

from __future__ import annotations

import csv
import io
import re

import numpy as np

from app.engine import cipher, economy, geo, linalg, morale, weather
from app.game import balance as B
from app.game.model import deep, num, troops_range, upper_ascii

BOM = "﻿"

TOOLS = {
    "intendencia": ["leontief", "matrix"],
    "operacoes": ["markov", "lanchester"],
    "inteligencia": ["hill_recover", "hill_decrypt", "modinv", "trilaterate"],
    "governo": ["regression", "matrix"],
}


# =============================================================================================
# Leitura de respostas
# =============================================================================================
_NUM_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)?%?$")
_LABEL_PREFIX = re.compile(r"^[A-Za-z_ºª.₀-₉\w]*\s*[=:]\s*")


def _to_float(token: str) -> float | None:
    t = token.strip().replace("−", "-").replace("–", "-")
    t = _LABEL_PREFIX.sub("", t).strip()
    if not _NUM_RE.match(t):
        return None
    pct = t.endswith("%")
    t = t.rstrip("%").replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v / 100.0 if pct else v


def parse_numbers(text: str, n: int, example: str = "") -> list[float]:
    """Extrai exatamente `n` números; aceita vírgula decimal e separadores flexíveis (; espaço, quebra de linha)."""
    s = str(text or "").strip()
    if not s:
        raise ValueError(f"Resposta vazia. Esperava {n} número(s) separado(s) por ponto e vírgula{example}.")
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s)
    s = re.sub(r"\s+%", "%", s)
    if ";" in s or "\n" in s:
        tokens = re.split(r"[;\n]+", s)
    elif len(s.split()) > 1:
        tokens = s.split()
    elif n > 1:
        parts = s.split(",")
        tokens = parts if len(parts) == n else [s]
    else:
        tokens = [s]
    tokens = [t.strip(" ,\t") for t in tokens]
    tokens = [t for t in tokens if t]
    values = []
    for t in tokens:
        v = _to_float(t)
        if v is None:
            raise ValueError(
                f"Não entendi o valor «{t}». Esperava {n} número(s) separado(s) por ponto e vírgula{example} "
                "(vírgula decimal é aceita, ex.: 1,25).")
        values.append(v)
    if len(values) != n:
        raise ValueError(
            f"Esperava {n} número(s) separado(s) por ponto e vírgula{example}, mas recebi {len(values)}.")
    return values


def parse_location(text: str, cols: str = "ABCDEFGHIJKLMNOPQRSTUVWX", rows: int = 16):
    """Quadrícula ('K7') ou par de coordenadas ('525; 310'). Devolve ('grid', 'K7') ou ('xy', (x, y))."""
    s = str(text or "").strip()
    m = re.fullmatch(r"([A-Za-z])\s*[-\s]?\s*(\d{1,2})", s)
    if m:
        col, row = m.group(1).upper(), int(m.group(2))
        if col not in cols or not 1 <= row <= rows:
            raise ValueError(f"Quadrícula «{s}» fora do mapa (colunas A–{cols[-1]}, linhas 1–{rows}).")
        return "grid", f"{col}{row}"
    try:
        x, y = parse_numbers(s, 2, " (x; y) ou uma quadrícula como K7")
    except ValueError as exc:
        raise ValueError(
            "Informe as coordenadas «x; y» (ex.: 525; 310) ou a quadrícula (ex.: K7). " + str(exc.args[0])) from exc
    return "xy", (x, y)


# =============================================================================================
# Telegramas de interceptação
# =============================================================================================
def _stack(game, fid: str):
    ts = [t for t in game.order_tids if game.owner[t] == fid]
    if not ts:
        return None
    return max(ts, key=lambda t: (game.troops[t], t))


def intercept_plain(game, emitter: str, variant: int) -> str:
    """Texto claro do telegrama (começa com o crib «URGENTE »), a partir do estado real da nação."""
    f = game.factions[emitter]
    nm = upper_ascii(f.short)
    total = game.troops_total(emitter)
    top = _stack(game, emitter)
    v = variant % 4
    if v == 0 and top:
        text = f"URGENTE {nm} CONCENTRA {game.troops[top]} BATALHOES EM {top} {upper_ascii(game.tname(top))}"
    elif v == 1:
        res = max(B.SECTORS, key=lambda r: f.stock[r])
        text = f"URGENTE {nm} TEM {total} BATALHOES E {int(round(f.stock[res]))} DE {res} EM ESTOQUE"
    elif v == 2:
        cap = game.capital_tid(emitter)
        text = (f"URGENTE {nm} GUARNECE CAPITAL {upper_ascii(game.tname(cap))} {cap} "
                f"COM {game.troops[cap]} BATALHOES")
    else:
        text = (f"URGENTE {nm} MORAL {int(round(f.morale))} E {game.n_territories(emitter)} "
                f"TERRITORIOS SOB CONTROLE")
    return clip_symbols(text)


def clip_symbols(text: str) -> str:
    text = cipher.normalize(text).strip()
    if len(text) > B.TELEGRAM_MAX_SYMBOLS - 6:
        text = text[: B.TELEGRAM_MAX_SYMBOLS - 6].rsplit(" ", 1)[0]
    return text


def encrypt_safe(plain: str, key) -> tuple[str, str]:
    """Cifra o texto; evita criptograma com espaço no fim (sufixos de telegrafista). Devolve (claro, cifrado)."""
    for suffix in ("", " STOP", " FIM", " OK", " AGORA"):
        p = cipher.normalize(plain + suffix)
        if len(p) > B.TELEGRAM_MAX_SYMBOLS:
            continue
        c = cipher.encrypt(p, key)
        if not c.endswith(" ") and not c.startswith(" "):
            return p, c
    p = cipher.normalize(plain)
    return p, cipher.encrypt(p, key)


def make_intercept(game, emitter: str, plain: str) -> tuple[str, str]:
    f = game.factions[emitter]
    return encrypt_safe(plain, f.cipher_key)


def flash_plain(game, receiver: str, emitter: str) -> str:
    """Texto do telegrama-relâmpago, a partir das ORDENS DE OPERAÇÕES já enviadas pelo emissor."""
    e = game.factions[emitter]
    nm = upper_ascii(e.short)
    order = e.orders.get("operacoes")
    moves = list((order or {}).get("moves") or [])
    if moves:
        moves.sort(key=lambda m: -m["troops"])
        parts = []
        for m in moves[:2]:
            attack = game.owner.get(m["to"]) != emitter
            verb = "ATACA" if attack else "REFORCA"
            parts.append(f"{verb} {m['to']} {upper_ascii(game.tname(m['to']))} COM {m['troops']} BATALHOES "
                         f"DE {m['from']}")
        return clip_symbols(f"URGENTE {nm} " + " E ".join(parts))
    top = _stack(game, emitter)
    total = game.troops_total(emitter)
    if top:
        return clip_symbols(f"URGENTE {nm} MANTEM {game.troops[top]} BATALHOES EM {top} "
                            f"{upper_ascii(game.tname(top))} TOTAL {total} ALI {int(round(e.stock['ALI']))} "
                            f"COM {int(round(e.stock['COM']))}")
    return clip_symbols(f"URGENTE {nm} SEM TROPAS EM CAMPO")


def flash_target(game, receiver: str) -> str | None:
    """Inimigo-alvo do flash: prefere quem já enviou movimentos (primeiro os que visam o receptor)."""
    enemies = [g for g in game.order if g != receiver and not game.factions[g].capitulated]
    if not enemies:
        return None
    with_moves = []
    for g in enemies:
        order = game.factions[g].orders.get("operacoes") or {}
        moves = order.get("moves") or []
        if moves:
            hits_me = any(game.owner.get(m["to"]) == receiver for m in moves)
            with_moves.append((0 if hits_me else 1, g))
    if with_moves:
        with_moves.sort()
        return with_moves[0][1]
    return enemies[(game.turn * 2 + game.order.index(receiver)) % len(enemies)]


# =============================================================================================
# Geração dos dossiês
# =============================================================================================
def _title(section: str, turn: int) -> str:
    return f"DOSSIÊ DA {B.SECTION_NAMES[section].upper()} — TURNO {turn}" if section in ("intendencia", "inteligencia") \
        else f"DOSSIÊ DAS {B.SECTION_NAMES[section].upper()} — TURNO {turn}" if section == "operacoes" \
        else f"DOSSIÊ DO GOVERNO — TURNO {turn}"


def _dataset(game, section, ds_id, title, description, columns, rows):
    return {"id": ds_id, "title": title, "description": description, "columns": columns,
            "rows": rows, "csv_url": f"/api/faction/dossier/{section}/{ds_id}.csv"}


def leontief_tables(game, fid: str):
    """(X, Z) mostrados ao aluno, já arredondados (X: 1 casa, Z: 2 casas), a partir do turno anterior."""
    f = game.factions[fid]
    A = np.array(f.A_prev, float)
    x = np.array(f.last_x, float)
    nominal = game.nominal_x(fid)
    X = np.where(x >= 3.0, x, nominal)
    X = np.round(X, 1)
    Z = np.round(A * X[np.newaxis, :], 2)
    return X, Z


def build_intendencia(game, fid: str, now_ms: int):
    f = game.factions[fid]
    turn = game.turn
    X, Z = leontief_tables(game, fid)
    A_shown = economy.A_from_transactions(Z, X)
    cap = game.capacity(fid)
    W8, W10, W12 = (game.workforce(fid, h) for h in (8, 10, 12))
    mil = B.UPKEEP_ALI_PER_BATTALION * game.troops_total(fid)
    civil = B.CIVIL_ALI[int(f.policy["racao"])]
    rng = game.rng

    # demanda líquida alvo, escolhida para ser viável (mão de obra e capacidade)
    base = np.array([mil + civil + 1 + int(rng.integers(0, 4)), 4 + int(rng.integers(0, 5)),
                     3 + int(rng.integers(0, 5))], float)
    d = np.round(base)
    for _ in range(40):
        x = economy.required_production(A_shown, d)
        labor = economy.labor_used([B.LABOR[s] for s in B.SECTORS], x)
        if labor <= 0.9 * W8 and all(x[i] <= 0.95 * cap[s] for i, s in enumerate(B.SECTORS)):
            break
        d = np.maximum(np.floor(d * 0.93), 2.0)
    x_key = economy.required_production(A_shown, d)

    names = B.SECTORS
    transacoes = _dataset(
        game, "intendencia", "transacoes",
        ("Tabela de transações intersetoriais (levantamento anterior à guerra)" if turn <= 1
         else f"Tabela de transações intersetoriais (turno {turn - 1})"),
        "Z[i][j] = insumo do setor i consumido pelo setor j; a última linha (X) é a produção total de cada setor. "
        "A matriz técnica é A = Z·diag(X)⁻¹ (divida cada coluna de Z pelo X do mesmo setor).",
        ["", *names],
        [[names[i], *[float(Z[i, j]) for j in range(3)]] for i in range(3)] + [["X", *[float(v) for v in X]]],
    )
    mao = _dataset(
        game, "intendencia", "mao_de_obra",
        "Mão de obra, capacidade e estoque",
        "L = mão de obra gasta por unidade bruta produzida; W = mão de obra disponível conforme a jornada "
        "(8, 10 ou 12 h); restrição: L·x ≤ W e x ≤ capacidade.",
        ["Setor", "L (por unidade)", "Capacidade máx.", "Estoque atual"],
        [[s, B.LABOR[s], float(cap[s]), round(float(f.stock[s]), 1)] for s in names]
        + [["W (8 h)", round(W8, 1), "", ""], ["W (10 h)", round(W10, 1), "", ""], ["W (12 h)", round(W12, 1), "", ""]],
    )
    briefing = (
        f"CONFIDENCIAL. Senhores, segue o levantamento da produção "
        f"{'do período anterior à guerra' if turn <= 1 else f'do turno {turn - 1}'}. "
        "A tabela Z registra o fluxo de insumos entre os setores e X a produção total de cada um; dividindo cada "
        "coluna de Z por X obtém-se a matriz técnica A. Para obter uma entrega líquida d, resolva (I − A)x = d "
        "na Mesa de Cálculo (ferramenta Leontief).\n\n"
        f"Estoque: ALI {num(f.stock['ALI'])}, ACO {num(f.stock['ACO'])}, COM {num(f.stock['COM'])}. "
        f"Consumo previsto de Alimento: {num(mil)} das tropas + {num(civil)} civil = {num(mil + civil)}. "
        f"Mão de obra: {num(W8)} (jornada de 8 h). A matriz muda levemente de turno a turno; bombardeios a pioram."
    )
    challenge = {
        "id": f"c{turn}-intendencia",
        "section": "intendencia",
        "prompt": (f"O Gabinete exige entrega líquida d* = ({int(d[0])} ALI; {int(d[1])} ACO; {int(d[2])} COM). "
                   "Com A = Z·diag(X)⁻¹ calculada da tabela, qual produção bruta x = (x_ALI; x_ACO; x_COM) "
                   "entrega d*? Resolva (I − A)x = d*."),
        "answer_format": "três números separados por ponto e vírgula: x_ALI; x_ACO; x_COM (ex.: 24,5; 11; 9,3)",
        "reward_text": "+10% de produtividade neste turno",
    }
    key = {"kind": "leontief", "x": [float(v) for v in x_key], "d": [float(v) for v in d]}
    extras = {
        "stock": {s: round(float(f.stock[s]), 1) for s in names},
        "labor": dict(B.LABOR),
        "capacity": {s: float(cap[s]) for s in names},
        "workforce": {"8": round(W8, 1), "10": round(W10, 1), "12": round(W12, 1)},
        "upkeep_forecast": {"troops": round(mil, 1), "civil": float(civil), "total": round(mil + civil, 1)},
        "recruit_cost": dict(B.RECRUIT_COST),
        "production_X": [float(v) for v in X],
    }
    return briefing, [transacoes, mao], challenge, key, extras


def region_name(game, region: str) -> str:
    for r in game.map["climate_regions"]:
        if r["id"] == region:
            return r["name"]
    return region.capitalize()


def build_operacoes(game, fid: str, now_ms: int):
    f = game.factions[fid]
    turn = game.turn
    regions = B.REGIONS
    n_obs = len(game.climate[regions[0]]["diary"])
    rows = []
    for i in range(n_obs):
        rows.append([i + 1, *[B.WEATHER_NAMES[game.climate[r]["diary"][i]] for r in regions]])
    diario = _dataset(
        game, "operacoes", "diario_clima",
        f"Diário meteorológico ({n_obs} observações por região)",
        "Estado do tempo observado a cada turno em cada região (limpo, chuva, tempestade). A última linha é o "
        "estado atual. Conte as transições de uma linha para a seguinte para estimar P.",
        ["Obs", *[region_name(game, r) for r in regions]], rows)

    # avistamentos: territórios vizinhos dos meus, que não são meus
    mine = {t for t in game.order_tids if game.owner[t] == fid}
    seen = []
    for t in game.order_tids:
        if t in mine:
            continue
        if any(t in game.adjacent(m) for m in mine):
            own = game.owner[t]
            seen.append([t, game.tname(t), game.owner_label(own), troops_range(game.troops[t]),
                         game.TER[t]["terrain"], game.terrain_mod(t)])
    avist = _dataset(
        game, "operacoes", "avistamentos",
        "Avistamentos de fronteira",
        "Territórios vizinhos aos seus (por terra ou por mar) e a faixa estimada de batalhões. "
        "Tropas exatas só nos seus territórios (ou onde a Inteligência localizar um depósito).",
        ["Território", "Nome", "Dono", "Faixa de tropas", "Terreno", "Defesa do terreno"], seen)

    mods = [["Terreno: planície (defensor)", 1.0], ["Terreno: urbano (defensor)", 1.3],
            ["Terreno: floresta (defensor)", 1.25], ["Terreno: pântano (defensor)", 1.2],
            ["Terreno: montanha (defensor)", 1.5], ["Clima: limpo (atacante)", 1.0],
            ["Clima: chuva (atacante)", 0.85], ["Clima: tempestade (atacante)", 0.65],
            ["Moral (qualquer lado)", "0,5 + moral/100"], ["Duração do combate T", B.BATTLE_T]]
    modif = _dataset(
        game, "operacoes", "modificadores", "Tabela de modificadores de combate",
        "Lanchester: A' = −β·B, B' = −α·A. α é a eficácia do atacante (moral × clima) e β a do defensor "
        "(moral × terreno). Use a ferramenta Lanchester da Mesa de Cálculo.",
        ["Fator", "Valor"], mods)

    cur_region = regions[(turn - 1 + game.slot_of(fid)) % 3]
    cur_state = game.climate[cur_region]["diary"][-1]
    cname = region_name(game, cur_region)
    seqs = {r: game.climate[r]["diary"] for r in regions}
    P_est = weather.estimate_P(seqs[cur_region], 3)
    p_key = float(P_est[cur_state, 2])

    briefing = (
        "CONFIDENCIAL. Senhores, anexo o diário meteorológico das três regiões e os avistamentos de fronteira. "
        "O tempo de cada região segue uma cadeia de Markov: contando as transições do diário estima-se a matriz "
        "P, e a linha do estado atual dá a previsão do próximo turno (ferramenta Markov da Mesa de Cálculo). "
        "Tempestade fecha as rotas marítimas e enfraquece o ataque; para avaliar um combate use a ferramenta "
        "Lanchester.\n\n"
        f"Estado atual do tempo: " + "; ".join(
            f"{region_name(game, r)} {B.WEATHER_NAMES[game.climate[r]['diary'][-1]]}" for r in regions)
        + f". Cada batalhão movido custa {B.MOVE_COM} COM (rota marítima {B.SEA_MOVE_COM})."
    )
    challenge = {
        "id": f"c{turn}-operacoes",
        "section": "operacoes",
        "prompt": (f"Na região {cname} o tempo está agora em «{B.WEATHER_NAMES[cur_state]}». Estime a matriz de "
                   f"transição P dessa região por contagem de transições no diário e informe a probabilidade de "
                   "TEMPESTADE no próximo turno."),
        "answer_format": "um número entre 0 e 1 (ex.: 0,25) ou em porcentagem (ex.: 25%)",
        "reward_text": "O servidor revela o clima exato de todas as regiões na resolução deste turno",
    }
    key = {"kind": "markov", "p": p_key, "region": cur_region, "state": int(cur_state)}
    extras = {
        "weather_now": {r: int(game.climate[r]["diary"][-1]) for r in regions},
        "weather_names": list(B.WEATHER_NAMES),
        "challenge_region": cur_region,
        "move_cost": {"land": B.MOVE_COM, "sea": B.SEA_MOVE_COM},
    }
    return briefing, [diario, avist, modif], challenge, key, extras


def build_inteligencia(game, fid: str, now_ms: int):
    f = game.factions[fid]
    turn = game.turn
    enemies = [g for g in game.order if g != fid and not game.factions[g].capitulated]
    target = None
    intercepts = []
    if enemies:
        idx = (turn - 1 + game.slot_of(fid)) % len(enemies)
        target = enemies[idx]
        emitters = [target] + ([enemies[(idx + 1) % len(enemies)]] if len(enemies) > 1 else [])
        for k, em in enumerate(emitters):
            plain = intercept_plain(game, em, turn + k + game.slot_of(fid))
            p, c = make_intercept(game, em, plain)
            intercepts.append((em, p, c))

    # estações de escuta e leituras ao depósito do alvo
    rng = game.rng
    stations = [[int(round(x + float(rng.uniform(-40, 40)))), int(round(y + float(rng.uniform(-30, 30))))]
                for x, y in B.STATION_BASE]
    depot = game.depots.get(target) if target else None
    rows, est, depot_terr, depot_true = [], None, None, None
    if depot:
        depot_true = depot["point"]
        readings = geo.station_readings(depot_true, stations, rng, noise=8.0)
        readings = [round(float(r), 1) for r in readings]
        est = geo.trilaterate(stations, readings)
        depot_terr = depot["territory"]
        rows = [[f"E{i + 1}", stations[i][0], stations[i][1], readings[i]] for i in range(4)]
    leituras = _dataset(
        game, "inteligencia", "leituras",
        "Radiogoniometria: leituras das 4 estações de escuta",
        "Distância (com ruído) de cada estação ao depósito de suprimentos inimigo. Cada leitura define um círculo; "
        "subtraindo a primeira equação das demais obtém-se um sistema linear em (x, y), resolvido por mínimos "
        "quadrados. Quadrícula: coluna = letra (x/50), linha = y/50 + 1.",
        ["Estação", "x", "y", "Distância"], rows)
    crip_rows = [[f"tg-{turn}-{i + 1}", game.factions[e].short, turn, c] for i, (e, p, c) in enumerate(intercepts)]
    cripto = _dataset(
        game, "inteligencia", "criptogramas",
        "Comunicados inimigos interceptados (cifra de Hill 2×2 sobre ℤ₃₇)",
        "Alfabeto de 37 símbolos: A–Z = 0–25, 0–9 = 26–35, espaço = 36 (o espaço conta como símbolo). "
        "Todo comunicado começa por «URGENTE » (8 símbolos): com dois pares claro/cifrado, K = C·P⁻¹ (mod 37). "
        "A chave de cada nação troca a cada 2 turnos.",
        ["Id", "Origem", "Turno", "Criptograma"], crip_rows)

    tname = game.factions[target].short if target else "o inimigo"
    briefing = (
        "CONFIDENCIAL. Senhores, nossas estações de escuta interceptaram comunicados inimigos, cifrados com Hill "
        "2×2 sobre 37 símbolos. Todo telegrama começa por «URGENTE »: com esse trecho conhecido recupere a chave "
        "K = C·P⁻¹ (mod 37) e decifre os demais (ferramentas Hill da Mesa de Cálculo).\n\n"
        f"As quatro estações também registraram as distâncias ao depósito de suprimentos de {tname}. "
        "Lineariza-se subtraindo a primeira equação das outras e resolve-se por mínimos quadrados (ferramenta "
        "Triangulação). Depósito localizado revela as tropas do território e libera o bombardeio "
        f"({B.BOMBARD_COM} COM)."
    )
    cid = f"c{turn}-inteligencia"
    challenge = {
        "id": cid,
        "section": "inteligencia",
        "prompt": (f"Onde está o depósito de suprimentos de {tname}? Triangule a posição a partir das leituras das "
                   "quatro estações e informe as coordenadas (x; y) ou a quadrícula do mapa."),
        "answer_format": "coordenadas «x; y» (ex.: 525; 310) ou quadrícula (ex.: K7)",
        "reward_text": "Revela as tropas do território do depósito e libera Bombardear depósito neste turno",
    } if depot else None
    key = ({"kind": "depot", "est": [float(est[0]), float(est[1])], "territory": depot_terr,
            "target": target, "true": [float(depot_true[0]), float(depot_true[1])]} if depot else None)
    extras = {
        "crib": "URGENTE ",
        "block_size": 2,
        "alphabet": cipher.ALPHABET,
        "stations": stations,
        "target_nation": target,
        "grid": {"cell": game.map["grid"]["cell"], "cols": game.map["grid"]["cols"], "rows": game.map["grid"]["rows"]},
        "key_period_turns": B.CIPHER_KEY_TURNS,
        "intercepts": [],   # preenchido por build_all depois de criar os telegramas
    }
    return briefing, [leituras, cripto], challenge, key, extras, intercepts


def build_governo(game, fid: str, now_ms: int):
    f = game.factions[fid]
    turn = game.turn
    rows = morale.survey(f.betas, game.rng, n=B.SURVEY_ROWS, noise=1.5)
    cols = ["racao", "propaganda", "horas_extra", "baixas", "saldo_territorial", "delta_moral"]
    pesquisa = _dataset(
        game, "governo", "pesquisa",
        f"Pesquisa de opinião ({B.SURVEY_ROWS} observações)",
        "Variação de moral registrada em períodos anteriores: ração (0 normal, 1 reduzida, 2 severa), propaganda "
        "(0–5), horas_extra (jornada − 8), baixas (em dezenas de batalhões) e saldo_territorial (territórios "
        "ganhos − perdidos). Ajuste delta_moral = β0 + β1·racao + β2·propaganda + … por mínimos quadrados.",
        ["obs", *cols], [[i + 1, *[r[c] for c in cols]] for i, r in enumerate(rows)])
    beta_key = float(morale.ols(rows)[2])    # β2: propaganda

    quadro_rows = []
    for g in game.order:
        gf = game.factions[g]
        quadro_rows.append([gf.short, game.n_territories(g), round(game.vp(g), 2),
                            "capitulou" if gf.capitulated else "em campanha"])
    quadro = _dataset(
        game, "governo", "quadro", "Quadro das nações",
        "Pontos de vitória e territórios (informação pública), para orientar a diplomacia.",
        ["Nação", "Territórios", "PV", "Situação"], quadro_rows)

    pol = f.policy
    briefing = (
        "CONFIDENCIAL. Senhores, a pesquisa de opinião anexa relaciona a variação da moral com ração, propaganda, "
        "jornada, baixas e saldo territorial. O modelo é linear: estime os coeficientes por regressão múltipla "
        "(ferramenta Regressão da Mesa de Cálculo) e decida a política do turno.\n\n"
        f"Moral atual: {num(f.morale)}. Política em vigor: ração {pol['racao']}, jornada de {pol['horas']} h. "
        f"Pacto de não agressão: proponha aos outros Governos por telegrama e confirme na ordem; "
        f"denunciar um pacto custa {-B.DENOUNCE_MORALE} de moral."
    )
    challenge = {
        "id": f"c{turn}-governo",
        "section": "governo",
        "prompt": ("Estime, por mínimos quadrados (equações normais, com intercepto), o efeito β da propaganda "
                   "(pontos de moral por ponto de propaganda) na pesquisa de opinião."),
        "answer_format": "um número (ex.: 1,35)",
        "reward_text": "+5 de moral imediato",
    }
    key = {"kind": "ols", "beta": beta_key}
    extras = {"morale": round(f.morale, 1), "policy": dict(pol), "features": list(morale.FEATURES)}
    return briefing, [pesquisa, quadro], challenge, key, extras


def build_all(game, now_ms: int) -> list[dict]:
    """Gera os dossiês de todas as nações em campo e os telegramas de abertura do turno."""
    from app.game.model import ev
    events = []
    turn = game.turn
    game.dossiers = {}
    game.keys = {}
    game.cstate = {}
    for fid in game.order:
        f = game.factions[fid]
        if f.capitulated:
            continue
        game.dossiers[fid] = {}
        game.keys[fid] = {}
        game.cstate[fid] = {}
        made = {}
        for section in B.SECTIONS:
            if section == "inteligencia":
                briefing, datasets, challenge, key, extras, intercepts = build_inteligencia(game, fid, now_ms)
            else:
                briefing, datasets, challenge, key, extras = {
                    "intendencia": build_intendencia, "operacoes": build_operacoes, "governo": build_governo,
                }[section](game, fid, now_ms)
            made[section] = (briefing, datasets, challenge, key, extras)
            if section == "inteligencia":
                tgs = []
                for k, (em, plain, cph) in enumerate(intercepts):
                    tg = game.add_telegram(
                        fid, "intercept", em, f"INTERCEPTAÇÃO — {game.factions[em].short.upper()}", cph,
                        "inteligencia", now_ms, plain=plain)
                    tgs.append(tg)
                    events.append(ev(f"faction:{fid}", "telegram", deep(tg)))
                    extras["intercepts"].append({
                        "id": tg["id"], "from": em, "from_name": game.factions[em].short, "turn": turn,
                        "kind": "briefing", "cipher": cph, "codes": _codes(cph),
                    })
            challenge_list = [challenge] if challenge else []
            game.dossiers[fid][section] = {
                "section": section, "turn": turn, "title": _title(section, turn),
                "briefing": briefing, "datasets": datasets, "challenges": challenge_list,
                "tools": list(TOOLS[section]), "extras": extras,
            }
            if challenge:
                game.keys[fid][challenge["id"]] = key
                game.cstate[fid][challenge["id"]] = {"attempts_left": B.CHALLENGE_ATTEMPTS, "solved": False}
        tg = game.add_telegram(
            fid, "report", None, f"BRIEFING — TURNO {turn}",
            f"Dossiês do turno {turn} disponíveis para as quatro seções. Prazo de {num(game.turn_ms / 60000)} min. "
            "Telegramas interceptados seguem para a Inteligência.", None, now_ms)
        events.append(ev(f"faction:{fid}", "telegram", deep(tg)))
        events.append(ev(f"faction:{fid}", "dossier", {"turn": turn, "sections": list(B.SECTIONS)}))
    return events


def _codes(cph: str) -> list[int]:
    return [cipher.ALPHABET.index(ch) for ch in cipher.symbols(cph)]


# =============================================================================================
# Visões
# =============================================================================================
def placeholder(game, fid: str, section: str) -> dict:
    if game.factions[fid].capitulated:
        text = "CONFIDENCIAL. Senhores, a nação capitulou: não há mais dossiês a entregar."
    else:
        text = "CONFIDENCIAL. Senhores, aguardem o sinal do árbitro: os dossiês chegam quando a guerra começar."
    return {
        "section": section, "turn": game.turn, "title": _title(section, game.turn) if game.turn else
        f"DOSSIÊ — {B.SECTION_NAMES[section].upper()}",
        "briefing": text,
        "datasets": [], "challenges": [], "tools": list(TOOLS[section]), "extras": {},
    }


def dossier_view(game, fid: str, section: str) -> dict:
    if fid not in game.factions:
        raise ValueError(f"Nação desconhecida: {fid}")
    if section not in B.SECTIONS:
        raise ValueError(f"Seção desconhecida: {section}")
    d = game.dossiers.get(fid, {}).get(section)
    if d is None:
        return placeholder(game, fid, section)
    out = deep(d)
    chs = []
    for c in out["challenges"]:
        st = game.cstate.get(fid, {}).get(c["id"], {"attempts_left": 0, "solved": False})
        chs.append({"id": c["id"], "prompt": c["prompt"], "answer_format": c["answer_format"],
                    "attempts_left": st["attempts_left"], "solved": st["solved"], "reward_text": c["reward_text"]})
    out["challenges"] = chs
    return out


def dataset_csv(game, fid: str, section: str, dataset_id: str) -> str:
    d = game.dossiers.get(fid, {}).get(section)
    if d is None:
        raise ValueError("Ainda não há dossiê disponível para esta seção.")
    for ds in d["datasets"]:
        if ds["id"] == dataset_id:
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(ds["columns"])
            for row in ds["rows"]:
                w.writerow(row)
            return BOM + buf.getvalue()
    raise ValueError(f"Conjunto de dados inexistente: {dataset_id}")


# =============================================================================================
# Correção dos desafios
# =============================================================================================
def check_answer(game, fid: str, key: dict, answer: str) -> dict:
    """Devolve {"status": "format"|"wrong"|"right", "message": str, "extra": {...}}."""
    kind = key["kind"]
    try:
        if kind == "leontief":
            vals = parse_numbers(answer, 3, " (x_ALI; x_ACO; x_COM)")
            tgt = key["x"]
            bad = []
            for name, v, t in zip(B.SECTORS, vals, tgt):
                if abs(v - t) > max(B.TOL_LEONTIEF_REL * abs(t), B.TOL_LEONTIEF_ABS):
                    bad.append(name)
            if not bad:
                return {"status": "right", "message": "Plano de produção aprovado! O Estado-Maior ordena +10% de "
                        "produtividade nesta jornada."}
            return {"status": "wrong", "message": (
                f"Fora da tolerância de 2% em {', '.join(bad)}. Confira A = Z·diag(X)⁻¹ (divida cada COLUNA de Z "
                "pelo X do mesmo setor) e resolva (I − A)x = d*.")}
        if kind == "markov":
            s = str(answer or "").strip()
            if not s:
                raise ValueError("Resposta vazia. Informe a probabilidade (ex.: 0,25 ou 25%).")
            vals = parse_numbers(s, 1, " (ex.: 0,25 ou 25%)")
            v = vals[0]
            if v > 1.0 and "%" not in s:
                v = v / 100.0
            if not 0.0 <= v <= 1.0:
                raise ValueError("A probabilidade deve estar entre 0 e 1 (ou 0% e 100%).")
            if abs(v - key["p"]) <= B.TOL_MARKOV:
                return {"status": "right", "message": "Previsão confirmada! O servidor revela o clima exato que "
                        "fará na resolução deste turno."}
            return {"status": "wrong", "message": (
                "Fora da tolerância de ±0,03. Conte as transições de cada estado no diário da região pedida, "
                "divida cada linha pelo seu total e use a linha do estado ATUAL, coluna «tempestade».")}
        if kind == "depot":
            mode, val = parse_location(answer, game.map["grid"]["cols"], game.map["grid"]["rows"])
            ex, ey = key["est"]
            cell = game.map["grid"]["cell"]
            cols = game.map["grid"]["cols"]
            if mode == "grid":
                est_label = geo.grid_label(ex, ey, cell, cols, game.map["grid"]["rows"])
                cx, cy = geo.grid_center(val, cell, cols)
                # distância do ponto estimado ao retângulo da quadrícula informada
                x0, y0 = cx - cell / 2, cy - cell / 2
                dx = max(x0 - ex, 0.0, ex - (x0 + cell))
                dy = max(y0 - ey, 0.0, ey - (y0 + cell))
                ok = val == est_label or (dx * dx + dy * dy) ** 0.5 <= 6.0
            else:
                ok = ((val[0] - ex) ** 2 + (val[1] - ey) ** 2) ** 0.5 <= B.TOL_DEPOT_DIST or \
                    geo.grid_label(val[0], val[1], cell, cols, game.map["grid"]["rows"]) == \
                    geo.grid_label(ex, ey, cell, cols, game.map["grid"]["rows"])
            if ok:
                return {"status": "right", "message": "Depósito localizado! As tropas do território foram reveladas "
                        "e o bombardeio está liberado neste turno."}
            return {"status": "wrong", "message": (
                "Posição distante da solução de mínimos quadrados. Subtraia a 1ª equação de círculo das demais, "
                "monte 2(xi−x1)x + 2(yi−y1)y = r1² − ri² + xi² − x1² + yi² − y1² e resolva por mínimos quadrados.")}
        if kind == "ols":
            vals = parse_numbers(answer, 1, "")
            if abs(vals[0] - key["beta"]) <= B.TOL_BETA:
                return {"status": "right", "message": "Estimativa aceita! O moral da nação sobe com a notícia "
                        "(+5 de moral)."}
            return {"status": "wrong", "message": (
                "Fora da tolerância de ±0,15. Use todas as variáveis juntas, inclua o intercepto (coluna de 1s) e "
                "resolva as equações normais (XᵀX)β = Xᵀy; queremos o coeficiente da PROPAGANDA.")}
    except ValueError as exc:
        return {"status": "format", "message": exc.args[0] if exc.args else "Formato de resposta inválido."}
    return {"status": "format", "message": "Tipo de desafio desconhecido."}
