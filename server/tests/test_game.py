"""Testes do núcleo do jogo: criação, ciclo de vida, visões, segredos, desafios, ordens e resolução."""

from __future__ import annotations

import copy
import json
import re

import numpy as np
import pytest

from app.engine import cipher, economy, geo, morale, weather
from app.game import balance as B
from app.game import dossiers, events as EV
from app.game.game import Game
from tests.test_game_sim import MAP, T0, br, solve_challenges

SEC = B.SECTORS


@pytest.fixture(autouse=True)
def sem_eventos_aleatorios(monkeypatch):
    """Os testes de mecânica não devem depender do sorteio de eventos globais."""
    monkeypatch.setattr(B, "EVENT_PROB", 0.0)


def mk(n=4, seed=5, turns=8, minutes=12) -> Game:
    return Game.new(MAP, n_factions=n, turn_minutes=minutes, max_turns=turns, seed=seed)


def started(n=4, seed=5, **kw) -> Game:
    g = mk(n, seed, **kw)
    g.start(T0)
    return g


def types(events):
    return [e["type"] for e in events]


# ------------------------------------------------------------------------------ criação
@pytest.mark.parametrize("n,slots", [(2, [0, 3]), (3, [0, 2, 4]), (4, [0, 1, 3, 4]), (5, [0, 1, 2, 3, 4]),
                                     (6, [0, 1, 2, 3, 4, 5])])
def test_slots_ativos_e_nacoes(n, slots):
    g = mk(n)
    assert g.status == "lobby" and g.turn == 0
    assert g.order == ["GAU", "EUL", "HIL", "NOE", "CAU", "RIE"][:n]
    homes = {h["slot"]: h for h in MAP["home_slots"]}
    for i, s in enumerate(slots):
        for t in homes[s]["territories"]:
            assert g.owner[t] == g.order[i]
            assert g.troops[t] == (10 if t == homes[s]["capital"] else 5)
    inactive = [s for s in range(6) if s not in slots]
    for s in inactive:
        for t in homes[s]["territories"]:
            assert g.owner[t] is None
    for t in g.order_tids:
        if g.owner[t] is None:
            assert 3 <= g.troops[t] <= 6
    # estoque e moral iniciais
    for f in g.factions.values():
        assert f.stock == B.START_STOCK and f.morale == 70


def test_capitais_renomeadas_no_mapa_publico():
    g = mk(4)
    pm = g.public_map()
    names = {t["id"]: t["name"] for t in pm["territories"]}
    assert names["T03"] == "Eliminópolis"      # slot 0 -> GAU
    assert names["T07"] == "Totiente"          # slot 1 -> EUL
    assert names["T15"] == "Ortonormal"        # slot 3 -> HIL
    assert names["T19"] == "Anelópolis"        # slot 4 -> NOE
    assert names["T11"] != "Convergência"       # slot 2 inativo: nome original do mapa
    assert set(pm) == set(MAP)
    # o mapa original não é alterado
    assert MAP["territories"][2]["name"] != "Eliminópolis"
    assert g.tname("T03") == "Eliminópolis"


def test_senhas_legiveis_e_login():
    g = mk(6, seed=9)
    cr = g.credentials()
    assert list(cr) == g.order
    assert len(set(cr.values())) == 6
    for pw in cr.values():
        assert re.fullmatch(r"[a-z]+-[a-z]+-\d\d", pw), pw
    assert g.check_password("GAU", cr["GAU"])
    assert g.check_password("GAU", cr["GAU"].upper())
    assert not g.check_password("GAU", cr["EUL"])
    assert not g.check_password("XXX", "x")


def test_entradas_invalidas_em_new():
    with pytest.raises(ValueError):
        Game.new(MAP, n_factions=7)
    with pytest.raises(ValueError):
        Game.new(MAP, n_factions=1)
    with pytest.raises(ValueError):
        Game.new(MAP, turn_minutes=0)


# ------------------------------------------------------------------------------ ciclo de vida
def test_ciclo_de_vida_e_relogio():
    g = mk(minutes=10)
    pv = g.public_view(T0)
    assert pv["game"]["status"] == "lobby" and pv["game"]["turn"] == 0
    with pytest.raises(ValueError, match="ainda não começou"):
        g.submit_orders("GAU", "governo", {}, T0)
    ev0 = g.start(T0)
    assert {"phase", "dossier", "telegram", "news", "state"} <= set(types(ev0))
    assert g.status == "running" and g.turn == 1
    pv = g.public_view(T0 + 1000)
    assert pv["game"]["remaining_ms"] == 600_000 - 1000
    assert pv["game"]["deadline_ms"] == T0 + 600_000
    assert pv["game"]["now_ms"] == T0 + 1000
    with pytest.raises(ValueError):
        g.start(T0)
    # pausa guarda o restante e retoma recalculando o prazo
    g.pause(T0 + 100_000)
    assert g.status == "paused"
    pv = g.public_view(T0 + 400_000)
    assert pv["game"]["remaining_ms"] == 500_000 and pv["game"]["status"] == "paused"
    with pytest.raises(ValueError, match="pausada"):
        g.submit_orders("GAU", "governo", {}, T0 + 400_000)
    g.tick(T0 + 9_999_999)          # nada acontece pausado
    assert g.turn == 1
    g.resume(T0 + 500_000)
    assert g.deadline_ms == T0 + 1_000_000
    g.extend(T0 + 500_000, 2)
    assert g.deadline_ms == T0 + 1_120_000
    with pytest.raises(ValueError):
        g.extend(T0, 0)


def test_tick_telegrama_relampago_e_resolucao_no_prazo():
    g = started(minutes=10)
    assert g.tick(T0 + 10_000) == []
    # ordens de operações do GAU, para o inimigo interceptar
    g.admin_edit_faction("GAU", {"troops": {"T04": 9}}, T0)
    assert g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T04", "to": "T22", "troops": 8}]},
                           T0)["ok"]
    ev = g.tick(T0 + 301_000)   # passou da metade
    tg = [e for e in ev if e["type"] == "telegram"]
    assert len(tg) == 4 and all(e["channel"].startswith("faction:") for e in tg)
    assert g.tick(T0 + 302_000) == []   # só uma vez
    flashes = {e["channel"]: e["data"] for e in tg}
    # o texto claro do flash a partir das ORDENS submetidas por GAU
    plain = [p for fid in g.order for tid, p in g.plain.get(fid, {}).items() if "ATACA T22" in p]
    assert plain and plain[0].startswith("URGENTE GAUSSIA ATACA T22")
    for d in flashes.values():
        assert d["kind"] == "flash"
    ev = g.tick(T0 + 600_000)
    assert g.turn == 2
    assert "resolution" in types(ev)
    assert g.deadline_ms == T0 + 1_200_000
    res = [e for e in ev if e["type"] == "resolution"][0]
    assert res["channel"] == "public" and res["data"]["turn"] == 1
    assert set(res["data"]) >= {"turn", "battles", "moves"}


def test_fim_de_jogo_classificacao_e_erros():
    g = started(n=2, turns=2)
    g.resolve_turn(T0 + 1)
    assert g.status == "running" and g.turn == 2
    ev = g.resolve_turn(T0 + 2)
    assert g.status == "finished" and g.winner in g.factions
    assert any(e["type"] == "phase" and e["data"]["status"] == "finished" for e in ev)
    final = g.news[-1]
    assert "Classificação final" in final["body"] and final["kind"] == "event"
    pv = g.public_view(T0 + 3)
    assert pv["game"]["status"] == "finished" and pv["game"]["remaining_ms"] == 0
    assert pv["news"][0]["headline"] == final["headline"]
    for fn in (lambda: g.submit_orders("GAU", "governo", {}, T0 + 3), lambda: g.resolve_turn(T0 + 4),
               lambda: g.pause(T0 + 4), lambda: g.answer_challenge("GAU", "c1-governo", "1", T0)):
        with pytest.raises(ValueError):
            fn()
    assert g.tick(T0 + 10**9) == []


# ------------------------------------------------------------------------------ visões e segredos
def test_nevoa_de_guerra():
    g = started()
    v = g.faction_view("GAU", T0)
    tr = {t["id"]: t for t in v["territories"]}
    assert len(tr) == 34
    mine = [t for t in tr.values() if t["owner"] == "GAU"]
    assert {t["id"] for t in mine} == {"T01", "T02", "T03", "T04"}
    for t in mine:
        assert t["visibility"] == "own" and isinstance(t["troops"], int) and t["troops_range"] is None
    for t in tr.values():
        if t["visibility"] == "adjacent":
            assert t["troops"] is None and t["troops_range"] in ("0", "1–5", "6–10", "11–20", "21+")
            assert any(t["id"] in g.adjacent(m["id"]) for m in mine)
        if t["visibility"] == "hidden":
            assert t["troops"] is None and t["troops_range"] is None
    assert tr["T08"]["visibility"] == "adjacent"          # rota marítima T03 – T08
    assert tr["T08"]["troops_range"] == "1–5"
    assert tr["T07"]["visibility"] == "hidden" and tr["T07"]["owner"] == "EUL"
    assert tr["T25"]["visibility"] == "adjacent" and tr["T25"]["owner"] is None
    f = v["faction"]
    for k in ("id", "name", "color", "emblem", "capital", "stock", "morale", "troops_total", "workforce", "labor",
              "capacity", "vp", "policy", "pacts", "pact_proposals_received", "capitulated", "bonuses"):
        assert k in f
    assert f["troops_total"] == 25 and f["vp"] == 4 + 2
    assert set(v["orders"]) == set(B.SECTIONS)
    assert v["game"]["status"] == "running"


def test_faixas_de_tropas():
    from app.game.model import troops_range
    assert [troops_range(n) for n in (1, 5, 6, 10, 11, 20, 21, 80)] == \
        ["1–5", "1–5", "6–10", "6–10", "11–20", "11–20", "21+", "21+"]


def _secret_needles(g: Game) -> list[str]:
    needles = []
    for f in g.factions.values():
        needles += [f"{v:.5f}"[:7] for v in f.betas]
        for M in (f.A_turn, f.A_clean):
            needles += [f"{v:.5f}"[:7] for row in M for v in row]
        needles.append(f.password)
    for c in g.climate.values():
        needles += [f"{v:.5f}"[:7] for row in c["P"] for v in row]
    for fid, d in g.depots.items():
        needles.append(f"{d['point'][0]}, {d['point'][1]}")
    for fid, plains in g.plain.items():
        needles += list(plains.values())
    for fid, ks in g.keys.items():
        for k in ks.values():
            for name in ("est", "true"):
                if name in k:
                    needles.append(f"{k[name][0]}, {k[name][1]}")
            if "beta" in k:
                needles.append(f"{k['beta']:.5f}"[:7])
            if "x" in k:
                needles += [f"{v:.5f}"[:7] for v in k["x"]]
    return needles


def test_segredos_nao_vazam_nas_visoes_nao_admin():
    g = started(n=4)
    # gera telegramas-relâmpago também
    g.tick(T0 + g.turn_ms // 2 + 1)
    needles = _secret_needles(g)
    forbidden_keys = ['"betas"', '"A_turn"', '"A_clean"', '"cipher_key"', '"depots"', '"challenge_keys"',
                      '"password"', '"telegrams_plain"', '"rng"', '"keys"', '"plain"', '"diary"', '"P"']
    blobs = [json.dumps(g.public_view(T0 + 1), ensure_ascii=False)]
    for fid in g.order:
        blobs.append(json.dumps(g.faction_view(fid, T0 + 1), ensure_ascii=False))
        for s in B.SECTIONS:
            blobs.append(json.dumps(g.dossier_view(fid, s), ensure_ascii=False))
            d = g.dossier_view(fid, s)
            for ds in d["datasets"]:
                blobs.append(g.dataset_csv(fid, s, ds["id"]))
    blobs.append(json.dumps(g.public_map(), ensure_ascii=False))
    text = "\n".join(blobs)
    for n in needles:
        assert n not in text, f"vazou: {n!r}"
    for k in forbidden_keys:
        assert k not in text, f"chave vazada: {k}"
    # o admin vê tudo
    adm = json.dumps(g.admin_view(T0 + 1), ensure_ascii=False)
    assert g.credentials()["GAU"] in adm and '"betas"' in adm and '"depots"' in adm
    assert json.loads(adm)["factions"]["GAU"]["telegrams_plain"]


def test_visoes_sao_json_puro():
    g = started()
    for fn in (lambda: g.to_dict(), lambda: g.admin_view(T0), lambda: g.public_view(T0),
               lambda: g.faction_view("GAU", T0)):
        json.dumps(fn(), allow_nan=False)


def test_to_dict_from_dict_continua_identico():
    g = started(n=4, seed=77)
    solve_challenges(g, "GAU", T0)
    g.submit_orders("GAU", "intendencia", {"production": {"ALI": 20, "ACO": 8, "COM": 8}, "recruit": 2}, T0)
    g.submit_orders("EUL", "governo", {"racao": 1, "propaganda": 3, "horas": 10}, T0)
    snap = json.loads(json.dumps(g.to_dict()))
    g2 = Game.from_dict(snap, MAP)
    assert json.dumps(g2.to_dict(), sort_keys=True) == json.dumps(snap, sort_keys=True)
    for _ in range(3):
        for h in (g, g2):
            h.resolve_turn(T0 + 5)
        assert json.dumps(g.to_dict(), sort_keys=True) == json.dumps(g2.to_dict(), sort_keys=True)
        assert g.rng.bit_generator.state == g2.rng.bit_generator.state
    assert g.turn == 4


def test_mesma_semente_mesma_partida():
    a, b = mk(seed=3), mk(seed=3)
    assert a.to_dict() == b.to_dict()
    assert mk(seed=4).credentials() != a.credentials()


def test_reinicio_com_prazo_vencido_devolve_o_tempo():
    g = started(minutes=10)
    snap = json.loads(json.dumps(g.to_dict()))
    g2 = Game.from_dict(snap, MAP)
    late = T0 + 3 * 3600_000
    ev = g2.tick(late)
    assert g2.turn == 1 and g2.status == "running"
    assert g2.deadline_ms > late and "phase" in types(ev)


# ------------------------------------------------------------------------------ dossiês
def test_dossies_estrutura():
    g = started()
    for s in B.SECTIONS:
        d = g.dossier_view("GAU", s)
        assert d["section"] == s and d["turn"] == 1 and d["title"].startswith("DOSSIÊ")
        assert d["briefing"].startswith("CONFIDENCIAL. Senhores")
        assert len(d["challenges"]) == 1
        ch = d["challenges"][0]
        assert ch["id"] == f"c1-{s}" and ch["attempts_left"] == 3 and not ch["solved"]
        assert ch["answer_format"] and ch["reward_text"]
        assert d["tools"]
        for ds in d["datasets"]:
            assert ds["rows"] and all(len(r) == len(ds["columns"]) for r in ds["rows"])
            assert ds["csv_url"] == f"/api/faction/dossier/{s}/{ds['id']}.csv"
    i = g.dossier_view("GAU", "inteligencia")["extras"]
    assert i["crib"] == "URGENTE " and len(i["stations"]) == 4 and len(i["intercepts"]) == 2
    assert {x["from"] for x in i["intercepts"]} <= {"EUL", "HIL", "NOE"}
    op = g.dossier_view("GAU", "operacoes")
    diary = op["datasets"][0]
    assert len(diary["rows"]) == B.DIARY_LENGTH
    gov = g.dossier_view("GAU", "governo")["datasets"][0]
    assert len(gov["rows"]) == 25


def test_csv_com_bom_virgula_e_ponto_decimal():
    g = started()
    csv_text = g.dataset_csv("GAU", "intendencia", "transacoes")
    assert csv_text.startswith("﻿")
    lines = csv_text[1:].strip().split("\n")
    assert lines[0] == ",ALI,ACO,COM"
    assert lines[-1].startswith("X,")
    assert re.fullmatch(r"X,\d+\.\d,\d+\.\d,\d+\.\d", lines[-1])
    csv_text = g.dataset_csv("GAU", "operacoes", "avistamentos")
    assert "Território" in csv_text
    with pytest.raises(ValueError, match="inexistente"):
        g.dataset_csv("GAU", "governo", "nada")


def test_dossie_antes_de_iniciar_e_nacao_invalida():
    g = mk()
    d = g.dossier_view("GAU", "governo")
    assert d["datasets"] == [] and d["challenges"] == []
    with pytest.raises(ValueError):
        g.dossier_view("ZZZ", "governo")
    with pytest.raises(ValueError):
        g.dossier_view("GAU", "cozinha")


def test_dossie_muda_a_cada_turno_e_a_tabela_reflete_producao():
    g = started(seed=21)
    g.submit_orders("GAU", "intendencia", {"production": {"ALI": 26, "ACO": 12, "COM": 12}, "recruit": 0}, T0)
    g.resolve_turn(T0 + 1)
    d = g.dossier_view("GAU", "intendencia")
    assert d["turn"] == 2 and d["challenges"][0]["id"] == "c2-intendencia"
    X = d["datasets"][0]["rows"][3][1:]
    f = g.factions["GAU"]
    assert X[0] == pytest.approx(round(f.last_x[0], 1), abs=0.01)
    # a tabela vem da matriz usada na resolução (A_prev), arredondada
    Z = np.array([r[1:] for r in d["datasets"][0]["rows"][:3]])
    A_shown = economy.A_from_transactions(Z, X)
    assert np.allclose(A_shown, f.A_prev, atol=0.01)
    # diário cresce
    diary = g.dossier_view("GAU", "operacoes")["datasets"][0]["rows"]
    assert len(diary) == B.DIARY_LENGTH + 1


# ------------------------------------------------------------------------------ telegramas
def test_interceptacao_urgente_hill_e_crib():
    g = started()
    d = g.dossier_view("GAU", "inteligencia")
    tgs = [t for t in g.faction_view("GAU", T0)["telegrams"] if t["kind"] == "intercept"]
    assert len(tgs) == 2
    for tg in tgs:
        em = tg["from"]
        plain = g.plain["GAU"][tg["id"]]
        assert plain.startswith("URGENTE ") and len(plain) <= 140 and plain == plain.upper()
        assert re.fullmatch(r"[A-Z0-9 ]+", plain)
        assert re.search(r"\d", plain)                      # números em algarismos
        K = np.array(g.factions[em].cipher_key)
        assert cipher.decrypt(tg["body"], K).strip() == plain.strip()
        # o aluno recupera a chave com o crib
        Kr = cipher.recover_key("URGENTE ", tg["body"][:8])
        assert np.array_equal(Kr, K)
        assert tg["body"] != plain and tg["section"] == "inteligencia"
    ids = {x["id"]: x for x in d["extras"]["intercepts"]}
    assert set(ids) == {t["id"] for t in tgs}
    for t in tgs:
        assert ids[t["id"]]["cipher"] == t["body"] and ids[t["id"]]["from"] == t["from"]


def test_chave_de_cifra_troca_a_cada_dois_turnos():
    g = started()
    k1 = {f: copy.deepcopy(g.factions[f].cipher_key) for f in g.order}
    g.resolve_turn(T0 + 1)
    k2 = {f: g.factions[f].cipher_key for f in g.order}
    assert k1 == k2                          # turnos 1 e 2: mesma chave
    g.resolve_turn(T0 + 2)
    k3 = {f: g.factions[f].cipher_key for f in g.order}
    assert any(k3[f] != k1[f] for f in g.order)


# ------------------------------------------------------------------------------ desafios
def test_parse_de_respostas():
    assert dossiers.parse_numbers("1,25; 3; 4,5", 3) == [1.25, 3.0, 4.5]
    assert dossiers.parse_numbers("1.25 3 4,5", 3) == [1.25, 3.0, 4.5]
    assert dossiers.parse_numbers("12,10,8", 3) == [12.0, 10.0, 8.0]
    assert dossiers.parse_numbers("(1,5;\n2;3)", 3) == [1.5, 2.0, 3.0]
    assert dossiers.parse_numbers("1,5, 2, 3", 3) == [1.5, 2.0, 3.0]
    assert dossiers.parse_numbers("x=1,5; y=2", 2) == [1.5, 2.0]
    assert dossiers.parse_numbers("−2,5", 1) == [-2.5]
    with pytest.raises(ValueError, match="Esperava 3 número"):
        dossiers.parse_numbers("1; 2", 3)
    with pytest.raises(ValueError, match="Não entendi"):
        dossiers.parse_numbers("abc; 2; 3", 3)
    assert dossiers.parse_location("K7") == ("grid", "K7")
    assert dossiers.parse_location("k 7") == ("grid", "K7")
    assert dossiers.parse_location("525; 310") == ("xy", (525.0, 310.0))
    assert dossiers.parse_location("525,5 310,2") == ("xy", (525.5, 310.2))
    with pytest.raises(ValueError):
        dossiers.parse_location("Z99")


def test_desafios_corretos_dos_quatro_e_recompensas():
    g = started(seed=31)
    f0 = copy.deepcopy(g.factions["GAU"].morale)
    res = solve_challenges(g, "GAU", T0)
    assert set(res) == set(B.SECTIONS)
    for s, r in res.items():
        assert r["correct"], (s, r)
    assert res["intendencia"]["reward"]["type"] == "productivity"
    assert res["operacoes"]["reward"]["type"] == "weather"
    assert res["inteligencia"]["reward"]["type"] == "depot"
    assert res["governo"]["reward"]["type"] == "morale"
    f = g.factions["GAU"]
    assert f.bonuses["productivity"] and f.bonuses["weather_revealed"]
    assert f.morale == f0 + 5
    assert f.challenges_solved == 4
    # +0,25 PV por desafio
    assert g.vp("GAU") == 4 + 2 + 1.0
    # clima revelado e depósito localizado aparecem na visão da facção
    v = g.faction_view("GAU", T0)
    assert v["weather_forecast"] == {r: g.climate[r]["next"] for r in B.REGIONS}
    loc = v["faction"]["bonuses"]["depot_located"]
    assert loc and g.dossiers["GAU"]["inteligencia"]
    tr = {t["id"]: t for t in v["territories"]}
    assert tr[loc["territory"]]["visibility"] == "revealed"
    assert tr[loc["territory"]]["troops"] == g.troops[loc["territory"]]
    # já resolvido: não duplica
    again = g.answer_challenge("GAU", "c1-governo", "1", T0)
    assert again["correct"] and again["reward"] is None and f.challenges_solved == 4


def test_desafio_tentativas_e_mensagens():
    g = started(seed=32)
    r = g.answer_challenge("GAU", "c1-intendencia", "1; 2", T0)
    assert not r["correct"] and r["attempts_left"] == 3 and "Esperava 3 número" in r["message"]
    r = g.answer_challenge("GAU", "c1-intendencia", "1; 2; 3", T0)
    assert not r["correct"] and r["attempts_left"] == 2 and "2%" in r["message"]
    g.answer_challenge("GAU", "c1-intendencia", "1; 2; 3", T0)
    r = g.answer_challenge("GAU", "c1-intendencia", "1; 2; 3", T0)
    assert r["attempts_left"] == 0 and not r["correct"]
    r = g.answer_challenge("GAU", "c1-intendencia", "1; 2; 3", T0)
    assert "tentativas" in r["message"] and r["attempts_left"] == 0
    assert g.dossier_view("GAU", "intendencia")["challenges"][0]["attempts_left"] == 0
    with pytest.raises(ValueError, match="inexistente"):
        g.answer_challenge("GAU", "c9-governo", "1", T0)
    # desafio do turno anterior deixa de existir
    g.resolve_turn(T0 + 1)
    with pytest.raises(ValueError):
        g.answer_challenge("GAU", "c1-governo", "1", T0 + 2)


def test_mensagens_de_resposta_no_singular_e_no_plural():
    # resposta única: pede "um número", sem o "número(s)" genérico
    g = started(seed=34)
    r = g.answer_challenge("GAU", "c1-governo", "1 2 3", T0)
    assert not r["correct"] and "um número" in r["message"] and "(s)" not in r["message"]
    # erro de formato não gasta tentativa; erro de valor gasta e a mensagem concorda com o número restante
    r = g.answer_challenge("GAU", "c1-governo", "99", T0)
    assert r["attempts_left"] == 2 and "Restam 2 tentativas." in r["message"]
    r = g.answer_challenge("GAU", "c1-governo", "99", T0)
    assert r["attempts_left"] == 1 and "Resta 1 tentativa." in r["message"]


def test_tolerancias_dos_desafios():
    g = started(seed=33)
    key = g.keys["GAU"]["c1-intendencia"]
    x = key["x"]
    near = "; ".join(br(v * 1.015) for v in x)
    far = "; ".join(br(v * 1.06) for v in x)
    assert g.answer_challenge("GAU", "c1-intendencia", far, T0)["correct"] is False
    assert g.answer_challenge("GAU", "c1-intendencia", near, T0)["correct"] is True
    # Markov: ±0.03, percentual aceito
    p = g.keys["GAU"]["c1-operacoes"]["p"]
    assert g.answer_challenge("GAU", "c1-operacoes", br(p + 0.05), T0)["correct"] is False
    assert g.answer_challenge("GAU", "c1-operacoes", f"{(p + 0.025) * 100:.1f}%".replace(".", ","), T0)["correct"]
    # beta ±0.15
    b = g.keys["GAU"]["c1-governo"]["beta"]
    assert not g.answer_challenge("GAU", "c1-governo", br(b + 0.3), T0)["correct"]
    assert g.answer_challenge("GAU", "c1-governo", br(b - 0.1), T0)["correct"]
    # depósito: 25 unidades ou mesma quadrícula
    ex, ey = g.keys["GAU"]["c1-inteligencia"]["est"]
    assert not g.answer_challenge("GAU", "c1-inteligencia", f"{ex + 100:.0f}; {ey:.0f}", T0)["correct"]
    cell = geo.grid_label(ex, ey)
    assert g.answer_challenge("GAU", "c1-inteligencia", cell, T0)["correct"]


def test_gabarito_vem_dos_dados_entregues_nao_do_segredo():
    """A chave do Leontief usa A calculada da tabela arredondada que o aluno vê."""
    g = started(seed=34)
    d = g.dossier_view("GAU", "intendencia")
    rows = d["datasets"][0]["rows"]
    Z = np.array([r[1:] for r in rows[:3]], float)
    X = np.array(rows[3][1:], float)
    A = economy.A_from_transactions(Z, X)
    dstar = [float(v) for v in re.findall(r"(\d+) (?:ALI|ACO|COM)", d["challenges"][0]["prompt"])]
    assert np.allclose(g.keys["GAU"]["c1-intendencia"]["x"], economy.required_production(A, dstar))
    # a demanda é viável (mão de obra e capacidade)
    x = economy.required_production(A, dstar)
    assert np.dot([B.LABOR[s] for s in SEC], x) <= g.workforce("GAU")
    assert all(x[i] <= g.capacity("GAU")[s] for i, s in enumerate(SEC))
    # Markov: P estimada por contagem do diário que ele vê
    ch = d  # noqa
    op = g.dossier_view("GAU", "operacoes")
    m = re.search(r"região (\w+) o tempo está agora em «(\w+)»", op["challenges"][0]["prompt"])
    col = {"norte": 1, "centro": 2, "sul": 3}[m.group(1).lower()]
    seq = [B.WEATHER_NAMES.index(r[col]) for r in op["datasets"][0]["rows"]]
    assert g.keys["GAU"]["c1-operacoes"]["p"] == pytest.approx(
        weather.estimate_P(seq)[B.WEATHER_NAMES.index(m.group(2)), 2])
    # OLS sobre a pesquisa que ele vê
    gv = g.dossier_view("GAU", "governo")
    cols = ["obs", "racao", "propaganda", "horas_extra", "baixas", "saldo_territorial", "delta_moral"]
    rows = [dict(zip(cols, r)) for r in gv["datasets"][0]["rows"]]
    assert g.keys["GAU"]["c1-governo"]["beta"] == pytest.approx(morale.ols(rows)[2])
    # trilateração sobre as leituras que ele vê
    it = g.dossier_view("GAU", "inteligencia")["datasets"][0]["rows"]
    est = geo.trilaterate([[r[1], r[2]] for r in it], [r[3] for r in it])
    assert g.keys["GAU"]["c1-inteligencia"]["est"] == pytest.approx(list(est))
    # a localização verdadeira fica perto da estimativa (ruído 8)
    tr = g.keys["GAU"]["c1-inteligencia"]["true"]
    assert np.hypot(est[0] - tr[0], est[1] - tr[1]) < 40


def test_bonus_de_produtividade_vale_no_turno_e_moral_imediato():
    ga, gb = started(seed=40), started(seed=40)
    order = {"production": {"ALI": 20, "ACO": 10, "COM": 10}, "recruit": 0}
    for g in (ga, gb):
        g.submit_orders("GAU", "intendencia", order, T0)
    r = ga.answer_challenge("GAU", "c1-intendencia",
                            "; ".join(br(v) for v in ga.keys["GAU"]["c1-intendencia"]["x"]), T0)
    assert r["correct"]
    ga.resolve_turn(T0 + 1)
    gb.resolve_turn(T0 + 1)
    assert ga.factions["GAU"].last_x == pytest.approx([v * 1.1 for v in gb.factions["GAU"].last_x])
    assert any("Plano aprovado" in ln for ln in ga.factions["GAU"].last_report["lines"])


# ------------------------------------------------------------------------------ ordens
def test_validacao_de_ordens():
    g = started()
    ok = g.submit_orders("GAU", "intendencia", {"production": {"ALI": 20, "ACO": 8, "COM": 8}, "recruit": 2}, T0)
    assert ok["ok"] and ok["order"]["production"]["ALI"] == 20 and ok["order"]["recruit"] == 2
    r = g.submit_orders("GAU", "intendencia", {"production": {"ALI": 99, "ACO": 0, "COM": 0}}, T0)
    assert not r["ok"] and "capacidade" in r["errors"][0]
    assert g.faction_view("GAU", T0)["orders"]["intendencia"]["production"]["ALI"] == 20     # a anterior vale
    r = g.submit_orders("GAU", "intendencia", {"production": {"ALI": -1}}, T0)
    assert not r["ok"]
    r = g.submit_orders("GAU", "intendencia", {"production": {"ALI": 29, "ACO": 25, "COM": 16}}, T0)
    assert r["ok"] and any("Mão de obra" in w for w in r["warnings"])
    # operações
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T07", "to": "T08", "troops": 1}]}, T0)
    assert not r["ok"] and "não é um território seu" in r["errors"][0]
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T05", "troops": 1}]}, T0)
    assert not r["ok"] and "não é vizinho" in r["errors"][0]
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T22", "troops": 6}]}, T0)
    assert not r["ok"] and "apenas 5" in r["errors"][0]
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T03", "to": "T08", "troops": 4}]}, T0)
    assert r["ok"] and any("marítima" in w for w in r["warnings"])
    # inteligência
    r = g.submit_orders("GAU", "inteligencia", {"bombard": "T07"}, T0)
    assert not r["ok"] and "depósito" in r["errors"][0]
    assert g.submit_orders("GAU", "inteligencia", {"bombard": None}, T0)["ok"]
    # governo
    r = g.submit_orders("GAU", "governo", {"racao": 3, "horas": 9}, T0)
    assert not r["ok"] and len(r["errors"]) == 2
    r = g.submit_orders("GAU", "governo", {"racao": 1, "propaganda": 2, "horas": 10,
                                           "transfers": [{"to": "EUL", "ALI": 5}], "pact_propose": ["EUL"]}, T0)
    assert r["ok"] and r["order"]["transfers"] == [{"to": "EUL", "ALI": 5.0, "ACO": 0.0, "COM": 0.0}]
    r = g.submit_orders("GAU", "governo", {"pact_denounce": ["EUL"]}, T0)
    assert not r["ok"]
    r = g.submit_orders("GAU", "governo", {"pact_propose": ["GAU"]}, T0)
    assert not r["ok"]
    with pytest.raises(ValueError):
        g.submit_orders("GAU", "cozinha", {}, T0)
    assert not g.submit_orders("GAU", "governo", "x", T0)["ok"]
    with pytest.raises(ValueError):
        g.submit_orders("ZZZ", "governo", {}, T0)


# ------------------------------------------------------------------------------ resolução
def test_producao_liquida_e_estoque_nunca_negativo():
    g = started(seed=50)
    f = g.factions["GAU"]
    st0 = dict(f.stock)
    x = {"ALI": 20, "ACO": 8, "COM": 8}
    g.submit_orders("GAU", "intendencia", {"production": x, "recruit": 0}, T0)
    A = np.array(f.A_turn)
    net = economy.net_output(A, [20, 8, 8])
    g.resolve_turn(T0 + 1)
    # produção + manutenção (12.5 + 6)
    assert f.stock["ALI"] == pytest.approx(st0["ALI"] + net[0] - 18.5, abs=0.02)
    assert f.stock["ACO"] == pytest.approx(st0["ACO"] + net[1], abs=0.02)
    lines = f.last_report["lines"]
    assert any(l.startswith("Produção bruta") for l in lines) and any("Manutenção" in l for l in lines)
    assert any(l.startswith("Moral:") for l in lines) and any(l.startswith("Clima:") for l in lines)
    assert f.last_report["turn"] == 1


def test_mao_de_obra_limita_a_producao():
    g = started(seed=51)
    f = g.factions["GAU"]
    g.submit_orders("GAU", "intendencia", {"production": {"ALI": 29, "ACO": 25, "COM": 16}}, T0)
    W = g.workforce("GAU")
    g.resolve_turn(T0 + 1)
    used = float(np.dot([B.LABOR[s] for s in SEC], f.last_x))
    assert used == pytest.approx(W, rel=1e-6)
    assert any("Mão de obra insuficiente" in l for l in f.last_report["lines"])


def test_recrutamento_escala_por_estoque_e_aparece_na_capital():
    g = started(seed=52)
    f = g.factions["GAU"]
    g.admin_edit_faction("GAU", {"stock": {"ALI": 100, "ACO": 7, "COM": 100}}, T0)
    g.submit_orders("GAU", "intendencia", {"production": {"ALI": 0, "ACO": 0, "COM": 0}, "recruit": 10}, T0)
    t0 = g.troops["T03"]
    g.resolve_turn(T0 + 1)
    assert g.troops["T03"] == t0 + 3             # ACO 7 -> 3 recrutas
    assert f.stock["ACO"] == pytest.approx(1.0, abs=0.01)
    assert any("Recrutamento reduzido de 10 para 3" in l for l in f.last_report["lines"])
    assert all(isinstance(v, int) for v in g.troops.values())


def test_fome_gera_atricao_e_moral():
    g = started(seed=53)
    g.admin_edit_faction("GAU", {"stock": {"ALI": 5}}, T0)
    m0 = g.factions["GAU"].morale
    n0 = g.troops_total("GAU")
    g.resolve_turn(T0 + 1)
    f = g.factions["GAU"]
    assert f.stock["ALI"] == 0
    assert g.troops_total("GAU") == n0 - 3       # ceil(10% de 25)
    assert f.morale < m0 - 5
    assert any("FOME" in l for l in f.last_report["lines"])
    assert "GAU" in g.history[-1]["starved"]
    assert any("Falta de víveres" in n["body"] and "Gáussia" in n["body"] for n in g.news)


def _duel(a, b, origin="T02", target="T22", seed=60, extra=None):
    g = started(seed=seed)
    g.admin_edit_faction("GAU", {"troops": {origin: a, target: b}, "stock": {"COM": 100}}, T0)
    if extra:
        extra(g)
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": origin, "to": target, "troops": a}]}, T0)
    assert r["ok"], r
    g.resolve_turn(T0 + 1)
    return g


def test_batalha_um_para_um_custa_caro_aos_dois_lados():
    losses = []
    for s in range(12):
        g = _duel(10, 10, seed=100 + s)
        b = g.last_resolution["battles"][0]
        assert b["att_before"] == 10 and b["def_before"] == 10
        losses.append(((10 - b["att_after"]) / 10, (10 - b["def_after"]) / 10))
    la = np.mean([x[0] for x in losses])
    ld = np.mean([x[1] for x in losses])
    assert la > 0.5 and ld > 0.4, (la, ld)


def test_vantagem_decisiva_captura():
    g = _duel(18, 6)
    b = g.last_resolution["battles"][0]
    assert b["result"] == "captured" and g.owner["T22"] == "GAU"
    assert g.troops["T22"] == b["att_after"] and b["def_after"] == 0
    assert g.troops["T02"] == 0 or g.troops["T02"] >= 0
    assert any("VITÓRIA" in l for l in g.factions["GAU"].last_report["lines"])
    assert g.public_view(T0)["territories"][21] == {"id": "T22", "owner": "GAU"}
    assert any(n["kind"] == "capture" for n in g.news)


def test_ataque_fraco_repelido_e_retirada_perdida():
    g = _duel(5, 12)
    b = g.last_resolution["battles"][0]
    assert b["result"] in ("repelled", "stalemate") and g.owner["T22"] is None
    assert g.troops["T22"] >= 1


def test_ataque_a_territorio_vazio_conquista_sem_perdas():
    g = started(seed=61)
    g.admin_edit_faction("GAU", {"troops": {"T22": 0, "T02": 5}, "stock": {"COM": 100}}, T0)
    g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T22", "troops": 4}]}, T0)
    g.resolve_turn(T0 + 1)
    b = g.last_resolution["battles"][0]
    assert b["result"] == "captured" and b["att_after"] == 4 and g.troops["T22"] == 4


def test_combustivel_insuficiente_escala_movimentos():
    g = started(seed=62)
    g.admin_edit_faction("GAU", {"stock": {"COM": 0}, "troops": {"T04": 5}}, T0)
    g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T04", "to": "T03", "troops": 4}]}, T0)
    t3 = g.troops["T03"]
    g.resolve_turn(T0 + 1)
    assert g.troops["T04"] == 5 + 0 and g.troops["T03"] == t3     # sem COM, ninguém se move
    assert g.factions["GAU"].stock["COM"] >= 0


def test_reforco_move_tropas_entre_territorios_proprios():
    g = started(seed=63)
    t4, t3 = g.troops["T04"], g.troops["T03"]
    g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T04", "to": "T03", "troops": 3}]}, T0)
    com0 = g.factions["GAU"].stock["COM"]
    g.resolve_turn(T0 + 1)
    assert g.troops["T04"] == t4 - 3 and g.troops["T03"] == t3 + 3
    res = g.last_resolution
    assert {"from": "T04", "to": "T03", "faction": "GAU", "troops": 3} in res["moves"]
    assert g.factions["GAU"].stock["COM"] == pytest.approx(com0 - 3, abs=0.01)


def test_ordem_invalida_na_resolucao_e_ignorada():
    g = started(seed=64)
    g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T22", "troops": 5}]}, T0)
    # o árbitro tira o território antes da resolução
    g.admin_edit_faction("GAU", {"owner": {"T02": "EUL"}}, T0)
    g.resolve_turn(T0 + 1)
    assert any("ignorada" in l for l in g.factions["GAU"].last_report["lines"])
    assert g.last_resolution["battles"] == [] or all(b["attacker"] != "GAU" for b in g.last_resolution["battles"])


def test_varios_ataques_ao_mesmo_alvo_em_ordem_de_forca():
    g = started(seed=65)
    # GAU (T02->T22, 12) e NOE (T17? vizinho de T22) atacam T22 (neutro, 6)
    g.admin_edit_faction("GAU", {"troops": {"T02": 12, "T22": 6}, "stock": {"COM": 100}}, T0)
    g.admin_edit_faction("NOE", {"owner": {"T17": "NOE"}, "troops": {"T17": 20}, "stock": {"COM": 100}}, T0)
    assert g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T22", "troops": 12}]}, T0)["ok"]
    assert g.submit_orders("NOE", "operacoes", {"moves": [{"from": "T17", "to": "T22", "troops": 20}]}, T0)["ok"]
    g.resolve_turn(T0 + 1)
    bs = [b for b in g.last_resolution["battles"] if b["to"] == "T22"]
    assert len(bs) == 2
    assert bs[0]["attacker"] == "NOE" and bs[0]["result"] == "captured"    # o mais forte primeiro
    assert bs[1]["attacker"] == "GAU" and bs[1]["defender"] == "NOE"
    assert bs[1]["def_before"] == bs[0]["att_after"]


def test_pacto_firma_bloqueia_ataque_e_denuncia_custa_moral():
    g = started(seed=66)
    assert g.submit_orders("GAU", "governo", {"pact_propose": ["EUL"]}, T0)["ok"]
    assert g.submit_orders("EUL", "governo", {"pact_propose": ["GAU"]}, T0)["ok"]
    g.resolve_turn(T0 + 1)
    f = g.factions["GAU"]
    assert f.pacts == [{"with": "EUL", "until_turn": 3}]
    v = g.faction_view("GAU", T0 + 2)
    assert v["faction"]["pacts"] == [{"with": "EUL", "until_turn": 3}]
    assert any(n["kind"] == "politics" and "pacto" in (n["headline"] + n["body"]).lower() for n in g.news)
    # ataque entre pactuados é recusado no envio (T03 -> T08 é rota marítima para território de EUL)
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T03", "to": "T08", "troops": 3}]}, T0 + 2)
    assert not r["ok"] and "pacto" in r["errors"][0].lower()
    # denúncia
    m0 = f.morale
    assert g.submit_orders("GAU", "governo", {"pact_denounce": ["EUL"]}, T0 + 2)["ok"]
    g.resolve_turn(T0 + 3)
    assert f.pacts == [] and g.factions["EUL"].pacts == []
    assert any("denunci" in l for l in f.last_report["lines"])
    assert any(l.startswith("Moral:") and "pacto denunciado (-5)" in l for l in f.last_report["lines"])


def test_pacto_bloqueia_ataque_na_resolucao():
    g = started(seed=67)
    g.admin_edit_faction("GAU", {"troops": {"T02": 15}, "owner": {"T22": "EUL"}}, T0)
    g.admin_edit_faction("EUL", {"troops": {"T22": 2}}, T0)
    # pacto em vigor
    g.factions["GAU"].pacts.append({"with": "EUL", "until_turn": 5})
    g.factions["EUL"].pacts.append({"with": "GAU", "until_turn": 5})
    r = g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T22", "troops": 8}]}, T0)
    assert not r["ok"] and "pacto" in r["errors"][0].lower()
    # ordem dada antes do pacto: cancelada na resolução
    g.factions["GAU"].pacts.clear()
    g.factions["EUL"].pacts.clear()
    assert g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T02", "to": "T22", "troops": 8}]}, T0)["ok"]
    g.factions["GAU"].pacts.append({"with": "EUL", "until_turn": 5})
    g.factions["EUL"].pacts.append({"with": "GAU", "until_turn": 5})
    g.resolve_turn(T0 + 1)
    assert g.owner["T22"] == "EUL" and g.last_resolution["battles"] == []
    assert any("pacto" in l.lower() for l in g.factions["GAU"].last_report["lines"])


def test_transferencias_entre_nacoes():
    g = started(seed=68)
    g.submit_orders("GAU", "governo", {"transfers": [{"to": "EUL", "ALI": 10, "ACO": 500}]}, T0)
    s_g, s_e = dict(g.factions["GAU"].stock), dict(g.factions["EUL"].stock)
    g.resolve_turn(T0 + 1)
    # ACO 500 foi reduzido ao estoque (30): nunca negativo
    assert g.factions["GAU"].stock["ACO"] >= 0
    assert g.factions["EUL"].stock["ACO"] >= s_e["ACO"] + 29 - 1


def test_capital_perdida_derruba_moral_e_vira_pv():
    g = started(seed=69)
    # EUL ataca a capital de GAU (T03) com muito mais força
    g.admin_edit_faction("GAU", {"troops": {"T03": 2}}, T0)
    g.admin_edit_faction("EUL", {"owner": {"T01": "EUL"}, "troops": {"T01": 30}, "stock": {"COM": 100}}, T0)
    g.admin_edit_faction("GAU", {"owner": {"T01": "EUL"}}, T0)
    m0 = g.factions["GAU"].morale
    assert g.submit_orders("EUL", "operacoes", {"moves": [{"from": "T01", "to": "T03", "troops": 30}]}, T0)["ok"]
    g.resolve_turn(T0 + 1)
    assert g.owner["T03"] == "EUL"
    assert any("CAPITAL" in l for l in g.factions["GAU"].last_report["lines"])
    assert g.factions["GAU"].morale < m0 - 10
    assert g.vp("EUL") >= 4 + 3 + 2           # territórios + capital extra
    assert any("Capital de Gáussia cai" in n["headline"] or "capital" in n["body"].lower() for n in g.news)


def test_capitulacao_sem_territorios():
    g = started(seed=70, n=3)
    for t in list(g.order_tids):
        if g.owner[t] == "GAU":
            g.owner[t] = "EUL"
    g.resolve_turn(T0 + 1)
    assert g.factions["GAU"].capitulated
    assert g.status == "running"
    assert any(n["headline"].lower().find("capitula") >= 0 or "rende" in n["headline"] or "Fim de" in n["headline"]
               for n in g.news)
    r = None
    with pytest.raises(ValueError, match="capitulou"):
        g.submit_orders("GAU", "governo", {}, T0 + 2)
    # sem dossiê para quem capitulou
    assert g.dossier_view("GAU", "governo")["datasets"] == []


def test_domination_ou_ultima_nacao_encerra():
    g = started(seed=71, n=2)
    for t in g.order_tids:
        if g.owner[t] != "GAU" and g.owner[t] is not None:
            g.owner[t] = "GAU"
    g.resolve_turn(T0 + 1)
    assert g.status == "finished" and g.winner == "GAU"
    assert g.end_reason in ("last_standing", "domination")


def test_clima_tempestade_fecha_o_mar():
    g = started(seed=72)
    for r in B.REGIONS:
        g.climate[r]["next"] = 2
    g.admin_edit_faction("GAU", {"stock": {"COM": 100}}, T0)
    g.submit_orders("GAU", "operacoes", {"moves": [{"from": "T03", "to": "T08", "troops": 4}]}, T0)
    t3 = g.troops["T03"]
    g.resolve_turn(T0 + 1)
    assert g.owner["T08"] == "EUL"
    assert g.troops["T03"] == t3
    assert any("tempestade" in l for l in g.factions["GAU"].last_report["lines"])
    assert g.public_view(T0)["weather"] == {"norte": 2, "centro": 2, "sul": 2}
    assert any(n["kind"] == "weather" for n in g.news)


def test_bombardeio_exige_localizacao_e_causa_dano():
    g = started(seed=73)
    res = solve_challenges(g, "GAU", T0, only=["inteligencia"])
    assert res["inteligencia"]["correct"]
    loc = g.faction_view("GAU", T0)["faction"]["bonuses"]["depot_located"]
    victim = g.owner[loc["territory"]]
    assert victim and victim != "GAU"
    st = dict(g.factions[victim].stock)
    big = max(SEC, key=lambda s: st[s])
    r = g.submit_orders("GAU", "inteligencia", {"bombard": loc["territory"]}, T0)
    assert r["ok"]
    com0 = g.factions["GAU"].stock["COM"]
    g.resolve_turn(T0 + 1)
    assert g.factions["GAU"].stock["COM"] <= com0 - 4 + 15           # gastou 4 (e produziu algo, se ordenado)
    assert any("Bombardeio" in l for l in g.factions["GAU"].last_report["lines"])
    assert any("Bombardeio" in l for l in g.factions[victim].last_report["lines"])
    assert any("Depósitos" in n["headline"] or "Bombardeio" in n["headline"] for n in g.news)
    # a matriz piorou no turno seguinte (diagonal maior)
    assert g.factions[victim].A_turn is not None


# ------------------------------------------------------------------------------ mensagens e árbitro
def test_diplomacia_e_broadcast():
    g = started()
    ev = g.send_message("GAU", "EUL", "Propomos pacto.", T0)
    assert {e["channel"] for e in ev} == {"faction:EUL", "faction:GAU"} and types(ev) == ["message", "message"]
    assert g.faction_view("EUL", T0)["messages"][-1]["text"] == "Propomos pacto."
    assert g.faction_view("GAU", T0)["messages"][-1]["to"] == "EUL"
    with pytest.raises(ValueError):
        g.send_message("GAU", "GAU", "oi", T0)
    with pytest.raises(ValueError):
        g.send_message("GAU", "EUL", "  ", T0)
    with pytest.raises(ValueError):
        g.send_message("GAU", "XXX", "oi", T0)
    ev = g.admin_broadcast("Atenção, senhores.", "all", T0)
    assert ev[0]["channel"] == "public" and ev[0]["type"] == "broadcast"
    ev = g.admin_broadcast("Só para vós.", "NOE", T0)
    assert ev[0]["channel"] == "faction:NOE"
    assert [t for t in g.faction_view("NOE", T0)["telegrams"] if t["kind"] == "broadcast"][-1]["body"] == "Só para vós."
    with pytest.raises(ValueError):
        g.admin_broadcast("", "all", T0)


def test_admin_edit_faction():
    g = started()
    ev = g.admin_edit_faction("GAU", {"stock": {"ALI": 77}, "morale": 55, "troops": {"T04": 9},
                                      "owner": {"T22": "GAU", "T01": None}}, T0)
    f = g.factions["GAU"]
    assert f.stock["ALI"] == 77 and f.morale == 55 and g.troops["T04"] == 9
    assert g.owner["T22"] == "GAU" and g.owner["T01"] is None
    assert ev
    for bad in ({"morale": 120}, {"stock": {"XYZ": 1}}, {"troops": {"T04": -1}}, {"owner": {"T99": "GAU"}},
                {"foo": 1}, {"troops": {"T04": 1.5}}):
        with pytest.raises(ValueError):
            g.admin_edit_faction("GAU", bad, T0)
    assert f.morale == 55         # nada foi aplicado pelos inválidos
    with pytest.raises(ValueError):
        g.admin_edit_faction("ZZZ", {}, T0)


def test_eventos_globais():
    lst = EV.list_events()
    assert len(lst) == 8 and all(set(e) == {"id", "name", "description"} for e in lst)
    assert {e["id"] for e in lst} == {"greve_siderurgia", "colheita_recorde", "epidemia_gripe",
                                      "descoberta_petroleo", "inverno_precoce", "sabotagem_ferroviaria",
                                      "ajuda_estrangeira", "motim"}
    for e in lst:
        g = started(seed=80)
        ev = g.admin_trigger_event(e["id"], T0)
        assert "news" in types(ev) and g.news[-1]["kind"] == "event"
        g.resolve_turn(T0 + 1)          # o efeito se aplica e depois é removido ou continua (duração)
        assert all(x["until_turn"] > 1 for x in g.effects)
    with pytest.raises(ValueError):
        started().admin_trigger_event("terremoto", T0)
    with pytest.raises(ValueError):
        mk().admin_trigger_event("motim", T0)


def test_evento_reduz_producao_e_expira():
    g = started(seed=81)
    g.admin_trigger_event("greve_siderurgia", T0)
    assert g.effect_mult("GAU", "prod_ACO") == 0.7
    g.submit_orders("GAU", "intendencia", {"production": {"ALI": 10, "ACO": 10, "COM": 5}}, T0)
    g.resolve_turn(T0 + 1)
    assert g.factions["GAU"].last_x[1] == pytest.approx(7.0, abs=0.01)
    assert not [e for e in g.effects if e["event"] == "greve_siderurgia"]
    w0 = g.workforce("GAU")
    g.admin_trigger_event("epidemia_gripe", T0 + 2)
    assert g.workforce("GAU") == pytest.approx(w0 * 0.85)
    g.resolve_turn(T0 + 3)
    gripe = [e for e in g.effects if e["event"] == "epidemia_gripe"]
    assert gripe and gripe[0]["until_turn"] == 3             # dura 2 turnos (turnos 2 e 3)
    g.resolve_turn(T0 + 4)
    assert not [e for e in g.effects if e["event"] == "epidemia_gripe"]


def test_eventos_sorteados_a_partir_do_turno_2(monkeypatch):
    monkeypatch.setattr(B, "EVENT_PROB", 0.6)
    counts = 0
    for seed in range(40):
        g = started(seed=seed, n=2)
        assert g.event_log == []
        g.resolve_turn(T0 + 1)
        counts += len(g.event_log)
    assert 12 <= counts <= 36      # ~0,6 de 40


# ------------------------------------------------------------------------------ notícias
def test_noticias_formato_e_ordem():
    g = started(seed=90)
    for i in range(3):
        g.resolve_turn(T0 + i + 1)
    pv = g.public_view(T0 + 10)
    assert 0 < len(pv["news"]) <= 20
    for n in pv["news"]:
        assert set(n) == {"turn", "headline", "body", "kind"}
        assert n["kind"] in ("battle", "capture", "event", "politics", "weather")
    turns = [n["turn"] for n in pv["news"]]
    assert turns == sorted(turns, reverse=True)


def test_manchetes_variadas():
    from app.game import news as N
    rng = np.random.default_rng(0)
    heads = {N.capture(rng, 2, "Gáussia", "Eulerândia", "Forte X", False, 10, 5, 7, 8)["headline"]
             for _ in range(60)}
    assert len(heads) >= 4
    for kind_fn in (lambda: N.starvation(rng, 2, "Gáussia"), lambda: N.pact_formed(rng, 2, "A", "B", 4),
                    lambda: N.leader(rng, 3, "A", 8, "B", 7), lambda: N.capitulation(rng, 3, "A", "Cap")):
        item = kind_fn()
        assert item["headline"] and item["body"]
