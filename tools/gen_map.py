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
from shapely.geometry import LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon, box
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
        d = -carry if carry else 0.0
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
    (860, 650), (800, 662), (748, 640), (716, 610), (700, 590), (690, 548), (676, 520), (660, 492),
    (630, 486), (604, 505), (596, 548), (588, 600), (560, 640), (520, 668), (470, 650), (430, 676),
    (380, 650), (352, 692), (326, 660), (290, 628), (250, 640), (205, 610), (150, 590), (110, 540), (106, 480),
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
    "T13": (812, 622), "T14": (748, 498), "T15": (790, 562), "T16": (925, 548),
    # slot 4 (sudoeste)
    "T17": (330, 560), "T18": (490, 490), "T19": (420, 575), "T20": (505, 628),
    # slot 5 (oeste)
    "T21": (180, 305), "T22": (292, 380), "T23": (200, 385), "T24": (190, 470),
    # neutros
    "T25": (600, 262), "T26": (525, 360), "T27": (680, 360), "T28": (610, 440),
    "T29": (1012, 612), "T30": (1035, 115), "T31": (150, 150),
    "T32": (580, 730), "T33": (715, 730), "T34": (150, 710),
}


# --------------------------------------------------------------------------------------
# Geometria: células
# --------------------------------------------------------------------------------------

ENV = box(-400, -400, 1600, 1200)
WARP = [  # (comprimento de onda, amplitude)
    (150.0, 17.0),
    (72.0, 8.0),
    (34.0, 3.6),
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
# Prévia
# --------------------------------------------------------------------------------------

SLOT_COLORS = ["#2b4a74", "#8c2f23", "#4d5b24", "#a87a1c", "#5b3a6b", "#3b5b5a"]


def preview_geometry_svg(geo, path):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             f'<rect width="{W}" height="{H}" fill="#cfd9d6"/>']
    for c in range(25):
        parts.append(f'<line x1="{c * 50}" y1="0" x2="{c * 50}" y2="{H}" stroke="#8a9a96" stroke-width="0.5"/>')
    for r in range(17):
        parts.append(f'<line x1="0" y1="{r * 50}" x2="{W}" y2="{r * 50}" stroke="#8a9a96" stroke-width="0.5"/>')
    for t in geo["ids"]:
        n = int(t[1:])
        col = SLOT_COLORS[(n - 1) // 4] if n <= 24 else "#c9bd96"
        pts = " ".join(f"{x},{y}" for x, y in geo["cells"][t].exterior.coords)
        parts.append(f'<polygon points="{pts}" fill="{col}" fill-opacity="0.55" stroke="#222" stroke-width="1"/>')
        cen = geo["cells"][t].representative_point()
        parts.append(f'<text x="{cen.x}" y="{cen.y}" font-size="11" text-anchor="middle" font-family="monospace">{t}</text>')
    parts.append("</svg>")
    pathlib.Path(path).write_text("\n".join(parts), encoding="utf-8")


def render_png(svg_path, png_path):
    from playwright.sync_api import sync_playwright
    svg = pathlib.Path(svg_path).read_text(encoding="utf-8")
    html = f"<html><body style='margin:0;background:#fff'>{svg}</body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.set_content(html)
        pg.screenshot(path=str(png_path))
        b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--geo", action="store_true", help="só geometria (depuração)")
    args = ap.parse_args()
    geo = build_geometry(verbose=True)
    out = ROOT / "tools" / "preview"
    out.mkdir(parents=True, exist_ok=True)
    preview_geometry_svg(geo, out / "geo.svg")
    render_png(out / "geo.svg", out / "geo.png")
    print({t: (round(c.area), len(c.exterior.coords)) for t, c in geo["cells"].items()})
