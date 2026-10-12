#!/usr/bin/env python3
"""Gerador determinístico do mapa do ESTADO-MAIOR (Continente de Lebesgue).

Uso (a partir da raiz do repositório):
    python tools/gen_map.py                 # grava server/app/data/map.json e web/mock/map.json
    python tools/gen_map.py --preview       # também gera tools/preview/map_preview.svg/.png

Dependências SÓ do gerador: numpy, shapely (>=2), scipy (opcional, não usado no núcleo).
O jogo em si lê apenas o JSON.

Pipeline:
  1. Contornos de terra: polígonos grosseiros -> Chaikin -> deslocamento de ponto médio (costa fractal).
  2. Sementes posicionadas à mão (pátrias em anel + neutros), Voronoi por massa de terra, Lloyd.
  3. Células de Voronoi convexas sem recorte: arestas subdivididas de forma canônica e deformadas por
     um campo de ruído (função pura da posição => as duas células vizinhas recebem as mesmas
     coordenadas: sem buracos nem sobreposições). Só depois recortadas pela costa.
  4. Terreno, capacidades, rios, relevo, rotas marítimas, rótulos, nomes.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

import numpy as np
from shapely.geometry import LineString, MultiPoint, MultiPolygon, Point, Polygon, box
from shapely.ops import polylabel, unary_union, voronoi_diagram

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H = 1200, 800
SEED = 1943

# --------------------------------------------------------------------------------------
# Ruído e utilidades
# --------------------------------------------------------------------------------------


class Noise:
    """Ruído de valor 2D suave, determinístico (função pura de (x, y))."""

    def __init__(self, seed: int, size: int = 256):
        rs = np.random.RandomState(seed)
        self.t = rs.uniform(-1, 1, (size, size))
        self.n = size

    def __call__(self, x: float, y: float) -> float:
        x0, y0 = math.floor(x), math.floor(y)
        fx, fy = x - x0, y - y0
        sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        i0, j0 = x0 % self.n, y0 % self.n
        i1, j1 = (i0 + 1) % self.n, (j0 + 1) % self.n
        a = self.t[i0, j0] * (1 - sx) + self.t[i1, j0] * sx
        b = self.t[i0, j1] * (1 - sx) + self.t[i1, j1] * sx
        return a * (1 - sy) + b * sy


def chaikin(pts, n=3):
    pts = [tuple(p) for p in pts]
    for _ in range(n):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        pts = out
    return pts


def resample_ring(pts, step):
    ring = list(pts) + [pts[0]]
    out = []
    carry = 0.0
    for i in range(len(ring) - 1):
        a, b = np.array(ring[i]), np.array(ring[i + 1])
        L = float(np.linalg.norm(b - a))
        d = step - carry if carry else 0.0
        while d < L:
            t = d / L if L else 0
            out.append(tuple(a + (b - a) * t))
            d += step
        carry = L - (d - step)
    return out


def fractal_ring(pts, rng, rs=(0.28, 0.2, 0.15)):
    for r in rs:
        out = []
        for i in range(len(pts)):
            a, b = np.array(pts[i]), np.array(pts[(i + 1) % len(pts)])
            d = b - a
            L = float(np.linalg.norm(d))
            nrm = np.array([-d[1], d[0]]) / (L or 1)
            off = float(np.clip(rng.normal(0, r * L), -0.55 * L, 0.55 * L))
            out.append(tuple(a))
            out.append(tuple((a + b) / 2 + nrm * off))
        pts = out
    return pts


def make_coast(coarse, rng_seed, step=50, rs=(0.28, 0.2, 0.15), tries=400):
    for k in range(tries):
        rng = np.random.RandomState(rng_seed + k)
        sm = chaikin(coarse, 2)
        res = resample_ring(sm, step)
        fr = fractal_ring(res, rng, rs)
        poly = Polygon(fr)
        if poly.is_valid and poly.area > 0:
            return poly
    raise RuntimeError("não foi possível gerar costa válida")


# --------------------------------------------------------------------------------------
# Configuração geográfica (editável)
# --------------------------------------------------------------------------------------

CONTINENT = [
    (78, 128), (120, 92), (190, 84), (238, 112), (236, 150), (282, 160), (318, 118), (372, 82),
    (430, 70), (480, 98), (488, 140), (528, 172), (556, 214), (600, 222), (640, 190), (646, 140),
    (690, 105), (760, 86), (812, 112), (850, 92), (915, 60), (990, 56), (1062, 84), (1108, 134),
    (1090, 180), (1052, 196), (1060, 240), (1092, 262), (1108, 320), (1090, 372), (1086, 430),
    (1108, 480), (1080, 540), (1040, 566), (1062, 622), (1020, 664), (940, 648), (900, 612),
    (860, 650), (800, 662), (776, 636), (772, 606), (762, 572), (754, 540), (738, 512), (722, 486),
    (676, 472), (630, 474), (590, 498), (556, 548), (534, 598), (514, 646), (520, 668), (470, 650), (430, 676),
    (384, 640), (352, 662), (330, 622), (292, 592), (250, 590), (190, 560), (140, 545), (110, 540), (106, 480),
    (100, 440), (100, 400), (96, 350), (98, 300), (84, 266), (140, 266), (198, 246), (150, 222), (96, 208),
]
ISLAND_SYLVESTER = [(535, 726), (580, 696), (650, 688), (722, 694), (778, 724), (752, 758),
                    (670, 768), (590, 764)]
ISLAND_TRACO = [(78, 690), (130, 656), (196, 668), (224, 716), (188, 760), (112, 756)]

# Sementes (x, y) por território, posicionadas à mão. IDs: slot k -> T(4k+1)..T(4k+4); em cada
# pátria a 3ª semente (T03, T07, ...) é a capital. Neutros T25..T34.
SEEDS = {
    # slot 0 (noroeste)
    "T01": (345, 128), "T02": (452, 272), "T03": (425, 188), "T04": (318, 250),
    # slot 1 (nordeste)
    "T05": (880, 172), "T06": (748, 268), "T07": (772, 172), "T08": (738, 112),
    # slot 2 (leste)
    "T09": (1020, 470), "T10": (900, 372), "T11": (1005, 372), "T12": (1012, 285),
    # slot 3 (sudeste)
    "T13": (830, 625), "T14": (792, 490), "T15": (815, 562), "T16": (925, 548),
    # slot 4 (sudoeste)
    "T17": (330, 560), "T18": (505, 508), "T19": (420, 575), "T20": (480, 632),
    # slot 5 (oeste)
    "T21": (180, 305), "T22": (292, 380), "T23": (200, 385), "T24": (190, 470),
    # neutros
    "T25": (600, 262), "T26": (525, 360), "T27": (680, 360), "T28": (610, 440),
    "T29": (1032, 628), "T30": (1035, 115), "T31": (150, 150),
    "T32": (580, 730), "T33": (715, 730), "T34": (150, 710),
}


# --------------------------------------------------------------------------------------
# Geometria: células
# --------------------------------------------------------------------------------------

ENV = box(-400, -400, 1600, 1200)
WARP = [  # (comprimento de onda, amplitude)
    (150.0, 17.0),
    (72.0, 9.5),
    (34.0, 4.5),
    (17.0, 1.6),
]
EDGE_STEP = 11.0


def warp_point(p, noises):
    x, y = p
    dx = dy = 0.0
    for (lam, amp), (nx, ny) in zip(WARP, noises):
        dx += amp * nx(x / lam + 7.3, y / lam + 3.1)
        dy += amp * ny(x / lam + 1.7, y / lam + 9.9)
    return (x + dx, y + dy)


def densify_edge(a, b, step):
    """Subdivisão canônica: o resultado independe do sentido em que a aresta é percorrida."""
    flip = (a[0], a[1]) > (b[0], b[1])
    p, q = (b, a) if flip else (a, b)
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    n = max(1, int(math.ceil(L / step)))
    pts = [(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n) for i in range(n + 1)]
    if flip:
        pts.reverse()
    return pts


def warp_cell(poly, noises):
    ring = list(poly.exterior.coords)[:-1]
    out = []
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        seg = densify_edge(a, b, EDGE_STEP)[:-1]
        out.extend(warp_point(p, noises) for p in seg)
    return Polygon(out)


def voronoi_cells(seed_pts):
    """seed_pts: lista de (x,y) -> lista de Polygons (mesma ordem), recortados por ENV."""
    if len(seed_pts) == 1:
        return [ENV]
    vd = voronoi_diagram(MultiPoint(seed_pts), envelope=ENV)
    cells = list(vd.geoms)
    res = []
    for s in seed_pts:
        pt = Point(s)
        c = next(c for c in cells if c.contains(pt))
        res.append(c)
    return res


def lloyd(seed_pts, land, iters=2, alpha=0.5):
    pts = list(seed_pts)
    for _ in range(iters):
        cells = voronoi_cells(pts)
        new = []
        for p, c in zip(pts, cells):
            inter = c.intersection(land)
            if inter.is_empty:
                new.append(p)
                continue
            if isinstance(inter, MultiPolygon):
                inter = max(inter.geoms, key=lambda g: g.area)
            cen = inter.centroid
            q = (p[0] + alpha * (cen.x - p[0]), p[1] + alpha * (cen.y - p[1]))
            new.append(q if land.contains(Point(q)) else p)
        pts = new
    return pts


def round_poly(poly, nd=1):
    ring = [(round(x, nd), round(y, nd)) for x, y in poly.exterior.coords]
    out = [ring[0]]
    for p in ring[1:]:
        if p != out[-1]:
            out.append(p)
    if out[0] == out[-1]:
        out.pop()
    return out


def build_geometry(verbose=False):
    rng_seed = SEED
    cont = make_coast(CONTINENT, rng_seed, step=50)
    isl1 = make_coast(ISLAND_SYLVESTER, rng_seed + 1000, step=30)
    isl2 = make_coast(ISLAND_TRACO, rng_seed + 2000, step=30)
    lands = [cont, isl1, isl2]

    seeds = dict(SEEDS)
    ids = sorted(seeds)

    noises = [(Noise(SEED + 11 * i), Noise(SEED + 11 * i + 5)) for i in range(len(WARP))]

    cells = {}
    final_seeds = {}
    for land in lands:
        members = [t for t in ids if land.contains(Point(seeds[t]))]
        pts = [seeds[t] for t in members]
        pts = lloyd(pts, land, iters=2, alpha=0.5)
        vcells = voronoi_cells(pts)
        for t, p, vc in zip(members, pts, vcells):
            final_seeds[t] = p
            wc = warp_cell(vc, noises)
            if not wc.is_valid:
                wc = wc.buffer(0)
            part = wc.intersection(land)
            cells[t] = part
    missing = [t for t in ids if t not in cells]
    if missing:
        raise RuntimeError(f"sementes fora da terra: {missing}")

    # peças soltas (células recortadas pela costa em várias partes) -> vizinho de maior fronteira
    for t in list(cells):
        g = cells[t]
        if isinstance(g, MultiPolygon):
            parts = sorted(g.geoms, key=lambda q: -q.area)
            cells[t] = parts[0]
            for extra in parts[1:]:
                best, bl = None, 0
                for u, h in cells.items():
                    if u == t:
                        continue
                    l = extra.buffer(0.05).intersection(h.boundary).length
                    if l > bl:
                        best, bl = u, l
                if best is not None:
                    cells[best] = unary_union([cells[best], extra.buffer(0.02)]).buffer(0)
                    if verbose:
                        print(f"  peça solta de {t} (área {extra.area:.0f}) -> {best}")
    # arredonda a 1 casa
    rcells = {}
    for t, g in cells.items():
        if isinstance(g, MultiPolygon):
            g = max(g.geoms, key=lambda q: q.area)
        rcells[t] = Polygon(round_poly(g))
    return {"ids": ids, "cells": rcells, "seeds": final_seeds, "lands": lands, "noises": noises}


# --------------------------------------------------------------------------------------
# Dados de design (à mão): nomes, terreno, rios, rotas, rótulos
# --------------------------------------------------------------------------------------

NAMES = {
    "T01": "Cabo Cholesky", "T02": "Serra de Schmidt", "T03": "Cidadela Hamilton", "T04": "Planície de Gram",
    "T05": "Campos de Gershgorin", "T06": "Pradaria Perron", "T07": "Forte Hessenberg", "T08": "Floresta de Frobenius",
    "T09": "Várzea de Gauss-Seidel", "T10": "Serra de Sherman", "T11": "Vila Hermite", "T12": "Charneca de Cayley",
    "T13": "Pântano de Householder", "T14": "Planura Rayleigh", "T15": "Porto Jordan", "T16": "Chapada Jacobi",
    "T17": "Planalto de Lanczos", "T18": "Colinas de Krylov", "T19": "Vale Woodbury", "T20": "Baía de Givens",
    "T21": "Brejo Arnoldi", "T22": "Vale de Cramer", "T23": "Ribeira Vandermonde", "T24": "Campina do Pivô",
    "T25": "Delta de Laplace", "T26": "Montes do Núcleo", "T27": "Desfiladeiro de Schur", "T28": "Monte Posto",
    "T29": "Recife de Moore", "T30": "Monte Toeplitz", "T31": "Ponta Penrose", "T32": "Ilha de Sylvester",
    "T33": "Costa de Ritz", "T34": "Ilha do Traço",
}

# Composição por pátria (além da capital): grupo A (slots 0,2,4) = montanha + planície + floresta;
# grupo B (slots 1,3,5) = 2 planícies + (floresta | pântano). Eixo montanhoso em "Y" pelo centro.
TERRAIN = {
    "T01": "floresta", "T02": "montanha", "T04": "planicie",
    "T05": "planicie", "T06": "planicie", "T08": "floresta",
    "T09": "planicie", "T10": "montanha", "T12": "floresta",
    "T13": "pantano", "T14": "planicie", "T16": "planicie",
    "T17": "planicie", "T18": "montanha", "T20": "floresta",
    "T21": "pantano", "T22": "planicie", "T24": "planicie",
    "T25": "pantano", "T26": "montanha", "T27": "montanha", "T28": "montanha",
    "T29": "floresta", "T30": "montanha", "T31": "floresta",
    "T32": "planicie", "T33": "floresta", "T34": "planicie",
}
for _k in range(6):
    TERRAIN[f"T{4 * _k + 3:02d}"] = "urbano"

CAP_BASE = {
    "planicie": (12, 3, 3),
    "floresta": (6, 5, 4),
    "montanha": (3, 10, 4),
    "pantano": (5, 2, 10),
    "urbano": (6, 8, 6),
}

# rios: (nome-guia, ponto de nascente [dentro de montanha], dica de foz [vira o ponto mais próximo da costa])
RIVERS = [
    ("T26", (560, 330), (606, 226), 11),
    ("T10", (900, 372), (1096, 318), 12),
    ("T18", (505, 500), (470, 672), 13),
    ("T27", (690, 392), (655, 496), 14),
    ("T02", (420, 270), (192, 247), 15),
]

# rotas marítimas (a, b, lado do arco: +1/-1)
SEA_ROUTES = [
    ("T32", "T20"), ("T33", "T13"), ("T33", "T29"), ("T34", "T24"), ("T18", "T15"), ("T03", "T08"),
]

LABELS = [
    {"text": "MAR DE BANACH", "pos": [390, 738], "kind": "sea", "angle": -3},
    {"text": "GOLFO DE HILBERT", "pos": [650, 590], "kind": "sea", "angle": -84},
    {"text": "OCEANO DE FOURIER", "pos": [1000, 742], "kind": "sea", "angle": 0},
    {"text": "ESTREITO DE HADAMARD", "pos": [172, 631], "kind": "sea", "angle": 0},
    {"text": "BAÍA DE ABEL", "pos": [572, 118], "kind": "sea", "angle": 0},
]


# --------------------------------------------------------------------------------------
# Construção do mapa
# --------------------------------------------------------------------------------------


def inside(poly, pt):
    return poly.contains(Point(pt))


def interior_point(poly):
    c = poly.centroid
    if poly.contains(c):
        return (c.x, c.y)
    r = poly.representative_point()
    return (r.x, r.y)


def smooth_open(pts, n=2):
    """Chaikin para polilinha aberta (preserva extremos)."""
    pts = [tuple(p) for p in pts]
    for _ in range(n):
        out = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        out.append(pts[-1])
        pts = out
    return pts


def balance_capacity(rng, ids_by_slot):
    """Variação ±20% por entrada, escolhida por busca para equilibrar somas por pátria."""
    ids = sorted(TERRAIN)
    best = None
    for attempt in range(4000):
        cap = {}
        for t in ids:
            base = CAP_BASE[TERRAIN[t]]
            cap[t] = [max(1, int(round(b * (1 + rng.uniform(-0.2, 0.2))))) for b in base]
        tot = np.array([[sum(cap[t][r] for t in ts) for r in range(3)] for ts in ids_by_slot])
        sums = tot.sum(axis=1)
        score = (sums.max() - sums.min()) / sums.mean() * 3 + (tot.max(0) - tot.min(0)).sum() / tot.sum() * 3
        if best is None or score < best[0]:
            best = (score, cap)
    return {t: {"ALI": v[0], "ACO": v[1], "COM": v[2]} for t, v in best[1].items()}


def poisson_in(poly, rng, mind, n_max, tries=600):
    minx, miny, maxx, maxy = poly.bounds
    pts = []
    for _ in range(tries):
        if len(pts) >= n_max:
            break
        x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
        if not poly.contains(Point(x, y)):
            continue
        if all((x - a) ** 2 + (y - b) ** 2 >= mind * mind for a, b in pts):
            pts.append((x, y))
    return pts


def r1(v):
    return round(float(v), 1)


def make_river(land, src, hint, seed):
    mouth_pt = land.boundary.interpolate(land.boundary.project(Point(hint)))
    mouth = (mouth_pt.x, mouth_pt.y)
    a = np.array(src, float)
    b = np.array(mouth, float)
    d = b - a
    L = float(np.linalg.norm(d))
    nrm = np.array([-d[1], d[0]]) / L
    inner = land.buffer(-2.5)
    best = None
    for k in range(60):
        rng = np.random.RandomState(seed * 100 + k)
        amp = L * 0.13 * (1.0 - k / 70.0)
        n = max(4, int(L / 28))
        pts = [tuple(a)]
        for i in range(1, n):
            t = i / n
            off = amp * math.sin(math.pi * t) ** 0.6 * rng.uniform(-1, 1) * 1.4
            pts.append(tuple(a + d * t + nrm * off))
        pts.append(tuple(b))
        sm = smooth_open(pts, 3)
        ls = LineString(sm)
        # tem que ficar em terra, exceto o último trecho (foz)
        body = LineString(sm[: int(len(sm) * 0.82)])
        if inner.contains(body):
            best = sm
            break
    if best is None:
        best = smooth_open([tuple(a), tuple(b)], 0)
    # reamostra para ~14 unidades
    ls = LineString(best)
    n = max(6, int(ls.length / 14))
    return [(r1(ls.interpolate(i / n, normalized=True).x), r1(ls.interpolate(i / n, normalized=True).y)) for i in range(n + 1)], (mouth_pt.x, mouth_pt.y)


def bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def make_sea_route(cells, land, a, b, coast_of):
    from shapely.ops import nearest_points
    pa, pb = nearest_points(coast_of[a], coast_of[b])
    p0, p3 = (pa.x, pa.y), (pb.x, pb.y)
    d = np.array(p3) - np.array(p0)
    L = float(np.linalg.norm(d))
    nrm = np.array([-d[1], d[0]]) / L
    inner = land.buffer(-1.0)
    best = None
    for k in (0.14, 0.2, 0.26, 0.33, 0.42, 0.55):
        for sg in (1, -1):
            o = nrm * L * k * sg
            p1 = tuple(np.array(p0) + d / 3 + o)
            p2 = tuple(np.array(p3) - d / 3 + o)
            curve = bezier(p0, p1, p2, p3, 40)
            mid = LineString(curve[4:-4])
            if not inner.intersects(mid) and land.distance(mid) >= 3.0:
                c5 = bezier(p0, p1, p2, p3, 4)
                best = (k, c5)
                break
        if best:
            break
    if best is None:
        raise RuntimeError(f"rota {a}-{b} não achou caminho livre")
    return [[r1(x), r1(y)] for x, y in best[1]]


def build_map(verbose=False):
    geo = build_geometry(verbose)
    cells = geo["cells"]
    ids = geo["ids"]
    rng = np.random.RandomState(SEED + 7)

    for t, g in cells.items():
        if not g.is_valid:
            raise RuntimeError(f"{t} inválido: {shapely_reason(g)}")
    land = unary_union(list(cells.values()))
    if verbose:
        print("terra: área", round(land.area), "partes", len(land.geoms) if hasattr(land, "geoms") else 1)

    # vizinhança
    nb = {t: [] for t in ids}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            inter = cells[a].boundary.intersection(cells[b].boundary)
            if inter.length > 8.0:
                nb[a].append(b)
                nb[b].append(a)
    # costa por território (trechos de fronteira não compartilhados com outro território)
    coast_of = {}
    for t in ids:
        others = unary_union([cells[u] for u in ids if u != t]).buffer(0.25)
        coast_of[t] = cells[t].boundary.difference(others)
    coastal = {t: coast_of[t].length > 8.0 for t in ids}

    slots_ids = [[f"T{4 * k + j + 1:02d}" for j in range(4)] for k in range(6)]
    caps = balance_capacity(rng, slots_ids)

    sea = []
    for a, b in SEA_ROUTES:
        sea.append({"a": a, "b": b, "path": make_sea_route(cells, land, a, b, coast_of)})
    sea_nb = {t: [] for t in ids}
    for r in sea:
        sea_nb[r["a"]].append(r["b"])
        sea_nb[r["b"]].append(r["a"])

    terrs = []
    for t in ids:
        g = cells[t]
        n = int(t[1:])
        slot = (n - 1) // 4 if n <= 24 else None
        cen = interior_point(g)
        lab = polylabel(g, 0.5)
        lp = (lab.x, lab.y)
        terrs.append({
            "id": t, "name": NAMES[t],
            "polygon": [[r1(x), r1(y)] for x, y in list(g.exterior.coords)[:-1]],
            "centroid": [r1(cen[0]), r1(cen[1])], "label_pos": [r1(lp[0]), r1(lp[1])],
            "terrain": TERRAIN[t],
            "climate": "norte" if cen[1] < H / 3 else ("sul" if cen[1] > 2 * H / 3 else "centro"),
            "home_slot": slot, "capital": slot is not None and n % 4 == 3,
            "capacity": caps[t],
            "neighbors": sorted(nb[t]), "sea_neighbors": sorted(sea_nb[t]),
            "coastal": bool(coastal[t]),
        })

    # contornos de terra
    polys = list(land.geoms) if hasattr(land, "geoms") else [land]
    land_rings = [[[r1(x), r1(y)] for x, y in list(p.exterior.coords)[:-1]] for p in sorted(polys, key=lambda q: -q.area)]

    # rios
    rivers = []
    for k, (tid, src, hint, sd) in enumerate(RIVERS):
        core = cells[tid].buffer(-10)
        sp = core.boundary.interpolate(core.boundary.project(Point(src))) if not core.contains(Point(src)) else Point(src)
        pts, _ = make_river(land, (sp.x, sp.y), hint, sd)
        rivers.append([[x, y] for x, y in pts])

    # relevo: carets sobre montanhas
    relief = []
    rrng = np.random.RandomState(SEED + 99)
    for t in ids:
        if TERRAIN[t] != "montanha":
            continue
        inner = cells[t].buffer(-9)
        if inner.is_empty:
            continue
        if isinstance(inner, MultiPolygon):
            inner = max(inner.geoms, key=lambda q: q.area)
        pts = poisson_in(inner, rrng, 15.5, 26)
        for (x, y) in sorted(pts, key=lambda q: (q[1], q[0])):
            s = rrng.uniform(5.0, 7.5)
            relief.append([[r1(x - s), r1(y + s * 0.55)], [r1(x + rrng.uniform(-1, 1)), r1(y - s * 0.8)], [r1(x + s), r1(y + s * 0.55)]])
            relief.append([[r1(x + 0.1 * s), r1(y - 0.5 * s)], [r1(x + 0.55 * s), r1(y + 0.55 * s)]])
    # curvas de nível suaves em volta dos picos (decorativo)
    for t in ids:
        if TERRAIN[t] != "montanha":
            continue
        c = np.array(interior_point(cells[t]))
        for rad, jit in ((26, 4), (15, 3)):
            ring = []
            for a in np.linspace(0, 2 * math.pi, 18, endpoint=False):
                rr = rad + rrng.uniform(-jit, jit)
                ring.append((c[0] + rr * math.cos(a) * 1.3, c[1] + rr * math.sin(a)))
            sm = smooth_open(ring + [ring[0]], 2)
            ls = Polygon(sm)
            inter = ls.exterior.intersection(cells[t].buffer(-5))
            parts = list(inter.geoms) if hasattr(inter, "geoms") else [inter]
            for pt in parts:
                if isinstance(pt, LineString) and pt.length > 12:
                    relief.append([[r1(x), r1(y)] for x, y in pt.coords])

    return {
        "width": W, "height": H,
        "grid": {"cell": 50, "cols": "ABCDEFGHIJKLMNOPQRSTUVWX", "rows": 16},
        "climate_regions": [{"id": "norte", "name": "Norte"}, {"id": "centro", "name": "Centro"}, {"id": "sul", "name": "Sul"}],
        "home_slots": [{"slot": k, "capital": f"T{4 * k + 3:02d}", "territories": slots_ids[k]} for k in range(6)],
        "territories": terrs,
        "sea_routes": sea,
        "land": land_rings,
        "rivers": rivers,
        "relief": relief,
        "labels": LABELS,
    }


def shapely_reason(g):
    from shapely.validation import explain_validity
    return explain_validity(g)


# --------------------------------------------------------------------------------------
# Prévia (SVG -> PNG via Chromium/Playwright)
# --------------------------------------------------------------------------------------

SLOT_COLORS = ["#2b4a74", "#8c2f23", "#4d5b24", "#a87a1c", "#5b3a6b", "#3b5b5a"]
TERRAIN_GLYPH = {"planicie": "", "floresta": "♣", "montanha": "▲", "pantano": "≈", "urbano": "★"}


def wrap_name(name, maxlen=13):
    words = name.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxlen:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return lines


def preview_svg(m, path):
    from shapely.geometry import Polygon as P
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           '<defs><filter id="rough"><feTurbulence baseFrequency="0.9" numOctaves="2" result="n"/><feColorMatrix in="n" type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope="0.06"/></feComponentTransfer><feBlend in2="SourceGraphic"/></filter></defs>',
           f'<rect width="{W}" height="{H}" fill="#c9d6d2"/>']
    land_polys = [P(r) for r in m["land"]]
    landu = unary_union(land_polys)
    # water-lining
    for dist, op in ((26, 0.12), (18, 0.18), (11, 0.26), (5.5, 0.38)):
        b = landu.buffer(dist, join_style=1)
        for g in (b.geoms if hasattr(b, "geoms") else [b]):
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in g.exterior.coords)
            out.append(f'<polygon points="{pts}" fill="none" stroke="#4d6b73" stroke-opacity="{op}" stroke-width="1"/>')
    # quadrícula
    for c in range(25):
        out.append(f'<line x1="{c * 50}" y1="0" x2="{c * 50}" y2="{H}" stroke="#46605f" stroke-opacity="0.28" stroke-width="0.6"/>')
    for r in range(17):
        out.append(f'<line x1="0" y1="{r * 50}" x2="{W}" y2="{r * 50}" stroke="#46605f" stroke-opacity="0.28" stroke-width="0.6"/>')
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWX"):
        out.append(f'<text x="{i * 50 + 25}" y="12" font-size="10" text-anchor="middle" fill="#46605f" font-family="monospace">{ch}</text>')
    for r in range(16):
        out.append(f'<text x="8" y="{r * 50 + 29}" font-size="10" text-anchor="middle" fill="#46605f" font-family="monospace">{r + 1}</text>')
    for pg in land_polys:
        pts = " ".join(f"{x},{y}" for x, y in pg.exterior.coords)
        out.append(f'<polygon points="{pts}" fill="#e6dcbc"/>')
    terr_fill = {"planicie": "#e3d9b4", "floresta": "#c8cf9a", "montanha": "#d2c3a1", "pantano": "#bfcdb4", "urbano": "#dccaa0"}
    for t in m["territories"]:
        pts = " ".join(f"{x},{y}" for x, y in t["polygon"])
        base = terr_fill[t["terrain"]]
        out.append(f'<polygon points="{pts}" fill="{base}"/>')
        if t["home_slot"] is not None:
            out.append(f'<polygon points="{pts}" fill="{SLOT_COLORS[t["home_slot"]]}" fill-opacity="0.55"/>')
        out.append(f'<polygon points="{pts}" fill="none" stroke="#3a2f20" stroke-width="1.1" stroke-linejoin="round"/>')
    for pg in land_polys:
        pts = " ".join(f"{x},{y}" for x, y in pg.exterior.coords)
        out.append(f'<polygon points="{pts}" fill="none" stroke="#2a2218" stroke-width="1.8" stroke-linejoin="round"/>')
    for rv in m["rivers"]:
        pts = " ".join(f"{x},{y}" for x, y in rv)
        out.append(f'<polyline points="{pts}" fill="none" stroke="#4e7d96" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    for rl in m["relief"]:
        pts = " ".join(f"{x},{y}" for x, y in rl)
        out.append(f'<polyline points="{pts}" fill="none" stroke="#5a4630" stroke-opacity="0.75" stroke-width="0.9"/>')
    for r in m["sea_routes"]:
        pts = " ".join(f"{x},{y}" for x, y in r["path"])
        out.append(f'<polyline points="{pts}" fill="none" stroke="#1f3a52" stroke-width="1.6" stroke-dasharray="6 4"/>')
        for (x, y) in (r["path"][0], r["path"][-1]):
            out.append(f'<circle cx="{x}" cy="{y}" r="2.6" fill="#1f3a52"/>')
    for lb in m["labels"]:
        x, y = lb["pos"]
        out.append(f'<text x="{x}" y="{y}" font-size="13" letter-spacing="3" text-anchor="middle" fill="#2f4b5c" fill-opacity="0.85" font-style="italic" font-family="Georgia,serif" transform="rotate({lb["angle"]} {x} {y})">{lb["text"]}</text>')
    for t in m["territories"]:
        x, y = t["label_pos"]
        lines = wrap_name(t["name"])
        y0 = y - (len(lines) - 1) * 5.5 + 3.5
        star = "★ " if t["capital"] else ""
        for i, ln in enumerate(lines):
            tx = (star if i == 0 else "") + ln
            out.append(f'<text x="{x}" y="{y0 + i * 11}" font-size="9.5" text-anchor="middle" fill="#1b140b" font-family="Georgia,serif" stroke="#efe6c8" stroke-width="2.4" paint-order="stroke">{tx}</text>')
        out.append(f'<text x="{x}" y="{y0 + len(lines) * 11 + 1}" font-size="8" text-anchor="middle" fill="#1b140b" font-family="monospace" stroke="#efe6c8" stroke-width="2" paint-order="stroke">{t["id"]} {TERRAIN_GLYPH[t["terrain"]]}</text>')
    out.append("</svg>")
    pathlib.Path(path).write_text("\n".join(out), encoding="utf-8")


def render_png(svg_path, png_path, scale=1):
    from playwright.sync_api import sync_playwright
    svg = pathlib.Path(svg_path).read_text(encoding="utf-8")
    html = f"<html><body style='margin:0;background:#fff'>{svg}</body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=scale)
        pg.set_content(html)
        pg.screenshot(path=str(png_path))
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="gera tools/preview/map_preview.svg/.png")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    m = build_map(args.verbose)
    txt = json.dumps(m, ensure_ascii=False, separators=(",", ":"))
    if not args.no_write:
        for rel in ("server/app/data/map.json", "web/mock/map.json"):
            pth = ROOT / rel
            pth.parent.mkdir(parents=True, exist_ok=True)
            pth.write_text(txt, encoding="utf-8")
        print(f"map.json: {len(txt) / 1024:.0f} KB, {len(m['territories'])} territórios")
    if args.preview:
        d = ROOT / "tools" / "preview"
        d.mkdir(parents=True, exist_ok=True)
        preview_svg(m, d / "map_preview.svg")
        render_png(d / "map_preview.svg", d / "map_preview.png", scale=1.5)
        print("prévia:", d / "map_preview.png")


if __name__ == "__main__":
    main()
