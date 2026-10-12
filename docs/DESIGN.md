# ESTADO-MAIOR — A Guerra do Continente de Lebesgue

Documento de design do jogo "Guerra" do Simpósio (Guia da Equipe Auxiliar).

## 1. Requisitos do guia (resumo)

| Requisito do guia | Como o jogo atende |
|---|---|
| Grupos de 8 a 16 pessoas por sala de laboratório | Cada sala é uma **nação** (facção). 2 a 6 nações, padrão 4. |
| Grupo dividido em seções com funções específicas | 4 seções por nação: **Intendência, Operações, Inteligência, Governo** (2–4 pessoas cada). |
| Decisões refletidas num site com campo de batalha | Servidor central (Docker) com o **Teatro de Operações** (mapa público, projetor) e o **Quartel-General** de cada nação. |
| Página específica por grupo, com senha | Login por nação (senha gerada pelo árbitro). Dentro, cada seção tem sua aba. |
| Bases de dados entregues individualmente, de tempos em tempos (não prontas) | A cada turno o servidor **gera dossiês novos** a partir do estado real do jogo (e um "telegrama-relâmpago" no meio do turno). |
| Funções que tratem os dados (não exigir programação) | **Mesa de Cálculo** embutida no site (matrizes, Hill, Leontief, Markov, triangulação, regressão, Lanchester) + `toolkit.py` opcional. |
| Evitar muitas variáveis | Só 3 recursos (Alimento, Aço, Combustível) + Tropas + Moral. |
| Evitar fazer tudo à mão | Todo cálculo pesado tem ferramenta; a decisão é humana. |
| Tema do simpósio: álgebra linear | Cada seção resolve um problema clássico de álgebra linear com dados reais do jogo. |
| Site não frágil (não quebrar com "inspecionar") | Toda lógica, gabaritos e segredos ficam no servidor; o cliente só recebe o que sua nação pode ver. |

## 2. Premissa

O Continente de Lebesgue, 1943 (ficcional). Seis nações disputam o continente. Cada sala de
laboratório é o Quartel-General de uma delas. Vence quem tiver mais **Pontos de Vitória (PV)** ao
final da guerra (ou dominar o continente).

| Código | Nação | Capital | Emblema | Cor (tinta) |
|---|---|---|---|---|
| GAU | República de Gáussia | Eliminópolis | ∇ | `#2b4a74` azul-prussiano |
| EUL | Império de Eulerândia | Totiente | e | `#8c2f23` sangue-de-boi |
| HIL | Federação de Hilbertânia | Ortonormal | ⊥ | `#4d5b24` oliva |
| NOE | Reino de Noethéria | Anelópolis | ℛ | `#a87a1c` mostarda |
| CAU | Principado de Cauchýria | Convergência | ε | `#5b3a6b` púrpura-ameixa |
| RIE | Confederação de Riemânnia | Zeta | ζ | `#3b5b5a` verde-ardósia |

Com menos de 6 nações, as "pátrias" não usadas viram território neutro (milícias). Os slots ativos
são escolhidos para equilíbrio (2: 0,3 · 3: 0,2,4 · 4: 0,1,3,4 · 5: 0–4 · 6: todos).

## 3. Recursos e números

- **Alimento (ALI)**, **Aço (ACO)**, **Combustível (COM)** — estoques inteiros/decimais por nação.
- **Batalhões** (tropas) — inteiros, alocados em territórios.
- **Moral** (0–100) — afeta combate e mão de obra.
- Estado inicial: pátria de 4 territórios (capital com 10 batalhões, demais 5), estoque
  ALI 40 / ACO 30 / COM 30, moral 70.

## 4. O turno

Turnos cronometrados (padrão **12 min**, padrão **8 turnos**; o árbitro pode pausar/estender/forçar).

1. **Briefing** (instantâneo): servidor gera os dossiês de cada seção de cada nação. Chega como telegrama.
2. **Planejamento**: as seções analisam dados, resolvem desafios (opcionais, dão recompensas) e
   enviam ordens. Podem reenviar até o prazo; vale a última. Na metade do turno chega o
   **telegrama-relâmpago** interceptado (para a Inteligência).
3. **Resolução**: no prazo, o servidor resolve tudo simultaneamente, anima o mapa no Teatro e publica
   as manchetes do jornal "O Arauto do Front".

### Ordem de resolução
1. Congela as ordens.
2. Governo: transferências entre nações, pactos, política (ração, propaganda, jornada).
3. Intendência: produção (Leontief) limitada por mão de obra e capacidade.
4. Recrutamento (custo por batalhão: ALI 2, ACO 2, COM 1), aparece na capital.
5. Inteligência: bombardeios a depósitos localizados.
6. Operações: movimentos (1 COM por batalhão; rota marítima 2 COM; tempestade fecha o mar), depois batalhas (Lanchester).
7. Manutenção: 0,5 ALI por batalhão + consumo civil (6/4/2 conforme ração). Falta de alimento: moral −10 e atrito de 10%.
8. Moral (modelo linear oculto + ruído). Perda da capital: −15.
9. Capitulação, PV, fim de jogo.
10. Manchetes; prepara o próximo turno (clima sorteado, depósitos realocados, nova matriz A, dossiês).

## 5. As quatro seções

Todo desafio é **corrigido contra os dados entregues** (não contra o segredo do servidor), com
tolerância. Até 3 tentativas; a recompensa vem na primeira resposta correta. Cada desafio resolvido
vale +0,25 PV.

### 5.1 Intendência (Economia e Logística) — Modelo de Leontief
- Três setores: Agricultura → ALI, Siderurgia → ACO, Refinaria → COM.
- Matriz técnica oculta **A** (3×3), que muda levemente a cada turno (e piora com bombardeios).
- Dossiê: tabela de transações intersetoriais **Z** e produção total **X** do turno anterior,
  coeficientes de mão de obra **L**, força de trabalho **W**, capacidades, estoque, previsão de consumo.
- Decisão: produção bruta **x = (x_ALI, x_ACO, x_COM)** e número de batalhões a recrutar.
  Produção líquida que entra no estoque: **y = (I − A)x**. Restrições: L·x ≤ W e x_i ≤ capacidade_i.
- Desafio: "Que produção bruta x entrega a demanda d* = (…)?" → resolver **(I − A)x = d\*** com
  A = Z·diag(X)⁻¹. Recompensa: **+10% de produtividade** neste turno ("Plano aprovado").

### 5.2 Operações (Estado-Maior de Campo) — Cadeias de Markov e EDO de Lanchester
- Decisão: ordens de movimento `{de, para, batalhões}` para territórios vizinhos. Para território
  próprio = reforço; inimigo/neutro = ataque.
- Combate pela **lei quadrática de Lanchester**: A' = −β·B, B' = −α·A, durante T = 0,9 (matriz
  com autovalores ±√(αβ)). Se o defensor zera antes de T, o atacante toma o território; senão o
  atacante recua com os sobreviventes. Modificadores: terreno do defensor (montanha 1,5; urbano 1,3;
  floresta 1,25; pântano 1,2; planície 1,0), moral (0,5 + moral/100), clima do atacante (chuva 0,85;
  tempestade 0,65), ruído log-normal pequeno ("névoa da guerra").
- Clima: 3 estados (limpo, chuva, tempestade) por região climática (norte, centro, sul), cada uma
  uma **cadeia de Markov** oculta.
- Dossiê: diário meteorológico (40+ observações por região, cresce a cada turno), avistamentos de
  fronteira (faixas de tropas inimigas vizinhas), tabela de modificadores.
- Desafio: "Dado o clima atual em R, qual a probabilidade de tempestade no próximo turno?"
  (estimar P por contagem de transições). Recompensa: o servidor revela **o clima exato** que fará
  na resolução em todas as regiões.

### 5.3 Inteligência (SIGINT e Reconhecimento) — Cifra de Hill sobre ℤ₃₇ e Mínimos Quadrados
- **Telegramas interceptados** cifrados com Hill 2×2 sobre o alfabeto de 37 símbolos
  `A–Z 0–9 espaço` (37 é primo → ℤ₃₇ é corpo). O texto vem do **estado real do inimigo**
  (briefing) e das **ordens reais que o inimigo já enviou** (telegrama-relâmpago, na metade do turno).
  Toda mensagem de uma nação começa com o cabeçalho conhecido "URGENTE " (pedra de roseta):
  com 2 pares conhecidos, K = C·P⁻¹ (mod 37). A chave de cada nação muda a cada 2 turnos.
  A recompensa é a própria informação.
- **Radiogoniometria**: 4 estações de escuta medem distâncias (com ruído) até o depósito de
  suprimentos de um inimigo. Linearizando os círculos, resolve-se por **mínimos quadrados**.
- Desafio: coordenadas (x, y) ou quadrícula (ex.: `K7`) do depósito. Recompensa: revela as tropas
  exatas daquele território e libera a ordem **Bombardear depósito** (custa 4 COM; o inimigo perde
  25% do seu maior estoque e sua matriz A piora no próximo turno).

### 5.4 Governo (Gabinete) — Regressão Linear Múltipla e Diplomacia
- Decisões: ração (0 normal, 1 reduzida, 2 severa), propaganda (0–5 ACO), jornada (8/10/12 h:
  mão de obra ×1,0/1,2/1,4), transferências de recursos, pactos de não agressão, telegramas
  diplomáticos aos outros Governos.
- A moral segue um modelo linear oculto com coeficientes "culturais" de cada nação:
  Δmoral = β₀ + β₁·ração + β₂·propaganda + β₃·(horas−8) + β₄·baixas/10 + β₅·saldo_territorial + ruído.
- Dossiê: pesquisa de opinião com ~25 observações (ração, propaganda, horas_extra, baixas,
  saldo_territorial, delta_moral).
- Desafio: estimar β₂ (efeito da propaganda) por **mínimos quadrados** (equações normais).
  Recompensa: **+5 de moral**.
- Pactos: ambos propõem → pacto ativo por 3 turnos, ataques entre eles bloqueados. Denunciar encerra
  o pacto ao fim do turno e custa 5 de moral.

## 6. Névoa de guerra
- Territórios próprios: tropas exatas. Vizinhos (inclui rotas marítimas): dono + faixa
  (`1–5`, `6–10`, `11–20`, `21+`). Demais: só o dono (cores do mapa são públicas).
- Reconhecimento bem-sucedido revela tropas exatas de um território no turno.

## 7. Vitória
- PV = 1 por território + 2 extras por capital controlada + 0,25 por desafio resolvido.
- Fim: após o último turno, ou dominação (≥ 60% dos territórios), ou só uma nação não capitulada.
- Capitulação: sem territórios, ou (sem capital e menos de 3 batalhões e estoque total < 10).

## 8. Eventos
A partir do turno 2, com probabilidade 0,6, um evento global: greve na siderurgia, colheita recorde,
epidemia de gripe, descoberta de petróleo, inverno precoce, sabotagem ferroviária, ajuda
estrangeira, motim. O árbitro também pode disparar eventos manualmente.

## 9. Telas

### Direção de arte — "Sala de Guerra, 1943: papel, tinta e lâmpada"
Nada de dashboard genérico (cartões arredondados, gradientes, roxo, emojis). A tela é uma **mesa
vista de cima sob uma luminária**: feltro verde-escuro com vinheta; os conteúdos são **objetos**:
mapa impresso em papel envelhecido com dobras, pastas de papel pardo com abas (as seções),
folhas datilografadas presas com clipe, telegramas em tiras coladas ("STOP"), formulários de ordem
em papel-carbono, **carimbos de borracha** (CONFIDENCIAL, INTERCEPTADO, APROVADO).
Tipografia: stencil nos títulos, máquina de escrever nos textos datilografados, mono nos números,
serifada clássica nas manchetes de jornal. Sombras direcionais (luz no canto superior esquerdo),
cantos retos, rotações sutis (±0,6°).
Movimento: telegrama "datilografado" com som de tecla (WebAudio, sem arquivos), carimbo que
"bate" (escala + tremor), setas de ataque traçadas a lápis-cera, território conquistado "vira" de cor.
Mapa: litoral com **water-lining** (linhas paralelas à costa, como mapas da 2ª Guerra), hachuras de
relevo, rios, quadrícula A–X × 1–16 na margem (a mesma usada na triangulação), rosa dos ventos.

### Páginas
- **/ (Portão)**: escolha da nação e senha — "credencial" de papel com carimbo.
- **/teatro (projetor, 16:9)**: mapa público animado; à direita o jornal "O Arauto do Front",
  relógio de turno estilo *split-flap*, quadro de PV com emblemas.
- **/qg (Quartel-General)**: timbre da nação, relógio, pasta com abas das 4 seções; em cada aba:
  briefing datilografado, tabelas (copiar/baixar CSV), questionário reservado (desafios),
  formulário de ordem ("Assinar e carimbar"), telegramas; mapa com névoa na aba Operações
  (clicar origem → destino para criar ordem). Gaveta inferior: **Mesa de Cálculo**.
- **/arbitro**: painel do árbitro estilo mesa telefônica: iniciar/pausar/estender/resolver,
  credenciais imprimíveis, todas as ordens, edição de emergência, eventos, avisos, rollback.

## 10. Arquitetura
- Um único contêiner Docker: Python 3.12 + FastAPI + Uvicorn + NumPy. Sem banco: estado em memória
  com snapshot JSON atômico em volume `/data` (sobrevive a reinício) e arquivo por turno (rollback).
- WebSocket para eventos ao vivo; REST para dados. Front-end estático em JS puro (sem build),
  fontes embutidas (funciona numa rede local **sem internet**).
- Um PC roda `docker compose up`; os outros acessam `http://IP-DO-PC:8000`.
