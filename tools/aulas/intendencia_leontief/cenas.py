"""Animações (Manim) da aula "Intendência · O modelo de Leontief".

Renderizar (a partir da raiz do repositório):
    AULA_VOZ=<voz> manim -r 1920,1080 --frame_rate 30 tools/aulas/intendencia_leontief/cenas.py <Classe>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import *  # noqa: E402,F401,F403

SETORES = ["ALI", "ACO", "COM"]
NOMES = {"ALI": "Alimento", "ACO": "Aço", "COM": "Combustível"}
COR_S = {"ALI": VERDE, "ACO": AZUL, "COM": AMBAR}
Z = [[3, 4, 0], [6, 2, 1], [3, 0, 2]]
X = [30, 20, 10]
A = [[Z[i][j] / X[j] for j in range(3)] for i in range(3)]
D_ = [23, 11, 5]
AX = [X[i] - D_[i] for i in range(3)]          # 7, 9, 5: o que os setores consomem como insumo


def br(v):
    """Número com vírgula decimal e sem zeros inúteis (0.2 -> 0,2)."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def tabela(valores, linhas, colunas, papel=True, tam=34):
    """Tabela num papel: devolve (grupo, células[i][j], rótulos de linha, rótulos de coluna, fundo)."""
    cor_txt = TINTA if papel else PAPEL
    dx, dy = 1.55, 0.78
    cel = [[txt(str(v), tam, cor_txt, font=MONO) for v in linha] for linha in valores]
    for i, linha in enumerate(cel):
        for j, c in enumerate(linha):
            c.move_to([j * dx, -i * dy, 0])
    rl = [txt(r, tam - 4, COR_S.get(r, cor_txt) if not papel else cor_txt, weight=BOLD).move_to([-1.5, -i * dy, 0])
          for i, r in enumerate(linhas)]
    rc = [txt(c, tam - 4, cor_txt, weight=BOLD).move_to([j * dx, dy, 0]) for j, c in enumerate(colunas)]
    g = VGroup(*[c for linha in cel for c in linha], *rl, *rc)
    fundo = RoundedRectangle(width=g.width + 1.2, height=g.height + 1.0, corner_radius=0.08, stroke_width=0,
                             fill_color=PAPEL if papel else "#232b24", fill_opacity=1).move_to(g)
    return VGroup(fundo, g), cel, rl, rc, fundo


def setor_no(s, raio=0.85):
    c = Circle(radius=raio, color=COR_S[s], stroke_width=5, fill_color=FUNDO, fill_opacity=1)
    return VGroup(c, txt(NOMES[s], 28, COR_S[s], weight=BOLD).move_to(c))


# =================================================================== CENAS
class Titulo(Scene):
    def construct(self):
        serie = txt("ESTADO-MAIOR · INSTRUÇÃO DA INTENDÊNCIA", 26, LATAO, weight=BOLD)
        t1 = txt("Quanto produzir?", 76, PAPEL, font=SERIF, weight=BOLD)
        t2 = txt("O modelo de Leontief", 44, AMBAR, font=SERIF, slant=ITALIC)
        g = VGroup(serie, t1, t2).arrange(DOWN, buff=0.45)
        linha = Line(LEFT * 3.2, RIGHT * 3.2, color=LATAO, stroke_width=2).next_to(t1, DOWN, buff=0.22)
        self.play(FadeIn(serie, shift=DOWN * 0.2), run_time=0.7)
        self.play(Write(t1), run_time=1.3)
        self.play(Create(linha), FadeIn(t2, shift=UP * 0.2), run_time=0.8)
        self.wait(1.1)
        self.play(FadeOut(VGroup(serie, t1, t2, linha)), run_time=0.6)


class Abertura(Ritmo, Scene):
    CENA = "abertura"

    def construct(self):
        self.preparar()
        # fala 0: o porão da Intendência
        self.fala(0)
        grupo, polys, dono, p = mapa(4, opacidade=lambda f: 0.4)
        self.play(FadeIn(grupo), run_time=1.4)
        neve = VGroup(*[Dot(radius=0.03, color=PAPEL).move_to([x, y, 0])
                        for x, y in np.random.default_rng(3).uniform([-7, -4], [7, 4], (90, 2))])
        self.play(FadeIn(neve, lag_ratio=0.02), run_time=1.2)
        q = txt("Quanto produzir?", 64, PAPEL, font=SERIF, weight=BOLD)
        self.play(grupo.animate.set_opacity(0.12), FadeOut(neve), FadeIn(q, scale=1.1), run_time=1.0)
        # fala 1: três setores que dependem uns dos outros
        self.fala(1)
        self.play(q.animate.scale(0.6).to_edge(UP, buff=0.4), run_time=0.7)
        pos = {"ALI": [0, 0.9, 0], "ACO": [-3.3, -2.2, 0], "COM": [3.3, -2.2, 0]}
        nos = {s: setor_no(s).move_to(pos[s]) for s in SETORES}
        self.play(LaggedStart(*[GrowFromCenter(nos[s]) for s in SETORES], lag_ratio=0.3), run_time=1.4)

        def fluxo(de, para, rotulo, curv=0.35):
            a = CurvedArrow(nos[de].get_center(), nos[para].get_center(), angle=curv, color=COR_S[de], stroke_width=5)
            a.scale(0.62, about_point=a.get_center())
            r = txt(rotulo, 24, COR_S[de], font=MAQ).move_to(a.point_from_proportion(0.5))
            r.shift(normalize(r.get_center() - ORIGIN + np.array([0, 0.6, 0])) * 0.45)
            return VGroup(a, r)

        f1 = fluxo("ACO", "ALI", "trator")
        f2 = fluxo("COM", "ALI", "diesel", -0.35)
        f3 = fluxo("ALI", "COM", "comida dos operários", 0.35)
        marcas = [0.32, 0.55, 0.78]
        for f, m in zip((f1, f2, f3), marcas):
            self.ate(self.ini[1] + self.dur[1] * m)
            self.play(Create(f[0]), FadeIn(f[1]), run_time=0.8)
        # fala 2: produzir para que sobre o que a tropa precisa
        self.fala(2)
        self.play(FadeOut(VGroup(f1, f2, f3, q, *nos.values())), run_time=0.6)
        total = Rectangle(width=9, height=0.9, color=PAPEL, fill_color=PAPEL_2, fill_opacity=0.25, stroke_width=2).shift(UP * 1.2)
        rt = txt("tudo o que a nação produz", 28, PAPEL).next_to(total, UP, buff=0.2)
        self.play(Create(total), FadeIn(rt), run_time=1.0)
        interno = Rectangle(width=4.6, height=0.9, stroke_width=0, fill_color=CINZA, fill_opacity=0.9).align_to(total, LEFT).align_to(total, UP)
        sobra = Rectangle(width=4.4, height=0.9, stroke_width=0, fill_color=AMBAR, fill_opacity=0.95).align_to(total, RIGHT).align_to(total, UP)
        ri = txt("consumido pelos próprios setores", 24, PAPEL).next_to(interno, DOWN, buff=0.3)
        rs = txt("o que sobra para a tropa", 24, AMBAR, weight=BOLD).next_to(sobra, DOWN, buff=0.3)
        self.ate(self.ini[2] + self.dur[2] * 0.35)
        self.play(FadeIn(interno), FadeIn(ri), run_time=0.9)
        self.ate(self.ini[2] + self.dur[2] * 0.7)
        self.play(FadeIn(sobra), FadeIn(rs), run_time=0.9)
        self.encerrar()


class Tabela(Ritmo, Scene):
    CENA = "tabela"

    def construct(self):
        self.preparar()
        vals = Z + [X]
        g, cel, rl, rc, fundo = tabela(vals, ["ALI", "ACO", "COM", "X"], ["ALI", "ACO", "COM"])
        g.shift(LEFT * 2.6 + DOWN * 0.2)
        tit = txt("TABELA DE TRANSAÇÕES · Z", 30, LATAO, weight=BOLD).next_to(g, UP, buff=0.35)
        sep = Line(fundo.get_left() + RIGHT * 0.3, fundo.get_right() + LEFT * 0.3, color=TINTA, stroke_width=2)
        sep.move_to([fundo.get_center()[0], (cel[2][0].get_y() + cel[3][0].get_y()) / 2, 0])
        dir_c = txt("consumido pelo setor →", 22, PAPEL_2, font=MAQ).next_to(fundo, UP, buff=0.12).align_to(fundo, RIGHT)
        dir_l = txt("produção do setor ↓", 22, PAPEL_2, font=MAQ).rotate(PI / 2).next_to(fundo, LEFT, buff=0.15)
        # fala 0: a tabela
        self.fala(0)
        self.play(FadeIn(fundo, shift=UP * 0.3), FadeIn(tit), run_time=0.9)
        self.play(LaggedStart(*[FadeIn(x) for x in [*rc, *rl[:3]]], lag_ratio=0.08), run_time=1.0)
        self.play(LaggedStart(*[FadeIn(c) for linha in cel[:3] for c in linha], lag_ratio=0.05), run_time=1.2)
        self.play(FadeIn(dir_c), FadeIn(dir_l), run_time=0.6)
        linha_ali = SurroundingRectangle(VGroup(rl[0], *cel[0]), color=VERDE, buff=0.12, stroke_width=4)
        self.play(Create(linha_ali), run_time=0.6)
        # fala 1: a célula (ALI, ACO) = 4
        self.fala(1)
        self.play(FadeOut(linha_ali), run_time=0.3)
        caixa = SurroundingRectangle(cel[0][1], color=VERMELHO, buff=0.14, stroke_width=5)
        self.play(Create(caixa), cel[0][1].animate.set_color(VERMELHO), run_time=0.7)
        nota = VGroup(txt("4 unidades de alimento", 32, VERDE, weight=BOLD),
                      txt("consumidas pelo setor de aço", 32, PAPEL),
                      txt("(a comida dos operários da siderúrgica)", 24, PAPEL_2, font=MAQ)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        nota.to_edge(RIGHT, buff=0.6).shift(UP * 0.8)
        seta = Arrow(nota.get_left() + LEFT * 0.1, caixa.get_right(), color=VERMELHO, buff=0.15)
        self.play(GrowArrow(seta), FadeIn(nota[0]), FadeIn(nota[1]), run_time=0.9)
        self.ate(self.ini[1] + self.dur[1] * 0.72)
        self.play(FadeIn(nota[2]), run_time=0.6)
        # fala 2: a linha X, produção total
        self.fala(2)
        self.play(FadeOut(VGroup(nota, seta)), FadeOut(caixa), cel[0][1].animate.set_color(TINTA), run_time=0.5)
        self.play(Create(sep), FadeIn(rl[3]), LaggedStart(*[FadeIn(c) for c in cel[3]], lag_ratio=0.2), run_time=1.0)
        cx = SurroundingRectangle(VGroup(rl[3], *cel[3]), color=AMBAR, buff=0.12, stroke_width=4)
        rx = txt("produção total de cada setor", 30, AMBAR, weight=BOLD).to_edge(RIGHT, buff=0.6).match_y(cx)
        self.play(Create(cx), FadeIn(rx, shift=LEFT * 0.2), run_time=0.8)
        self.encerrar()


class MatrizA(Ritmo, Scene):
    CENA = "matriz_a"

    def construct(self):
        self.preparar()
        g, cel, rl, rc, fundo = tabela(Z + [X], ["ALI", "ACO", "COM", "X"], ["ALI", "ACO", "COM"])
        g.shift(LEFT * 2.6 + DOWN * 0.2)
        tit = txt("TABELA DE TRANSAÇÕES · Z", 30, LATAO, weight=BOLD).next_to(g, UP, buff=0.35)
        # fala 0: a receita por unidade
        self.fala(0)
        self.play(FadeIn(g), FadeIn(tit), run_time=0.9)
        ideia = VGroup(txt("receita por unidade", 34, AMBAR, weight=BOLD),
                       txt("insumo gasto ÷ produção do setor", 28, PAPEL)).arrange(DOWN, buff=0.2).to_edge(RIGHT, buff=0.6)
        self.play(FadeIn(ideia, shift=LEFT * 0.2), run_time=0.8)
        # fala 1: divide cada coluna pelo seu X
        self.fala(1)
        self.play(FadeOut(ideia), run_time=0.4)
        marcas = [0.08, 0.3, 0.5]
        divs = VGroup()
        for j in range(3):
            self.ate(self.ini[1] + self.dur[1] * marcas[j])
            col = SurroundingRectangle(VGroup(*[cel[i][j] for i in range(4)]), color=COR_S[SETORES[j]], buff=0.12, stroke_width=4)
            dv = txt(f"÷ {X[j]}", 30, COR_S[SETORES[j]], weight=BOLD).next_to(fundo, DOWN, buff=0.2).match_x(cel[3][j])
            divs.add(dv)
            novos = [txt(br(A[i][j]), 34, TINTA, font=MONO).move_to(cel[i][j]) for i in range(3)]
            self.play(Create(col), FadeIn(dv), run_time=0.5)
            self.play(*[Transform(cel[i][j], novos[i]) for i in range(3)], run_time=0.8)
            self.play(FadeOut(col), run_time=0.3)
        tit2 = txt("MATRIZ TÉCNICA · A", 30, AMBAR, weight=BOLD).move_to(tit)
        self.play(FadeOut(VGroup(rl[3], *cel[3], divs)), Transform(tit, tit2), run_time=0.8)
        formula = MathTex(r"A = Z\,\mathrm{diag}(X)^{-1}", font_size=52).to_edge(RIGHT, buff=0.7).shift(UP * 0.6)
        self.play(Write(formula), run_time=1.2)
        # fala 2: como ler 0,2
        self.fala(2)
        caixa = SurroundingRectangle(cel[0][1], color=VERMELHO, buff=0.14, stroke_width=5)
        nota = VGroup(txt("cada 1 de aço", 32, AZUL, weight=BOLD), txt("consome 0,2 de alimento", 32, VERDE, weight=BOLD)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        nota.next_to(formula, DOWN, buff=0.8).align_to(formula, LEFT)
        self.play(Create(caixa), cel[0][1].animate.set_color(VERMELHO), run_time=0.6)
        self.play(FadeIn(nota, shift=UP * 0.2), run_time=0.8)
        self.encerrar()


class Equacao(Ritmo, Scene):
    CENA = "equacao"

    def construct(self):
        self.preparar()
        u = 0.13                                   # altura por unidade
        base_y = -3.0
        xs = [-4.6, -2.6, -0.6]
        barras, insumos, entregas, rot = VGroup(), VGroup(), VGroup(), VGroup()
        for k, s in enumerate(SETORES):
            b = Rectangle(width=1.3, height=X[k] * u, stroke_color=COR_S[s], stroke_width=3, fill_opacity=0)
            b.move_to([xs[k], base_y + X[k] * u / 2, 0])
            ins = Rectangle(width=1.3, height=AX[k] * u, stroke_width=0, fill_color=CINZA, fill_opacity=0.9)
            ins.move_to([xs[k], base_y + AX[k] * u / 2, 0])
            ent = Rectangle(width=1.3, height=D_[k] * u, stroke_width=0, fill_color=COR_S[s], fill_opacity=0.85)
            ent.move_to([xs[k], base_y + AX[k] * u + D_[k] * u / 2, 0])
            barras.add(b)
            insumos.add(ins)
            entregas.add(ent)
            rot.add(txt(s, 26, COR_S[s], weight=BOLD).next_to([xs[k], base_y, 0], DOWN, buff=0.2))
        # fala 0: x = produção bruta; uma parte é insumo (A·x)
        self.fala(0)
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.2), FadeIn(rot), run_time=1.4)
        lx = MathTex(r"x", r"\ \text{(produção bruta)}", font_size=44).to_corner(UR, buff=0.6)
        self.play(FadeIn(lx), run_time=0.6)
        self.ate(self.ini[0] + self.dur[0] * 0.55)
        self.play(LaggedStart(*[FadeIn(i) for i in insumos], lag_ratio=0.2), run_time=1.0)
        lax = MathTex(r"A\,x", r"\ \text{(insumos)}", font_size=44, color=CINZA).next_to(lx, DOWN, buff=0.3).align_to(lx, LEFT)
        self.play(FadeIn(lax), run_time=0.5)
        # fala 1: o que sobra é d; x − Ax = d
        self.fala(1)
        self.play(LaggedStart(*[FadeIn(e) for e in entregas], lag_ratio=0.2), run_time=1.0)
        ld = MathTex(r"d", r"\ \text{(entrega líquida)}", font_size=44, color=AMBAR).next_to(lax, DOWN, buff=0.3).align_to(lx, LEFT)
        self.play(FadeIn(ld), run_time=0.5)
        eq1 = MathTex(r"x", r"-", r"A\,x", r"=", r"d", font_size=72).move_to([3.6, -0.6, 0])
        eq1[2].set_color(CINZA)
        eq1[4].set_color(AMBAR)
        self.ate(self.ini[1] + self.dur[1] * 0.7)
        self.play(Write(eq1), run_time=1.2)
        # fala 2: (I − A)x = d — um sistema linear 3×3
        self.fala(2)
        eq2 = MathTex(r"(I - A)", r"\,x", r"=", r"d", font_size=80).move_to(eq1)
        eq2[3].set_color(AMBAR)
        self.play(TransformMatchingTex(eq1, eq2), run_time=1.4)
        sis = txt("3 equações · 3 incógnitas", 30, PAPEL_2, font=MAQ).next_to(eq2, DOWN, buff=0.4)
        self.ate(self.ini[2] + self.dur[2] * 0.6)
        self.play(FadeIn(sis), run_time=0.6)
        # fala 3: d é entrega, x é produção — a ordem pede x
        self.fala(3)
        self.play(FadeOut(VGroup(barras, insumos, entregas, rot, lx, lax, ld, sis)), eq2.animate.to_edge(UP, buff=0.8), run_time=0.8)
        c1 = VGroup(MathTex("d", font_size=90, color=AMBAR), txt("o que entregar", 32, PAPEL)).arrange(DOWN, buff=0.25)
        c2 = VGroup(MathTex("x", font_size=90, color=PAPEL), txt("o que produzir", 32, PAPEL)).arrange(DOWN, buff=0.25)
        cards = VGroup(c1, c2).arrange(RIGHT, buff=3.0).shift(DOWN * 0.3)
        neq = MathTex(r"\neq", font_size=90, color=VERMELHO).move_to(cards)
        self.play(FadeIn(c1, shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[3] + self.dur[3] * 0.4)
        self.play(FadeIn(neq), FadeIn(c2, shift=UP * 0.2), run_time=0.7)
        self.ate(self.ini[3] + self.dur[3] * 0.75)
        carimbo = txt("A ORDEM PEDE x", 54, VERMELHO, weight=BOLD)
        st = VGroup(carimbo, SurroundingRectangle(carimbo, color=VERMELHO, buff=0.2, stroke_width=6)).rotate(-5 * DEGREES).to_edge(DOWN, buff=0.6)
        self.play(FadeIn(st, scale=1.8), run_time=0.4, rate_func=rush_into)
        self.encerrar()


class Resolver(Ritmo, Scene):
    CENA = "resolver"

    def construct(self):
        self.preparar()
        # fala 0: a entrega exigida
        self.fala(0)
        d = MathTex(r"d = \begin{bmatrix} 23 \\ 11 \\ 5 \end{bmatrix}", font_size=56, color=AMBAR).to_corner(UL, buff=0.7)
        rotd = txt("exigido pelo Gabinete", 24, AMBAR, font=MAQ).next_to(d, DOWN, buff=0.2)
        self.play(Write(d), FadeIn(rotd), run_time=1.4)
        # fala 1: I − A e as três equações
        self.fala(1)
        ima = MathTex(r"I - A = \begin{bmatrix} 0{,}9 & -0{,}2 & 0 \\ -0{,}2 & 0{,}9 & -0{,}1 \\ -0{,}1 & 0 & 0{,}8 \end{bmatrix}",
                      font_size=50).to_edge(UP, buff=0.7).shift(RIGHT * 2.2)
        self.play(Write(ima), run_time=1.6)
        sis = MathTex(r"0{,}9\,x_1 - 0{,}2\,x_2 &= 23 \\ -0{,}2\,x_1 + 0{,}9\,x_2 - 0{,}1\,x_3 &= 11 \\ -0{,}1\,x_1 + 0{,}8\,x_3 &= 5",
                      font_size=48).shift(DOWN * 1.0 + RIGHT * 0.6)
        self.ate(self.ini[1] + self.dur[1] * 0.5)
        self.play(Write(sis), run_time=2.0)
        # fala 2: a solução
        self.fala(2)
        sol = MathTex(r"x = \begin{bmatrix} 30 \\ 20 \\ 10 \end{bmatrix}", font_size=64).to_corner(DR, buff=0.8)
        self.play(sis.animate.shift(LEFT * 1.8).scale(0.85), run_time=0.7)
        self.ate(self.ini[2] + self.dur[2] * 0.55)
        caixa = SurroundingRectangle(sol, color=AMBAR, buff=0.2)
        self.play(Write(sol), run_time=1.0)
        self.play(Create(caixa), run_time=0.5)
        # fala 3: conferência da primeira linha
        self.fala(3)
        conf = MathTex(r"0{,}9 \cdot 30 - 0{,}2 \cdot 20", r"= 27 - 4", r"= 23", font_size=50).next_to(sis, DOWN, buff=0.5).align_to(sis, LEFT)
        conf[2].set_color(VERDE)
        self.play(Indicate(sis[0][:15], color=AMBAR), run_time=0.8)
        self.play(Write(conf), run_time=1.6)
        ok = txt("✓ bate", 34, VERDE, weight=BOLD).next_to(conf, RIGHT, buff=0.4)
        self.play(FadeIn(ok, scale=1.3), run_time=0.4)
        self.ate(self.ini[3] + self.dur[3] * 0.7)
        frase = txt("entregar 23 de comida → produzir 30", 32, AMBAR, weight=BOLD).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(frase, shift=UP * 0.2), run_time=0.7)
        self.encerrar()


class Limites(Ritmo, Scene):
    CENA = "limites"

    def construct(self):
        self.preparar()
        u = 0.1
        base_y = -2.6
        caps = [36, 28, 16]
        pedido = [34, 30, 12]
        xs = [-4.4, -2.4, -0.4]
        # fala 0: capacidade e mão de obra
        self.fala(0)
        barras, tetos, rots = VGroup(), VGroup(), VGroup()
        for k, s in enumerate(SETORES):
            b = Rectangle(width=1.2, height=pedido[k] * u, stroke_width=0, fill_color=COR_S[s], fill_opacity=0.85)
            b.move_to([xs[k], base_y + pedido[k] * u / 2, 0])
            t = DashedLine([xs[k] - 0.8, base_y + caps[k] * u, 0], [xs[k] + 0.8, base_y + caps[k] * u, 0], color=PAPEL, stroke_width=3)
            barras.add(b)
            tetos.add(t)
            rots.add(txt(s, 24, COR_S[s], weight=BOLD).next_to([xs[k], base_y, 0], DOWN, buff=0.2))
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in barras], lag_ratio=0.2), FadeIn(rots), run_time=1.2)
        rcap = txt("capacidade máxima", 24, PAPEL, font=MAQ).next_to(tetos, UP, buff=0.5)
        self.play(Create(tetos), FadeIn(rcap), run_time=0.8)
        alerta = SurroundingRectangle(barras[1], color=VERMELHO, buff=0.08)
        self.play(Create(alerta), run_time=0.4)
        # mão de obra: medidor
        med = Rectangle(width=4.2, height=0.5, color=PAPEL, stroke_width=2).move_to([3.8, 0.6, 0])
        uso = ValueTracker(1.18)
        enche = always_redraw(lambda: Rectangle(width=4.2 * min(uso.get_value(), 1.3) / 1.3, height=0.5, stroke_width=0,
                                                fill_color=VERMELHO if uso.get_value() > 1.0 else VERDE, fill_opacity=0.9)
                              .align_to(med, LEFT).match_y(med))
        lim = Line(med.get_left() + RIGHT * 4.2 / 1.3 + UP * 0.4, med.get_left() + RIGHT * 4.2 / 1.3 + DOWN * 0.4, color=PAPEL, stroke_width=4)
        rmed = txt("mão de obra usada", 26, PAPEL).next_to(med, UP, buff=0.25)
        rlim = txt("disponível (W)", 22, PAPEL_2, font=MAQ).next_to(lim, DOWN, buff=0.1)
        self.ate(self.ini[0] + self.dur[0] * 0.45)
        self.play(FadeIn(med), FadeIn(enche), Create(lim), FadeIn(rmed), FadeIn(rlim), run_time=0.9)
        self.ate(self.ini[0] + self.dur[0] * 0.72)
        f = 1 / 1.18
        self.play(uso.animate.set_value(1.0), *[b.animate.stretch(f, 1, about_edge=DOWN) for b in barras], FadeOut(alerta), run_time=1.4)
        corte = txt("o servidor corta tudo na mesma proporção", 24, AMBAR, font=MAQ).next_to(med, DOWN, buff=0.7)
        self.play(FadeIn(corte), run_time=0.5)
        # fala 1: comida das tropas
        self.fala(1)
        self.play(FadeOut(VGroup(barras, tetos, rots, rcap, med, enche, lim, rmed, rlim, corte)), run_time=0.6)
        batalhoes = VGroup(*[Square(0.42, color=PAPEL, fill_color="#3a4436", fill_opacity=1, stroke_width=2) for _ in range(12)]).arrange_in_grid(2, 6, buff=0.18).shift(UP * 1.0 + LEFT * 2.6)
        come = txt("cada batalhão: ½ ALI por turno", 30, VERDE, weight=BOLD).next_to(batalhoes, DOWN, buff=0.35)
        self.play(LaggedStart(*[FadeIn(b) for b in batalhoes], lag_ratio=0.05), FadeIn(come), run_time=1.2)
        fome = VGroup(txt("sem comida:", 30, VERMELHO, weight=BOLD), txt("−10 de moral", 30, PAPEL), txt("10% das tropas desertam", 30, PAPEL)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        fome.to_edge(RIGHT, buff=0.8).shift(UP * 0.6)
        self.ate(self.ini[1] + self.dur[1] * 0.45)
        self.play(FadeIn(fome, shift=LEFT * 0.2), run_time=0.7)
        self.ate(self.ini[1] + self.dur[1] * 0.7)
        self.play(batalhoes[-1].animate.set_fill(VERMELHO), run_time=0.3)
        self.play(FadeOut(batalhoes[-1], shift=DOWN * 0.4), run_time=0.5)
        # fala 2: o bônus do desafio
        self.fala(2)
        self.play(FadeOut(VGroup(batalhoes[:-1], come, fome)), run_time=0.5)
        bonus = txt("+10%", 150, AMBAR, weight=BOLD)
        rb = txt("de produtividade neste turno", 34, PAPEL).next_to(bonus, DOWN, buff=0.3)
        self.play(FadeIn(bonus, scale=1.6), run_time=0.6)
        self.play(FadeIn(rb), run_time=0.5)
        self.encerrar()


class Fim(Ritmo, Scene):
    CENA = "fim"

    def construct(self):
        self.preparar()
        self.fala(0)
        tres = VGroup(txt("uma tabela", 34, PAPEL), txt("uma divisão por colunas", 34, PAPEL), txt("um sistema linear", 34, PAPEL)).arrange(RIGHT, buff=0.9)
        for k, t in enumerate(tres):
            self.ate(self.ini[0] + self.dur[0] * (0.05 + 0.13 * k))
            self.play(FadeIn(t, shift=UP * 0.2), run_time=0.6)
        self.ate(self.ini[0] + self.dur[0] * 0.62)
        nobel = VGroup(txt("Wassily Leontief", 44, AMBAR, font=SERIF, weight=BOLD),
                       txt("Nobel de Economia, 1973", 28, PAPEL_2, font=MAQ)).arrange(DOWN, buff=0.2).shift(DOWN * 1.6)
        self.play(FadeIn(nobel, shift=UP * 0.2), run_time=0.8)
        self.fala(1)
        self.play(FadeOut(VGroup(tres, nobel)), run_time=0.5)
        bs = txt("Boa sorte, intendente.", 72, AMBAR, font=SERIF, slant=ITALIC)
        self.play(Write(bs), run_time=1.2)
        self.encerrar()


class Creditos(Scene):
    def construct(self):
        a = txt("ESTADO-MAIOR", 54, PAPEL, weight=BOLD)
        b = txt("A Guerra do Continente de Lebesgue", 34, LATAO, font=SERIF, slant=ITALIC)
        c = txt("Outras instruções: Operações · Inteligência · Governo", 24, CINZA)
        g = VGroup(a, b, c).arrange(DOWN, buff=0.4)
        self.play(FadeIn(g, shift=UP * 0.2), run_time=1.0)
        self.wait(2.2)
        self.play(FadeOut(g), run_time=0.8)
