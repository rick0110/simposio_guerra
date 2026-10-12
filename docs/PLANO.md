# Plano de ação

Execução em ondas. Cada pacote tem dono (modelo), arquivos que pode tocar, critério de pronto.
Agentes da mesma onda trabalham em paralelo em arquivos **disjuntos**; o coordenador integra,
testa, faz commit/push e sincroniza o Google Drive ao fim de cada onda.

| Onda | Pacote | Modelo | Arquivos | Pronto quando |
|---|---|---|---|---|
| 0 | Design, contrato, sistema visual base | coordenador | `docs/DESIGN.md`, `docs/CONTRATO.md`, `docs/PLANO.md`, `web/css/base.css` | publicado |
| 1 | **A — Motor matemático** + rotas da Mesa de Cálculo | Haiku | `server/app/engine/*`, `server/app/routes_tools.py`, `server/tests/test_engine*.py`, `server/tests/test_tools.py` | `pytest` verde; todas as assinaturas do contrato §3 |
| 1 | **B — Gerador do mapa** | Sonnet | `tools/gen_map.py`, `server/app/data/map.json`, `server/tests/test_map.py`, `web/mock/map.json` | 34 territórios válidos, grafo conexo, prévia SVG |
| 1 | **C — Infra Docker, config, fontes** | Haiku | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `server/requirements.txt`, `server/app/config.py`, `web/fonts/*`, `web/css/fonts.css`, `README.md` | `docker build` ok; fontes locais |
| 2 | **D1 — Núcleo do jogo** (`Game`) | Sonnet | `server/app/game/*`, `server/tests/test_game*.py` | partida simulada de 8 turnos sem erro; balanceamento verificado |
| 2 | **D2 — Camada HTTP/WS** | Haiku | `server/app/main.py`, `auth.py`, `persistence.py`, `hub.py`, `routes_public.py`, `routes_faction.py`, `routes_admin.py`, `server/tests/test_api.py` | testes de API com `TestClient` |
| 2 | **E — Mapa, Teatro e Portão** | Sonnet | `web/js/map.js`, `web/css/map.css`, `web/teatro.html`, `web/css/teatro.css`, `web/js/teatro.js`, `web/index.html`, `web/js/login.js`, `web/js/api.js`, `web/js/ws.js`, `web/js/sfx.js`, `web/mock/public_state.json` | telas funcionam com mocks e com servidor |
| 3 | **F — Quartel-General + Mesa de Cálculo** | Haiku | `web/qg.html`, `web/css/qg.css`, `web/js/qg.js`, `web/js/calc.js`, `web/mock/faction_*.json`, `web/mock/dossier_*.json` | 4 seções completas |
| 3 | **F2 — Painel do Árbitro** | Haiku | `web/arbitro.html`, `web/css/arbitro.css`, `web/js/arbitro.js` | todas as ações do árbitro |
| 4 | **G — Manuais e toolkit** | Haiku | `docs/MANUAL_JOGADORES.md`, `docs/MANUAL_ARBITRO.md`, `tools/toolkit.py` | revisado |
| 4 | Integração, testes E2E (Playwright), capturas de tela, ajustes | coordenador + Sonnet | — | partida completa jogada no navegador via Docker |

Sincronização com o Drive (pasta "Guerra"): ao fim de cada onda, o código é espelhado em
`Guerra/estado-maior/…` mantendo a estrutura de pastas. O repositório Git é a fonte da verdade.

## Constantes de balanceamento (ponto de partida, `game/balance.py`)
```
TURN_MINUTES=12  MAX_TURNS=8  BATTLE_T=0.9  BATTLE_NOISE_SIGMA=0.08
START_STOCK={ALI:40, ACO:30, COM:30}  START_MORALE=70  START_TROOPS: capital 10, demais 5
LABOR={ALI:1.0, ACO:1.5, COM:1.2}  LABOR_PER_TERRITORY=18 (era 12; ajustado por simulação)  HOURS_MULT={8:1.0, 10:1.2, 12:1.4}
WORKFORCE = LABOR_PER_TERRITORY × nº territórios × HOURS_MULT × (0.6 + 0.4·moral/100)
RECRUIT_COST={ALI:2, ACO:2, COM:1}  UPKEEP_ALI_PER_BATTALION=0.5  CIVIL_ALI={0:6, 1:4, 2:2}
MOVE_COM=1  SEA_MOVE_COM=2  BOMBARD_COM=4  BOMBARD_STOCK_LOSS=0.25  BOMBARD_A_DAMAGE=0.05
PRODUCTIVITY_BONUS=1.10  CHALLENGE_VP=0.25  CAPITAL_VP_EXTRA=2  DOMINATION=0.60
CAPITAL_LOST_MORALE=-15  STARVATION_MORALE=-10  STARVATION_ATTRITION=0.10  DENOUNCE_MORALE=-5
PACT_TURNS=3  CHALLENGE_ATTEMPTS=3  CIPHER_KEY_TURNS=2  NEUTRAL_MILITIA=3..6 (moral 60)
A_SCALE=0.65 (matriz A sorteada × 0,65)  A_PERTURB_SCALE=0.010  BETA0_RANGE=(-1.0, 0.5)
```
Os valores finais estão em `server/app/game/balance.py` (fonte da verdade).
```
```
