"""Constantes de balanceamento e dados fixos das nações (ver docs/PLANO.md e docs/DESIGN.md).

Tudo o que o árbitro pode querer ajustar fica aqui. Os valores marcados com (*) foram
calibrados por simulação (server/tests/test_game_sim.py) e diferem do ponto de partida do PLANO.
"""

from __future__ import annotations

# --- tempo -----------------------------------------------------------------------------
TURN_MINUTES = 12
MAX_TURNS = 8

# --- combate -----------------------------------------------------------------------------
BATTLE_T = 0.9
BATTLE_NOISE_SIGMA = 0.08
NEUTRAL_MORALE = 60            # moral efetiva das milícias neutras
NEUTRAL_MILITIA = (3, 6)       # sorteio inclusivo

# --- estado inicial ------------------------------------------------------------------------
START_STOCK = {"ALI": 40.0, "ACO": 30.0, "COM": 30.0}
START_MORALE = 70.0
START_TROOPS_CAPITAL = 10
START_TROOPS_OTHER = 5

# --- economia ------------------------------------------------------------------------------
SECTORS = ["ALI", "ACO", "COM"]
LABOR = {"ALI": 1.0, "ACO": 1.5, "COM": 1.2}
LABOR_PER_TERRITORY = 18       # (*) PLANO: 12
HOURS_MULT = {8: 1.0, 10: 1.2, 12: 1.4}
A_SCALE = 0.65                 # (*) a matriz sorteada por engine.economy.random_A é multiplicada por isto
CAPACITY_MULT = 1.0
A_PERTURB_SCALE = 0.010        # variação de A de um turno para o outro
RECRUIT_COST = {"ALI": 2, "ACO": 2, "COM": 1}
UPKEEP_ALI_PER_BATTALION = 0.5
CIVIL_ALI = {0: 6, 1: 4, 2: 2}
MOVE_COM = 1
SEA_MOVE_COM = 2
BOMBARD_COM = 4
BOMBARD_STOCK_LOSS = 0.25
BOMBARD_A_DAMAGE = 0.05
PRODUCTIVITY_BONUS = 1.10
PROPAGANDA_MAX = 5

BETA0_RANGE = (-1.0, 0.5)      # (*) intercepto da moral (o motor sorteia +1 a +3)

# --- pontos e vitória ----------------------------------------------------------------------
CHALLENGE_VP = 0.25
CAPITAL_VP_EXTRA = 2
DOMINATION = 0.60
CAPITAL_LOST_MORALE = -15
STARVATION_MORALE = -10
STARVATION_ATTRITION = 0.10
DENOUNCE_MORALE = -5
CHALLENGE_REWARD_MORALE = 5
PACT_TURNS = 3
CHALLENGE_ATTEMPTS = 3
CIPHER_KEY_TURNS = 2
CAPITULATION_TROOPS = 3
CAPITULATION_STOCK = 10

# --- eventos ---------------------------------------------------------------------------------
EVENT_PROB = 0.6
EVENT_FIRST_TURN = 2

# --- tolerâncias dos desafios ----------------------------------------------------------------
TOL_LEONTIEF_REL = 0.02
TOL_LEONTIEF_ABS = 0.1
TOL_MARKOV = 0.03
TOL_BETA = 0.15
TOL_DEPOT_DIST = 25.0

# --- dados diversos ----------------------------------------------------------------------------
SECTIONS = ("intendencia", "operacoes", "inteligencia", "governo")
SECTION_NAMES = {
    "intendencia": "Intendência",
    "operacoes": "Operações",
    "inteligencia": "Inteligência",
    "governo": "Governo",
}
WEATHER_NAMES = ["limpo", "chuva", "tempestade"]
REGIONS = ["norte", "centro", "sul"]
DIARY_LENGTH = 44             # observações do diário meteorológico no início
SURVEY_ROWS = 25
MAX_TELEGRAMS = 60
MAX_NEWS = 200
MAX_MESSAGE_CHARS = 600
MAX_MOVES = 16
TELEGRAM_MAX_SYMBOLS = 140

# Ordem de preferência das nações; os slots ativos recebem-nas nesta ordem.
NATIONS = [
    {"id": "GAU", "name": "República de Gáussia", "short": "Gáussia", "capital": "Eliminópolis",
     "emblem": "∇", "color": "#2b4a74"},
    {"id": "EUL", "name": "Império de Eulerândia", "short": "Eulerândia", "capital": "Totiente",
     "emblem": "e", "color": "#8c2f23"},
    {"id": "HIL", "name": "Federação de Hilbertânia", "short": "Hilbertânia", "capital": "Ortonormal",
     "emblem": "⊥", "color": "#4d5b24"},
    {"id": "NOE", "name": "Reino de Noethéria", "short": "Noethéria", "capital": "Anelópolis",
     "emblem": "ℛ", "color": "#a87a1c"},
    {"id": "CAU", "name": "Principado de Cauchýria", "short": "Cauchýria", "capital": "Convergência",
     "emblem": "ε", "color": "#5b3a6b"},
    {"id": "RIE", "name": "Confederação de Riemânnia", "short": "Riemânnia", "capital": "Zeta",
     "emblem": "ζ", "color": "#3b5b5a"},
]
NATION_BY_ID = {n["id"]: n for n in NATIONS}

ACTIVE_SLOTS = {2: [0, 3], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 2, 3, 4], 6: [0, 1, 2, 3, 4, 5]}

# Vocabulário das senhas (português sem acento, fácil de ditar e digitar).
PASSWORD_WORDS = [
    "vetor", "ponte", "norte", "ferro", "aurora", "trigo", "farol", "bussola", "cavalo", "escudo",
    "lanca", "muralha", "trovao", "brasa", "fortim", "canhao", "vale", "serra", "cume", "lobo",
    "falcao", "aguia", "tigre", "urso", "raposa", "corvo", "ancora", "remo", "vela", "tocha",
    "bandeira", "medalha", "tambor", "clarim", "patrulha", "radar", "sinal", "codigo", "chave", "cifra",
    "mapa", "quadro", "relogio", "motor", "trilho", "balsa", "porto", "cais", "onda", "mare",
    "vento", "nuvem", "neve", "geada", "brisa", "areia", "pedra", "bosque", "campo", "colina",
    "rio", "lume", "alvorada", "tenda", "forja", "arado", "celeiro", "moinho", "sino", "pomar",
]

# Estações de escuta (base); cada nação recebe uma pequena variação.
STATION_BASE = [(110, 110), (1090, 110), (110, 690), (1090, 690)]
