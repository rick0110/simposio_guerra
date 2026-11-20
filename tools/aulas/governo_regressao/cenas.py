"""Animações (Manim) do vídeo "Governo · Regressão linear".

Cada classe é uma cena do roteiro e dura exatamente o tempo da sua narração (ver ritmo.py).
Renderizar (a partir da raiz do repositório):
    AULA_VOZ=<pasta_da_voz> manim -r 1920,1080 --frame_rate 30 tools/aulas/governo_regressao/cenas.py <Classe>
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from manim import *

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
sys.path.insert(0, str(AQUI.parent))
import ritmo  # noqa: E402

DUR = json.loads((Path(os.environ["AULA_VOZ"]) / "duracoes.json").read_text())

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
NACOES = {"GAU": "#4a74a8", "EUL": "#b8473a", "HIL": "#7d8f3e", "NOE": "#d6a032"}
SANS, SERIF, MAQ, MONO = "IBM Plex Sans Condensed", "Old Standard TT", "Special Elite", "IBM Plex Mono"

config.background_color = FUNDO
MathTex.set_default(color=PAPEL)
Tex.set_default(color=PAPEL)


def txt(s, size=32, color=PAPEL, font=SANS, **kw):
    return Text(s, font=font, font_size=size, color=color, **kw)


class Ritmo:
    """Sincroniza a animação com a narração: fala(i) espera até o instante em que a fala i começa."""
    CENA = None

    def preparar(self):
        d = DUR[self.CENA]
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

    def fim_da_fala(self, i, folga=0.0):
        return self.ini[i] + self.dur[i] - folga

    def encerrar(self):
        self.ate(self.total - 0.7)
        objs = [m for m in self.mobjects]
        if objs:
            self.play(*[FadeOut(m) for m in objs], run_time=0.6)
        self.ate(self.total)


# ------------------------------------------------------------------ o mapa do continente (do map.json do jogo)
def mapa_continente(escala=0.0092, destaque=None):
    mapa = json.loads((RAIZ / "server/app/data/map.json").read_text())
    dono = {}
    for slot, fid in zip([0, 1, 3, 4], ["GAU", "EUL", "HIL", "NOE"]):
        h = next(x for x in mapa["home_slots"] if x["slot"] == slot)
        for t in h["territories"]:
            dono[t] = fid

    def p(x, y):
        return np.array([(x - 600) * escala, -(y - 400) * escala, 0])

    terra = VGroup(*[Polygon(*[p(*q) for q in poly], color=PAPEL_2, fill_color=PAPEL_2, fill_opacity=0.18,
                             stroke_width=2.5) for poly in mapa["land"]])
    terr = VGroup()
    for t in mapa["territories"]:
        fid = dono.get(t["id"])
        cor = NACOES.get(fid, CINZA)
        op = 0.85 if (destaque is None or fid == destaque) else 0.28
        terr.add(Polygon(*[p(*q) for q in t["polygon"]], color=FUNDO, stroke_width=1.2,
                         fill_color=cor, fill_opacity=op if fid else 0.18))
    return VGroup(terra, terr), dono, p


# =================================================================== CENAS
class Titulo(Scene):
    """Abertura sem narração (4,5 s)."""

    def construct(self):
        serie = txt("ESTADO-MAIOR · INSTRUÇÃO DO GOVERNO", 26, LATAO, font=SANS, weight=BOLD)
        t1 = txt("O que faz um povo feliz?", 72, PAPEL, font=SERIF, weight=BOLD)
        t2 = txt("Regressão linear", 44, AMBAR, font=SERIF, slant=ITALIC)
        g = VGroup(serie, t1, t2).arrange(DOWN, buff=0.45)
        linha = Line(LEFT * 3.2, RIGHT * 3.2, color=LATAO, stroke_width=2).next_to(t1, DOWN, buff=0.22)
        self.play(FadeIn(serie, shift=DOWN * 0.2), run_time=0.7)
        self.play(Write(t1), run_time=1.3)
        self.play(Create(linha), FadeIn(t2, shift=UP * 0.2), run_time=0.8)
        self.wait(1.1)
        self.play(FadeOut(VGroup(serie, t1, t2, linha)), run_time=0.6)


class Abertura(Ritmo, MovingCameraScene):
    CENA = "abertura"

    def construct(self):
        self.preparar()
        mapa, dono, p = mapa_continente()
        # fala 0: o continente, o Gabinete de Noethéria e a moral
        self.fala(0)
        self.play(FadeIn(mapa[0]), LaggedStart(*[FadeIn(t) for t in mapa[1]], lag_ratio=0.03), run_time=2.4)
        nome = txt("NOETHÉRIA", 30, NACOES["NOE"], weight=BOLD).move_to(p(330, 590))
        self.play(FadeIn(nome, scale=1.2), run_time=0.8)
        self.play(self.camera.frame.animate.scale(0.62).move_to(p(330, 600)), run_time=2.0)
        self.play(FadeOut(mapa), FadeOut(nome), self.camera.frame.animate.scale(1 / 0.62).move_to(ORIGIN),
                  run_time=1.0)
        moral = ValueTracker(70)
        tubo = RoundedRectangle(width=0.7, height=4.4, corner_radius=0.35, color=PAPEL, stroke_width=3).shift(LEFT * 3)
        bulbo = Circle(radius=0.55, color=PAPEL, stroke_width=3, fill_color=VERMELHO, fill_opacity=1).next_to(tubo, DOWN, buff=-0.25)
        coluna = always_redraw(lambda: Rectangle(width=0.36, height=max(0.05, 3.9 * moral.get_value() / 100),
                                                  color=VERMELHO, fill_color=VERMELHO, fill_opacity=1, stroke_width=0)
                               .move_to(tubo.get_bottom() + UP * (0.25 + 1.95 * moral.get_value() / 100)))
        num = always_redraw(lambda: Integer(round(moral.get_value()), font_size=150, color=PAPEL)
                            .next_to(tubo, RIGHT, buff=1.2))
        rot = txt("MORAL DO POVO", 30, LATAO, weight=BOLD).next_to(num, UP, buff=0.4).align_to(num, LEFT)
        self.play(FadeIn(tubo, bulbo, coluna), FadeIn(num), FadeIn(rot), run_time=1.2)
        # fala 1: a moral cai, e com ela tudo
        self.fala(1)
        self.play(moral.animate.set_value(62), run_time=2.5, rate_func=smooth)
        f1 = txt("fábricas produzem menos", 30, PAPEL).next_to(num, DOWN, buff=0.7).align_to(num, LEFT)
        f2 = txt("o exército luta pior", 30, PAPEL).next_to(f1, DOWN, buff=0.3).align_to(f1, LEFT)
        for f in (f1, f2):
            seta = Arrow(UP * 0.35, DOWN * 0.35, color=VERMELHO, buff=0).next_to(f, LEFT, buff=0.25)
            self.play(FadeIn(f, shift=RIGHT * 0.2), GrowArrow(seta), run_time=0.8)
            f.add(seta)
        # fala 2: três propostas
        self.fala(2)
        self.play(FadeOut(VGroup(tubo, bulbo, coluna, num, rot, f1, f2)), run_time=0.6)
        cartas = VGroup()
        for titulo, custo in [("Propaganda", "custa Aço"), ("Aliviar o\nracionamento", "custa Alimento"),
                              ("Reduzir a\njornada", "custa produção")]:
            r = Rectangle(width=3.9, height=2.4, color=PAPEL_2, fill_color=PAPEL, fill_opacity=1, stroke_width=0)
            a = txt(titulo, 30, TINTA, font=SERIF, weight=BOLD, line_spacing=0.8).move_to(r.get_center() + UP * 0.3)
            b = txt(custo, 26, VERMELHO, font=MAQ).move_to(r.get_center() + DOWN * 0.5)
            cartas.add(VGroup(r, a, b))
        cartas.arrange(RIGHT, buff=0.5)
        for c, ang in zip(cartas, (-3, 1.5, -1.5)):
            c.rotate(ang * DEGREES)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.6) for c in cartas], lag_ratio=0.45), run_time=2.4)
        # fala 3: a pergunta
        self.fala(3)
        q = txt("Quanto cada medida mexe na moral?", 44, AMBAR, font=SERIF, weight=BOLD).to_edge(UP, buff=0.9)
        marcas = VGroup(*[txt("?", 64, AMBAR, font=SERIF, weight=BOLD).next_to(c, DOWN, buff=0.3) for c in cartas])
        self.play(Write(q), LaggedStart(*[FadeIn(m, scale=1.6) for m in marcas], lag_ratio=0.3), run_time=1.8)
        # fala 4: dados + regressão linear
        self.fala(4)
        self.play(FadeOut(cartas), FadeOut(marcas), FadeOut(q), run_time=0.8)
        dados = txt("dados", 46, PAPEL, font=SERIF, slant=ITALIC).shift(UP * 0.9)
        self.play(FadeIn(dados, shift=UP * 0.2), run_time=0.8)
        self.ate(self.ini[4] + 4.2)
        tit = txt("Regressão linear", 84, AMBAR, font=SERIF, weight=BOLD).shift(DOWN * 0.5)
        sub = Line(LEFT * 4.2, RIGHT * 4.2, color=LATAO).next_to(tit, DOWN, buff=0.25)
        self.play(Write(tit), Create(sub), run_time=1.6)
        self.encerrar()


def pesquisa_exemplo(n=7, seed=11):
    """Linhas no formato da pesquisa do jogo (mesmo gerador do servidor, engine/morale.py)."""
    sys.path.insert(0, str(RAIZ / "server"))
    from app.engine import morale
    rng = np.random.default_rng(seed)
    betas = np.array([0.0, -3.0, 1.5, -0.8, -2.2, 2.4])
    return morale.survey(betas, rng, n=n)


class Dados(Ritmo, Scene):
    CENA = "dados"

    def construct(self):
        self.preparar()
        linhas = pesquisa_exemplo()
        cols = ["ração", "propaganda", "horas extra", "baixas", "saldo terr.", "Δ moral"]
        chaves = ["racao", "propaganda", "horas_extra", "baixas", "saldo_territorial", "delta_moral"]
        larg = [1.55, 2.0, 1.95, 1.5, 1.85, 1.75]
        folha = Rectangle(width=12.6, height=7.5, color=PAPEL_2, fill_color=PAPEL, fill_opacity=1, stroke_width=0).shift(DOWN * 0.15)
        cab = txt("PESQUISA DE OPINIÃO · NOETHÉRIA", 30, TINTA, font=MAQ).move_to(folha.get_top() + DOWN * 0.55)
        conf = txt("CONFIDENCIAL", 22, VERMELHO, font=SANS, weight=BOLD).rotate(-6 * DEGREES).move_to(folha.get_corner(UR) + LEFT * 1.6 + DOWN * 0.55)
        conf_box = SurroundingRectangle(conf, color=VERMELHO, buff=0.08, stroke_width=2.5)
        x0 = -5.4
        xs = []
        for w in larg:
            xs.append(x0 + w / 2)
            x0 += w + 0.2
        ytop = 1.95
        head = VGroup(*[txt(c, 24, "#5a5040", weight=BOLD).move_to([x, ytop, 0]) for c, x in zip(cols, xs)])
        regua = Line([-5.5, ytop - 0.32, 0], [5.6, ytop - 0.32, 0], color=TINTA, stroke_width=2)
        corpo = VGroup()
        for k, row in enumerate(linhas):
            y = ytop - 0.82 - k * 0.56
            vals = [row[c] for c in chaves]
            fmt = [f"{v:g}".replace(".", ",") if not isinstance(v, float) or abs(v - round(v)) < 1e-9 else f"{v:.2f}".replace(".", ",") for v in vals]
            corpo.add(VGroup(*[txt(f, 26, TINTA, font=MONO).move_to([x, y, 0]) for f, x in zip(fmt, xs)]))
        etc = txt("⋮", 30, TINTA).move_to([xs[2], ytop - 0.82 - len(linhas) * 0.56 + 0.1, 0])
        # fala 0: a folha e as linhas
        self.fala(0)
        self.play(FadeIn(folha, shift=UP * 0.3), run_time=0.8)
        self.play(AddTextLetterByLetter(cab), FadeIn(conf, conf_box), run_time=1.2)
        self.play(FadeIn(head), Create(regua), run_time=0.7)
        self.play(LaggedStart(*[FadeIn(r, shift=DOWN * 0.1) for r in corpo], lag_ratio=0.25), FadeIn(etc), run_time=2.4)
        linha_obs = SurroundingRectangle(corpo[0], color=AZUL, buff=0.1, stroke_width=3)
        self.play(Create(linha_obs), run_time=0.6)
        self.play(FadeOut(linha_obs), run_time=0.4)

        def caixa_col(i0, i1, cor):
            g = VGroup(head[i0:i1 + 1], *[r[i0:i1 + 1] for r in corpo])
            return SurroundingRectangle(g, color=cor, buff=0.14, stroke_width=4)
        # fala 1: o que o governo fez / o que a guerra fez
        self.fala(1)
        c_gov = caixa_col(0, 2, AZUL)
        self.play(Create(c_gov), run_time=0.9)
        self.ate(self.ini[1] + 6.3)
        c_guerra = caixa_col(3, 4, LATAO)
        self.play(Create(c_guerra), run_time=0.9)
        # fala 2: a resposta
        self.fala(2)
        c_resp = caixa_col(5, 5, VERMELHO)
        self.play(Create(c_resp), run_time=0.9)
        # fala 3: explicativas x resposta
        self.fala(3)
        self.play(FadeOut(c_gov), FadeOut(c_guerra), run_time=0.4)
        g_exp = VGroup(head[0:5], *[r[0:5] for r in corpo])
        br1 = Brace(g_exp, DOWN, color=AZUL).shift(DOWN * 0.35)
        l1 = txt("variáveis explicativas (causas)", 26, AZUL, weight=BOLD).next_to(br1, DOWN, buff=0.12)
        br2 = Brace(VGroup(*[r[5] for r in corpo]), DOWN, color=VERMELHO).shift(DOWN * 0.35)
        l2 = txt("resposta (efeito)", 26, VERMELHO, weight=BOLD).next_to(br2, DOWN, buff=0.12)
        self.play(GrowFromCenter(br1), FadeIn(l1), run_time=1.0)
        self.play(GrowFromCenter(br2), FadeIn(l2), run_time=1.0)
        self.encerrar()


# dados de uma causa só (propaganda contínua para os quadrados não se sobreporem)
_rng = np.random.default_rng(5)
XS = np.sort(_rng.uniform(0.2, 5.0, 16))
YS = 0.6 + 1.4 * XS + _rng.normal(0, 1.1, XS.size)
_A = np.vstack([np.ones_like(XS), XS]).T
B0, B1 = np.linalg.lstsq(_A, YS, rcond=None)[0]


def eixos_reta():
    ax = Axes(x_range=[0, 5.5, 1], y_range=[-2, 10, 2], x_length=7.6, y_length=5.4,
              axis_config={"color": PAPEL, "stroke_width": 2.5, "include_ticks": True},
              tips=True).shift(LEFT * 1.6 + DOWN * 0.45)
    lx = txt("propaganda", 26, PAPEL).next_to(ax.x_axis.get_end(), DOWN, buff=0.25).shift(LEFT * 0.6)
    ly = txt("variação da moral", 26, PAPEL).next_to(ax.y_axis.get_end(), RIGHT, buff=0.2)
    return ax, lx, ly


class Reta(Ritmo, Scene):
    CENA = "reta"

    def construct(self):
        self.preparar()
        ax, lx, ly = eixos_reta()
        pts = VGroup(*[Dot(ax.c2p(x, y), radius=0.075, color=VERMELHO) for x, y in zip(XS, YS)])
        # fala 0
        self.fala(0)
        self.play(Create(ax), FadeIn(lx, ly), run_time=1.6)
        self.play(LaggedStart(*[GrowFromCenter(d) for d in pts], lag_ratio=0.08), run_time=2.2)
        # fala 1: tendência
        self.fala(1)
        self.play(*[d.animate.shift(UP * 0.12) for d in pts[::2]], rate_func=there_and_back, run_time=0.8)
        tend = Arrow(ax.c2p(0.6, 0.5), ax.c2p(4.8, 8.6), color=AMBAR, stroke_width=5, buff=0)
        tt = txt("mais propaganda,\nmais moral", 28, AMBAR, line_spacing=0.85).move_to([4.9, 1.8, 0])
        self.ate(self.ini[1] + 4.6)
        self.play(GrowArrow(tend), FadeIn(tt), run_time=1.2)
        # fala 2: a reta e a equação
        self.fala(2)
        a, b = ValueTracker(3.0), ValueTracker(0.6)
        reta = always_redraw(lambda: ax.plot(lambda x: a.get_value() + b.get_value() * x, x_range=[0, 5.3],
                                             color=PAPEL, stroke_width=4))
        eq = MathTex(r"\Delta\text{moral} \approx", r"\beta_0", "+", r"\beta_1", r"\cdot \text{propaganda}", font_size=46).to_edge(UP, buff=0.35)
        eq[1].set_color(AMBAR)
        eq[3].set_color(AMBAR)
        self.play(FadeOut(tend), FadeOut(tt), Create(reta), run_time=1.2)
        self.play(Write(eq), run_time=1.8)
        # fala 3: qual a melhor?
        self.fala(3)
        fantasmas = VGroup(*[ax.plot(lambda x, aa=aa, bb=bb: aa + bb * x, x_range=[0, 5.3], color=PAPEL,
                                     stroke_opacity=0.35, stroke_width=2)
                             for aa, bb in [(5, 0.2), (-1, 2.4), (2, 1.0), (0.5, 1.8), (4, 0.6)]])
        self.play(LaggedStart(*[Create(f) for f in fantasmas], lag_ratio=0.15), run_time=1.5)
        self.play(FadeOut(fantasmas), run_time=0.6)
        # fala 4: resíduos
        self.fala(4)
        res = always_redraw(lambda: VGroup(*[DashedLine(ax.c2p(x, y), ax.c2p(x, a.get_value() + b.get_value() * x),
                                                        color=LATAO, stroke_width=2.5, dash_length=0.06)
                                             for x, y in zip(XS, YS)]))
        self.play(FadeIn(res), run_time=0.8)
        k = 9
        lab = txt("resíduo", 24, AMBAR).next_to(ax.c2p(XS[k], (YS[k] + a.get_value() + b.get_value() * XS[k]) / 2), LEFT, buff=0.25)
        self.play(FadeIn(lab, shift=LEFT * 0.2), run_time=0.6)

        # fala 5: quadrados e soma
        def quadrados():
            g = VGroup()
            for x, y in zip(XS, YS):
                p1 = ax.c2p(x, y)
                p2 = ax.c2p(x, a.get_value() + b.get_value() * x)
                s = abs(p1[1] - p2[1])
                g.add(Polygon(p2, p1, p1 + RIGHT * s, p2 + RIGHT * s, color=AMBAR, stroke_width=1.2,
                              fill_color=AMBAR, fill_opacity=0.22))
            return g

        def sse():
            return float(np.sum((YS - (a.get_value() + b.get_value() * XS)) ** 2))

        base_barra = np.array([5.6, -2.9, 0])
        alt = lambda: min(5.2, 0.32 * np.sqrt(sse()))
        barra = always_redraw(lambda: Rectangle(width=0.8, height=max(0.02, alt()), color=AMBAR,
                                                fill_color=AMBAR, fill_opacity=0.85, stroke_width=0)
                              .move_to(base_barra + UP * alt() / 2))
        rot_b = txt("soma dos\nquadrados", 22, AMBAR, line_spacing=0.8).move_to(base_barra + DOWN * 0.5)
        self.fala(5)
        self.play(FadeOut(lab), run_time=0.3)
        qd = always_redraw(quadrados)
        self.play(FadeIn(qd), run_time=1.6)
        self.ate(self.ini[5] + 5.0)
        self.play(FadeIn(barra), FadeIn(rot_b), run_time=1.0)
        self.play(a.animate.set_value(5.0), b.animate.set_value(0.1), run_time=1.6)
        self.play(a.animate.set_value(1.5), b.animate.set_value(1.1), run_time=1.4)
        # fala 6: o mínimo
        self.fala(6)
        self.play(a.animate.set_value(B0), b.animate.set_value(B1), run_time=2.6, rate_func=smooth)
        mq = txt("mínimos\nquadrados", 34, AMBAR, font=SERIF, weight=BOLD, line_spacing=0.85).move_to([5.6, 1.6, 0])
        self.play(Indicate(barra, color=PAPEL), Write(mq), run_time=1.4)
        self.encerrar()


class Leitura(Ritmo, Scene):
    CENA = "leitura"

    def construct(self):
        self.preparar()
        ax, lx, ly = eixos_reta()
        pts = VGroup(*[Dot(ax.c2p(x, y), radius=0.07, color=VERMELHO, fill_opacity=0.55) for x, y in zip(XS, YS)])
        reta = ax.plot(lambda x: B0 + B1 * x, x_range=[0, 5.3], color=PAPEL, stroke_width=4)
        self.add(ax, lx, ly, pts, reta)
        self.fala(0)
        tit = txt("O que significam esses números?", 40, AMBAR, font=SERIF, weight=BOLD).to_edge(UP, buff=0.4)
        self.play(Write(tit), run_time=1.4)
        # fala 1: inclinação
        self.fala(1)
        x1, x2 = 2.5, 3.5
        pA, pB, pC = ax.c2p(x1, B0 + B1 * x1), ax.c2p(x2, B0 + B1 * x1), ax.c2p(x2, B0 + B1 * x2)
        h = Line(pA, pB, color=AZUL, stroke_width=5)
        v = Line(pB, pC, color=AMBAR, stroke_width=5)
        lh = txt("+1 de propaganda", 24, AZUL).next_to(h, DOWN, buff=0.15)
        lv = MathTex(r"+\beta_1", font_size=44, color=AMBAR).next_to(v, RIGHT, buff=0.15)
        self.play(Create(h), FadeIn(lh), run_time=1.2)
        self.play(Create(v), FadeIn(lv), run_time=1.2)
        val = MathTex(r"\beta_1 \approx " + f"{B1:.1f}".replace(".", "{,}"), font_size=52, color=AMBAR).move_to([3.4, 1.4, 0], aligned_edge=LEFT)
        self.ate(self.ini[1] + 6.0)
        self.play(TransformFromCopy(lv, val), run_time=1.2)
        exp = txt("cada ponto de propaganda\n≈ +" + f"{B1:.1f}".replace(".", ",") + " de moral", 26, PAPEL, line_spacing=0.9).next_to(val, DOWN, buff=0.35, aligned_edge=LEFT)
        self.play(FadeIn(exp, shift=UP * 0.15), run_time=0.8)
        # fala 2: intercepto
        self.fala(2)
        p0 = Dot(ax.c2p(0, B0), radius=0.13, color=AZUL)
        l0 = MathTex(r"\beta_0", font_size=48, color=AZUL).next_to(p0, LEFT, buff=0.2)
        self.play(GrowFromCenter(p0), Write(l0), Indicate(ax.y_axis, color=AZUL), run_time=1.4)
        e0 = txt("propaganda = 0:\na tendência de fundo", 26, AZUL, line_spacing=0.9).next_to(exp, DOWN, buff=0.6).align_to(exp, LEFT)
        self.play(FadeIn(e0, shift=UP * 0.15), run_time=0.8)
        self.encerrar()


# dados com duas causas (ração e propaganda) para o plano
_r2 = np.random.default_rng(8)
RAC = _r2.uniform(0, 2, 22)
PRO = np.clip(1.2 + 1.4 * RAC + _r2.normal(0, 0.9, 22), 0, 5)     # as causas andam juntas
DM = 1.0 - 3.0 * RAC + 1.5 * PRO + _r2.normal(0, 0.9, 22)
_X2 = np.vstack([np.ones_like(RAC), RAC, PRO]).T
C0, C1, C2 = np.linalg.lstsq(_X2, DM, rcond=None)[0]


class Plano(Ritmo, ThreeDScene):
    CENA = "plano"

    def construct(self):
        self.preparar()
        ax = ThreeDAxes(x_range=[0, 2.2, 1], y_range=[0, 5.5, 1], z_range=[-6, 8, 2],
                        x_length=4.4, y_length=5.0, z_length=4.6, axis_config={"color": PAPEL}).shift(DOWN * 0.35)
        lx = txt("ração", 28, AZUL).move_to(ax.c2p(2.6, 0, 0))
        ly = txt("propaganda", 28, AZUL).move_to(ax.c2p(0, 6.1, 0))   # abaixo da equação do topo
        self.add_fixed_orientation_mobjects(lx, ly)
        self.remove(lx, ly)
        self.set_camera_orientation(phi=0, theta=-90 * DEGREES, zoom=0.95)
        pts_base = VGroup(*[Dot3D(ax.c2p(r, p, 0), radius=0.07, color=AZUL, resolution=(6, 6)) for r, p in zip(RAC, PRO)])
        # fala 0: as causas andam juntas (vista de cima)
        self.fala(0)
        self.play(Create(ax), FadeIn(lx, ly), run_time=1.4)
        self.play(LaggedStart(*[FadeIn(d) for d in pts_base], lag_ratio=0.05), run_time=1.6)
        aviso = txt("onde há mais propaganda, há mais racionamento", 28, AMBAR).to_edge(UP, buff=0.5)
        self.add_fixed_in_frame_mobjects(aviso)
        self.play(FadeIn(aviso), run_time=0.8)
        tend = Line(ax.c2p(0.1, 1.3, 0), ax.c2p(2.0, 4.1, 0), color=AMBAR, stroke_width=4)
        self.play(Create(tend), run_time=1.2)
        # fala 1: a equação com todas as causas
        self.fala(1)
        eq = MathTex(r"\Delta\text{moral} = \beta_0 + \beta_1\,\text{ração} + \beta_2\,\text{propaganda} + \beta_3\,\text{horas} + \cdots",
                     font_size=40).to_edge(UP, buff=0.45)
        self.add_fixed_in_frame_mobjects(eq)
        self.remove(eq)
        self.play(FadeOut(aviso), FadeOut(tend), run_time=0.5)
        self.play(Write(eq), run_time=2.6)
        # fala 2: o plano em 3D
        self.fala(2)
        lz = txt("variação da moral", 28, VERMELHO).move_to(ax.c2p(0, 0, 9.0))
        self.add_fixed_orientation_mobjects(lz)
        self.remove(lz)
        self.move_camera(phi=68 * DEGREES, theta=-48 * DEGREES, zoom=0.82, run_time=2.4)
        pts = VGroup(*[Dot3D(ax.c2p(r, p, z), radius=0.075, color=VERMELHO, resolution=(6, 6)) for r, p, z in zip(RAC, PRO, DM)])
        self.play(*[Transform(a_, b_) for a_, b_ in zip(pts_base, pts)], FadeIn(lz), run_time=1.6)
        plano = Surface(lambda u, v: ax.c2p(u, v, C0 + C1 * u + C2 * v), u_range=[0, 2.1], v_range=[0, 5.3],
                        resolution=(6, 10), fill_opacity=0.26, checkerboard_colors=[AMBAR, AMBAR],
                        stroke_color=AMBAR, stroke_width=0.8, stroke_opacity=0.6)
        hastes = VGroup(*[Line(ax.c2p(r, p, z), ax.c2p(r, p, C0 + C1 * r + C2 * p), color=PAPEL, stroke_width=1.5)
                          for r, p, z in zip(RAC, PRO, DM)])
        self.play(Create(plano), run_time=1.8)
        self.play(Create(hastes), run_time=1.0)
        self.begin_ambient_camera_rotation(rate=0.12)
        # fala 3: cada beta, com as outras fixas
        self.fala(3)
        r_fixo = 1.0
        corte = Line(ax.c2p(r_fixo, 0, C0 + C1 * r_fixo), ax.c2p(r_fixo, 5.3, C0 + C1 * r_fixo + C2 * 5.3),
                     color=AZUL, stroke_width=7)
        legenda = MathTex(r"\beta_2 = \text{efeito da propaganda, com a ração fixa}", font_size=38, color=AZUL).to_edge(DOWN, buff=0.5)
        self.add_fixed_in_frame_mobjects(legenda)
        self.remove(legenda)
        self.play(Create(corte), Write(legenda), run_time=1.8)
        self.ate(self.total - 0.8)
        self.stop_ambient_camera_rotation()
        self.encerrar()


class Matriz(Ritmo, Scene):
    CENA = "matriz"

    def construct(self):
        self.preparar()
        self.fala(0)
        tit = txt("Álgebra linear", 56, AMBAR, font=SERIF, weight=BOLD)
        self.play(Write(tit), run_time=1.4)
        self.play(tit.animate.scale(0.6).to_edge(UP, buff=0.35), run_time=0.8)
        # fala 1: empilhar as equações e virar matriz
        self.fala(1)
        sis = MathTex(
            r"y_1 &= \beta_0 + \beta_1 x_{11} + \beta_2 x_{12} + \cdots\\",
            r"y_2 &= \beta_0 + \beta_1 x_{21} + \beta_2 x_{22} + \cdots\\",
            r"&\ \ \vdots\\",
            r"y_n &= \beta_0 + \beta_1 x_{n1} + \beta_2 x_{n2} + \cdots", font_size=44)
        self.play(LaggedStart(*[FadeIn(p, shift=RIGHT * 0.3) for p in sis], lag_ratio=0.4), run_time=2.6)
        Y = Matrix([["y_1"], ["y_2"], [r"\vdots"], ["y_n"]], element_alignment_corner=ORIGIN)
        X = Matrix([["1", "x_{11}", "x_{12}", r"\cdots"], ["1", "x_{21}", "x_{22}", r"\cdots"],
                    [r"\vdots", r"\vdots", r"\vdots", ""], ["1", "x_{n1}", "x_{n2}", r"\cdots"]],
                   h_buff=1.15, element_alignment_corner=ORIGIN)
        Bv = Matrix([[r"\beta_0"], [r"\beta_1"], [r"\beta_2"], [r"\vdots"]], element_alignment_corner=ORIGIN)
        aprox = MathTex(r"\approx", font_size=60)
        mat = VGroup(Y, aprox, X, Bv).arrange(RIGHT, buff=0.35).scale(0.95)
        self.ate(self.ini[1] + 4.6)
        self.play(TransformMatchingShapes(sis, mat), run_time=2.2)
        ry = txt("y", 36, VERMELHO, font=SERIF, slant=ITALIC).next_to(Y, DOWN, buff=0.35)
        rx = txt("X", 36, AZUL, font=SERIF, slant=ITALIC).next_to(X, DOWN, buff=0.35)
        rb = MathTex(r"\beta", font_size=48, color=AMBAR).next_to(Bv, DOWN, buff=0.35)
        self.play(FadeIn(ry), Y.animate.set_color(VERMELHO), run_time=0.7)
        self.play(FadeIn(rx), X.animate.set_color(AZUL), run_time=0.7)
        self.play(FadeIn(rb), Bv.animate.set_color(AMBAR), run_time=0.7)
        # fala 2: a coluna de uns
        self.fala(2)
        col1 = X.get_columns()[0]
        caixa = SurroundingRectangle(col1, color=AMBAR, buff=0.12, stroke_width=4)
        nota = MathTex(r"\text{carrega } \beta_0", font_size=40, color=AMBAR).next_to(caixa, UP, buff=0.25)
        self.play(Create(caixa), col1.animate.set_color(AMBAR), FadeIn(nota), run_time=1.2)
        # fala 3: y ≈ Xβ
        self.fala(3)
        comp = MathTex(r"y", r"\approx", r"X", r"\beta", font_size=120)
        comp[0].set_color(VERMELHO)
        comp[2].set_color(AZUL)
        comp[3].set_color(AMBAR)
        self.play(FadeOut(VGroup(caixa, nota, ry, rx, rb)), TransformMatchingShapes(mat, comp), run_time=1.8)
        self.encerrar()


def seta3d(a, b, color, thickness=0.03):
    """Arrow3D com menos faces (o renderizador Cairo ordena cada face a cada quadro: menos faces, render mais rápido)."""
    s = Arrow3D(a, b, color=color, thickness=thickness, resolution=10)
    ponta = Cone(direction=s.direction, base_radius=0.08, height=0.3, resolution=10).shift(np.asarray(b, dtype=float))
    s.remove(s.cone)
    s.cone = ponta
    s.add(ponta)
    return s.set_color(color)


class Projecao(Ritmo, ThreeDScene):
    CENA = "projecao"

    def construct(self):
        self.preparar()
        self.set_camera_orientation(phi=58 * DEGREES, theta=100 * DEGREES, zoom=0.9)
        ax = ThreeDAxes(x_range=[-1, 4], y_range=[-1, 4], z_range=[-1, 4], x_length=5, y_length=5, z_length=5,
                        axis_config={"color": "#55604f"})
        o = ax.c2p(0, 0, 0)
        c1 = np.array([1.0, 1.0, 0.25])
        c2 = np.array([0.4, 2.2, 0.0])
        y = np.array([2.6, 2.4, 3.1])
        M = np.vstack([c1, c2]).T
        beta = np.linalg.lstsq(M, y, rcond=None)[0]
        yh = M @ beta
        P = lambda v: ax.c2p(*v)
        # fala 0: y como uma seta
        self.fala(0)
        self.play(Create(ax), run_time=1.2)
        vy = seta3d(o, P(y), VERMELHO, 0.03)
        ly = MathTex("y", font_size=56, color=VERMELHO).move_to(P(y * 1.12))
        self.add_fixed_orientation_mobjects(ly)
        self.remove(ly)
        self.play(Create(vy), FadeIn(ly), run_time=1.4)
        dims = txt("uma dimensão por observação", 28, PAPEL).to_corner(UL, buff=0.5)
        self.add_fixed_in_frame_mobjects(dims)
        self.remove(dims)
        self.play(FadeIn(dims), run_time=0.6)
        # fala 1: o plano das colunas de X
        self.fala(1)
        v1 = seta3d(o, P(c1 * 1.6), AZUL, 0.025)
        v2 = seta3d(o, P(c2 * 1.4), AZUL, 0.025)
        plano = Surface(lambda u, v: P(u * c1 + v * c2), u_range=[-0.6, 3.2], v_range=[-0.5, 1.9], resolution=(6, 6),
                        fill_opacity=0.32, checkerboard_colors=[AZUL, "#4a6f9a"], stroke_width=0.4, stroke_color=AZUL)
        lp = MathTex(r"\text{tudo o que } X\beta \text{ produz}", font_size=36, color=AZUL).to_corner(UR, buff=0.5)
        self.add_fixed_in_frame_mobjects(lp)
        self.remove(lp)
        self.play(Create(v1), Create(v2), run_time=1.2)
        self.play(Create(plano), FadeIn(lp), run_time=1.6)
        self.begin_ambient_camera_rotation(rate=0.035)
        # fala 2: a sombra
        self.fala(2)
        self.ate(self.ini[2] + 4.0)
        queda = DashedLine(P(y), P(yh), color=PAPEL, dash_length=0.08)
        vyh = seta3d(o, P(yh), AMBAR, 0.03)
        lyh = MathTex(r"X\beta", font_size=50, color=AMBAR).move_to(P(yh * 1.18) + np.array([0, 0, -0.2]))
        self.add_fixed_orientation_mobjects(lyh)
        self.remove(lyh)
        self.play(Create(queda), run_time=1.4)
        self.play(Create(vyh), FadeIn(lyh), run_time=1.4)
        # fala 3: o erro é perpendicular
        self.fala(3)
        e = y - yh
        n_e = e / np.linalg.norm(e)
        d1 = (yh / np.linalg.norm(yh))
        s = 0.28
        canto = VGroup(Line(P(yh + n_e * s), P(yh + n_e * s - d1 * s), color=PAPEL),
                       Line(P(yh - d1 * s), P(yh + n_e * s - d1 * s), color=PAPEL))
        ve = seta3d(P(yh), P(y), VERMELHO, 0.02)
        self.play(Create(canto), Create(ve), run_time=1.4)
        eq1 = MathTex(r"X^{T}\,(y - X\beta) = 0", font_size=56).to_edge(DOWN, buff=0.6)
        self.add_fixed_in_frame_mobjects(eq1)
        self.remove(eq1)
        self.ate(self.ini[3] + 6.2)
        self.play(Write(eq1), run_time=1.8)
        # fala 4: equações normais
        self.fala(4)
        eq2 = MathTex(r"X^{T}X\,\beta = X^{T}y", font_size=60, color=AMBAR).to_edge(DOWN, buff=0.6)
        self.add_fixed_in_frame_mobjects(eq2)
        self.remove(eq2)
        self.play(FadeOut(eq1), FadeIn(eq2), run_time=1.2)
        rot2 = txt("equações normais", 30, AMBAR, font=SERIF, slant=ITALIC).next_to(eq2, UP, buff=0.25)
        self.add_fixed_in_frame_mobjects(rot2)
        self.remove(rot2)
        self.play(FadeIn(rot2), run_time=0.6)
        # fala 5: a fórmula
        self.fala(5)
        eq3 = MathTex(r"\beta = (X^{T}X)^{-1}X^{T}y", font_size=66, color=AMBAR).to_edge(DOWN, buff=0.6)
        caixa = SurroundingRectangle(eq3, color=AMBAR, buff=0.2)
        self.add_fixed_in_frame_mobjects(eq3, caixa)
        self.remove(eq3, caixa)
        self.play(FadeOut(eq2), FadeOut(rot2), FadeIn(eq3), run_time=1.2)
        self.play(Create(caixa), run_time=0.8)
        # fala 6: geometria = cálculo
        self.fala(6)
        g1 = MathTex(r"\min_\beta \;\|y - X\beta\|^2", font_size=44).to_corner(UL, buff=0.5).shift(DOWN * 0.9)
        g2 = txt("= a sombra perpendicular", 30, PAPEL).next_to(g1, DOWN, buff=0.25).align_to(g1, LEFT)
        self.add_fixed_in_frame_mobjects(g1, g2)
        self.remove(g1, g2)
        self.play(FadeOut(dims), FadeIn(g1), run_time=0.8)
        self.play(FadeIn(g2), run_time=0.8)
        self.ate(self.total - 0.8)
        self.stop_ambient_camera_rotation()
        self.encerrar()


class Decisao(Ritmo, Scene):
    CENA = "decisao"

    def construct(self):
        self.preparar()
        itens = [("ração", -3.0), ("propaganda", 1.5), ("horas extra", -0.8), ("baixas", -2.2), ("saldo territorial", 2.4)]
        zero = 0.6
        u = 1.15
        barras = VGroup()
        self.fala(0)
        tit = txt("Os betas de Noethéria", 40, AMBAR, font=SERIF, weight=BOLD).to_edge(UP, buff=0.45)
        eixo = Line([zero, 2.55, 0], [zero, -2.2, 0], color=PAPEL, stroke_width=2)
        self.play(Write(tit), Create(eixo), run_time=1.2)
        for k, (nome, v) in enumerate(itens):
            yk = 2.05 - k * 0.92
            cor = VERDE if v > 0 else VERMELHO
            r = Rectangle(width=abs(v) * u, height=0.62, color=cor, fill_color=cor, fill_opacity=0.85, stroke_width=0)
            r.move_to([zero + v * u / 2, yk, 0])
            n = txt(nome, 28, PAPEL).move_to([-4.6, yk, 0]).align_to([-6.2, 0, 0], LEFT)
            val = txt(("+" if v > 0 else "−") + f"{abs(v):.1f}".replace(".", ","), 28, cor, font=MONO)
            val.next_to(r, RIGHT if v > 0 else LEFT, buff=0.15)
            barras.add(VGroup(n, r, val))
        alvo = [0, 1, 2]
        for k in alvo:
            n, r, val = barras[k]
            self.play(FadeIn(n), GrowFromEdge(r, LEFT if itens[k][1] > 0 else RIGHT), FadeIn(val), run_time=1.0)
            self.wait(0.6)
        for k in (3, 4):
            n, r, val = barras[k]
            self.play(FadeIn(n), GrowFromEdge(r, LEFT if itens[k][1] > 0 else RIGHT), FadeIn(val), run_time=0.6)
        # fala 1: o preço
        self.fala(1)
        e1 = SurroundingRectangle(barras[0], color=PAPEL, buff=0.1)
        e2 = SurroundingRectangle(barras[1], color=PAPEL, buff=0.1)
        p1 = txt("1 nível de ração = −3 de moral", 26, VERMELHO, font=MAQ).move_to([0, -2.75, 0])
        p2 = txt("1 ponto de propaganda = +1,5 de moral (custa 1 Aço)", 26, VERDE, font=MAQ).next_to(p1, DOWN, buff=0.2)
        self.play(Create(e1), FadeIn(p1), run_time=1.0)
        self.ate(self.ini[1] + 4.6)
        self.play(ReplacementTransform(e1, e2), FadeIn(p2), run_time=1.0)
        # fala 2: o cuidado
        self.fala(2)
        self.play(FadeOut(e2), barras.animate.set_opacity(0.25), FadeOut(p1), FadeOut(p2), run_time=0.8)
        carimbo = txt("ASSOCIAÇÃO ≠ CAUSA", 58, VERMELHO, font=SANS, weight=BOLD)
        moldura = SurroundingRectangle(carimbo, color=VERMELHO, buff=0.25, stroke_width=6)
        sel = VGroup(carimbo, moldura).rotate(-7 * DEGREES)
        self.play(FadeIn(sel, scale=1.8), run_time=0.5, rate_func=rush_into)
        nota = txt("se uma causa importante ficou de fora", 28, PAPEL).move_to([0, -3.05, 0])
        fundo_nota = BackgroundRectangle(nota, color=FUNDO, fill_opacity=0.9, buff=0.15)
        self.play(FadeIn(fundo_nota), FadeIn(nota), run_time=0.8)
        self.encerrar()


class JogoMoldura(Scene):
    """Quadro parado usado por cima do clipe do jogo (o título da cena)."""

    def construct(self):
        t = txt("NO JOGO · ABA GOVERNO", 30, LATAO, weight=BOLD).to_edge(UP, buff=0.32)
        self.add(t)
        self.wait(0.1)


class Fim(Ritmo, Scene):
    CENA = "fim"

    def construct(self):
        self.preparar()
        mapa, dono, p = mapa_continente(destaque="NOE")
        self.fala(0)
        self.play(FadeIn(mapa), run_time=1.6)
        tres = VGroup(txt("uma tabela", 30, PAPEL), txt("uma reta", 30, PAPEL), txt("uma sombra", 30, PAPEL)).arrange(RIGHT, buff=1.2).to_edge(DOWN, buff=0.7)
        for t in tres:
            self.play(FadeIn(t, shift=UP * 0.2), run_time=0.6)
            self.wait(0.6)
        self.fala(1)
        self.play(mapa.animate.set_opacity(0.15), FadeOut(tres), run_time=0.6)
        bs = txt("Boa sorte, ministro.", 72, AMBAR, font=SERIF, slant=ITALIC)
        self.play(Write(bs), run_time=1.2)
        self.encerrar()


class Creditos(Scene):
    """Encerramento sem narração (4 s)."""

    def construct(self):
        a = txt("ESTADO-MAIOR", 54, PAPEL, font=SANS, weight=BOLD)
        b = txt("A Guerra do Continente de Lebesgue", 34, LATAO, font=SERIF, slant=ITALIC)
        c = txt("Próximas instruções: Intendência · Operações · Inteligência", 24, CINZA)
        g = VGroup(a, b, c).arrange(DOWN, buff=0.4)
        self.play(FadeIn(g, shift=UP * 0.2), run_time=1.0)
        self.wait(2.2)
        self.play(FadeOut(g), run_time=0.8)
