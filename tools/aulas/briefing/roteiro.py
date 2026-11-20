"""Roteiro do briefing de uma nação: o contexto da guerra, o mapa visto dela, como se vence, o turno,
as seções e a tela do QG. É gerado a partir dos dados do jogo (balance.py e map.json).

A nação e o número de nações da partida vêm do ambiente:
    NACAO=NOE N_NACOES=4 python tools/aulas/narracao.py tools/aulas/briefing <voz>
O texto está na forma FALADA (nomes estrangeiros escritos como se pronunciam); o que aparece
na tela usa a grafia do jogo.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jogo_dados import nacao  # noqa: E402

FID = os.environ.get("NACAO", "NOE")
N = int(os.environ.get("N_NACOES", "4"))
D = nacao(FID, N)

# grafia do jogo -> como se fala (o Kokoro lê pelas regras do português)
FALADO = {
    "Eulerândia": "Óilerândia", "Noethéria": "Noetéria", "Hilbertânia": "Ilbertânia", "Cauchýria": "Côchíria",
    "Riemânnia": "Rimânia", "Lebesgue": "Lebêg", "briefing": "brífin",
    "Floresta de Frobenius": "Floresta de Frobênius", "Colinas de Krylov": "Colinas de Krílof",
    "Cabo Cholesky": "Cabo Kolésqui", "Serra de Schmidt": "Serra de Chmít", "Planície de Gram": "Planície de Grâm",
    "Campos de Gershgorin": "Campos de Guérchgorin", "Pradaria Perron": "Pradaria Perrôn",
    "Pântano de Householder": "Pântano de Ráus-rôlder", "Planura Rayleigh": "Planura Rêilei",
    "Chapada Jacobi": "Chapada Jacóbi", "Planalto de Lanczos": "Planalto de Lântsos", "Baía de Givens": "Baía de Guívens",
}


def f(s):
    """Troca a grafia do jogo pela forma falada (nomes mais longos primeiro)."""
    for k in sorted(FALADO, key=len, reverse=True):
        s = s.replace(k, FALADO[k])
    return s


NUM = {2: "duas", 3: "três", 4: "quatro", 5: "cinco", 6: "seis"}
PREP = {"norte": "ao norte", "sul": "ao sul", "leste": "a leste", "oeste": "a oeste", "nordeste": "a nordeste",
        "noroeste": "a noroeste", "sudeste": "a sudeste", "sudoeste": "a sudoeste"}
TERRENO = {"planicie": "planície", "pantano": "pântano", "urbano": "cidade", "floresta": "floresta", "montanha": "montanha"}
DEFESA = {"urbano": "trinta", "floresta": "vinte e cinco", "pantano": "vinte", "montanha": "cinquenta"}

HISTORIA = {
    "GAU": "A República de Gáussia ocupa o noroeste: florestas, a Serra de Chmít e a cidade de Eliminópolis. "
           "Um povo de engenheiros, famoso por resolver qualquer problema eliminando uma incógnita de cada vez.",
    "EUL": "O Império de Óilerândia domina o nordeste: os maiores campos de trigo do continente e a fortaleza de "
           "Totiente. Um império antigo, que mede tudo, e não esquece nenhuma ofensa.",
    "HIL": "A Federação de Ilbertânia guarda o sudeste: pântanos, planuras e o grande porto de Ortonormal. "
           "Uma federação de muitas províncias, que só funciona quando todas apontam na mesma direção.",
    "NOE": "O Reino de Noetéria guarda o sudoeste: colinas, baías e a cidade de Anelópolis. Um reino conhecido "
           "pela teimosia do seu povo, e por descobrir o que se conserva mesmo quando tudo muda.",
    "CAU": "O Principado de Côchíria é pequeno, mas paciente: avança aos poucos, e sempre chega aonde quer.",
    "RIE": "A Confederação de Rimânia vive entre montes e costas curvas, e conhece atalhos que ninguém mais vê.",
}

nome, curto, cap = f(D["name"]), f(D["short"]), D["capital"]
terr = D["territorios"]
outras = D["outras"]
rival = next((o for o in outras if o["fronteiras"]), None)


def lista(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " e " + xs[-1]


# --- frases que dependem da nação
fala_vizinhos = "; ".join(f"{PREP[o['dir']]}, {f(o['short'])}" for o in outras)
fala_vizinhos = fala_vizinhos[0].upper() + fala_vizinhos[1:] + "."
fortes = [t for t in terr if t["terreno"] in ("montanha", "floresta", "pantano") and not t["capital"]]
fala_terreno = (f"A capital, {cap}, é uma cidade: quem defende ali luta trinta por cento melhor."
                + (f" E em {f(fortes[0]['nome'])}, terreno de {TERRENO[fortes[0]['terreno']]}, "
                   f"quem defende ganha {DEFESA[fortes[0]['terreno']]} por cento." if fortes else ""))
if rival:
    meu, dele = rival["fronteiras"][0]
    nm, nd, rv = f(D["nome_de"](meu)), f(D["nome_de"](dele)), f(rival["short"])
    if meu == D["capital_tid"]:
        fala_fronteira = (f"Atenção para a fronteira com {rv}: a capital de vocês, {cap}, encosta em {nd}, "
                          f"território de {rv}. É a fronteira mais quente do mapa.")
        fala_conselho = (f"Primeiro conselho do Gabinete: a fronteira com {rv} encosta na capital de vocês. "
                         f"Não deixem {cap} com poucas tropas: perder a capital custa três pontos e quinze de moral.")
    else:
        fala_fronteira = (f"Atenção para a fronteira com {rv}: {nm} encosta em {nd}, a capital de {rv}. "
                          f"É a fronteira mais quente do mapa.")
        fala_conselho = (f"Primeiro conselho do Gabinete: de {nm}, vocês alcançam {nd}, a capital de {rv}. "
                         f"Tomá-la vale três pontos de uma vez. Mas uma cidade defende trinta por cento melhor, "
                         f"e {rv} sabe disso.")
else:
    fala_fronteira = ("Entre vocês e as outras nações só há territórios neutros. "
                      "Ninguém encosta na sua fronteira, por enquanto.")
    fala_conselho = ("Primeiro conselho do Gabinete: ocupem os territórios neutros antes dos vizinhos. "
                     "Cada um vale um ponto, sem enfrentar outra sala.")

TITULO = f"Briefing · {D['name']}"
CLIPE_ROTULO = f"NO JOGO · QG DE {D['short'].upper()}"

CENAS = [
    ("abertura", [
        f"Estado-Maior de {curto}, atenção. Por muitos anos, o Continente de Lebêg viveu numa paz armada. "
        "Essa paz acabou.",
        f"{NUM[N].capitalize()} nações disputam agora cada vale, cada porto e cada colina do continente. "
        f"E vocês governam uma delas: {nome}, com capital em {cap}.",
        HISTORIA.get(FID, "") + " A partir de agora, cada decisão desta sala vale território, comida e vidas.",
    ]),
    ("mapa", [
        "Este é o continente. São trinta e quatro territórios, em três regiões de clima: norte, centro e sul.",
        f"{curto} é esta mancha, {PREP[D['posicao']]} do continente. São quatro territórios: "
        f"{lista([f(t['nome']) for t in terr])}. " + fala_terreno,
        f"{fala_vizinhos} Cada uma dessas nações é outra sala, com outros alunos, "
        "ouvindo um briefing como este, agora mesmo.",
        fala_fronteira,
        f"Em volta de vocês há {NUM.get(len(D['neutros_vizinhos']), str(len(D['neutros_vizinhos'])))} territórios neutros, "
        "em cinza, defendidos por milícias. E as linhas tracejadas são rotas marítimas: a travessia custa o dobro "
        "de combustível, e fecha com tempestade.",
    ]),
    ("vitoria", [
        "Como se vence. Cada território vale um ponto de vitória. Cada capital vale mais dois. "
        "E cada desafio resolvido rende um quarto de ponto.",
        "Vocês começam com quatro territórios, um deles a capital: seis pontos. A guerra dura oito turnos. "
        "Vence quem terminar com mais pontos, ou quem dominar vinte e um dos trinta e quatro territórios antes disso.",
        "E cuidado: uma nação que perde todos os territórios, ou perde a capital e fica quase sem tropas "
        "e sem estoque, capitula, e sai da guerra.",
    ]),
    ("turno", [
        "A guerra anda em turnos de cerca de doze minutos. No começo de cada turno chega o briefing: "
        "cada seção recebe os próprios dados, num dossiê.",
        "Durante o turno, vocês calculam e enviam as ordens. Na metade, chega o telegrama-relâmpago, "
        "com ordens interceptadas do inimigo. Mandem uma ordem cedo, e corrijam depois: "
        "vale a última ordem enviada.",
        "Quando o relógio zera, o servidor resolve tudo ao mesmo tempo: produção, movimentos, batalhas, "
        "comida e moral. O mapa do projetor mostra o resultado, e começa o turno seguinte.",
    ]),
    ("secoes", [
        "A sala se divide em quatro seções. Cada uma decide uma parte da guerra, "
        "e cada uma usa uma ferramenta da álgebra linear.",
        "A Intendência cuida da economia. Decide quanto produzir de alimento, aço e combustível, "
        "resolvendo o sistema de Leôntief. E recruta os batalhões.",
        "Operações move as tropas e ataca. Prevê o clima com cadeias de Márkof, "
        "e calcula o resultado das batalhas com a lei de Lântchester.",
        "A Inteligência decifra as mensagens do inimigo, escritas na cifra de Ríl, "
        "e localiza os depósitos inimigos por mínimos quadrados, para bombardeá-los.",
        "E o Governo cuida da moral do povo, com regressão linear, e da diplomacia: "
        "pactos, transferências e telegramas para os outros governos.",
        "Com dez a dezesseis pessoas na sala, ponham de duas a quatro em cada seção. E escolham um chefe "
        "de estado-maior, que junta as informações e confere as ordens antes do prazo.",
    ]),
    ("jogo", [
        f"Esta é a tela do Quartel-General de {curto}. No alto, o timbre da nação: os estoques de alimento, "
        "aço e combustível, as tropas, os pontos de vitória e os territórios.",
        "Ao lado, o termômetro da moral do povo, e o relógio do turno. "
        "Quando ele zerar, valem as ordens que estiverem enviadas.",
        "Embaixo fica a pasta, com uma aba para cada seção. Cada aba traz o dossiê do turno, "
        "os dados em tabela, o desafio e o formulário da ordem.",
        "Na aba de Operações está o mapa, com névoa de guerra: "
        "vocês só enxergam o que as suas tropas alcançam.",
        "No rodapé, a gaveta da Mesa de Cálculo guarda as ferramentas de cada seção. "
        "Ninguém precisa programar: é colar os dados e calcular.",
        "E em cada aba, o botão de instrução em vídeo ensina, passo a passo, como resolver o problema daquela seção. "
        "O botão de briefing, lá em cima, reabre este vídeo.",
    ]),
    ("fim", [
        fala_conselho + " E não esqueçam: o alimento acaba rápido, e tropa com fome deserta.",
        f"Agora, dividam as seções, abram as abas, e esperem o sinal do árbitro. Boa sorte, Estado-Maior de {curto}.",
    ]),
]

CENAS = [(cena, [f(x) for x in falas]) for cena, falas in CENAS]

# ordem do vídeo: (classe do Manim ou "JOGO", cena com narração ou None)
SEQUENCIA = [("Titulo", None), ("Abertura", "abertura"), ("Mapa", "mapa"), ("Vitoria", "vitoria"),
             ("Turno", "turno"), ("Secoes", "secoes"), ("JOGO", "jogo"), ("Fim", "fim"), ("Creditos", None)]

if __name__ == "__main__":
    for cena, falas in CENAS:
        print(f"== {cena}")
        for x in falas:
            print("  -", x)
