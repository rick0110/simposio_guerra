"""Dados do jogo para os roteiros e as animações (sem Manim): nações, mapa, vizinhanças, direções.

Tudo vem dos mesmos arquivos que o servidor usa (balance.py e map.json): se o mapa mudar, os vídeos
gerados de novo acompanham.
"""
import importlib.util
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def balance():
    """server/app/game/balance.py (só constantes): nações, slots ativos, custos."""
    spec = importlib.util.spec_from_file_location("balance", RAIZ / "server/app/game/balance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mapa_json():
    return json.loads((RAIZ / "server/app/data/map.json").read_text())


def donos(n):
    """território -> id da nação, numa partida com n nações (mesma regra de setup.py)."""
    B, m = balance(), mapa_json()
    home = {h["slot"]: h for h in m["home_slots"]}
    dono = {}
    for i, slot in enumerate(B.ACTIVE_SLOTS[n]):
        for t in home[slot]["territories"]:
            dono[t] = B.NATIONS[i]["id"]
    return dono


DIRECOES = ["leste", "nordeste", "norte", "noroeste", "oeste", "sudoeste", "sul", "sudeste"]


def direcao(de, para):
    """Rumo de 'de' para 'para' em coordenadas do mapa (y cresce para baixo)."""
    ang = math.degrees(math.atan2(-(para[1] - de[1]), para[0] - de[0])) % 360
    return DIRECOES[int(((ang + 22.5) % 360) // 45)]


def nacao(fid, n=4):
    """Tudo o que o briefing de uma nação precisa saber sobre ela e os vizinhos."""
    B, m = balance(), mapa_json()
    T = {t["id"]: t for t in m["territories"]}
    dono = donos(n)
    ativos = [B.NATIONS[i] for i in range(n)]
    nat = B.NATION_BY_ID[fid]
    slot = B.ACTIVE_SLOTS[n][[x["id"] for x in ativos].index(fid)]
    home = next(h for h in m["home_slots"] if h["slot"] == slot)
    capitais = {}                      # tid da capital -> id da nação
    for i, s in enumerate(B.ACTIVE_SLOTS[n]):
        capitais[next(h for h in m["home_slots"] if h["slot"] == s)["capital"]] = ativos[i]["id"]

    def nome(tid):                     # o servidor mostra a capital com o nome da cidade da nação
        return B.NATION_BY_ID[capitais[tid]]["capital"] if tid in capitais else T[tid]["name"]

    def centro(f):
        cs = [T[t]["centroid"] for t, d in dono.items() if d == f]
        return (sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs))

    meus = list(home["territories"])
    c0 = centro(fid)
    outras = []
    for o in ativos:
        if o["id"] == fid:
            continue
        fronteiras = []                # (meu território, território dele) vizinhos por terra ou mar
        for t in meus:
            for v in T[t]["neighbors"] + T[t]["sea_neighbors"]:
                if dono.get(v) == o["id"]:
                    fronteiras.append((t, v))
        outras.append({**o, "dir": direcao(c0, centro(o["id"])), "fronteiras": fronteiras})
    vizinhos_neutros = sorted({v for t in meus for v in T[t]["neighbors"] + T[t]["sea_neighbors"]
                               if v not in dono})
    rotas = [r for r in m["sea_routes"] if r["a"] in meus or r["b"] in meus]
    return {
        **nat, "n": n, "slot": slot, "centro": c0,
        "posicao": direcao((600, 400), c0),
        "capital_tid": home["capital"],
        "territorios": [{"id": t, "nome": nome(t), "terreno": T[t]["terrain"], "clima": T[t]["climate"],
                         "capital": t == home["capital"]} for t in meus],
        "outras": outras,
        "neutros_vizinhos": [{"id": v, "nome": nome(v), "terreno": T[v]["terrain"]} for v in vizinhos_neutros],
        "rotas": rotas,
        "nome_de": nome,
        "capitais": capitais,
    }
