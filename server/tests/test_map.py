"""Validação do mapa gerado (server/app/data/map.json). Rodar de `server/`: pytest tests/test_map.py"""
import json
import math
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "server" / "app" / "data" / "map.json"
MOCK_PATH = ROOT / "web" / "mock" / "map.json"

TERRAINS = {"planicie", "floresta", "montanha", "pantano", "urbano"}
CLIMATES = {"norte", "centro", "sul"}
BASE = {
    "planicie": (12, 3, 3), "floresta": (6, 5, 4), "montanha": (3, 10, 4),
    "pantano": (5, 2, 10), "urbano": (6, 8, 6),
}


@pytest.fixture(scope="module")
def m():
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def T(m):
    return {t["id"]: t for t in m["territories"]}


# ---------------------------------------------------------------- geometria auxiliar


def point_in_polygon(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def dist_to_ring(p, ring):
    return min(seg_dist(p, ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring)))


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(p1, p2, p3, p4):
    """Interseção própria (cruzamento) entre segmentos; toques em extremos compartilhados são ignorados."""
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    return ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and \
           ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9))


def self_intersections(poly):
    n = len(poly)
    bad = []
    for i in range(n):
        a1, a2 = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            b1, b2 = poly[j], poly[(j + 1) % n]
            if segments_cross(a1, a2, b1, b2):
                bad.append((i, j))
    return bad


def area(poly):
    s = 0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


# ---------------------------------------------------------------- esquema


def test_toplevel(m):
    assert m["width"] == 1200 and m["height"] == 800
    assert m["grid"] == {"cell": 50, "cols": "ABCDEFGHIJKLMNOPQRSTUVWX", "rows": 16}
    assert [c["id"] for c in m["climate_regions"]] == ["norte", "centro", "sul"]
    for key in ("territories", "home_slots", "sea_routes", "land", "rivers", "relief", "labels"):
        assert key in m and len(m[key]) > 0, key


def test_territory_schema(m):
    assert len(m["territories"]) == 34
    ids = [t["id"] for t in m["territories"]]
    assert ids == [f"T{i:02d}" for i in range(1, 35)]
    names = [t["name"] for t in m["territories"]]
    assert len(set(names)) == 34
    for t in m["territories"]:
        for k in ("id", "name", "polygon", "centroid", "label_pos", "terrain", "climate", "home_slot",
                  "capital", "capacity", "neighbors", "sea_neighbors", "coastal"):
            assert k in t, (t["id"], k)
        assert t["terrain"] in TERRAINS
        assert t["climate"] in CLIMATES
        assert t["home_slot"] is None or t["home_slot"] in range(6)
        assert isinstance(t["capital"], bool) and isinstance(t["coastal"], bool)
        assert set(t["capacity"]) == {"ALI", "ACO", "COM"}
        assert all(isinstance(v, int) and v >= 1 for v in t["capacity"].values())
        assert 3 <= len(t["polygon"]) <= 120, (t["id"], len(t["polygon"]))
        assert len(t["centroid"]) == 2 and len(t["label_pos"]) == 2
        for x, y in t["polygon"]:
            assert 0 < x < 1200 and 0 < y < 800
            assert round(x, 1) == x and round(y, 1) == y


def test_capacity_follows_terrain_within_20pct(T):
    for t in T.values():
        base = BASE[t["terrain"]]
        for v, b in zip((t["capacity"]["ALI"], t["capacity"]["ACO"], t["capacity"]["COM"]), base):
            assert abs(v - b) <= max(1, 0.2 * b) + 0.51, (t["id"], v, b)


def test_home_slots(m, T):
    assert [h["slot"] for h in m["home_slots"]] == list(range(6))
    for h in m["home_slots"]:
        assert len(h["territories"]) == 4 and len(set(h["territories"])) == 4
        for tid in h["territories"]:
            assert T[tid]["home_slot"] == h["slot"]
        caps = [tid for tid in h["territories"] if T[tid]["capital"]]
        assert caps == [h["capital"]]
        assert T[h["capital"]]["terrain"] == "urbano"
        # IDs legíveis: slot k = T(4k+1)..T(4k+4)
        assert h["territories"] == [f"T{4 * h['slot'] + j:02d}" for j in range(1, 5)]
        # 4 territórios da pátria contíguos
        seen, stack = {h["territories"][0]}, [h["territories"][0]]
        while stack:
            x = stack.pop()
            for y in T[x]["neighbors"]:
                if y in h["territories"] and y not in seen:
                    seen.add(y)
                    stack.append(y)
        assert seen == set(h["territories"]), f"pátria {h['slot']} não é contígua"
    neutrals = [t for t in T.values() if t["home_slot"] is None]
    assert len(neutrals) == 10
    assert all(not t["capital"] for t in neutrals)
    assert sum(t["capital"] for t in T.values()) == 6


def test_terrain_distribution(T):
    n = len(T)
    frac = {k: sum(t["terrain"] == k for t in T.values()) / n for k in TERRAINS}
    assert 0.28 <= frac["planicie"] <= 0.42
    assert 0.15 <= frac["floresta"] <= 0.26
    assert 0.15 <= frac["montanha"] <= 0.26
    assert 0.05 <= frac["pantano"] <= 0.15
    assert 0.12 <= frac["urbano"] <= 0.20


def test_climate_matches_centroid(T):
    for t in T.values():
        y = t["centroid"][1]
        exp = "norte" if y < 800 / 3 else ("sul" if y > 1600 / 3 else "centro")
        assert t["climate"] == exp, t["id"]


# ---------------------------------------------------------------- grafo


def test_neighbors_symmetric_and_valid(T):
    for t in T.values():
        assert t["id"] not in t["neighbors"] and t["id"] not in t["sea_neighbors"]
        assert len(set(t["neighbors"])) == len(t["neighbors"])
        for n in t["neighbors"]:
            assert n in T and t["id"] in T[n]["neighbors"], (t["id"], n)
        for n in t["sea_neighbors"]:
            assert n in T and t["id"] in T[n]["sea_neighbors"], (t["id"], n)
        assert not set(t["neighbors"]) & set(t["sea_neighbors"])


def test_neighbors_share_boundary(T):
    """Vizinhos terrestres compartilham ao menos 2 vértices (aresta comum) e comprimento > 8."""
    for t in T.values():
        pa = {tuple(p) for p in t["polygon"]}
        for n in t["neighbors"]:
            pb = {tuple(p) for p in T[n]["polygon"]}
            assert len(pa & pb) >= 2, (t["id"], n)
            shared = sorted(pa & pb)
            L = sum(math.dist(shared[i], shared[i + 1]) for i in range(len(shared) - 1))
            assert L > 8, (t["id"], n, L)


def test_sea_routes(m, T):
    assert 5 <= len(m["sea_routes"]) <= 8
    pairs = set()
    for r in m["sea_routes"]:
        a, b = r["a"], r["b"]
        assert a in T and b in T and a != b
        assert b in T[a]["sea_neighbors"] and a in T[b]["sea_neighbors"]
        assert 3 <= len(r["path"]) <= 5
        pairs.add(frozenset((a, b)))
        # pontas na costa dos respectivos territórios
        assert dist_to_ring(r["path"][0], T[a]["polygon"]) < 3
        assert dist_to_ring(r["path"][-1], T[b]["polygon"]) < 3
        # meio do caminho no mar (fora de qualquer território)
        for p in r["path"][1:-1]:
            assert not any(point_in_polygon(p, t["polygon"]) for t in T.values()), (a, b, p)
    assert len(pairs) == len(m["sea_routes"])
    assert sum(len(t["sea_neighbors"]) for t in T.values()) == 2 * len(m["sea_routes"])


def graph_dist(T, src):
    d = {src: 0}
    q = [src]
    for x in q:
        for y in T[x]["neighbors"] + T[x]["sea_neighbors"]:
            if y not in d:
                d[y] = d[x] + 1
                q.append(y)
    return d


def test_connected(T):
    assert len(graph_dist(T, "T01")) == 34


def test_ring_fairness(m, T):
    caps = [h["capital"] for h in m["home_slots"]]
    D = [[graph_dist(T, a)[b] for b in caps] for a in caps]
    for k in range(6):
        assert D[k][(k + 1) % 6] <= 3, f"slots {k} e {(k + 1) % 6} longe demais"
    # opostos (2 nações: 0,3) a boa distância, mas alcançáveis
    assert 3 <= D[0][3] <= 6


def test_islands(T):
    island = {"T32", "T33", "T34"}
    for i in island:
        assert T[i]["home_slot"] is None and T[i]["coastal"]
        assert all(n in island for n in T[i]["neighbors"])
        assert T[i]["sea_neighbors"] or any(T[n]["sea_neighbors"] for n in T[i]["neighbors"])


# ---------------------------------------------------------------- geometria


def test_points_inside_polygon(T):
    for t in T.values():
        assert point_in_polygon(t["centroid"], t["polygon"]), f"centroid fora: {t['id']}"
        assert point_in_polygon(t["label_pos"], t["polygon"]), f"label_pos fora: {t['id']}"


def test_no_self_intersection(T):
    for t in T.values():
        assert self_intersections(t["polygon"]) == [], t["id"]
    # fronteiras entre territórios distintos não se cruzam (só se tocam em vértices comuns)
    ids = sorted(T)
    for i, a in enumerate(ids):
        pa = T[a]["polygon"]
        for b in ids[i + 1:]:
            pb = T[b]["polygon"]
            ba, bb = _bbox(pa), _bbox(pb)
            if ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
                continue
            for k in range(len(pa)):
                for l in range(len(pb)):
                    assert not segments_cross(pa[k], pa[(k + 1) % len(pa)], pb[l], pb[(l + 1) % len(pb)]), (a, b)


def _bbox(p):
    xs = [q[0] for q in p]
    ys = [q[1] for q in p]
    return min(xs), min(ys), max(xs), max(ys)


def test_land_covers_territories(m, T):
    # soma das áreas dos territórios == soma das áreas das massas de terra (sem buracos/sobreposição)
    land_area = sum(area(r) for r in m["land"])
    terr_area = sum(area(t["polygon"]) for t in T.values())
    assert abs(land_area - terr_area) / terr_area < 0.003, (land_area, terr_area)
    assert len(m["land"]) == 3  # continente + 2 ilhas
    for r in m["land"]:
        assert self_intersections(r) == []
    # cada centroide de território cai dentro de alguma massa de terra
    for t in T.values():
        assert any(point_in_polygon(t["centroid"], r) for r in m["land"])


def test_sea_margin(m):
    for r in m["land"]:
        for x, y in r:
            assert 30 <= x <= 1170 and 30 <= y <= 780


def test_capacity_balance(m, T):
    tot = []
    for h in m["home_slots"]:
        tot.append(sum(sum(T[i]["capacity"].values()) for i in h["territories"]))
    mean = sum(tot) / 6
    for v in tot:
        assert abs(v - mean) / mean <= 0.10, tot


def test_rivers_relief_labels(m, T):
    assert 3 <= len(m["rivers"]) <= 5
    mountains = [t for t in T.values() if t["terrain"] == "montanha"]
    for rv in m["rivers"]:
        assert len(rv) >= 5
        src = rv[0]
        assert any(point_in_polygon(src, t["polygon"]) for t in mountains), "rio deve nascer em montanha"
        end = rv[-1]
        assert min(dist_to_ring(end, r) for r in m["land"]) < 3, "rio deve terminar na costa"
        for p in rv:
            assert 0 < p[0] < 1200 and 0 < p[1] < 800
    assert len(m["relief"]) >= 40
    for tr in m["relief"]:
        assert len(tr) >= 2
        assert any(point_in_polygon(tr[0], t["polygon"]) for t in mountains)
    texts = {lb["text"] for lb in m["labels"]}
    for need in ("MAR DE BANACH", "GOLFO DE HILBERT", "OCEANO DE FOURIER", "ESTREITO DE HADAMARD"):
        assert need in texts
    for lb in m["labels"]:
        assert lb["kind"] == "sea" and len(lb["pos"]) == 2 and "angle" in lb
        # rótulos de mar ficam no mar
        assert not any(point_in_polygon(lb["pos"], t["polygon"]) for t in T.values()), lb["text"]


def test_mock_copy_identical():
    assert MOCK_PATH.read_bytes() == MAP_PATH.read_bytes()
