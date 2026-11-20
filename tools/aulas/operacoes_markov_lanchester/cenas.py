"""Animações (Manim) da aula "Operações · Markov e Lanchester".

Renderizar (a partir da raiz do repositório):
    AULA_VOZ=<voz> manim -r 1920,1080 --frame_rate 30 tools/aulas/operacoes_markov_lanchester/cenas.py <Classe>
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import *  # noqa: E402,F401,F403

SEQ = "L C C T C L L C T T C L C C L T C L L C".split()
EST = {"L": ("limpo", AMBAR), "C": ("chuva", AZUL), "T": ("tempestade", "#9b6fd0")}
ORD = ["L", "C", "T"]
CONT = [[0] * 3 for _ in range(3)]
for a_, b_ in zip(SEQ, SEQ[1:]):
    CONT[ORD.index(a_)][ORD.index(b_)] += 1


def br(v, casas=2):
    s = f"{v:.{casas}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def icone(e, r=0.32):
    """Ícone do estado do tempo: sol, gota ou raio, num círculo da cor do estado."""
    nome, cor = EST[e]
    c = Circle(radius=r, color=cor, fill_color=cor, fill_opacity=0.25, stroke_width=3)
    if e == "L":
        s = VGroup(Circle(radius=r * 0.38, color=cor, fill_opacity=1, stroke_width=0),
                   *[Line(ORIGIN, UP * r * 0.22, color=cor, stroke_width=3).shift(UP * r * 0.55).rotate(k * PI / 4, about_point=ORIGIN) for k in range(8)])
    elif e == "C":
        s = VGroup(*[Line(UP * r * 0.3, DOWN * r * 0.3, color=cor, stroke_width=4).shift(RIGHT * dx * r) for dx in (-0.35, 0, 0.35)]).rotate(-15 * DEGREES)
    else:
        s = Polygon([0.1, 0.5, 0], [-0.25, 0.0, 0], [0.05, 0.0, 0], [-0.1, -0.5, 0], [0.3, 0.1, 0], [0.0, 0.1, 0],
                    color=cor, fill_opacity=1, stroke_width=0).scale(r * 1.1)
    return VGroup(c, s.move_to(c))


# =================================================================== CENAS
class Titulo(Scene):
    def construct(self):
        serie = txt("ESTADO-MAIOR · INSTRUÇÃO DE OPERAÇÕES", 26, LATAO, weight=BOLD)
        t1 = txt("Quando atacar, e com quanto?", 68, PAPEL, font=SERIF, weight=BOLD)
        t2 = txt("Cadeias de Markov e a lei de Lanchester", 40, AMBAR, font=SERIF, slant=ITALIC)
        g = VGroup(serie, t1, t2).arrange(DOWN, buff=0.45)
        linha = Line(LEFT * 3.4, RIGHT * 3.4, color=LATAO, stroke_width=2).next_to(t1, DOWN, buff=0.22)
        self.play(FadeIn(serie, shift=DOWN * 0.2), run_time=0.7)
        self.play(Write(t1), run_time=1.3)
        self.play(Create(linha), FadeIn(t2, shift=UP * 0.2), run_time=0.8)
        self.wait(1.1)
        self.play(FadeOut(VGroup(serie, t1, t2, linha)), run_time=0.6)


class Abertura(Ritmo, Scene):
    CENA = "abertura"

    def construct(self):
        self.preparar()
        grupo, polys, dono, p = mapa(4)
        self.fala(0)
        self.play(FadeIn(grupo), run_time=1.4)
        setas = VGroup(*[Arrow(p(*a), p(*b), color=VERMELHO, stroke_width=7, buff=0.1, max_tip_length_to_length_ratio=0.2)
                         for a, b in [((430, 520), (560, 470)), ((800, 230), (680, 300)), ((380, 250), (520, 330))]])
        self.play(LaggedStart(*[GrowArrow(s) for s in setas], lag_ratio=0.3), run_time=1.6)
        self.fala(1)
        self.play(grupo.animate.set_opacity(0.15), setas.animate.set_opacity(0.2), run_time=0.6)
        q1 = VGroup(icone("C", 0.5), txt("o tempo vai ajudar?", 40, PAPEL, font=SERIF)).arrange(RIGHT, buff=0.4)
        q2 = VGroup(Text("⚔", font=SANS, font_size=70, color=VERMELHO), txt("se atacarmos, vencemos?", 40, PAPEL, font=SERIF)).arrange(RIGHT, buff=0.4)
        qs = VGroup(q1, q2).arrange(DOWN, aligned_edge=LEFT, buff=0.7).shift(LEFT * 1.5)
        r1 = txt("→ Markov", 36, AZUL, weight=BOLD).next_to(q1, RIGHT, buff=0.6)
        r2 = txt("→ Lanchester", 36, VERMELHO, weight=BOLD).next_to(q2, RIGHT, buff=0.6)
        self.play(FadeIn(q1, shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[1] + self.dur[1] * 0.25)
        self.play(FadeIn(q2, shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[1] + self.dur[1] * 0.6)
        self.play(FadeIn(r1, shift=LEFT * 0.2), run_time=0.5)
        self.ate(self.ini[1] + self.dur[1] * 0.8)
        self.play(FadeIn(r2, shift=LEFT * 0.2), run_time=0.5)
        self.encerrar()


class Clima(Ritmo, Scene):
    CENA = "clima"

    def construct(self):
        self.preparar()
        # fala 0: três estados; o amanhã depende só do hoje
        self.fala(0)
        pos = {"L": [-3.2, 0.6, 0], "C": [0, 0.6, 0], "T": [3.2, 0.6, 0]}
        nos = {e: VGroup(icone(e, 0.75), txt(EST[e][0], 30, EST[e][1], weight=BOLD)).arrange(DOWN, buff=0.25).move_to(pos[e]) for e in ORD}
        self.play(LaggedStart(*[GrowFromCenter(nos[e]) for e in ORD], lag_ratio=0.3), run_time=1.4)
        hoje = txt("hoje", 30, PAPEL, font=MAQ).move_to([-1.6, -1.9, 0])
        amanha = txt("amanhã", 30, PAPEL, font=MAQ).move_to([1.6, -1.9, 0])
        seta = Arrow(hoje.get_right(), amanha.get_left(), color=PAPEL, buff=0.2)
        regra = txt("depende só de hoje", 30, AMBAR, weight=BOLD).next_to(seta, DOWN, buff=0.3)
        self.ate(self.ini[0] + self.dur[0] * 0.5)
        self.play(FadeIn(hoje), GrowArrow(seta), FadeIn(amanha), run_time=0.9)
        self.play(FadeIn(regra), run_time=0.5)
        # fala 1: o diário; contar transições
        self.fala(1)
        self.play(FadeOut(VGroup(*nos.values(), hoje, amanha, seta, regra)), run_time=0.5)
        fita = VGroup(*[icone(e, 0.27) for e in SEQ]).arrange(RIGHT, buff=0.1).to_edge(UP, buff=0.9)
        rot = txt("diário do tempo · 20 observações", 26, LATAO, font=MAQ).next_to(fita, UP, buff=0.25)
        self.play(FadeIn(rot), LaggedStart(*[FadeIn(i, shift=DOWN * 0.2) for i in fita], lag_ratio=0.06), run_time=2.0)
        # tabela de contagem (vazia)
        dx, dy = 1.5, 0.8
        org = np.array([-2.2, -0.6, 0])
        cab_c = VGroup(*[icone(e, 0.25).move_to(org + [j * dx, dy, 0]) for j, e in enumerate(ORD)])
        cab_l = VGroup(*[icone(e, 0.25).move_to(org + [-1.4, -i * dy, 0]) for i, e in enumerate(ORD)])
        tit_c = txt("amanhã →", 22, PAPEL_2, font=MAQ).next_to(cab_c, UP, buff=0.15)
        tit_l = txt("hoje ↓", 22, PAPEL_2, font=MAQ).next_to(cab_l, LEFT, buff=0.25)
        valores = [[Integer(0, font_size=40, color=PAPEL).move_to(org + [j * dx, -i * dy, 0]) for j in range(3)] for i in range(3)]
        self.ate(self.ini[1] + self.dur[1] * 0.45)
        self.play(FadeIn(cab_c), FadeIn(cab_l), FadeIn(tit_c), FadeIn(tit_l), *[FadeIn(v) for linha in valores for v in linha], run_time=0.8)
        # percorre as transições (rápido)
        par = SurroundingRectangle(VGroup(fita[0], fita[1]), color=PAPEL, buff=0.06)
        self.play(Create(par), run_time=0.3)
        n = len(SEQ) - 1
        passo = max(0.12, (self.ini[1] + self.dur[1] - 0.3 - self.renderer.time) / n)
        cont = [[0] * 3 for _ in range(3)]
        for k in range(n):
            i, j = ORD.index(SEQ[k]), ORD.index(SEQ[k + 1])
            cont[i][j] += 1
            novo = Integer(cont[i][j], font_size=40, color=PAPEL).move_to(valores[i][j])
            self.play(par.animate.move_to(VGroup(fita[k], fita[k + 1])), Transform(valores[i][j], novo), run_time=passo)
        self.play(FadeOut(par), run_time=0.3)
        # fala 2: a linha da chuva: 4, 2, 2
        self.fala(2)
        linha_c = SurroundingRectangle(VGroup(cab_l[1], *valores[1]), color=AZUL, buff=0.15, stroke_width=4)
        self.play(Create(linha_c), run_time=0.6)
        soma = MathTex(r"4 + 2 + 2 = 8", font_size=46, color=AZUL).next_to(linha_c, RIGHT, buff=0.6)
        self.ate(self.ini[2] + self.dur[2] * 0.35)
        self.play(Write(soma), run_time=1.0)
        # fala 3: dividir cada linha pelo total -> P; P(chuva -> tempestade) = 0,25; P²
        self.fala(3)
        tot = [sum(r) for r in CONT]
        novos = []
        for i in range(3):
            for j in range(3):
                novos.append(Transform(valores[i][j], txt(br(CONT[i][j] / tot[i]), 34, PAPEL, font=MONO).move_to(valores[i][j])))
        self.play(*novos, FadeOut(soma), run_time=1.2)
        lp = MathTex("P =", font_size=56).next_to(cab_l, LEFT, buff=1.2)
        self.play(FadeOut(tit_l), FadeIn(lp), run_time=0.5)
        self.ate(self.ini[3] + self.dur[3] * 0.35)
        alvo = SurroundingRectangle(valores[1][2], color=VERMELHO, buff=0.12, stroke_width=5)
        resp = VGroup(txt("hoje chove →", 28, PAPEL), txt("tempestade amanhã: 0,25", 30, VERMELHO, weight=BOLD)).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        resp.next_to(alvo, RIGHT, buff=0.6)
        self.play(Create(alvo), FadeIn(resp, shift=LEFT * 0.2), run_time=0.8)
        self.ate(self.ini[3] + self.dur[3] * 0.78)
        p2 = MathTex(r"\text{dois turnos: } P^{2}", font_size=44, color=AMBAR).to_edge(DOWN, buff=0.5)
        self.play(Write(p2), run_time=0.8)
        self.encerrar()


class PorQueClima(Ritmo, Scene):
    CENA = "por_que_clima"

    def construct(self):
        self.preparar()
        grupo, polys, dono, p = mapa(4, opacidade=lambda f: 0.5, escala=0.0075)
        desloc = LEFT * 1.6
        grupo.shift(desloc)
        self.fala(0)
        self.play(FadeIn(grupo), run_time=1.0)
        rotas = VGroup()
        for r in mapa_json()["sea_routes"]:
            v = VMobject(color=AZUL, stroke_width=6).set_points_smoothly([p(*q) + desloc for q in r["path"]])
            rotas.add(DashedVMobject(v, num_dashes=10))
        self.play(Create(rotas), run_time=1.0)
        raio = icone("T", 0.9).move_to([5.0, 1.8, 0])
        self.ate(self.ini[0] + self.dur[0] * 0.3)
        self.play(GrowFromCenter(raio), run_time=0.5)
        atq = txt("ataque × 0,65", 34, EST["T"][1], weight=BOLD).next_to(raio, DOWN, buff=0.3)
        self.play(FadeIn(atq), run_time=0.5)
        self.ate(self.ini[0] + self.dur[0] * 0.6)
        xs = VGroup(*[Cross(r, stroke_color=VERMELHO, stroke_width=6).scale(0.5) for r in rotas])
        fechado = txt("mar fechado", 34, VERMELHO, weight=BOLD).next_to(atq, DOWN, buff=0.4)
        self.play(Create(xs), FadeIn(fechado), run_time=0.8)
        self.fala(1)
        self.play(FadeOut(VGroup(grupo, rotas, xs, raio, atq, fechado)), run_time=0.6)
        rec = VGroup(txt("desafio resolvido →", 36, PAPEL), txt("o clima exato da resolução", 40, AMBAR, weight=BOLD)).arrange(DOWN, buff=0.3)
        self.play(FadeIn(rec, shift=UP * 0.2), run_time=0.8)
        self.ate(self.ini[1] + self.dur[1] * 0.55)
        dec = VGroup(txt("atacar hoje", 34, VERDE, weight=BOLD), txt("ou", 30, PAPEL_2, font=SERIF, slant=ITALIC),
                     txt("esperar", 34, VERMELHO, weight=BOLD)).arrange(RIGHT, buff=0.5).next_to(rec, DOWN, buff=0.8)
        self.play(FadeIn(dec), run_time=0.7)
        self.encerrar()


class Lanchester(Ritmo, Scene):
    CENA = "lanchester"

    def construct(self):
        self.preparar()
        a_, b_ = 1.2, 1.8
        A0, B0 = 12.0, 6.0
        t = ValueTracker(0.0)

        def estado(tt):
            k = math.sqrt(a_ * b_)
            A = A0 * math.cosh(k * tt) - math.sqrt(b_ / a_) * B0 * math.sinh(k * tt)
            B = B0 * math.cosh(k * tt) - math.sqrt(a_ / b_) * A0 * math.sinh(k * tt)
            return max(A, 0), max(B, 0)

        # fala 0: dois exércitos; cada um perde conforme o outro
        self.fala(0)
        ladoA = VGroup(*[Square(0.34, color=VERMELHO, fill_opacity=0.9, stroke_width=0) for _ in range(12)]).arrange_in_grid(4, 3, buff=0.12).move_to([-4.2, 0.3, 0])
        ladoB = VGroup(*[Square(0.34, color=AZUL, fill_opacity=0.9, stroke_width=0) for _ in range(6)]).arrange_in_grid(3, 2, buff=0.12).move_to([4.2, 0.3, 0])
        rA = txt("atacante A", 28, VERMELHO, weight=BOLD).next_to(ladoA, UP, buff=0.3)
        rB = txt("defensor B", 28, AZUL, weight=BOLD).next_to(ladoB, UP, buff=0.3)
        self.play(FadeIn(ladoA, lag_ratio=0.05), FadeIn(ladoB, lag_ratio=0.05), FadeIn(rA), FadeIn(rB), run_time=1.2)
        tiros = VGroup(*[Line([-3.2, y, 0], [3.2, y + 0.3 * ((-1) ** k), 0], color=PAPEL, stroke_width=1.5, stroke_opacity=0.5) for k, y in enumerate(np.linspace(-0.6, 1.2, 6))])
        self.ate(self.ini[0] + self.dur[0] * 0.4)
        self.play(LaggedStart(*[ShowPassingFlash(l.copy().set_stroke(width=4), time_width=0.4) for l in tiros], lag_ratio=0.15), run_time=1.6)
        # fala 1: as equações
        self.fala(1)
        eqs = MathTex(r"A' = -\beta\,B", r"\qquad", r"B' = -\alpha\,A", font_size=60).to_edge(UP, buff=0.5)
        eqs[0].set_color(VERMELHO)
        eqs[2].set_color(AZUL)
        self.play(Write(eqs), run_time=1.6)
        self.ate(self.ini[1] + self.dur[1] * 0.6)
        segredo = txt("uma quantidade que nunca muda…", 32, AMBAR, font=MAQ).next_to(eqs, DOWN, buff=0.35)
        self.play(FadeIn(segredo), run_time=0.6)
        # fala 2: o invariante e a batalha simulada
        self.fala(2)
        inv = MathTex(r"\alpha A^{2} - \beta B^{2}", r"= \text{constante}", font_size=60, color=AMBAR).move_to(segredo)
        self.play(FadeOut(segredo), Write(inv), run_time=1.4)
        barA = always_redraw(lambda: Rectangle(width=0.8, height=max(0.01, estado(t.get_value())[0] * 0.28), stroke_width=0, fill_color=VERMELHO, fill_opacity=0.9)
                             .move_to([-1.2, -3.0, 0], aligned_edge=DOWN))
        barB = always_redraw(lambda: Rectangle(width=0.8, height=max(0.01, estado(t.get_value())[1] * 0.28), stroke_width=0, fill_color=AZUL, fill_opacity=0.9)
                             .move_to([1.2, -3.0, 0], aligned_edge=DOWN))
        nA = always_redraw(lambda: DecimalNumber(estado(t.get_value())[0], num_decimal_places=1, font_size=34, color=VERMELHO).next_to(barA, UP, buff=0.1))
        nB = always_redraw(lambda: DecimalNumber(estado(t.get_value())[1], num_decimal_places=1, font_size=34, color=AZUL).next_to(barB, UP, buff=0.1))
        val = always_redraw(lambda: MathTex(r"= " + br(a_ * estado(t.get_value())[0] ** 2 - b_ * estado(t.get_value())[1] ** 2, 1), font_size=46, color=AMBAR)
                            .next_to(inv[0], DOWN, buff=0.3))
        self.play(FadeOut(VGroup(ladoA, ladoB)), rA.animate.next_to([-1.2, -3.0, 0], DOWN, buff=0.15).scale(0.8),
                  rB.animate.next_to([1.2, -3.0, 0], DOWN, buff=0.15).scale(0.8), run_time=0.8)
        self.add(barA, barB, nA, nB, val)
        self.play(t.animate.set_value(0.484), run_time=3.2, rate_func=linear)
        venc = VGroup(txt("vence a maior força:", 30, PAPEL, weight=BOLD),
                      MathTex(r"\alpha A_0^{2} \ \text{ou}\ \beta B_0^{2}", font_size=46)).arrange(DOWN, buff=0.15)
        venc.to_edge(RIGHT, buff=0.5).shift(DOWN * 1.6)
        self.ate(self.ini[2] + self.dur[2] * 0.7)
        self.play(FadeIn(venc), run_time=0.6)
        # fala 3: o quadrado: dobrar quadruplica
        self.fala(3)
        for m in (barA, barB, nA, nB, val):
            m.clear_updaters()
        self.play(FadeOut(VGroup(barA, barB, nA, nB, val, rA, rB, venc)), run_time=0.5)
        q1 = VGroup(*[Square(0.4, color=VERMELHO, fill_opacity=0.9, stroke_width=0) for _ in range(5)]).arrange(RIGHT, buff=0.1)
        q2 = VGroup(*[Square(0.4, color=VERMELHO, fill_opacity=0.9, stroke_width=0) for _ in range(10)]).arrange(RIGHT, buff=0.1)
        f1 = MathTex(r"5^2 = 25", font_size=48).next_to(q1, RIGHT, buff=0.5)
        f2 = MathTex(r"10^2 = 100", font_size=48, color=AMBAR).next_to(q2, RIGHT, buff=0.5)
        g = VGroup(VGroup(q1, f1), VGroup(q2, f2)).arrange(DOWN, aligned_edge=LEFT, buff=0.6).shift(DOWN * 1.2)
        self.play(FadeIn(g[0]), run_time=0.6)
        self.ate(self.ini[3] + self.dur[3] * 0.3)
        self.play(FadeIn(g[1]), run_time=0.6)
        x4 = txt("×4", 60, AMBAR, weight=BOLD).next_to(g, RIGHT, buff=0.6)
        self.play(FadeIn(x4, scale=1.5), run_time=0.5)
        self.ate(self.ini[3] + self.dur[3] * 0.7)
        conc = txt("concentrem as tropas", 40, AMBAR, font=SERIF, weight=BOLD).to_edge(DOWN, buff=0.35)
        self.play(Write(conc), run_time=0.9)
        self.encerrar()


class Exemplo(Ritmo, Scene):
    CENA = "exemplo"

    def construct(self):
        self.preparar()
        # fala 0: o cenário
        self.fala(0)
        a = VGroup(txt("12", 80, VERMELHO, font=MONO, weight=BOLD), txt("atacantes", 28, VERMELHO)).arrange(DOWN, buff=0.1)
        monte = Polygon([-1.2, -0.6, 0], [0, 0.9, 0], [1.2, -0.6, 0], color=PAPEL_2, fill_opacity=0.25, stroke_width=3)
        seis = txt("6", 72, AZUL, font=MONO, weight=BOLD).move_to(monte.get_center() + DOWN * 0.12)
        b = VGroup(seis, txt("defensores", 28, AZUL).next_to(monte, DOWN, buff=0.1))
        cena = VGroup(a, VGroup(monte, b)).arrange(RIGHT, buff=2.2).to_edge(UP, buff=0.7)
        vs = txt("contra", 28, PAPEL_2, font=SERIF, slant=ITALIC).move_to(cena)
        moral = txt("moral 70 nos dois lados", 26, PAPEL, font=MAQ).next_to(cena, DOWN, buff=0.3)
        self.play(FadeIn(a), run_time=0.6)
        self.play(FadeIn(vs), FadeIn(monte), FadeIn(b), run_time=0.8)
        self.ate(self.ini[0] + self.dur[0] * 0.7)
        self.play(FadeIn(moral), run_time=0.5)
        # fala 1: α e β
        self.fala(1)
        ea = MathTex(r"\alpha = 0{,}5 + \tfrac{70}{100} = 1{,}2", font_size=48, color=VERMELHO)
        eb = MathTex(r"\beta = 1{,}2 \times 1{,}5", r"= 1{,}8", font_size=48, color=AZUL)
        cols = VGroup(ea, eb).arrange(DOWN, aligned_edge=LEFT, buff=0.4).next_to(moral, DOWN, buff=0.5)
        self.play(Write(ea), run_time=1.2)
        self.ate(self.ini[1] + self.dur[1] * 0.55)
        mont = txt("(montanha)", 24, PAPEL_2, font=MAQ).next_to(eb, RIGHT, buff=0.3)
        self.play(Write(eb), FadeIn(mont), run_time=1.2)
        # fala 2: forças
        self.fala(2)
        fa = MathTex(r"1{,}2 \cdot 12^2 = 172{,}8", font_size=50, color=VERMELHO)
        fb = MathTex(r"1{,}8 \cdot 6^2 = 64{,}8", font_size=50, color=AZUL)
        forcas = VGroup(fa, fb).arrange(RIGHT, buff=1.4).to_edge(DOWN, buff=1.3)
        self.play(Write(fa), run_time=1.0)
        self.ate(self.ini[2] + self.dur[2] * 0.55)
        self.play(Write(fb), run_time=1.0)
        maior = MathTex(">", font_size=60).move_to(forcas)
        self.play(FadeIn(maior), run_time=0.4)
        vence = txt("vence o atacante", 34, VERMELHO, weight=BOLD).next_to(forcas, DOWN, buff=0.3)
        self.play(FadeIn(vence), run_time=0.5)
        # fala 3: sobreviventes e o limite T
        self.fala(3)
        self.play(FadeOut(VGroup(ea, eb, mont, vence)), run_time=0.5)
        sob = MathTex(r"\sqrt{\frac{172{,}8 - 64{,}8}{1{,}2}} \approx 9{,}5", font_size=60, color=AMBAR).next_to(moral, DOWN, buff=0.6)
        self.play(Write(sob), run_time=1.6)
        self.ate(self.ini[3] + self.dur[3] * 0.5)
        tmax = VGroup(txt("duração máxima T = 0,9", 32, PAPEL, weight=BOLD),
                      txt("ninguém zerou? batalha indecisa: o atacante recua", 28, PAPEL_2, font=MAQ)).arrange(DOWN, buff=0.15)
        tmax.move_to(forcas).shift(DOWN * 0.2)
        self.play(FadeOut(VGroup(forcas, maior)), FadeIn(tmax), run_time=0.8)
        self.encerrar()


class Ordens(Ritmo, Scene):
    CENA = "ordens"

    def construct(self):
        self.preparar()
        self.fala(0)
        custos = VGroup(
            VGroup(txt("por terra", 32, PAPEL), txt("1 COM / batalhão", 34, AMBAR, weight=BOLD)).arrange(DOWN, buff=0.15),
            VGroup(txt("pelo mar", 32, AZUL), txt("2 COM / batalhão", 34, AMBAR, weight=BOLD)).arrange(DOWN, buff=0.15),
        ).arrange(RIGHT, buff=2.0).to_edge(UP, buff=0.9)
        self.play(FadeIn(custos[0]), run_time=0.6)
        self.ate(self.ini[0] + self.dur[0] * 0.2)
        self.play(FadeIn(custos[1]), run_time=0.6)
        vazio = txt("território vazio: tomado sem luta", 32, PAPEL).shift(DOWN * 0.3)
        soma = txt("ataques ao mesmo alvo se somam", 32, PAPEL).next_to(vazio, DOWN, buff=0.4)
        self.ate(self.ini[0] + self.dur[0] * 0.45)
        self.play(FadeIn(vazio, shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[0] + self.dur[0] * 0.7)
        self.play(FadeIn(soma, shift=UP * 0.2), run_time=0.6)
        self.fala(1)
        self.play(FadeOut(VGroup(custos, vazio, soma)), run_time=0.5)
        relogio = Circle(radius=1.4, color=PAPEL, stroke_width=6).shift(LEFT * 3)
        metade = Sector(radius=1.4, angle=-PI, start_angle=PI / 2, color=AMBAR, fill_opacity=0.5).move_arc_center_to(relogio.get_center())
        tg = VGroup(txt("⚡ TELEGRAMA-RELÂMPAGO", 34, AMBAR, weight=BOLD), txt("as ordens do inimigo, cifradas", 28, PAPEL, font=MAQ),
                    txt("Inteligência decifra · Operações reage", 28, PAPEL_2)).arrange(DOWN, aligned_edge=LEFT, buff=0.2).shift(RIGHT * 2.2)
        self.play(Create(relogio), FadeIn(metade), run_time=0.8)
        self.play(FadeIn(tg[0], scale=1.2), run_time=0.5)
        self.ate(self.ini[1] + self.dur[1] * 0.4)
        self.play(FadeIn(tg[1]), run_time=0.5)
        self.ate(self.ini[1] + self.dur[1] * 0.65)
        self.play(FadeIn(tg[2]), run_time=0.5)
        self.encerrar()


class Fim(Ritmo, Scene):
    CENA = "fim"

    def construct(self):
        self.preparar()
        self.fala(0)
        a = VGroup(txt("contagem → matriz P", 36, AZUL, weight=BOLD), txt("quando atacar", 28, PAPEL, font=MAQ)).arrange(DOWN, buff=0.15)
        b = VGroup(MathTex(r"\alpha A^2 - \beta B^2", font_size=50, color=VERMELHO), txt("com quanto", 28, PAPEL, font=MAQ)).arrange(DOWN, buff=0.15)
        g = VGroup(a, b).arrange(RIGHT, buff=2.0)
        self.play(FadeIn(a, shift=UP * 0.2), run_time=0.7)
        self.ate(self.ini[0] + self.dur[0] * 0.35)
        self.play(FadeIn(b, shift=UP * 0.2), run_time=0.7)
        self.fala(1)
        self.play(FadeOut(g), run_time=0.5)
        bs = txt("Boa sorte, comandante.", 72, AMBAR, font=SERIF, slant=ITALIC)
        self.play(Write(bs), run_time=1.2)
        self.encerrar()


class Creditos(Scene):
    def construct(self):
        a = txt("ESTADO-MAIOR", 54, PAPEL, weight=BOLD)
        b = txt("A Guerra do Continente de Lebesgue", 34, LATAO, font=SERIF, slant=ITALIC)
        c = txt("Outras instruções: Intendência · Inteligência · Governo", 24, CINZA)
        g = VGroup(a, b, c).arrange(DOWN, buff=0.4)
        self.play(FadeIn(g, shift=UP * 0.2), run_time=1.0)
        self.wait(2.2)
        self.play(FadeOut(g), run_time=0.8)
