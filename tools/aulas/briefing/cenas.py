"""Animações (Manim) do briefing de uma nação. Cada classe dura exatamente o tempo da sua narração.

Renderizar (a partir da raiz do repositório):
    NACAO=NOE N_NACOES=4 AULA_VOZ=<voz> manim -r 1920,1080 --frame_rate 30 tools/aulas/briefing/cenas.py <Classe>
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from comum import *  # noqa: E402,F401,F403
from jogo_dados import mapa_json, nacao  # noqa: E402

FID = os.environ.get("NACAO", "NOE")
N = int(os.environ.get("N_NACOES", "4"))
D = nacao(FID, N)
COR = NACOES[FID]
T = {t["id"]: t for t in mapa_json()["territories"]}
ROTAS = mapa_json()["sea_routes"]
GLIFO = {"GAU": r"\nabla", "EUL": r"e", "HIL": r"\perp", "NOE": r"\mathcal{R}", "CAU": r"\varepsilon", "RIE": r"\zeta"}
LEMA = {"GAU": "“Uma incógnita de cada vez.”", "EUL": "“Tudo se mede. Nada se esquece.”",
        "HIL": "“Muitas províncias, uma só direção.”", "NOE": "“O que se conserva, vence.”",
        "CAU": "“Devagar, mas sempre converge.”", "RIE": "“Há sempre um caminho mais curto.”"}
TERRENO = {"planicie": "planície", "pantano": "pântano", "urbano": "cidade", "floresta": "floresta", "montanha": "montanha"}
DEFESA = {"urbano": "+30%", "floresta": "+25%", "pantano": "+20%", "montanha": "+50%"}
CLIMA = {"norte": AZUL, "centro": VERDE, "sul": AMBAR}


def selo(raio=1.2, cor=COR, fid=FID):
    """O selo da nação: dois anéis e o emblema."""
    g = MathTex(GLIFO[fid], color=cor).scale(raio * 2.3)
    return VGroup(Circle(radius=raio, color=cor, stroke_width=7), Circle(radius=raio * 0.82, color=cor, stroke_width=2.5), g)


def nome_curto(fid):
    return next(o["short"] for o in D["outras"] if o["id"] == fid) if fid != FID else D["short"]


def caixa_texto(grupo, cor=LATAO, buff=0.3):
    return SurroundingRectangle(grupo, color=cor, buff=buff, stroke_width=2, fill_color=FUNDO, fill_opacity=0.88)


def enquadrar(self, mobj, margem=2.3):
    """Anima a câmera para enquadrar mobj com folga."""
    w = max(mobj.width * margem, mobj.height * margem * 16 / 9)
    return self.camera.frame.animate.set(width=w).move_to(mobj.get_center())


# =================================================================== CENAS
class Titulo(Scene):
    """Abertura sem narração (5 s)."""

    def construct(self):
        s = selo(1.25)
        serie = txt("ESTADO-MAIOR · BRIEFING DA NAÇÃO", 26, LATAO, weight=BOLD)
        nome = txt(D["name"], 64, PAPEL, font=SERIF, weight=BOLD)
        cap = txt(f"Capital: {D['capital']}", 30, COR, font=MAQ)
        g = VGroup(s, serie, nome, cap).arrange(DOWN, buff=0.35)
        linha = Line(LEFT * 3.4, RIGHT * 3.4, color=LATAO, stroke_width=2).next_to(nome, DOWN, buff=0.16)
        cap.next_to(linha, DOWN, buff=0.3)
        self.play(DrawBorderThenFill(s), run_time=1.2)
        self.play(FadeIn(serie, shift=DOWN * 0.2), Write(nome), run_time=1.2)
        self.play(Create(linha), FadeIn(cap, shift=UP * 0.2), run_time=0.8)
        self.wait(1.2)
        self.play(FadeOut(VGroup(s, serie, nome, cap, linha)), run_time=0.6)


class Abertura(Ritmo, Scene):
    CENA = "abertura"

    def construct(self):
        self.preparar()
        grupo, polys, dono, p = mapa(N)
        terra, terr = grupo
        # fala 0: o continente em paz armada... que acabou
        self.fala(0)
        tit = txt("CONTINENTE DE LEBESGUE", 30, LATAO, weight=BOLD).to_edge(UP, buff=0.3)
        self.play(FadeIn(terra), FadeIn(tit, shift=DOWN * 0.2), run_time=1.6)
        self.ate(self.ini[0] + self.dur[0] - 1.3)
        carimbo = txt("GUERRA", 120, VERMELHO, weight=BOLD)
        moldura = SurroundingRectangle(carimbo, color=VERMELHO, buff=0.25, stroke_width=8)
        st = VGroup(carimbo, moldura).rotate(-9 * DEGREES)
        self.play(FadeIn(st, scale=2.2), run_time=0.35, rate_func=rush_into)
        # fala 1: as nações aparecem; a nossa por último, com o nome e a capital
        self.fala(1)
        self.play(FadeOut(st), run_time=0.4)
        ordem = [o["id"] for o in D["outras"]] + [FID]
        neutros = [pl for t, pl in polys.items() if t not in dono]
        self.play(LaggedStart(*[FadeIn(pl) for pl in neutros], lag_ratio=0.02), run_time=1.0)
        for fid in ordem:
            ps = [polys[t] for t, d in dono.items() if d == fid]
            self.play(LaggedStart(*[FadeIn(pl) for pl in ps], lag_ratio=0.15), run_time=0.6)
        nossos = VGroup(*[polys[t["id"]] for t in D["territorios"]])
        contorno = VGroup(*[pl.copy().set_fill(opacity=0).set_stroke(PAPEL, 3) for pl in nossos])
        cartao = VGroup(txt(D["name"], 34, COR, font=SERIF, weight=BOLD), txt(f"capital: {D['capital']}", 24, PAPEL, font=MAQ)).arrange(DOWN, buff=0.12)
        cartao.next_to(nossos, DOWN if D["centro"][1] < 400 else UP, buff=0.35)
        fundo = caixa_texto(cartao, COR, 0.2)
        self.play(Create(contorno), FadeIn(fundo), FadeIn(cartao), run_time=1.2)
        # fala 2: a história da nação; território, comida e vidas
        self.fala(2)
        tudo = VGroup(terra, terr, contorno, fundo, cartao)
        self.play(tudo.animate.scale(0.55).to_edge(LEFT, buff=0.4).set_opacity(0.35), FadeOut(tit), run_time=1.2)
        s = selo(1.0).move_to([3.4, 1.4, 0])
        lema = txt(LEMA.get(FID, ""), 34, PAPEL, font=SERIF, slant=ITALIC).next_to(s, DOWN, buff=0.5)
        self.play(DrawBorderThenFill(s), run_time=1.0)
        self.play(Write(lema), run_time=1.4)
        self.ate(self.ini[2] + self.dur[2] - 4.0)
        tres = VGroup(*[txt(x, 30, AMBAR, weight=BOLD) for x in ("TERRITÓRIO", "COMIDA", "VIDAS")]).arrange(RIGHT, buff=0.6)
        tres.next_to(lema, DOWN, buff=0.7)
        for x in tres:
            self.play(FadeIn(x, shift=UP * 0.15), run_time=0.45)
        self.encerrar()


class Mapa(Ritmo, MovingCameraScene):
    CENA = "mapa"

    def construct(self):
        self.preparar()
        grupo, polys, dono, p = mapa(N)
        frame = self.camera.frame
        # fala 0: 34 territórios em três regiões de clima
        self.fala(0)
        self.play(FadeIn(grupo), run_time=1.2)
        conta = txt("34 territórios", 34, PAPEL, weight=BOLD).to_corner(UL, buff=0.35)
        self.play(FadeIn(conta), run_time=0.5)
        regioes = VGroup()
        rot_reg = VGroup()
        for reg, cor in CLIMA.items():
            ts = [t for t in T.values() if t["climate"] == reg]
            regioes.add(*[polys[t["id"]].copy().set_fill(cor, 0.55).set_stroke(width=0) for t in ts])
            cx = sum(t["centroid"][0] for t in ts) / len(ts)
            cy = sum(t["centroid"][1] for t in ts) / len(ts)
            r = txt(reg.upper(), 34, PAPEL, weight=BOLD)
            rot_reg.add(VGroup(caixa_texto(r, cor, 0.12), r).move_to(p(cx, cy)))
        self.ate(self.ini[0] + 2.8)
        self.play(FadeIn(regioes), LaggedStart(*[FadeIn(r) for r in rot_reg], lag_ratio=0.3), run_time=1.6)
        self.ate(self.ini[0] + self.dur[0] - 0.3)
        self.play(FadeOut(regioes), FadeOut(rot_reg), FadeOut(conta), run_time=0.6)
        # fala 1: a nossa nação, de perto: territórios, capital e terrenos que defendem melhor
        self.fala(1)
        nossos = VGroup(*[polys[t["id"]] for t in D["territorios"]])
        outros_polys = [pl for t, pl in polys.items() if dono.get(t) != FID]
        self.play(*[pl.animate.set_fill(opacity=0.12) for pl in outros_polys], enquadrar(self, nossos, 2.0), run_time=1.6)
        s = frame.width / config.frame_width
        rotulos = VGroup()
        for t in D["territorios"]:
            c = p(*T[t["id"]]["label_pos"])
            r = txt(t["nome"], 26 * s, PAPEL, weight=BOLD)
            rotulos.add(VGroup(caixa_texto(r, PAPEL_2, 0.06 * s * 2).set_stroke(width=1), r).move_to(c))
        self.play(LaggedStart(*[FadeIn(r) for r in rotulos], lag_ratio=0.35), run_time=1.8)
        cap = T[D["capital_tid"]]
        estrela = Star(5, outer_radius=0.16 * s * 2, color=AMBAR, fill_opacity=1).move_to(p(*cap["centroid"]))
        self.ate(self.ini[1] + self.dur[1] * 0.55)
        self.play(SpinInFromNothing(estrela), run_time=0.6)
        tags = VGroup()
        fortes = [t for t in D["territorios"] if t["terreno"] in DEFESA]
        for t in fortes:
            tg = txt(f"{TERRENO[t['terreno']]} · defesa {DEFESA[t['terreno']]}", 20 * s, FUNDO, weight=BOLD)
            tags.add(VGroup(BackgroundRectangle(tg, color=AMBAR, fill_opacity=0.95, buff=0.05 * s * 2), tg)
                     .next_to(rotulos[D["territorios"].index(t)], DOWN, buff=0.05 * s * 2))
        self.play(LaggedStart(*[FadeIn(tg, shift=UP * 0.1 * s) for tg in tags], lag_ratio=0.6), run_time=1.4)
        # fala 2: as outras nações, cada uma uma sala
        self.fala(2)
        self.play(FadeOut(rotulos), FadeOut(tags), frame.animate.set(width=config.frame_width).move_to(ORIGIN),
                  *[pl.animate.set_fill(opacity=0.85 if t in dono else 0.16) for t, pl in polys.items()], run_time=1.4)
        c0 = p(*D["centro"])
        setas = VGroup()
        for o in D["outras"]:
            ts = [T[t]["centroid"] for t, d in dono.items() if d == o["id"]]
            c = p(sum(x for x, _ in ts) / len(ts), sum(y for _, y in ts) / len(ts))
            seta = Arrow(c0, c, buff=1.0, color=PAPEL, stroke_width=5, max_tip_length_to_length_ratio=0.12)
            nm = txt(o["short"], 34, PAPEL, weight=BOLD)
            sala = txt("outra sala", 22, PAPEL, font=MAQ)
            et = VGroup(nm, sala).arrange(DOWN, buff=0.06).move_to(c)
            setas.add(VGroup(seta, caixa_texto(et, NACOES[o["id"]], 0.14), et))
        for st in setas:
            self.play(GrowArrow(st[0]), FadeIn(st[1]), FadeIn(st[2]), run_time=0.8)
        # fala 3: a fronteira mais quente
        self.fala(3)
        self.play(FadeOut(setas), run_time=0.5)
        rival = next((o for o in D["outras"] if o["fronteiras"]), None)
        if rival:
            meu, dele = rival["fronteiras"][0]
            par = VGroup(polys[meu], polys[dele])
            self.play(enquadrar(self, par, 2.6), run_time=1.4)
            s = frame.width / config.frame_width
            linha = DashedLine(p(*T[meu]["centroid"]), p(*T[dele]["centroid"]), color=VERMELHO, stroke_width=8, dash_length=0.12 * s)
            self.play(Create(linha), polys[meu].animate.set_stroke(PAPEL, 4), polys[dele].animate.set_stroke(VERMELHO, 5), run_time=1.0)
            nomes = VGroup()
            for tid in (meu, dele):
                r = txt(D["nome_de"](tid), 28 * s, PAPEL, weight=BOLD)
                if tid in D["capitais"]:
                    r = VGroup(r, txt(f"capital de {nome_curto(D['capitais'][tid])}", 20 * s, AMBAR, font=MAQ)).arrange(DOWN, buff=0.04 * s)
                nomes.add(VGroup(caixa_texto(r, PAPEL_2, 0.1 * s), r).move_to(p(*T[tid]["label_pos"])))
            self.play(LaggedStart(*[FadeIn(x) for x in nomes], lag_ratio=0.4), run_time=1.0)
            quente = txt("FRONTEIRA QUENTE", 40 * s, VERMELHO, weight=BOLD).next_to(par, UP, buff=0.25 * s)
            self.play(FadeIn(quente, scale=1.3), Flash(linha.get_center(), color=VERMELHO, flash_radius=0.5 * s), run_time=0.8)
            self.ate(self.ini[3] + self.dur[3] + 0.1)
            self.play(FadeOut(VGroup(linha, nomes, quente)), polys[meu].animate.set_stroke(FUNDO, 1.2),
                      polys[dele].animate.set_stroke(FUNDO, 1.2), frame.animate.set(width=config.frame_width).move_to(ORIGIN), run_time=0.8)
        # fala 4: neutros (milícias) e rotas marítimas
        self.fala(4)
        neutros = VGroup(*[polys[v["id"]] for v in D["neutros_vizinhos"]])
        self.play(LaggedStart(*[pl.animate.set_fill(PAPEL, 0.55) for pl in neutros], lag_ratio=0.15), run_time=1.4)
        mil = txt("milícias neutras", 30, PAPEL, font=MAQ).to_corner(DL, buff=0.4)
        self.play(FadeIn(mil), run_time=0.5)
        self.ate(self.ini[4] + self.dur[4] * 0.5)
        rotas = VGroup()
        for r in ROTAS:
            v = VMobject(color=AZUL, stroke_width=5).set_points_smoothly([p(*q) for q in r["path"]])
            rotas.add(DashedVMobject(v, num_dashes=10))
        rot = txt("rotas marítimas", 30, AZUL, font=MAQ).next_to(mil, RIGHT, buff=0.8)
        self.play(Create(rotas), FadeIn(rot), *[pl.animate.set_fill(CINZA, 0.16) for pl in neutros], run_time=1.6)
        self.encerrar()


class Vitoria(Ritmo, Scene):
    CENA = "vitoria"

    def construct(self):
        self.preparar()
        tit = txt("Como se vence", 52, AMBAR, font=SERIF, weight=BOLD).to_edge(UP, buff=0.5)
        # fala 0: quanto vale cada coisa
        self.fala(0)
        self.play(Write(tit), run_time=0.9)
        fichas = VGroup()
        itens = [("território", "1 PV", Square(0.9, color=COR, fill_opacity=0.85, stroke_width=0)),
                 ("capital", "+2 PV", Star(5, outer_radius=0.55, color=AMBAR, fill_opacity=1)),
                 ("desafio resolvido", "+0,25 PV", Text("✓", font=SANS, font_size=80, color=VERDE))]
        for nome, val, icone in itens:
            fichas.add(VGroup(icone, txt(nome, 30, PAPEL), txt(val, 44, AMBAR, font=MONO, weight=BOLD)).arrange(DOWN, buff=0.3))
        fichas.arrange(RIGHT, buff=1.6).shift(UP * 0.2)
        marcas = [0.2, 0.42, 0.72]
        for f, m in zip(fichas, marcas):
            self.ate(self.ini[0] + self.dur[0] * m)
            self.play(FadeIn(f, shift=UP * 0.3), run_time=0.6)
        # fala 1: começam com 6 PV; 8 turnos; dominação = 21 de 34
        self.fala(1)
        self.play(fichas.animate.scale(0.55).to_edge(UP, buff=1.45), run_time=0.8)
        conta = MathTex(r"4 \times 1", r"\;+\;", r"2", r"\;=\;", r"6\ \text{PV}", font_size=64)
        conta[4].set_color(AMBAR)
        conta.shift(UP * 0.2)
        self.play(Write(conta), run_time=1.4)
        turnos = VGroup(*[VGroup(Square(0.5, color=LATAO, stroke_width=2), txt(str(i + 1), 22, PAPEL, font=MONO)) for i in range(8)]).arrange(RIGHT, buff=0.12)
        for q in turnos:
            q[1].move_to(q[0])
        rt = txt("8 turnos", 26, LATAO).next_to(turnos, LEFT, buff=0.3)
        g_t = VGroup(rt, turnos).move_to([0, -1.35, 0])
        self.ate(self.ini[1] + self.dur[1] * 0.35)
        self.play(FadeIn(rt), LaggedStart(*[FadeIn(q) for q in turnos], lag_ratio=0.1), run_time=1.2)
        celulas = VGroup(*[Rectangle(width=0.3, height=0.42, stroke_width=1.2, color=PAPEL_2) for _ in range(34)]).arrange(RIGHT, buff=0.05)
        celulas.move_to([0, -2.6, 0])
        rot = txt("dominação: 21 de 34 territórios", 26, VERMELHO, weight=BOLD).next_to(celulas, DOWN, buff=0.2)
        self.ate(self.ini[1] + self.dur[1] * 0.62)
        self.play(FadeIn(celulas), run_time=0.5)
        self.play(LaggedStart(*[c.animate.set_fill(VERMELHO, 0.85) for c in celulas[:21]], lag_ratio=0.05), FadeIn(rot), run_time=1.6)
        # fala 2: capitulação
        self.fala(2)
        self.play(FadeOut(VGroup(fichas, conta, g_t, celulas, rot)), run_time=0.6)
        c1 = VGroup(txt("perder todos os territórios", 32, PAPEL)).arrange(DOWN)
        c2 = VGroup(txt("perder a capital", 32, PAPEL), txt("+ menos de 3 batalhões", 28, PAPEL_2),
                    txt("+ menos de 10 unidades de estoque", 28, PAPEL_2)).arrange(DOWN, buff=0.12)
        ou = txt("ou", 34, LATAO, font=SERIF, slant=ITALIC)
        conds = VGroup(VGroup(caixa_texto(c1, PAPEL_2), c1), ou, VGroup(caixa_texto(c2, PAPEL_2), c2)).arrange(RIGHT, buff=0.6).shift(UP * 0.4)
        self.play(FadeIn(conds[0]), run_time=0.7)
        self.ate(self.ini[2] + self.dur[2] * 0.3)
        self.play(FadeIn(conds[1]), FadeIn(conds[2]), run_time=0.8)
        self.ate(self.ini[2] + self.dur[2] - 1.4)
        carimbo = txt("CAPITULOU", 96, VERMELHO, weight=BOLD)
        st = VGroup(carimbo, SurroundingRectangle(carimbo, color=VERMELHO, buff=0.2, stroke_width=7)).rotate(-6 * DEGREES).move_to([0, -2.3, 0])
        self.play(FadeIn(st, scale=1.9), run_time=0.4, rate_func=rush_into)
        self.encerrar()


class Turno(Ritmo, Scene):
    CENA = "turno"

    def construct(self):
        self.preparar()
        centro = LEFT * 3.6 + DOWN * 0.2
        aro = Circle(radius=2.2, color=CINZA, stroke_width=10).move_to(centro)
        prog = ValueTracker(0.0)
        arco = always_redraw(lambda: Arc(radius=2.2, start_angle=PI / 2, angle=-TAU * max(prog.get_value(), 1e-4),
                                         color=AMBAR, stroke_width=10, arc_center=centro))
        minutos = always_redraw(lambda: txt(f"{int(12 - 12 * prog.get_value()):02d}:00", 64, PAPEL, font=MONO, weight=BOLD).move_to(centro))
        # fala 0: o turno começa com o briefing (um dossiê por seção)
        self.fala(0)
        self.play(Create(aro), FadeIn(minutos), run_time=1.0)
        self.add(arco)
        lado = RIGHT * 3.2
        dossies = VGroup(*[VGroup(Rectangle(width=2.6, height=0.8, color=LATAO, fill_color="#2a2f26", fill_opacity=1, stroke_width=2),
                                  txt(s, 26, PAPEL, weight=BOLD)) for s in ("Intendência", "Operações", "Inteligência", "Governo")])
        for d in dossies:
            d[1].move_to(d[0])
        dossies.arrange_in_grid(2, 2, buff=0.35).move_to(lado + UP * 0.4)
        rot = txt("dossiês do turno", 26, LATAO, font=MAQ).next_to(dossies, UP, buff=0.3)
        self.ate(self.ini[0] + self.dur[0] * 0.5)
        self.play(FadeIn(rot), LaggedStart(*[FadeIn(d, shift=LEFT * 0.6) for d in dossies], lag_ratio=0.2), run_time=1.4)
        # fala 1: planejamento; relâmpago na metade; vale a última ordem
        self.fala(1)
        self.play(FadeOut(dossies), FadeOut(rot), prog.animate.set_value(0.5), run_time=3.0, rate_func=linear)
        raio = txt("⚡ telegrama-relâmpago", 30, AMBAR, weight=BOLD).next_to(aro, DOWN, buff=0.3)
        self.play(FadeIn(raio, scale=1.2), Flash(centro + DOWN * 2.2, color=AMBAR, flash_radius=0.4), run_time=0.7)
        o1 = VGroup(Rectangle(width=2.8, height=1.0, color=PAPEL_2, stroke_width=2), txt("ordem enviada às 03:10", 22, PAPEL_2, font=MAQ))
        o2 = VGroup(Rectangle(width=2.8, height=1.0, color=VERDE, stroke_width=3), txt("ordem corrigida às 09:40", 22, PAPEL, font=MAQ))
        for o in (o1, o2):
            o[1].move_to(o[0])
        o1.move_to(lado + UP * 1.0)
        o2.move_to(lado + DOWN * 0.4)
        self.ate(self.ini[1] + self.dur[1] * 0.62)
        self.play(FadeIn(o1, shift=LEFT * 0.4), run_time=0.6)
        self.play(FadeIn(o2, shift=LEFT * 0.4), o1.animate.set_opacity(0.35), run_time=0.6)
        vale = txt("vale a última", 30, VERDE, weight=BOLD).next_to(o2, DOWN, buff=0.3)
        self.play(FadeIn(vale), run_time=0.5)
        # fala 2: o relógio zera e o servidor resolve tudo
        self.fala(2)
        self.play(FadeOut(VGroup(o1, o2, vale, raio)), prog.animate.set_value(1.0), run_time=1.8, rate_func=linear)
        passos = ["Governo", "Intendência (produção)", "Recrutamento", "Inteligência (bombardeio)",
                  "Operações (movimentos e batalhas)", "Manutenção (comida)", "Moral e pontos"]
        lista = VGroup(*[txt(f"{i + 1}. {s}", 28, PAPEL) for i, s in enumerate(passos)]).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
        tit = txt("RESOLUÇÃO", 34, AMBAR, weight=BOLD)
        bloco = VGroup(tit, lista).arrange(DOWN, aligned_edge=LEFT, buff=0.3).move_to(lado)
        self.play(FadeIn(tit), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(l, shift=RIGHT * 0.2) for l in lista], lag_ratio=0.25), run_time=2.6)
        self.ate(self.ini[2] + self.dur[2] - 1.6)
        self.remove(arco)
        prog.set_value(0.0)
        novo = txt("próximo turno ↻", 30, VERDE, weight=BOLD).next_to(aro, DOWN, buff=0.3)
        self.add(arco)
        self.play(FadeIn(novo), run_time=0.6)
        self.encerrar()


class Secoes(Ritmo, Scene):
    CENA = "secoes"

    def construct(self):
        self.preparar()
        info = [
            ("INTENDÊNCIA", "produção e recrutamento", r"(I - A)\,x = d", "Leontief"),
            ("OPERAÇÕES", "movimentos e ataques", r"\alpha A_0^2 \;\text{vs}\; \beta B_0^2", "Markov + Lanchester"),
            ("INTELIGÊNCIA", "decifrar e bombardear", r"K = C\,P^{-1} \pmod{37}", "Hill + mínimos quadrados"),
            ("GOVERNO", "moral e diplomacia", r"\beta = (X^{T}X)^{-1}X^{T}y", "regressão linear"),
        ]
        cartoes = VGroup()
        for nome, decide, eq, metodo in info:
            caixa = RoundedRectangle(width=6.3, height=2.9, corner_radius=0.12, color=LATAO, stroke_width=2.5,
                                     fill_color="#232b24", fill_opacity=1)
            t = txt(nome, 36, PAPEL, weight=BOLD)
            d = txt(decide, 26, PAPEL_2)
            m = MathTex(eq, font_size=44, color=AMBAR)
            mt = txt(metodo, 22, LATAO, font=MAQ)
            conteudo = VGroup(t, d, m, mt).arrange(DOWN, buff=0.2)
            cartoes.add(VGroup(caixa, conteudo))
        cartoes.arrange_in_grid(2, 2, buff=(0.45, 0.4)).shift(DOWN * 0.15)
        for c in cartoes:
            c[1].move_to(c[0])
            c[1][2].set_opacity(0)
            c[1][3].set_opacity(0)
        # fala 0: quatro seções
        self.fala(0)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.2) for c in cartoes], lag_ratio=0.2), run_time=1.8)
        # falas 1 a 4: cada seção com a sua matemática
        for i, c in enumerate(cartoes):
            self.fala(i + 1)
            outros = [x for j, x in enumerate(cartoes) if j != i]
            self.play(c[0].animate.set_stroke(AMBAR, 5), *[x.animate.set_opacity(0.3) for x in outros],
                      c.animate.set_opacity(1), run_time=0.6)
            c[1][2].set_opacity(1)
            c[1][3].set_opacity(1)
            self.play(Write(c[1][2]), FadeIn(c[1][3]), run_time=1.3)
            self.ate(self.ini[i + 1] + self.dur[i + 1] + 0.2)
            self.play(c[0].animate.set_stroke(LATAO, 2.5), run_time=0.3)
        # fala 5: a equipe se divide; um chefe de estado-maior
        self.fala(5)
        self.play(*[x.animate.set_opacity(1) for x in cartoes], run_time=0.5)
        for c in cartoes:
            c[1][2].set_opacity(0.35)
            c[1][3].set_opacity(0.35)
        pessoas = VGroup()
        for k, c in enumerate(cartoes):
            n = 3 if k < 2 else 3
            g = VGroup(*[VGroup(Circle(radius=0.13, color=PAPEL, fill_opacity=1, stroke_width=0),
                                Arc(radius=0.22, start_angle=0, angle=PI, color=PAPEL, stroke_width=6).shift(DOWN * 0.33))
                         for _ in range(n)]).arrange(RIGHT, buff=0.18)
            g.next_to(c[0].get_bottom(), UP, buff=0.25)
            pessoas.add(g)
        self.play(LaggedStart(*[FadeIn(g, shift=DOWN * 0.3) for g in pessoas], lag_ratio=0.25), run_time=1.6)
        chefe = VGroup(Circle(radius=0.72, color=AMBAR, fill_color=FUNDO, fill_opacity=1, stroke_width=4),
                       Star(5, outer_radius=0.28, color=AMBAR, fill_opacity=1).shift(UP * 0.12),
                       txt("chefe", 20, AMBAR, weight=BOLD).shift(DOWN * 0.34))
        chefe.move_to(cartoes.get_center())
        self.ate(self.ini[5] + self.dur[5] * 0.45)
        self.play(GrowFromCenter(chefe), run_time=0.7)
        linhas = VGroup(*[DashedLine(chefe.get_center(), c[0].get_center(), color=AMBAR, stroke_width=2) for c in cartoes])
        for l in linhas:
            l.put_start_and_end_on(chefe.get_center() + 0.75 * normalize(l.get_end() - chefe.get_center()), l.get_end())
            l.set_z_index(-1)
        self.play(Create(linhas), run_time=0.8)
        self.encerrar()


class Fim(Ritmo, MovingCameraScene):
    CENA = "fim"

    def construct(self):
        self.preparar()
        grupo, polys, dono, p = mapa(N, opacidade=lambda f: 0.85 if f == FID else 0.35)
        frame = self.camera.frame
        rival = next((o for o in D["outras"] if o["fronteiras"]), None)
        # fala 0: o conselho do Gabinete
        self.fala(0)
        self.play(FadeIn(grupo), run_time=1.0)
        if rival:
            meu, dele = rival["fronteiras"][0]
            par = VGroup(polys[meu], polys[dele])
            self.play(enquadrar(self, par, 2.6), run_time=1.4)
            s = frame.width / config.frame_width
            if meu == D["capital_tid"]:
                frase = f"Guardem {D['capital']}"
                seta = Arrow(p(*T[dele]["centroid"]), p(*T[meu]["centroid"]), buff=0.25 * s, color=VERMELHO, stroke_width=10 * s)
            else:
                frase = f"{D['nome_de'](dele)} está ao alcance"
                seta = Arrow(p(*T[meu]["centroid"]), p(*T[dele]["centroid"]), buff=0.25 * s, color=AMBAR, stroke_width=10 * s)
            r = txt(frase, 40 * s, PAPEL, font=SERIF, weight=BOLD)
            r.next_to(par, UP, buff=0.3 * s)
            self.play(GrowArrow(seta), FadeIn(r), run_time=1.0)
            self.ate(self.ini[0] + self.dur[0] - 3.6)
            ali = txt("Alimento acaba rápido.", 30 * s, AMBAR, font=MAQ).next_to(par, DOWN, buff=0.3 * s)
            self.play(FadeIn(ali), run_time=0.6)
        # fala 1: boa sorte
        self.fala(1)
        self.play(FadeOut(grupo), *[FadeOut(m) for m in self.mobjects if m is not grupo],
                  frame.animate.set(width=config.frame_width).move_to(ORIGIN), run_time=1.0)
        sl = selo(1.0).shift(UP * 1.4)
        bs = txt(f"Boa sorte, Estado-Maior de {D['short']}.", 56, AMBAR, font=SERIF, slant=ITALIC).next_to(sl, DOWN, buff=0.5)
        ag = txt("Aguardem o sinal do árbitro.", 30, PAPEL, font=MAQ).next_to(bs, DOWN, buff=0.4)
        self.play(DrawBorderThenFill(sl), run_time=0.9)
        self.play(Write(bs), run_time=1.4)
        self.play(FadeIn(ag), run_time=0.6)
        self.encerrar()


class Creditos(Scene):
    """Encerramento sem narração (4 s)."""

    def construct(self):
        a = txt("ESTADO-MAIOR", 54, PAPEL, weight=BOLD)
        b = txt("A Guerra do Continente de Lebesgue", 34, LATAO, font=SERIF, slant=ITALIC)
        c = txt("Em cada aba do QG: ▶ Instrução em vídeo", 24, CINZA)
        g = VGroup(a, b, c).arrange(DOWN, buff=0.4)
        self.play(FadeIn(g, shift=UP * 0.2), run_time=1.0)
        self.wait(2.2)
        self.play(FadeOut(g), run_time=0.8)
