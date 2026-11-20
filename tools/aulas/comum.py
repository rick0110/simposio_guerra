"""Peças comuns às animações das aulas (Manim): identidade visual, sincronia com a narração e o mapa.

Uso dentro de um cenas.py:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from comum import *
A pasta da narração vem de AULA_VOZ (saída de narracao.py, com duracoes.json).
"""
import json
import os
from pathlib import Path

import numpy as np
from manim import *

import ritmo

RAIZ = Path(__file__).resolve().parents[2]

# ------------------------------------------------------------------ identidade visual (a mesma do jogo)
FUNDO = "#1c241e"
PAPEL = "#e9dfc7"
PAPEL_2 = "#d9cba8"
TINTA = "#1d1b16"
VERMELHO = "#c0392b"
AMBAR = "#e0a040"
LATAO = "#b08d3c"
AZUL = "#6f9fd8"
VERDE = "#8fbf6a"
CINZA = "#8f866e"
# cores das nações, clareadas para o fundo escuro do vídeo (no jogo elas são tinta sobre papel)
NACOES = {"GAU": "#4a74a8", "EUL": "#b8473a", "HIL": "#7d8f3e", "NOE": "#d6a032", "CAU": "#8a5fa0", "RIE": "#4f8f8c"}
SANS, SERIF, MAQ, MONO = "IBM Plex Sans Condensed", "Old Standard TT", "Special Elite", "IBM Plex Mono"

config.background_color = FUNDO
MathTex.set_default(color=PAPEL)
Tex.set_default(color=PAPEL)


def txt(s, size=32, color=PAPEL, font=SANS, **kw):
    return Text(s, font=font, font_size=size, color=color, **kw)


def _duracoes():
    return json.loads((Path(os.environ["AULA_VOZ"]) / "duracoes.json").read_text())


class Ritmo:
    """Sincroniza a animação com a narração: fala(i) espera até o instante em que a fala i começa."""
    CENA = None

    def preparar(self):
        d = _duracoes()[self.CENA]
        self.ini = ritmo.inicios(d)
        self.dur = d
        self.total = ritmo.duracao_cena(d)

    def ate(self, t):
        dt = t - self.renderer.time
        if dt > 1 / 60:
            self.wait(dt)
        elif dt < -0.1:
            print(f"   [atraso] {type(self).__name__}: {-dt:.2f} s depois do previsto", flush=True)

    def fala(self, i):
        self.ate(self.ini[i])

    def encerrar(self):
        self.ate(self.total - 0.7)
        objs = [m for m in self.mobjects]
        if objs:
            self.play(*[FadeOut(m) for m in objs], run_time=0.6)
        self.ate(self.total)


from jogo_dados import balance, donos, mapa_json  # noqa: E402,F401


def mapa(n=4, escala=0.0092, opacidade=None):
    """O continente como VGroup(terra, territórios). opacidade(fid) -> opacidade do preenchimento.
    Devolve (grupo, {tid: polígono}, dono, p), onde p(x, y) converte coordenadas do mapa do jogo."""
    m = mapa_json()
    dono = donos(n)

    def p(x, y):
        return np.array([(x - 600) * escala, -(y - 400) * escala, 0])

    terra = VGroup(*[Polygon(*[p(*q) for q in poly], color=PAPEL_2, fill_color=PAPEL_2, fill_opacity=0.18,
                             stroke_width=2.5) for poly in m["land"]])
    polys = {}
    for t in m["territories"]:
        fid = dono.get(t["id"])
        op = (opacidade(fid) if opacidade else 0.85) if fid else 0.16
        polys[t["id"]] = Polygon(*[p(*q) for q in t["polygon"]], color=FUNDO, stroke_width=1.2,
                                 fill_color=NACOES.get(fid, CINZA), fill_opacity=op)
    return VGroup(terra, VGroup(*polys.values())), polys, dono, p
