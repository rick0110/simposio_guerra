"""Animações (Manim) da aula "Inteligência · Cifra de Hill e mínimos quadrados".

Renderizar (a partir da raiz do repositório):
    AULA_VOZ=<voz> manim -r 1920,1080 --frame_rate 30 tools/aulas/inteligencia_hill_mmq/cenas.py <Classe>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import *  # noqa: E402,F401,F403

ALFA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
CLARO = "URGENTE ATACA K7"
CIFRADO = "8LBDXLHBVWKO64K3"
FITA = "#efe3a6"            # papel de telegrama
ROXO = "#9b6fd0"
EST = [(100, 100), (700, 150), (300, 650)]
DIST = [394.1, 332.9, 341.8]
DEP = (420, 330)


def simb(c):
    return "␣" if c == " " else c


def tira(texto, cor=TINTA, fundo=FITA, tam=40):
    """Uma tira de telegrama com um símbolo por casa."""
    casas = VGroup()
    for c in texto:
        q = Rectangle(width=0.62, height=0.8, stroke_width=1.2, stroke_color="#b9a77e", fill_color=fundo, fill_opacity=1)
        casas.add(VGroup(q, txt(simb(c), tam, cor, font=MONO, weight=BOLD).move_to(q)))
    return casas.arrange(RIGHT, buff=0)


# =================================================================== CENAS
class Titulo(Scene):
    def construct(self):
        serie = txt("ESTADO-MAIOR · INSTRUÇÃO DA INTELIGÊNCIA", 26, LATAO, weight=BOLD)
        t1 = txt("Ler o inimigo. Achar o depósito.", 64, PAPEL, font=SERIF, weight=BOLD)
        t2 = txt("Cifra de Hill e mínimos quadrados", 42, AMBAR, font=SERIF, slant=ITALIC)
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
        self.fala(0)
        t = tira(CIFRADO).scale(0.95)
        ruido = VGroup(*[Line([x, -0.25, 0], [x, 0.25 * np.sin(5 * x), 0], color=VERDE, stroke_width=2) for x in np.linspace(-6.5, 6.5, 120)]).shift(DOWN * 2.2)
        self.play(Create(ruido), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(c, shift=DOWN * 0.3) for c in t], lag_ratio=0.08), run_time=2.0)
        self.fala(1)
        self.play(t.animate.scale(0.7).to_edge(UP, buff=0.6), FadeOut(ruido), run_time=0.7)
        m1 = VGroup(txt("1. ler o que o inimigo escreve", 38, PAPEL), txt("→ matrizes (cifra de Hill)", 32, AMBAR)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        m2 = VGroup(txt("2. achar o depósito de suprimentos", 38, PAPEL), txt("→ mínimos quadrados", 32, AMBAR)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        g = VGroup(m1, m2).arrange(DOWN, aligned_edge=LEFT, buff=0.7).shift(DOWN * 0.4)
        self.play(FadeIn(m1[0], shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[1] + self.dur[1] * 0.25)
        self.play(FadeIn(m2[0], shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[1] + self.dur[1] * 0.6)
        self.play(FadeIn(m1[1]), run_time=0.5)
        self.ate(self.ini[1] + self.dur[1] * 0.8)
        self.play(FadeIn(m2[1]), run_time=0.5)
        self.encerrar()


class HillIdeia(Ritmo, Scene):
    CENA = "hill_ideia"

    def construct(self):
        self.preparar()
        # fala 0: o alfabeto de 37 símbolos
        self.fala(0)
        linhas = VGroup()
        for ini_, fim_ in ((0, 13), (13, 26), (26, 37)):
            linha = VGroup()
            for k in range(ini_, fim_):
                c = VGroup(txt(simb(ALFA[k]), 30, PAPEL, font=MONO, weight=BOLD), txt(str(k), 22, AMBAR, font=MONO)).arrange(DOWN, buff=0.08)
                linha.add(c)
            linhas.add(linha.arrange(RIGHT, buff=0.32))
        linhas.arrange(DOWN, aligned_edge=LEFT, buff=0.35).shift(UP * 0.4)
        for k, ln in enumerate(linhas):
            self.ate(self.ini[0] + self.dur[0] * (0.08 + 0.25 * k))
            self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.15) for c in ln], lag_ratio=0.05), run_time=1.0)
        n37 = txt("37 símbolos", 40, AMBAR, weight=BOLD).to_edge(DOWN, buff=0.6)
        self.ate(self.ini[0] + self.dur[0] * 0.85)
        self.play(FadeIn(n37), run_time=0.5)
        # fala 1: pares viram vetores; c = K·p
        self.fala(1)
        self.play(FadeOut(VGroup(linhas, n37)), run_time=0.5)
        par = tira("UR").move_to([-4.5, 1.6, 0])
        vec = MathTex(r"p = \begin{bmatrix} 20 \\ 17 \end{bmatrix}", font_size=54).next_to(par, DOWN, buff=0.5)
        self.play(FadeIn(par), run_time=0.5)
        self.play(Write(vec), run_time=0.9)
        eq = MathTex(r"c", r"=", r"K", r"\,p", font_size=80).move_to([1.6, 1.0, 0])
        eq[2].set_color(AMBAR)
        rk = txt("K: a chave, matriz 2 × 2", 30, AMBAR).next_to(eq, DOWN, buff=0.4)
        self.ate(self.ini[1] + self.dur[1] * 0.5)
        self.play(Write(eq), FadeIn(rk), run_time=1.2)
        # fala 2: módulo 37 — o relógio
        self.fala(2)
        self.play(FadeOut(VGroup(par, vec, rk)), eq.animate.scale(0.7).to_corner(UL, buff=0.6), run_time=0.6)
        rel = Circle(radius=2.2, color=PAPEL, stroke_width=4).shift(DOWN * 0.3)
        marcas = VGroup()
        for k in range(37):
            ang = PI / 2 - TAU * k / 37
            pt = rel.get_center() + 2.2 * np.array([np.cos(ang), np.sin(ang), 0])
            marcas.add(Dot(pt, radius=0.04, color=PAPEL))
            if k % 6 == 0 or k == 36:
                marcas.add(txt(str(k), 22, AMBAR, font=MONO).move_to(rel.get_center() + 2.65 * np.array([np.cos(ang), np.sin(ang), 0])))
        self.play(Create(rel), FadeIn(marcas), run_time=1.2)
        pont = Arrow(rel.get_center(), rel.get_center() + UP * 1.9, buff=0, color=VERMELHO, stroke_width=6)
        self.add(pont)
        self.ate(self.ini[2] + self.dur[2] * 0.4)
        self.play(Rotate(pont, angle=-TAU * 40 / 37, about_point=rel.get_center()), run_time=2.0)
        conta = MathTex(r"40 \equiv 3 \pmod{37}", font_size=50, color=AMBAR).to_edge(RIGHT, buff=0.7).shift(UP * 0.4)
        resto = txt("só o resto da divisão por 37", 26, PAPEL, font=MAQ).next_to(conta, DOWN, buff=0.3)
        self.play(Write(conta), FadeIn(resto), run_time=1.0)
        # fala 3: com a chave, a inversa; o problema é achar K
        self.fala(3)
        self.play(FadeOut(VGroup(rel, marcas, pont, conta, resto)), run_time=0.5)
        dec = MathTex(r"p = K^{-1}\,c \pmod{37}", font_size=64).shift(UP * 0.3)
        self.play(Write(dec), run_time=1.2)
        self.ate(self.ini[3] + self.dur[3] * 0.65)
        q = txt("mas quanto vale K?", 44, VERMELHO, font=SERIF, weight=BOLD).next_to(dec, DOWN, buff=0.7)
        self.play(FadeIn(q, scale=1.2), run_time=0.6)
        self.encerrar()


class HillChave(Ritmo, Scene):
    CENA = "hill_chave"

    def construct(self):
        self.preparar()
        # fala 0: a pedra de Roseta
        self.fala(0)
        cif = tira(CIFRADO).scale(0.82).to_edge(UP, buff=1.0)
        cla = tira("URGENTE ", fundo=PAPEL).scale(0.82).next_to(cif, DOWN, buff=0.15).align_to(cif, LEFT)
        rc = txt("cifrado", 24, PAPEL_2, font=MAQ).next_to(cif, LEFT, buff=0.3)
        rl = txt("claro", 24, PAPEL_2, font=MAQ).next_to(cla, LEFT, buff=0.3)
        self.play(FadeIn(cif), FadeIn(rc), run_time=0.8)
        self.ate(self.ini[0] + self.dur[0] * 0.3)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.2) for c in cla], lag_ratio=0.1), FadeIn(rl), run_time=1.4)
        pedra = txt("pedra de Roseta", 36, AMBAR, font=SERIF, slant=ITALIC).next_to(cla, DOWN, buff=0.6)
        self.ate(self.ini[0] + self.dur[0] * 0.78)
        self.play(FadeIn(pedra), run_time=0.6)
        # fala 1: P e C; K = C·P⁻¹
        self.fala(1)
        b1 = SurroundingRectangle(VGroup(cla[0], cla[1]), color=VERDE, buff=0.04, stroke_width=4)
        b2 = SurroundingRectangle(VGroup(cla[2], cla[3]), color=VERDE, buff=0.04, stroke_width=4)
        c1 = SurroundingRectangle(VGroup(cif[0], cif[1]), color=VERMELHO, buff=0.04, stroke_width=4)
        c2 = SurroundingRectangle(VGroup(cif[2], cif[3]), color=VERMELHO, buff=0.04, stroke_width=4)
        self.play(FadeOut(pedra), Create(b1), Create(b2), run_time=0.6)
        Pm = MathTex(r"P = \begin{bmatrix} 20 & 6 \\ 17 & 4 \end{bmatrix}", font_size=52, color=VERDE).move_to([-3.6, -1.4, 0])
        self.play(Write(Pm), run_time=1.0)
        self.ate(self.ini[1] + self.dur[1] * 0.4)
        self.play(Create(c1), Create(c2), run_time=0.5)
        Cm = MathTex(r"C = \begin{bmatrix} 34 & 1 \\ 11 & 3 \end{bmatrix}", font_size=52, color=VERMELHO).move_to([0.4, -1.4, 0])
        self.play(Write(Cm), run_time=1.0)
        self.ate(self.ini[1] + self.dur[1] * 0.72)
        Kf = MathTex(r"C = K\,P", r"\ \Rightarrow\ ", r"K = C\,P^{-1}", font_size=50).move_to([4.6, -1.4, 0])
        Kf[2].set_color(AMBAR)
        self.play(Write(Kf), run_time=1.2)
        # fala 2: inverter P módulo 37
        self.fala(2)
        self.play(FadeOut(VGroup(cif, cla, rc, rl, b1, b2, c1, c2, Cm, Kf)), Pm.animate.to_corner(UL, buff=0.7), run_time=0.7)
        d1 = MathTex(r"\det P = 20\cdot 4 - 6\cdot 17 = -22", r"\equiv 15", font_size=50).shift(UP * 1.2)
        d1[1].set_color(AMBAR)
        self.play(Write(d1), run_time=1.4)
        self.ate(self.ini[2] + self.dur[2] * 0.48)
        d2 = MathTex(r"15^{-1} = 5", r"\quad\text{pois}\quad", r"15 \cdot 5 = 75 = 2\cdot 37 + 1", font_size=48).next_to(d1, DOWN, buff=0.5)
        d2[0].set_color(AMBAR)
        self.play(Write(d2), run_time=1.6)
        # fala 3: a chave
        self.fala(3)
        pinv = MathTex(r"P^{-1} \equiv 5\begin{bmatrix} 4 & -6 \\ -17 & 20 \end{bmatrix} \equiv \begin{bmatrix} 20 & 7 \\ 26 & 26 \end{bmatrix}", font_size=46).next_to(d2, DOWN, buff=0.5)
        self.play(Write(pinv), run_time=1.4)
        K = MathTex(r"K = C\,P^{-1} \equiv \begin{bmatrix} 3 & 5 \\ 2 & 7 \end{bmatrix}", font_size=60, color=AMBAR).to_edge(DOWN, buff=0.4)
        cx = SurroundingRectangle(K, color=AMBAR, buff=0.18)
        self.play(FadeOut(VGroup(d1, d2)), pinv.animate.shift(UP * 2.0), run_time=0.5)
        self.play(Write(K), run_time=1.2)
        self.play(Create(cx), run_time=0.4)
        self.encerrar()


class HillDecifrar(Ritmo, Scene):
    CENA = "hill_decifrar"

    def construct(self):
        self.preparar()
        self.fala(0)
        cif = tira(CIFRADO).scale(0.9).shift(UP * 1.4)
        self.play(FadeIn(cif), run_time=0.6)
        cla = tira(CLARO, fundo=PAPEL).scale(0.9).shift(DOWN * 0.2)
        chave = MathTex(r"K^{-1}", font_size=50, color=AMBAR).next_to(VGroup(cif, cla), LEFT, buff=0.4)
        self.play(FadeIn(chave), run_time=0.4)
        self.play(LaggedStart(*[TransformFromCopy(cif[k], cla[k]) for k in range(len(CLARO))], lag_ratio=0.08), run_time=2.4)
        alvo = SurroundingRectangle(VGroup(*cla[8:]), color=VERMELHO, buff=0.05, stroke_width=4)
        self.play(Create(alvo), run_time=0.5)
        rev = txt("tropas · estoques · moral — de verdade", 30, PAPEL, font=MAQ).to_edge(DOWN, buff=1.4)
        self.ate(self.ini[0] + self.dur[0] * 0.7)
        self.play(FadeIn(rev), run_time=0.6)
        self.fala(1)
        self.play(FadeOut(VGroup(cif, cla, chave, alvo, rev)), run_time=0.5)
        turnos = VGroup(*[VGroup(Rectangle(width=1.2, height=0.7, color=LATAO, stroke_width=2), txt(f"turno {k}", 22, PAPEL)) for k in range(1, 9)]).arrange(RIGHT, buff=0.12)
        for q in turnos:
            q[1].move_to(q[0])
        turnos.shift(UP * 0.8)
        self.play(FadeIn(turnos), run_time=0.6)
        chaves = VGroup(*[Brace(VGroup(turnos[2 * k], turnos[2 * k + 1]), DOWN, color=AMBAR) for k in range(4)])
        rots = VGroup(*[txt(f"chave {k + 1}", 22, AMBAR).next_to(chaves[k], DOWN, buff=0.1) for k in range(4)])
        self.play(LaggedStart(*[GrowFromCenter(c) for c in chaves], lag_ratio=0.2), FadeIn(rots), run_time=1.2)
        self.ate(self.ini[1] + self.dur[1] * 0.45)
        rel = txt("⚡ o relâmpago usa a mesma chave", 34, AMBAR, weight=BOLD).to_edge(DOWN, buff=1.0)
        self.play(FadeIn(rel, scale=1.2), run_time=0.6)
        self.encerrar()


class Deposito(Ritmo, Scene):
    CENA = "deposito"

    def construct(self):
        self.preparar()
        esc = 0.0085

        def p(x, y):
            return np.array([(x - 400) * esc, -(y - 380) * esc, 0]) + LEFT * 2.6

        quad = NumberPlane(x_range=[0, 800, 50], y_range=[0, 760, 50], x_length=800 * esc, y_length=760 * esc,
                           background_line_style={"stroke_color": "#3a4436", "stroke_width": 1}, axis_config={"stroke_opacity": 0}).move_to(p(400, 380))
        # fala 0: estações e círculos
        self.fala(0)
        self.play(FadeIn(quad), run_time=0.8)
        ests = VGroup()
        for k, (x, y) in enumerate(EST):
            e = VGroup(Triangle(color=AZUL, fill_opacity=1).scale(0.14), txt(f"E{k + 1}", 22, AZUL, weight=BOLD)).arrange(DOWN, buff=0.05).move_to(p(x, y))
            ests.add(e)
        self.play(LaggedStart(*[GrowFromCenter(e) for e in ests], lag_ratio=0.2), run_time=1.0)
        circ = VGroup(*[Circle(radius=DIST[k] * esc, color=AZUL, stroke_width=2.5).move_to(p(*EST[k])) for k in range(3)])
        self.ate(self.ini[0] + self.dur[0] * 0.5)
        self.play(LaggedStart(*[Create(c) for c in circ], lag_ratio=0.3), run_time=2.0)
        eqc = MathTex(r"(x - x_i)^2 + (y - y_i)^2 = r_i^2", font_size=40).to_edge(RIGHT, buff=0.4).shift(UP * 2.4)
        self.play(Write(eqc), run_time=1.0)
        # fala 1: subtrair a primeira equação -> sistema linear
        self.fala(1)
        menos = MathTex(r"\text{equação } i \;-\; \text{equação } 1", font_size=38, color=AMBAR).next_to(eqc, DOWN, buff=0.5)
        self.play(FadeIn(menos), run_time=0.6)
        lin = MathTex(r"2(x_i - x_1)\,x + 2(y_i - y_1)\,y = b_i", font_size=38).next_to(menos, DOWN, buff=0.4)
        self.ate(self.ini[1] + self.dur[1] * 0.55)
        self.play(Write(lin), run_time=1.4)
        rl = txt("linear!", 32, VERDE, weight=BOLD).next_to(lin, DOWN, buff=0.25)
        self.play(FadeIn(rl), run_time=0.4)
        # fala 2: três estações -> solução exata (420; 330)
        self.fala(2)
        sis = MathTex(r"1200\,x + 100\,y &= 536\,992{,}4 \\ 400\,x + 1100\,y &= 530\,987{,}6", font_size=38)
        sis.next_to(rl, DOWN, buff=0.4).align_to(lin, LEFT)
        self.play(Write(sis), run_time=1.4)
        alvo = Star(5, outer_radius=0.2, color=VERMELHO, fill_opacity=1).move_to(p(*DEP))
        sol = MathTex(r"(x;\,y) = (420;\,330)", font_size=44, color=VERMELHO).next_to(sis, DOWN, buff=0.4)
        self.ate(self.ini[2] + self.dur[2] * 0.55)
        self.play(SpinInFromNothing(alvo), Write(sol), run_time=1.0)
        # fala 3: quatro estações, ruído -> mínimos quadrados
        self.fala(3)
        e4 = VGroup(Triangle(color=ROXO, fill_opacity=1).scale(0.14), txt("E4", 22, ROXO, weight=BOLD)).arrange(DOWN, buff=0.05).move_to(p(720, 640))
        r4 = float(np.hypot(720 - DEP[0], 640 - DEP[1])) + 22
        c4 = Circle(radius=r4 * esc, color=ROXO, stroke_width=2.5).move_to(p(720, 640))
        self.play(GrowFromCenter(e4), Create(c4), run_time=1.0)
        zona = Circle(radius=0.22, color=AMBAR, stroke_width=3).move_to(p(*DEP))
        self.play(Create(zona), run_time=0.5)
        self.play(FadeOut(VGroup(menos, lin, rl, sis, sol)), run_time=0.5)
        mais = txt("3 equações, 2 incógnitas: sem solução exata", 28, PAPEL).next_to(eqc, DOWN, buff=0.6)
        self.play(FadeIn(mais), run_time=0.5)
        self.ate(self.ini[3] + self.dur[3] * 0.6)
        normal = MathTex(r"A^{T}A\,p = A^{T}b", font_size=60, color=AMBAR).next_to(mais, DOWN, buff=0.6)
        rn = txt("equações normais", 28, AMBAR, font=SERIF, slant=ITALIC).next_to(normal, DOWN, buff=0.2)
        self.play(Write(normal), FadeIn(rn), run_time=1.2)
        self.encerrar()


class Recompensa(Ritmo, Scene):
    CENA = "recompensa"

    def construct(self):
        self.preparar()
        self.fala(0)
        col = "ABCDEFGHIJKL"
        grade = VGroup()
        for i in range(8):
            for j in range(12):
                grade.add(Square(0.5, stroke_width=1, color="#4a5546").move_to([(j - 5.5) * 0.5 - 2.0, (3.5 - i) * 0.5, 0]))
        letras = VGroup(*[txt(col[j], 22, PAPEL_2, font=MONO).move_to([(j - 5.5) * 0.5 - 2.0, 2.25, 0]) for j in range(12)])
        nums = VGroup(*[txt(str(i + 1), 22, PAPEL_2, font=MONO).move_to([-5.25, (3.5 - i) * 0.5, 0]) for i in range(8)])
        self.play(FadeIn(grade), FadeIn(letras), FadeIn(nums), run_time=1.0)
        alvo = grade[6 * 12 + 8].copy().set_fill(VERMELHO, 0.8).set_stroke(VERMELHO, 3)
        self.ate(self.ini[0] + self.dur[0] * 0.4)
        regra = VGroup(txt("coluna = x ÷ 50 → 420 ÷ 50 = 8 → I", 28, PAPEL, font=MONO),
                       txt("linha = y ÷ 50 + 1 → 330 ÷ 50 + 1 = 7", 28, PAPEL, font=MONO)).arrange(DOWN, aligned_edge=LEFT, buff=0.2).to_edge(RIGHT, buff=0.4).shift(UP * 1.0)
        self.play(FadeIn(regra), run_time=0.8)
        self.play(FadeIn(alvo), run_time=0.5)
        i7 = txt("I7", 60, VERMELHO, weight=BOLD).next_to(regra, DOWN, buff=0.5)
        self.play(FadeIn(i7, scale=1.4), run_time=0.5)
        self.fala(1)
        self.play(FadeOut(VGroup(grade, letras, nums, alvo, regra, i7)), run_time=0.5)
        itens = VGroup(txt("✓ tropas exatas do território", 36, PAPEL),
                       txt("✓ bombardeio liberado (4 COM)", 36, PAPEL),
                       txt("inimigo perde ¼ do maior estoque", 32, VERMELHO, weight=BOLD),
                       txt("e a economia dele piora", 32, VERMELHO)).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        for k, it in enumerate(itens):
            self.ate(self.ini[1] + self.dur[1] * (0.05 + 0.2 * k))
            self.play(FadeIn(it, shift=RIGHT * 0.2), run_time=0.5)
        self.encerrar()


class Fim(Ritmo, Scene):
    CENA = "fim"

    def construct(self):
        self.preparar()
        self.fala(0)
        tres = VGroup(MathTex(r"c = K\,p", font_size=54), MathTex(r"p = K^{-1}c", font_size=54, color=AMBAR),
                      MathTex(r"A^{T}A\,p = A^{T}b", font_size=54, color=AZUL)).arrange(RIGHT, buff=1.2)
        for k, t in enumerate(tres):
            self.ate(self.ini[0] + self.dur[0] * (0.05 + 0.25 * k))
            self.play(FadeIn(t, shift=UP * 0.2), run_time=0.6)
        self.fala(1)
        self.play(FadeOut(tres), run_time=0.5)
        bs = txt("Boa sorte, agente.", 72, AMBAR, font=SERIF, slant=ITALIC)
        self.play(Write(bs), run_time=1.2)
        self.encerrar()


class Creditos(Scene):
    def construct(self):
        a = txt("ESTADO-MAIOR", 54, PAPEL, weight=BOLD)
        b = txt("A Guerra do Continente de Lebesgue", 34, LATAO, font=SERIF, slant=ITALIC)
        c = txt("Outras instruções: Intendência · Operações · Governo", 24, CINZA)
        g = VGroup(a, b, c).arrange(DOWN, buff=0.4)
        self.play(FadeIn(g, shift=UP * 0.2), run_time=1.0)
        self.wait(2.2)
        self.play(FadeOut(g), run_time=0.8)
