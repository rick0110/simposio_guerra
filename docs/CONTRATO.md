# Contrato técnico (fonte da verdade para todos os módulos)

Qualquer agente/colaborador deve seguir este documento. Se algo precisar mudar, mude aqui primeiro.
Regras do jogo: ver `docs/DESIGN.md`.

## 0. Convenções
- Python 3.12, FastAPI, NumPy. Sem SciPy em runtime. Testes com `pytest` em `server/tests/`.
- Identificadores em inglês; termos do jogo em português sem acento nos códigos:
  seções `intendencia`, `operacoes`, `inteligencia`, `governo`; recursos `ALI`, `ACO`, `COM`;
  terrenos `planicie`, `floresta`, `montanha`, `pantano`, `urbano`; clima `limpo`, `chuva`, `tempestade`
  (índices 0, 1, 2); regiões climáticas `norte`, `centro`, `sul`.
- IDs de nação: `GAU`, `EUL`, `HIL`, `NOE`, `CAU`, `RIE` (slot 0..5 nessa ordem de preferência).
- Tempo sempre em **milissegundos epoch** (`int`). Funções do jogo recebem `now_ms` (testável).
- Toda aleatoriedade via `numpy.random.Generator` recebido por parâmetro (reprodutível por seed).
- Textos de interface em português do Brasil.

## 1. Estrutura de diretórios
```
Dockerfile, docker-compose.yml, README.md, .dockerignore
docs/        DESIGN.md, CONTRATO.md, PLANO.md, MANUAL_JOGADORES.md, MANUAL_ARBITRO.md
tools/       gen_map.py (gera server/app/data/map.json), toolkit.py (para jogadores)
server/
  requirements.txt
  app/
    __init__.py
    main.py              # cria FastAPI, monta rotas, estáticos, WS, laço do relógio
    config.py            # Settings (variáveis de ambiente)
    auth.py              # cookies assinados (HMAC)
    persistence.py       # snapshot atômico /data/state.json + /data/turns/turn_XX.json
    hub.py               # WebSocket hub (canais)
    routes_public.py, routes_faction.py, routes_admin.py, routes_tools.py
    data/map.json        # gerado por tools/gen_map.py (versionado)
    engine/              # MATEMÁTICA PURA, sem estado do jogo
      __init__.py, linalg.py, cipher.py, economy.py, combat.py, weather.py, geo.py, morale.py
    game/                # REGRAS DO JOGO, sem FastAPI
      __init__.py, balance.py, model.py, setup.py, dossiers.py, resolution.py, news.py, events.py, game.py
  tests/
web/
  index.html, teatro.html, qg.html, arbitro.html
  css/fonts.css, css/base.css (tokens + componentes), css/map.css, css/teatro.css, css/qg.css, css/arbitro.css
  js/api.js, js/ws.js, js/sfx.js, js/map.js, js/teatro.js, js/qg.js, js/calc.js, js/arbitro.js, js/login.js
  fonts/*.woff2
  mock/*.json            # respostas de exemplo da API (para desenvolver front sem servidor)
```
O servidor serve `web/` em `/` (`/teatro` → `teatro.html`, `/qg` → `qg.html`, `/arbitro` → `arbitro.html`).

## 2. `map.json`
```jsonc
{
  "width": 1200, "height": 800,
  "grid": {"cell": 50, "cols": "ABCDEFGHIJKLMNOPQRSTUVWX", "rows": 16},
  //  quadrícula "K7": coluna K (x de 500 a 550), linha 7 (y de 300 a 350). Linhas 1-based.
  "climate_regions": [{"id": "norte", "name": "Norte"}, {"id": "centro", "name": "Centro"}, {"id": "sul", "name": "Sul"}],
  "home_slots": [{"slot": 0, "capital": "T03", "territories": ["T01","T02","T03","T04"]}],   // 6 slots, 4 territórios cada
  "territories": [{
    "id": "T01", "name": "Vale de Cramer",
    "polygon": [[x, y], ...],          // anel fechado implícito, sentido qualquer
    "centroid": [x, y], "label_pos": [x, y],
    "terrain": "planicie", "climate": "norte",
    "home_slot": 0,                    // ou null (neutro)
    "capital": false,
    "capacity": {"ALI": 12, "ACO": 4, "COM": 3},
    "neighbors": ["T02", "T05"],       // vizinhos terrestres
    "sea_neighbors": ["T19"],          // vizinhos por rota marítima
    "coastal": true
  }],
  "sea_routes": [{"a": "T05", "b": "T19", "path": [[x, y], ...]}],
  "land": [[[x, y], ...]],             // contornos de massas de terra (continente + ilhas)
  "rivers": [[[x, y], ...]],
  "relief": [[[x, y], ...]],           // traços decorativos de relevo (hachuras/curvas de nível)
  "labels": [{"text": "MAR DE BANACH", "pos": [x, y], "kind": "sea", "angle": -8}]
}
```
34 territórios: 6 pátrias × 4 + 10 neutros. Vizinhança simétrica. Grafo conexo (com rotas marítimas).

## 3. `engine/` (funções puras — assinaturas obrigatórias)
Matrizes entram/saem como `list[list[float]]` ou `np.ndarray` (aceitar ambos; retornar listas
quando for para JSON é responsabilidade de quem chama). Erros → `ValueError` com mensagem em português.

### `engine/linalg.py`
```python
def det(A) -> float
def inv(A) -> np.ndarray
def solve(A, b) -> np.ndarray
def lstsq(A, b) -> tuple[np.ndarray, float]          # (x, soma dos resíduos²)
def eig(A) -> tuple[list[complex|float], np.ndarray] # autovalores, autovetores (colunas)
def mat_pow(A, k: int) -> np.ndarray
def stationary(P) -> np.ndarray                       # vetor estacionário (soma 1) de matriz estocástica por LINHAS
def matmul(A, B) -> np.ndarray
def mod_inv_int(a: int, m: int) -> int
def mod_inv_matrix(K, m: int = 37) -> np.ndarray      # inversa inteira mod m (2x2 e 3x3), ValueError se det ≡ 0
```
### `engine/cipher.py`
```python
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "  # 37 símbolos, espaço = 36
M = 37
def normalize(text: str) -> str            # maiúsculas, remove acentos (Ç→C), outros símbolos → espaço, colapsa espaços
def to_nums(text: str) -> list[int]
def to_text(nums) -> str
def random_key(rng, n: int = 2) -> np.ndarray        # det invertível mod 37
def encrypt(plain: str, K) -> str          # normaliza, completa com espaço até múltiplo de n, c = K·p (vetores-coluna consecutivos)
def decrypt(cipher: str, K) -> str
def recover_key(plain_crib: str, cipher_crib: str, n: int = 2) -> np.ndarray   # K = C·P⁻¹ mod 37, tenta blocos até achar P invertível
```
### `engine/economy.py`
```python
SECTORS = ["ALI", "ACO", "COM"]
def random_A(rng) -> np.ndarray                      # 3x3, entradas 0.05–0.30, somas de coluna < 0.6 (produtiva)
def perturb_A(A, rng, scale: float = 0.02, damage: float = 0.0) -> np.ndarray  # damage soma à diagonal; mantém produtiva
def transactions(A, x) -> np.ndarray                 # Z = A·diag(x)
def A_from_transactions(Z, X) -> np.ndarray          # A = Z·diag(X)⁻¹
def net_output(A, x) -> np.ndarray                   # (I − A)·x
def required_production(A, d) -> np.ndarray          # resolve (I − A)x = d
def labor_used(L, x) -> float
```
### `engine/combat.py`
```python
TERRAIN_DEFENSE = {"planicie": 1.0, "floresta": 1.25, "montanha": 1.5, "pantano": 1.2, "urbano": 1.3}
WEATHER_ATTACK = {0: 1.0, 1: 0.85, 2: 0.65}
def effectiveness(morale: float, terrain: str | None = None, weather: int | None = None, role: str = "attack") -> float
    # base (0.5 + morale/100); defensor × TERRAIN_DEFENSE[terrain]; atacante × WEATHER_ATTACK[weather]
def lanchester(A0: float, B0: float, alpha: float, beta: float, T: float = 0.9, steps: int = 60) -> dict
    # A' = −beta·B ; B' = −alpha·A   (alpha = eficácia do atacante A, beta = eficácia do defensor B)
    # solução fechada: w = sqrt(alpha·beta); A(t) = A0·cosh(wt) − sqrt(beta/alpha)·B0·sinh(wt); B(t) = B0·cosh(wt) − sqrt(alpha/beta)·A0·sinh(wt)
    # para no primeiro t em que um lado zera, ou em T.
    # retorna {"a_final", "b_final", "t_end", "winner": "attacker"|"defender"|"none", "trajectory": [[t, A, B], ...]}
    # winner = "attacker" se B zerou; "defender" se A zerou; "none" se ninguém zerou até T.
```
### `engine/weather.py`
```python
STATES = ["limpo", "chuva", "tempestade"]
def random_transition_matrix(rng, n: int = 3, persistence: tuple = (0.45, 0.8)) -> np.ndarray   # estocástica por linhas, diagonal dominante
def simulate(P, start: int, steps: int, rng) -> list[int]
def estimate_P(seq: list[int], n: int = 3) -> np.ndarray       # contagem de transições, linhas sem dados → uniforme
def forecast(P, state: int, k: int = 1) -> np.ndarray           # linha `state` de P^k
```
### `engine/geo.py`
```python
def grid_label(x, y, cell=50, cols="ABCDEFGHIJKLMNOPQRSTUVWX") -> str     # (525, 310) → "K7"
def grid_center(label, cell=50, cols=...) -> tuple[float, float]
def point_in_polygon(pt, polygon) -> bool
def random_point_in_polygon(polygon, rng) -> tuple[float, float]
def station_readings(target, stations, rng, noise: float = 8.0) -> list[float]   # distâncias com ruído gaussiano
def trilaterate(stations, distances) -> tuple[float, float]   # lineariza subtraindo a 1ª equação, mínimos quadrados
```
### `engine/morale.py`
```python
FEATURES = ["racao", "propaganda", "horas_extra", "baixas", "saldo_territorial"]
def random_betas(rng) -> np.ndarray       # [β0..β5]; sinais: ração −, propaganda +, horas −, baixas −, saldo +
def survey(betas, rng, n: int = 25, noise: float = 1.5) -> list[dict]   # linhas com FEATURES + "delta_moral"
def ols(rows, features=FEATURES, target="delta_moral") -> np.ndarray   # [β0..β5] por equações normais
def delta_morale(betas, feats: dict, rng=None, noise: float = 1.0) -> float
```
`baixas` nas features = baixas/10 (dezenas de batalhões perdidos).

## 4. `game/` — interface da classe `Game` (usada pela camada HTTP)
```python
class Game:
    @classmethod
    def new(cls, map_data: dict, n_factions: int = 4, turn_minutes: float = 12, max_turns: int = 8, seed: int | None = None) -> "Game"
    def to_dict(self) -> dict ; @classmethod from_dict(cls, d: dict, map_data: dict) -> "Game"
    # ciclo de vida (status: "lobby" | "running" | "paused" | "finished")
    def start(self, now_ms) -> list[Event]
    def pause(self, now_ms) -> list[Event]
    def resume(self, now_ms) -> list[Event]
    def extend(self, now_ms, minutes: float) -> list[Event]
    def tick(self, now_ms) -> list[Event]          # chamado a cada ~1 s: telegrama-relâmpago na metade, resolução no prazo
    def resolve_turn(self, now_ms) -> list[Event]
    # visões (já filtradas pela névoa de guerra; nunca expõem segredos)
    def public_map(self) -> dict                    # map.json com nomes das capitais trocados pelos das nações
    def public_view(self, now_ms) -> dict
    def faction_view(self, fid, now_ms) -> dict
    def dossier_view(self, fid, section) -> dict
    def dataset_csv(self, fid, section, dataset_id) -> str
    def admin_view(self, now_ms) -> dict            # tudo, inclusive segredos
    # ações
    def check_password(self, fid, password) -> bool
    def credentials(self) -> dict[str, str]
    def submit_orders(self, fid, section, payload: dict, now_ms) -> dict   # {"ok", "errors": [], "warnings": [], "order"}
    def answer_challenge(self, fid, challenge_id, answer: str, now_ms) -> dict  # {"correct", "message", "attempts_left", "reward"}
    def send_message(self, fid, to_fid, text, now_ms) -> list[Event]
    def admin_broadcast(self, text, to: str, now_ms) -> list[Event]   # to = "all" ou fid
    def admin_edit_faction(self, fid, patch: dict, now_ms) -> list[Event]
    def admin_trigger_event(self, event_id: str, now_ms) -> list[Event]

Event = {"channel": "public" | "faction:GAU" | "admin", "type": str, "data": dict}
```
`main.py` guarda uma instância `Game`, chama `tick` a cada segundo, salva snapshot depois de cada
ação que muda estado, e publica cada `Event` no canal do WebSocket. Todo evento de `public` também
vai para todas as facções e para o admin; eventos `faction:X` também vão para o admin.

Tipos de evento: `phase` (mudou status/turno/fase), `state` (algo mudou → cliente refaz GET),
`dossier` (dossiê novo), `telegram` (telegrama novo para a facção), `broadcast` (aviso do árbitro),
`news` (manchete nova), `resolution` (relatório do turno: batalhas, para animação), `message` (diplomacia).

## 5. API HTTP
Cookie `em_session` (HMAC, HttpOnly, SameSite=Lax) carrega `{"fid": "GAU"}` ou `{"admin": true}`.
Erros: HTTP 4xx com `{"detail": "mensagem em português"}`.

### Público
| Método e rota | Resposta |
|---|---|
| `GET /api/public/map` | `map.json` (nomes das capitais já trocados pelos da nação dona do slot) |
| `GET /api/public/state` | ver abaixo |
| `POST /api/login` `{faction_id, password}` | `{ok: true, faction_id}` + cookie |
| `POST /api/logout` | `{ok: true}` |
| `GET /api/me` | `{faction_id: "GAU" \| null, admin: bool}` |
| `GET /api/server_time` | `{now_ms}` (sincronizar relógio) |

```jsonc
// GET /api/public/state
{
  "game": {"status": "running", "turn": 3, "max_turns": 8, "phase": "planejamento",
           "deadline_ms": 1760000000000, "remaining_ms": 412000, "turn_ms": 720000, "now_ms": 1759999588000},
  "factions": [{"id": "GAU", "name": "República de Gáussia", "short": "Gáussia", "color": "#2b4a74", "emblem": "∇",
                "capital": "T03", "capitulated": false, "vp": 7.5, "territories": 5}],
  "territories": [{"id": "T01", "owner": "GAU"}],          // owner null = neutro
  "weather": {"norte": 0, "centro": 1, "sul": 2},            // clima vigente (do turno resolvido)
  "news": [{"turn": 2, "headline": "...", "body": "...", "kind": "battle|capture|event|politics|weather"}], // mais recente primeiro, até 20
  "last_resolution": {"turn": 2, "battles": [{"from": "T02", "to": "T07", "attacker": "GAU", "defender": "EUL",
                       "att_before": 12, "def_before": 6, "att_after": 8, "def_after": 0, "result": "captured"}],
                       "moves": [{"from": "T01", "to": "T02", "faction": "GAU", "troops": 4}]}
}
```

### Facção (cookie de facção)
| Método e rota | Corpo / resposta |
|---|---|
| `GET /api/faction/state` | ver abaixo |
| `GET /api/faction/dossier/{section}` | ver abaixo |
| `GET /api/faction/dossier/{section}/{dataset_id}.csv` | `text/csv` |
| `POST /api/faction/orders/{section}` | payload da seção → `{ok, errors, warnings, order}` |
| `POST /api/faction/challenge/{challenge_id}` | `{answer: "texto"}` → `{correct, message, attempts_left, reward}` |
| `POST /api/faction/message` | `{to_faction, text}` → `{ok}` (só faz sentido para o Governo, mas não é restrito) |

```jsonc
// GET /api/faction/state
{
  "faction": {"id": "GAU", "name": "...", "color": "#2b4a74", "emblem": "∇", "capital": "T03",
              "stock": {"ALI": 40, "ACO": 30, "COM": 30}, "morale": 70, "troops_total": 25,
              "workforce": 48, "labor": {"ALI": 1.0, "ACO": 1.5, "COM": 1.2},
              "capacity": {"ALI": 40, "ACO": 18, "COM": 16}, "vp": 4, "policy": {"racao": 0, "propaganda": 0, "horas": 8},
              "pacts": [{"with": "EUL", "until_turn": 5}], "pact_proposals_received": ["NOE"], "capitulated": false,
              "bonuses": {"productivity": false, "weather_revealed": false, "depot_located": null}},
  "territories": [{"id": "T01", "owner": "GAU", "troops": 5, "troops_range": null, "visibility": "own"},
                  {"id": "T07", "owner": "EUL", "troops": null, "troops_range": "6–10", "visibility": "adjacent"},
                  {"id": "T20", "owner": "NOE", "troops": null, "troops_range": null, "visibility": "hidden"}],
                  // visibility: own | adjacent | revealed | hidden
  "orders": {"intendencia": null, "operacoes": {...}, "inteligencia": null, "governo": null},  // última submissão por seção
  "telegrams": [{"id": "tg-3-1", "turn": 3, "at_ms": 0, "kind": "intercept|flash|report|broadcast|diplomacy",
                 "from": "EUL", "title": "INTERCEPTAÇÃO — EULERÂNDIA", "body": "texto (cifrado, se interceptado)",
                 "section": "inteligencia"}],   // section null = todas
  "messages": [{"from": "NOE", "to": "GAU", "turn": 3, "text": "...", "at_ms": 0}],
  "last_report": {"turn": 2, "lines": ["Produção líquida: ALI +12.3 ...", "..."]},
  "game": { /* igual a public_state.game */ }
}
```

```jsonc
// GET /api/faction/dossier/{section}
{
  "section": "intendencia", "turn": 3, "title": "DOSSIÊ DA INTENDÊNCIA — TURNO 3",
  "briefing": "Texto datilografado (parágrafos separados por \n\n).",
  "datasets": [{"id": "transacoes", "title": "Tabela de transações intersetoriais (turno 2)",
                "description": "...", "columns": ["", "ALI", "ACO", "COM"],
                "rows": [["ALI", 4.1, 2.0, 1.2], ["ACO", 1.0, 3.3, 2.2], ["COM", 0.8, 1.9, 2.5]],
                "csv_url": "/api/faction/dossier/intendencia/transacoes.csv"}],
  "challenges": [{"id": "c3-intendencia", "prompt": "...", "answer_format": "três números separados por vírgula: x_ALI, x_ACO, x_COM",
                  "attempts_left": 3, "solved": false, "reward_text": "+10% de produtividade neste turno"}],
  "tools": ["leontief", "matrix"],      // ferramentas sugeridas da Mesa de Cálculo
  "extras": {}                          // dados específicos (ex.: inteligencia → {"crib": "URGENTE ", "stations": [[x,y],...]})
}
```

### Payloads de ordens
```jsonc
// intendencia
{"production": {"ALI": 30, "ACO": 12, "COM": 10}, "recruit": 3}
// operacoes
{"moves": [{"from": "T02", "to": "T07", "troops": 8}]}
// inteligencia
{"bombard": "T22"}            // ou null; só válido se depósito localizado neste turno
// governo
{"racao": 0, "propaganda": 2, "horas": 10,
 "transfers": [{"to": "NOE", "ALI": 5, "ACO": 0, "COM": 0}],
 "pact_propose": ["NOE"], "pact_denounce": []}
```
Validação no envio (erros impedem; avisos não): vizinhança, tropas disponíveis, pacto, produção ≥ 0,
limites de capacidade, etc. Recursos são checados de novo na resolução (escala proporcional).

### Mesa de Cálculo (sem login): `POST /api/tools/{tool}`
| tool | entrada | saída |
|---|---|---|
| `matrix` | `{op: "det"\|"inv"\|"solve"\|"lstsq"\|"eig"\|"pow"\|"mul"\|"transpose"\|"stationary", A, B?, b?, k?}` | `{result, ...}` |
| `modinv` | `{K, m?}` | `{result}` |
| `hill_recover` | `{plain, cipher, n?}` | `{key}` |
| `hill_decrypt` | `{cipher, key}` | `{plain}` |
| `hill_encrypt` | `{plain, key}` | `{cipher}` |
| `leontief` | `{Z?, X?, A?, d?, x?, L?}` | `{A?, x_required?, net?, labor?}` |
| `markov` | `{sequence?: [int\|str], P?, state?, k?}` | `{P_estimated?, forecast?, stationary?}` |
| `trilaterate` | `{stations: [[x,y]...], distances: [...]}` | `{x, y, grid}` |
| `regression` | `{rows: [{...}], features: [...], target}` ou `{csv, target}` | `{coefficients: {nome: valor}, r2}` |
| `lanchester` | `{A0, B0, alpha, beta, T?}` | saída de `combat.lanchester` |
Respostas sempre JSON serializável (listas, floats arredondados a 6 casas, complexos como `[re, im]`).

### Árbitro (cookie admin)
`POST /api/admin/login {password}` · `GET /api/admin/state` · `GET /api/admin/credentials` ·
`POST /api/admin/new_game {n_factions, turn_minutes, max_turns, seed?}` · `POST /api/admin/start` ·
`/pause` · `/resume` · `/extend {minutes}` · `/resolve_now` · `/rollback {turn}` ·
`/broadcast {text, to}` · `/edit_faction {faction_id, patch}` · `/event {event_id}`.
`GET /api/admin/events` → lista de eventos disponíveis `[{id, name, description}]`.

### WebSocket `GET /ws?ch=public|faction|admin`
Facção/admin autenticados pelo cookie. Mensagens servidor→cliente: `{"type", "data"}` (o `Event`
sem o campo channel). Cliente reconecta com backoff; ao (re)conectar, refaz os GETs.

## 6. Front-end: sistema visual (`web/css/base.css`)
Tokens e componentes já definidos em `web/css/base.css` — **use as classes existentes**, não
invente outra paleta. Fontes locais em `web/css/fonts.css` (sem CDN: a rede do evento pode não ter
internet). JS em módulos ES (`<script type="module">`), sem frameworks, sem build.
`web/js/api.js` exporta `api.get(path)`, `api.post(path, body)`, `api.tool(name, body)`;
`web/js/ws.js` exporta `connect(channel, onMessage)`; `web/js/sfx.js` exporta `sfx.key()`,
`sfx.stamp()`, `sfx.morse(text)`, `sfx.alarm()` (WebAudio, mudo até o primeiro clique);
`web/js/map.js` exporta `renderMap(svgEl, mapData, options)` e `updateMap(state)`.
