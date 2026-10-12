# ESTADO-MAIOR — A Guerra do Continente de Lebesgue

## Manual dos jogadores

Para imprimir e deixar em cada sala. Leitura: cerca de 15 minutos. Leia com a equipe antes do primeiro turno.

---

## 1. Objetivo e como vencer

Sua sala é o Quartel-General de uma nação. Vence quem tiver mais **Pontos de Vitória (PV)** ao fim da guerra, ou quem dominar o continente antes disso.

**Pontos de Vitória:**

- 1 PV por território que sua nação controla;
- +2 PV por capital que você controla (a capital de cada nação está marcada no mapa);
- +0,25 PV por desafio resolvido.

**Fim da guerra:**

- após o último turno (8 turnos, salvo ajuste do árbitro);
- ou por **dominação**: controlar 21 dos 34 territórios (60%);
- ou quando só sobra uma nação de pé.

**Empate no ranking:** vence quem tiver mais territórios; se ainda empatar, mais batalhões.

**Capitulação:** sua nação capitula, e fica fora da partida, se:

- perder todos os territórios; ou
- perder a capital e ficar com menos de 3 batalhões e com menos de 10 unidades somadas de estoque.

---

## 2. Como entrar

1. No navegador de qualquer computador da rede, abra o endereço que o árbitro informou, no formato `http://IP-DO-SERVIDOR:8000` (ex.: `http://192.168.0.25:8000`). Não é preciso instalar nada.
2. Na tela de entrada (o **Portão**), escolha a sua nação.
3. Digite a senha impressa no cartão da sala. A senha tem três partes, separadas por hífen: **palavra-palavra-número**, por exemplo `vetor-ponte-42`.
   - Escreva os hífens e os números. Não é preciso acentuar; maiúsculas e minúsculas não fazem diferença.
4. Se a senha não funcionar, chame o árbitro. Ele consulta as credenciais no painel dele.

Cada sala tem uma nação e uma senha. Várias pessoas da mesma sala podem entrar, em computadores diferentes, com a mesma nação e a mesma senha.

O **Teatro de Operações** (o mapa do projetor) não tem senha e mostra a guerra para todos. Ele não mostra informações secretas.

Antes da largada, a tela mostra "aguardem o sinal do árbitro". Os dossiês só chegam quando o árbitro inicia a guerra.

---

## 3. O turno

### 3.1 O ciclo

Cada turno tem três fases:

1. **Briefing (instantâneo).** Chega um telegrama "BRIEFING — TURNO n", e os dossiês das quatro seções aparecem nas abas. Cada seção recebe os próprios dados.
2. **Planejamento (cerca de 12 minutos).** As seções calculam, resolvem os desafios (opcionais) e enviam as ordens. Na metade do turno chega o **telegrama-relâmpago**.
3. **Resolução (automática).** Quando o prazo acaba, o servidor resolve tudo ao mesmo tempo. O mapa é animado no Teatro, e o jornal *O Arauto do Front* publica as manchetes. Já começa o turno seguinte.

### 3.2 Relógio, prazo e pausa

- O relógio aparece no cabeçalho do QG e no Teatro.
- Você pode reenviar ordens quantas vezes quiser até o prazo. **Vale a última ordem válida.**
- Se o prazo acabar e a seção não tiver enviado nada, a resolução usa o padrão: a Intendência não produz nada, a Operações não move tropas e o Governo mantém a ração e a jornada, sem propaganda.
- Quando o árbitro pausa a partida, o relógio para e **não é possível enviar ordens nem responder desafios**. Telegramas diplomáticos continuam circulando.
- Não deixe a ordem para o último minuto. Envie uma versão cedo, e reenvie se mudar de ideia.

### 3.3 Ordem da resolução

A ordem importa. O que acontece primeiro já pode ser usado pelo que vem depois:

1. **Governo:** transferências de recursos entre nações, propostas e denúncias de pacto, ração, propaganda e jornada.
2. **Intendência:** produção. Ela entra no estoque na hora.
3. **Recrutamento:** usa o estoque **já com a produção deste turno**.
4. **Inteligência:** bombardeio a depósito (só se o depósito tiver sido localizado neste turno).
5. **Operações:** movimentos (usam o Combustível que sobrou), depois as batalhas. Reforços chegam antes das batalhas.
6. **Manutenção:** alimento para as tropas e para a população civil. Se faltar, há fome.
7. **Moral:** muda conforme as decisões e o resultado das batalhas.
8. **Capitulação, PV e fim de jogo.**
9. Manchetes do jornal. Preparação do turno seguinte: novos dossiês, clima sorteado, depósitos realocados.

### 3.4 Desafios e ordens

- Cada seção tem **um desafio por turno**. Resolver é opcional, mas dá recompensa.
- Você tem **3 tentativas** por desafio. A recompensa vem na primeira resposta correta.
- **Resolver o desafio não envia a ordem.** Depois de resolver, copie o resultado para o formulário de ordem da seção e envie.
- Ao enviar uma ordem, o sistema responde com **erros** e **avisos**. Erro impede o envio: corrija e envie de novo. Aviso não impede: leia com atenção, porque ele diz o que o servidor vai ajustar na resolução.

---

## 4. A tela do QG

- **Cabeçalho:** nome e timbre da nação, turno atual e relógio.
- **Pasta com quatro abas**, uma por seção: Intendência, Operações, Inteligência, Governo.
- **Em cada aba:**
  - o briefing (texto do dossiê);
  - as tabelas, que você pode copiar ou baixar em CSV;
  - o desafio do turno (questionário reservado) e as tentativas que restam;
  - o formulário de ordem ("Assinar e carimbar");
  - os telegramas recebidos.
- **Mapa com névoa de guerra**, na aba Operações. Você vê o que a sua nação alcança (ver a seção 7).
- **Gaveta da Mesa de Cálculo**, com as ferramentas (ver a seção 11).
- **Telegramas:** avisos do árbitro, interceptações, o relatório do turno e as mensagens de outras nações.

---

## 5. As seções

Cada seção tem a mesma estrutura: **o que decide**, **que dados recebe**, **o problema de álgebra linear**, **um exemplo resolvido**, **a ferramenta**, **a recompensa** e **dicas**.

### 5.1 Intendência — Modelo de Leontief

**O que decide**

- A produção bruta de cada setor: **x = (x_ALI; x_ACO; x_COM)**, em unidades.
- Quantos batalhões recrutar (e o custo, ver a seção 6).

**Que dados recebe**

- A tabela de transações **Z** entre os setores e a produção total **X** do turno anterior.
- Mão de obra: o coeficiente **L** de cada setor e a força de trabalho **W**, que depende dos territórios, da jornada e da moral (o dossiê informa W para cada jornada).
- As capacidades de produção de cada setor e os estoques.
- A previsão de consumo de Alimento (tropas e população civil).

**O problema**

Cada setor produz para si mesmo e para os outros. Por isso, a produção bruta x precisa cobrir o que se consome como insumo (**A·x**) e ainda sobrar a entrega final **d** para a nação:

- **A** é a matriz técnica. Cada coluna **j** de A mostra quanto de cada insumo o setor j consome por unidade que produz. Calcula-se a partir da tabela: **A = Z · diag(X)⁻¹**, ou seja, divida cada coluna de Z pelo X do setor correspondente.
- Entrega líquida: d = x − A·x = **(I − A)·x**.
- Para entregar uma demanda **d**, resolva **(I − A)·x = d**. A solução x é a produção bruta que você deve ordenar.

**Exemplo resolvido** (números pequenos, conferidos com o motor do jogo)

Tabela recebida (Z e X):

| | ALI | ACO | COM |
|---|---:|---:|---:|
| ALI | 3 | 4 | 0 |
| ACO | 6 | 2 | 1 |
| COM | 3 | 0 | 2 |
| **X** (produção total) | 30 | 20 | 10 |

1. Matriz técnica: divida cada coluna pelo X do setor. Coluna ALI por 30, coluna ACO por 20, coluna COM por 10:

| | ALI | ACO | COM |
|---|---:|---:|---:|
| ALI | 0,1 | 0,2 | 0 |
| ACO | 0,2 | 0,1 | 0,1 |
| COM | 0,1 | 0 | 0,2 |

2. O Gabinete exige a entrega líquida **d = (23; 11; 5)**. Resolva **(I − A)·x = d**, com I − A igual a:

| | ALI | ACO | COM |
|---|---:|---:|---:|
| ALI | 0,9 | −0,2 | 0 |
| ACO | −0,2 | 0,9 | −0,1 |
| COM | −0,1 | 0 | 0,8 |

3. Resposta: **x = (30; 20; 10)**.

Conferência: 0,9·30 − 0,2·20 = 23; −0,2·30 + 0,9·20 − 0,1·10 = 11; −0,1·30 + 0,8·10 = 5. Os três valores batem com d.

Cuidado: **d é a entrega, x é a produção**. A ordem pede x.

**A ferramenta**

- **Leontief:** informe Z e X (a ferramenta devolve A) e o vetor d (a ferramenta devolve a produção x necessária).
- **Matrizes, operação "solve":** para resolver o sistema (I − A)·x = d diretamente.

**Recompensa**

- **+10% de produtividade neste turno**: a produção ordenada rende 10% a mais na resolução.

**Dicas táticas**

- A produção acima da capacidade do setor é recusada no envio. Confira os limites no dossiê.
- Se a produção pedir mais mão de obra do que W, o servidor reduz a produção na mesma proporção. O aviso aparece no envio.
- Produzir pouco demais pode fazer o estoque cair: como o consumo de insumos é descontado, a produção líquida pode ser negativa.
- O recrutamento usa o estoque depois da produção do mesmo turno. Você pode contar com ela.
- O Alimento é o recurso mais urgente: cada batalhão consome 0,5 ALI por turno, e a população civil consome mais ainda. Se faltar, a nação passa fome (ver seção 6).
- A matriz A muda levemente de um turno para o outro, e piora quando o inimigo bombardeia seus depósitos. Recalcule a cada turno.
- O bônus de produtividade multiplica a produção **depois** dos limites: se a sua mão de obra já estava no limite, ele multiplica a produção já reduzida.

### 5.2 Operações — Cadeias de Markov e Lanchester

**O que decide**

- Movimentos: de um território seu para um vizinho, com um número de batalhões. Se o destino for seu, é reforço. Se for de outra nação ou neutro, é ataque. Até 16 ordens por turno.

**Que dados recebe**

- O **diário meteorológico**: o clima observado a cada turno em cada uma das três regiões (limpo, chuva ou tempestade), com dezenas de observações.
- Os **avistamentos de fronteira**: os territórios vizinhos aos seus, com a faixa estimada de tropas (1–5, 6–10, 11–20, 21+) e o terreno.
- A tabela de **modificadores de combate**.

**Problema 1: previsão do clima com Markov**

O clima de cada região segue uma cadeia de Markov: o estado de amanhã depende só do estado de hoje.

- **P** é a matriz de transição. O elemento P[i][j] é a probabilidade de o clima ir de i para j no próximo turno.
- **Estimativa:** conte quantas vezes cada estado foi seguido de cada outro, no diário. Divida cada linha pelo total dela.
- **Previsão:** a linha do estado atual de P dá a probabilidade para o próximo turno. Para dois turnos à frente, use a linha de P².

**Exemplo resolvido** (20 observações, números conferidos com o motor)

Sequência: limpo, chuva, chuva, tempestade, chuva, limpo, limpo, chuva, tempestade, tempestade, chuva, limpo, chuva, chuva, limpo, tempestade, chuva, limpo, limpo, chuva.

Contagem das transições (de → para):

| de \ para | limpo | chuva | tempestade | total |
|---|---:|---:|---:|---:|
| limpo | 2 | 4 | 1 | 7 |
| chuva | 4 | 2 | 2 | 8 |
| tempestade | 0 | 3 | 1 | 4 |

Matriz estimada P (cada linha dividida pelo total):

| de \ para | limpo | chuva | tempestade |
|---|---:|---:|---:|
| limpo | 0,29 | 0,57 | 0,14 |
| chuva | 0,50 | 0,25 | 0,25 |
| tempestade | 0,00 | 0,75 | 0,25 |

Se hoje está **chuva**, a probabilidade de **tempestade** amanhã é **0,25**.

**Problema 2: resultado de um combate com a lei quadrática de Lanchester**

Dois exércitos se enfrentam. Com A batalhões atacantes e B defensores, e eficácias α (atacante) e β (defensor):

- A' = −β·B e B' = −α·A: as baixas de cada lado crescem com a força e a eficácia do adversário.
- **Invariante:** α·A² − β·B² não muda durante o combate, onde A e B são os batalhões atacantes e defensores. Por isso, se o combate termina antes de T, vence quem tiver o maior valor de **α·A0²** (atacante) ou **β·B0²** (defensor), com A0 e B0 os batalhões iniciais. O sobrevivente do vencedor fica com **√((α·A0² − β·B0²)/α)**, se o atacante vence, ou **√((β·B0² − α·A0²)/β)**, se o defensor vence.
- O combate dura um tempo fixo **T = 0,9**. Se ninguém zerar até T, o combate é **indeciso**: o atacante recua com os sobreviventes e o defensor fica com os dele.

Como calcular α e β para a batalha:

- **α (atacante)** = (0,5 + moral do atacante / 100) × fator do clima na região de **origem** (limpo 1,0; chuva 0,85; tempestade 0,65).
- **β (defensor)** = (0,5 + moral do defensor / 100) × fator do **terreno do alvo** (planície 1,0; urbano 1,3; floresta 1,25; pântano 1,2; montanha 1,5).
- Milícias neutras têm moral 60.
- **A0** é o total de batalhões que atacam o mesmo território, somando todas as origens. Reforços que chegam a um território seu entram antes das batalhas.

Exemplos (conferidos com o motor, com moral 70 para os dois lados):

- **Caso 1.** 12 atacantes, sem chuva, contra 6 defensores em montanha. α = 1,2 e β = 1,2 × 1,5 = 1,8. Como 1,2 × 12² = 172,8 é maior que 1,8 × 6² = 64,8, vence o atacante. Sobram cerca de **9 batalhões** (9,49). O defensor é zerado em t = 0,48, antes de T.
- **Caso 2.** 6 atacantes contra 12 defensores, na mesma montanha. 1,2 × 6² = 43,2 é menor que 1,8 × 12² = 259,2. Vence o defensor, e sobram cerca de **11** (10,95).
- **Caso 3.** 10 atacantes em chuva (α = 1,2 × 0,85 = 1,02) contra 9 defensores em floresta (β = 1,2 × 1,25 = 1,5). Pela lei quadrática, o defensor venceria (1,02 × 10² = 102 é menor que 1,5 × 9² = 121,5), mas ele só zeraria o atacante em t = 1,27, depois de T = 0,9. O combate é **indeciso**: o atacante recua com cerca de **2** batalhões, e o defensor fica com cerca de **4**.

**As ferramentas**

- **Markov (clima):** informe a sequência de climas (ou P) e o estado atual. A ferramenta devolve P estimada e a previsão.
- **Lanchester:** informe A0, B0, α, β e T. A ferramenta devolve o vencedor e os sobreviventes.
- **Matrizes:** para P², use "mul", ou "pow" com k = 2.

**Recompensa**

- **O servidor revela o clima exato de todas as regiões na resolução deste turno.** Isso é útil para decidir se a rota marítima estará fechada por tempestade.

**Dicas táticas**

- O mar (rota marítima) custa **2 COM** por batalhão, e a travessia **é cancelada** se a região de origem ou a de destino estiver em tempestade. O aviso aparece no envio.
- A travessia por terra custa **1 COM** por batalhão. Se o Combustível não der para todos, os movimentos são reduzidos na mesma proporção.
- Território sem nenhuma tropa é tomado sem combate.
- Duas ordens para o mesmo alvo, vindas de origens diferentes, se somam numa única batalha.
- Se você deixar uma origem sem guarnição, o aviso aparece, mas o movimento é aceito.
- Um pacto de não agressão bloqueia o ataque ao território da outra nação (ver seção 8).
- No telegrama-relâmpago, você vê as ordens de operações do inimigo que ele já enviou. Se ele ainda não enviou ordens na metade do turno, o relâmpago mostra só a concentração de tropas e os totais dele.

### 5.3 Inteligência — Cifra de Hill e Mínimos Quadrados

**O que decide**

- Bombardear um depósito de suprimentos inimigo, **só se o depósito tiver sido localizado neste turno**. Custa 4 COM. O inimigo perde 25% do seu maior estoque, e a matriz A dele piora no turno seguinte.

**Que dados recebe**

- **Dois criptogramas** interceptados de nações inimigas. O alfabeto tem 37 símbolos: A–Z (0 a 25), 0–9 (26 a 35) e o espaço (36). Os cálculos são feitos **módulo 37**.
- **Quatro leituras** das estações de escuta: a distância (com ruído) de cada estação até o depósito inimigo.
- Os telegramas-relâmpago chegam na metade do turno, com as ordens de operações do inimigo, cifradas com a chave dele.

**Problema 1: decifrar com a cifra de Hill**

- A cifra trabalha com **pares de símbolos**. Cada par é um vetor p = (p1; p2). O criptograma é c = K·p (mod 37), onde K é a chave 2×2.
- **Pedra de Roseta:** toda mensagem começa com "URGENTE " (8 símbolos, com o espaço). Você conhece esse trecho claro. Pegue os dois primeiros pares, P, e os dois primeiros pares cifrados, C. Como C = K·P, temos **K = C·P⁻¹ (mod 37)**.
- **Inversa mod 37:** para uma matriz 2×2, P⁻¹ = (det P)⁻¹ × [[d, −b], [−c, a]], com tudo reduzido mod 37. (det P)⁻¹ é o inverso de um número mod 37: ele existe quando det P não é múltiplo de 37. Exemplo: 15⁻¹ = 5, porque 15 × 5 = 75 = 2 × 37 + 1.
- Cada nação tem a **sua** chave, e cada criptograma precisa do próprio trecho conhecido. A chave de uma nação vale por **dois turnos** (turnos 1–2, 3–4, 5–6 e 7–8). Se você recuperou a chave de uma nação num turno, ela serve no turno seguinte.

**Exemplo resolvido** (chave K = [[3; 5]; [2; 7]], conferida com o motor)

Mensagem de exemplo: "URGENTE ATACA K7". Criptograma: `8LBDXLHBVWKO64K3`. Trecho conhecido, "URGENTE ", cifrado como `8LBDXLHB`.

1. Blocos: "UR" = (20; 17) e "GE" = (6; 4). Então P = [[20; 6]; [17; 4]] (cada bloco é uma coluna).
2. Blocos cifrados: "8L" = (34; 11) e "BD" = (1; 3). Então C = [[34; 1]; [11; 3]].
3. det P = 20·4 − 6·17 = −22 ≡ 15 (mod 37). 15⁻¹ = 5. P⁻¹ = 5 × [[4; −6]; [−17; 20]] ≡ [[20; 7]; [26; 26]] (mod 37).
4. K = C · P⁻¹ = [[3; 5]; [2; 7]] (mod 37).

Conferência: K · (20; 17) = (3·20 + 5·17; 2·20 + 7·17) = (145; 159) ≡ (34; 11) (mod 37), que são "8" e "L".

Com K, decifre o resto da mensagem: "URGENTE ATACA K7".

**Problema 2: localizar o depósito com mínimos quadrados**

Cada estação mede uma distância até o depósito. Cada medida define um círculo: (x − xi)² + (y − yi)² = ri².

- Subtraia a primeira equação das demais. Os termos quadráticos somem, e sobra um sistema **linear**: 2(xi − x1)·x + 2(yi − y1)·y = r1² − ri² + xi² − x1² + yi² − y1².
- Como as distâncias têm ruído, o sistema não tem solução exata. Use **mínimos quadrados**: a solução é a que minimiza o erro total, e é dada pelas equações normais AᵀA·p = Aᵀb.

**Exemplo resolvido** (conferido com o motor)

Estações E1 = (100; 100), E2 = (700; 150) e E3 = (300; 650). Distâncias medidas: 394,1; 332,9; 341,8.

Sistema linearizado (subtraindo a equação de E1):

- 1200·x + 100·y = 536 992,4
- 400·x + 1100·y = 530 987,6

Solução: **x = 420,0 e y = 330,0**, ou seja, a quadrícula **I7**.

Conferência: a distância de (420; 330) até E1 é √(320² + 230²) ≈ 394,1.

Quadrícula: a letra é a coluna, dada por x ÷ 50 (A = 0 a X = 23), e o número é a linha, dada por y ÷ 50 + 1. Exemplo: (420; 330) → coluna 420 ÷ 50 = 8, que é I; linha 330 ÷ 50 + 1 = 7; logo I7.

**As ferramentas**

- **Cifra de Hill:** recuperar a chave (trecho claro e cifrado), decifrar (cifrado e chave), cifrar (texto e chave). A inversa mod 37 também fica aqui.
- **Triangulação:** informe as coordenadas das estações e as distâncias; a ferramenta devolve x, y e a quadrícula.

**Desafio e recompensa**

- **Desafio:** informe a posição do depósito, como "x; y" (ex.: 420; 330) ou como quadrícula (ex.: I7).
- **Tolerância:** 25 unidades de distância, ou a mesma quadrícula da solução. A resposta correta é a solução dos **dados entregues**, não a posição verdadeira do depósito.
- **Recompensa:** revela as tropas exatas do território do depósito e libera a ordem **Bombardear depósito** neste turno.
- A recompensa da cifra é a própria informação: decifrar as mensagens mostra o estado real do inimigo (tropas, estoques, moral).

**Dicas táticas**

- Decifre a mensagem de um inimigo antes de planejar o ataque. Ela pode mostrar a capital dele mal guarnecida.
- O telegrama-relâmpago é cifrado com a chave do inimigo, da mesma forma. Se você já tem a chave dele, leia-o na hora.
- A Inteligência e a Operações devem trabalhar juntas no relâmpago: as ordens do inimigo mudam o alvo da sua defesa.
- Bombardear sem depósito localizado é recusado. Resolva o desafio de triangulação primeiro.

### 5.4 Governo — Regressão Linear Múltipla e Diplomacia

**O que decide**

- **Ração:** 0 normal, 1 reduzida, 2 severa. Ração menor economiza Alimento, mas reduz a moral.
- **Propaganda:** de 0 a 5 níveis. Cada nível custa 1 unidade de Aço (ACO). Se faltar Aço, o nível é reduzido.
- **Jornada:** 8, 10 ou 12 horas. Jornada maior dá mais mão de obra (×1,0; ×1,2; ×1,4), mas reduz a moral.
- **Transferências** de Alimento, Aço ou Combustível para outras nações, limitadas pelo seu estoque.
- **Pactos:** propor ou denunciar um pacto de não agressão.
- **Telegramas diplomáticos** para outros Governos (até 600 caracteres).

**Que dados recebe**

- A **pesquisa de opinião**, com 25 observações: ração, propaganda, horas extras (jornada − 8), baixas (em dezenas de batalhões), saldo territorial (territórios ganhos menos perdidos) e a variação da moral (Δ moral).
- O **quadro das nações**: territórios e PV de cada nação (informação pública).

**O problema**

A moral segue um modelo linear, com efeitos diferentes em cada nação. Você quer saber quanto a **propaganda** muda a moral, por ponto de propaganda. Para isso, ajuste:

Δ moral = β0 + β1·ração + β2·propaganda + β3·horas extras + β4·baixas + β5·saldo + ruído

pelo método dos **mínimos quadrados**. Em forma matricial, a solução β é dada pelas **equações normais**: **(XᵀX)·β = Xᵀy**, onde X é a matriz das variáveis, com uma primeira coluna de 1s para o intercepto (β0), e y é a coluna da variação da moral.

**Exemplo resolvido** (6 observações simplificadas, conferidas com o motor)

Usamos só ração e propaganda, para caber no papel.

| obs | ração | propaganda | Δ moral |
|---:|---:|---:|---:|
| 1 | 0 | 0 | 2,0 |
| 2 | 0 | 2 | 4,9 |
| 3 | 1 | 1 | 1,9 |
| 4 | 1 | 3 | 4,2 |
| 5 | 2 | 0 | −2,1 |
| 6 | 2 | 4 | 2,9 |

Equações normais:

- XᵀX = [[6; 6; 10]; [6; 10; 12]; [10; 12; 30]]
- Xᵀy = (13,8; 7,7; 35,9)

Solução: **β0 ≈ 2,32; β1 (ração) ≈ −2,17; β2 (propaganda) ≈ 1,29**.

A resposta do desafio, neste exemplo, seria **1,29**. A ração reduz a moral, e a propaganda aumenta.

**As ferramentas**

- **Regressão:** informe as observações (ou o CSV baixado do jogo), **a lista das variáveis explicativas** e o alvo (`delta_moral`). A ferramenta devolve os coeficientes e o R².
- **Matrizes, operação "solve":** se você montou as equações normais à mão.

**Cuidado com a coluna "obs"**: o CSV baixado da pesquisa tem uma coluna `obs`, que é só o número da linha. **Ela não é variável.** Se você não listar as variáveis explicativas, a ferramenta usa todas as colunas, inclusive `obs`, e o resultado sai errado. Liste sempre: racao, propaganda, horas_extra, baixas e saldo_territorial.

**Desafio e recompensa**

- **Desafio:** informe β2, o efeito da propaganda, com um número (ex.: 1,35).
- **Tolerância:** ±0,15.
- **Recompensa:** +5 de moral.

**Dicas táticas**

- Use **todas** as variáveis juntas. Se você regredir só a propaganda, o efeito dela sai contaminado pelos outros fatores.
- A moral alta aumenta a eficácia de combate: (0,5 + moral/100). Moral 70 dá 1,2; moral 40 dá 0,9. Também aumenta a mão de obra disponível.
- Ração e jornada custam moral, mas a propaganda custa Aço. Decida conforme o que falta mais na sua nação.
- Denunciar um pacto custa **5 de moral**, e o pacto só acaba ao fim do turno.
- Perder a capital custa **15 de moral**. Ficar sem Alimento custa **10 de moral** e faz desertar 10% das tropas.
- Se a nação não manda ordem do Governo, a ração e a jornada são mantidas, e a propaganda vai para zero.

---

## 6. Tabela de custos e modificadores

**Custos**

| Ação | Custo |
|---|---|
| Mover 1 batalhão por terra | 1 COM |
| Mover 1 batalhão por mar (rota marítima) | 2 COM |
| Recrutar 1 batalhão | 2 ALI + 2 ACO + 1 COM. Aparece na capital, ou no território com mais tropas, se a capital estiver perdida |
| Bombardear depósito | 4 COM (só com depósito localizado no turno) |
| Propaganda, por nível | 1 ACO por nível (0 a 5) |
| Manutenção das tropas | 0,5 ALI por batalhão, por turno |
| Consumo civil | 6 ALI (ração normal), 4 ALI (ração reduzida), 2 ALI (ração severa) |

**Mão de obra por unidade produzida**

| Setor | Unidades de trabalho por unidade produzida |
|---|---:|
| Alimento (ALI) | 1,0 |
| Aço (ACO) | 1,5 |
| Combustível (COM) | 1,2 |

**Jornada**

| Jornada | Multiplicador da mão de obra |
|---|---:|
| 8 horas | ×1,0 |
| 10 horas | ×1,2 |
| 12 horas | ×1,4 |

**Combate**

| Fator | Valor |
|---|---|
| Terreno: planície (defensor) | 1,0 |
| Terreno: urbano (defensor) | 1,3 |
| Terreno: floresta (defensor) | 1,25 |
| Terreno: pântano (defensor) | 1,2 |
| Terreno: montanha (defensor) | 1,5 |
| Clima: limpo (atacante) | 1,0 |
| Clima: chuva (atacante) | 0,85 |
| Clima: tempestade (atacante) | 0,65 |
| Moral (qualquer lado) | 0,5 + moral/100 |
| Duração do combate T | 0,9 |

**Efeitos sobre a moral e os PV**

| Evento | Efeito |
|---|---|
| Capital perdida | −15 de moral |
| Fome (faltou Alimento) | −10 de moral; 10% das tropas desertam |
| Denúncia de pacto | −5 de moral |
| Desafio do Governo resolvido | +5 de moral |
| Desafio resolvido (qualquer seção) | +0,25 PV |
| Capital controlada | +2 PV |
| Território controlado | +1 PV |

**Outras regras**

- Bônus de produtividade (desafio de Intendência): +10% sobre a produção, neste turno.
- Clima exato revelado (desafio de Operações): vale para a resolução deste turno.
- Depósito localizado (desafio de Inteligência): vale para este turno.
- Tolerâncias dos desafios: Leontief, 2% (ou 0,1 em valor absoluto, o que for maior); Markov, ±0,03; regressão, ±0,15; depósito, 25 unidades ou a mesma quadrícula.

---

## 7. Névoa de guerra

Você não vê tudo o que os outros fazem. O que você vê depende de onde está o território:

- **Seus territórios:** tropas exatas.
- **Vizinhos** (por terra ou por rota marítima): dono e faixa de tropas (1–5, 6–10, 11–20 ou 21+).
- **Território revelado por um depósito localizado:** tropas exatas, neste turno.
- **Demais territórios:** só o dono, que aparece no mapa público.

O mapa mostra as cores de todas as nações, porque o controle territorial é público.

O mesmo vale para os inimigos: eles veem a faixa de tropas das suas fronteiras, e não o número exato.

---

## 8. Pactos e diplomacia

**Pacto de não agressão**

- Um pacto só se firma quando **as duas nações propõem**. Isso acontece se as duas propõem no mesmo turno, ou se a outra propôs no turno anterior e você propõe agora.
- Uma proposta fica pendente para a resolução seguinte. Se a outra nação propõe nessa resolução, o pacto é firmado. Propostas separadas por mais de um turno não se somam.
- O pacto vale por **3 turnos**, incluindo o turno em que foi firmado.
- Enquanto o pacto vale, nenhuma das duas pode atacar o território da outra, nem bombardear o depósito dela.
- Denunciar o pacto encerra o pacto **ao fim do turno** e custa **5 de moral**.
- Pacto não impede transferências de recursos.

**Telegramas diplomáticos**

- Qualquer nação pode enviar telegramas a qualquer outra, com até 600 caracteres.
- Só o remetente e o destinatário recebem o telegrama diplomático. O árbitro vê todos os telegramas. Não envie nada que você não quer que o árbitro leia.
- O árbitro pode enviar avisos a todas as nações ou a uma só.

**Transferências**

- Você pode enviar recursos a outra nação. A quantidade é limitada pelo seu estoque, e é reduzida se faltar.

---

## 9. Eventos

A partir do turno 2, há 60% de chance de um evento global em cada turno. Um evento pode:

- **Greve na siderurgia:** produção de Aço −30%, neste turno.
- **Colheita recorde:** produção de Alimento +30%, neste turno.
- **Epidemia de gripe:** mão de obra −15%, por 2 turnos.
- **Descoberta de petróleo:** uma nação sorteada recebe 18 de Combustível.
- **Inverno precoce:** consumo civil +2 ALI, movimentos 50% mais caros e ataques −10%, por 2 turnos.
- **Sabotagem ferroviária:** uma nação sorteada perde 25% do Combustível, e seus movimentos custam o dobro, neste turno.
- **Ajuda estrangeira:** a nação com menos PV recebe 12 ALI, 8 ACO e 8 COM.
- **Motim nas tropas:** a nação de moral mais baixa perde 12 de moral.

Os eventos aparecem no jornal. Os efeitos de cada um aparecem no seu relatório do turno.

---

## 10. Como dividir a sala

Cada nação tem de 8 a 16 pessoas. Divida-as em quatro seções, com **2 a 4 pessoas por seção**, e nomeie um **chefe de estado-maior**, que integra as decisões das quatro seções.

| Pessoas na sala | Por seção | Chefe de estado-maior |
|---:|---:|---|
| 8 | 2 | uma pessoa da Intendência, que acumula a função |
| 12 | 3 | uma pessoa da Operações, que acumula a função |
| 16 | 4 | uma pessoa do Governo, que acumula a função |

**Funções dentro de cada seção**

- **Chefe de seção:** lê o dossiê e decide com a equipe. Não precisa ser o mais rápido em matemática.
- **Calculista:** usa a Mesa de Cálculo para resolver o desafio.
- **Conferente:** confere o resultado com a conta da seção e procura erros de unidade.

**O chefe de estado-maior**

- Cuida do relógio e avisa a sala quando faltam 3 minutos.
- Faz a checagem cruzada das quatro seções antes do envio: a produção cabe na mão de obra? O Alimento cobre o consumo? Os movimentos têm Combustível? A propaganda tem Aço?
- Confirma o envio de cada seção no formulário.

**Roteiro de um turno de 12 minutos**

| Minuto | O que fazer |
|---:|---|
| 0–2 | Ler o briefing e o telegrama. Dividir as tarefas. |
| 2–6 | Resolver os desafios. Montar as contas. |
| 6 | Chega o telegrama-relâmpago. Operações e Inteligência revisam as ordens do inimigo. |
| 6–9 | Decidir e preencher os formulários de ordem. |
| 9–10 | Checagem cruzada. O chefe confere os erros e os avisos. |
| 10–11 | Enviar. |
| 11–12 | Margem para reenvio. Não guarde nada para o último segundo. |

**Rotação**

Troque de seção entre os turnos, para que todos conheçam as quatro áreas. A Inteligência e a Operações devem sempre conversar, porque as informações de uma alimentam as decisões da outra.

---

## 11. Mesa de Cálculo e toolkit.py

A **Mesa de Cálculo** fica na gaveta da tela do QG. Ela tem as ferramentas abaixo. Ela não exige login e faz as contas do jogo com o mesmo motor:

| Ferramenta | O que você informa | O que ela devolve |
|---|---|---|
| Matrizes | uma operação (determinante, inversa, solve, mínimos quadrados, autovalores, potência, produto, transposta, estacionária) e as matrizes ou vetores que ela pedir | o resultado |
| Cifra de Hill | o trecho claro e o cifrado (recuperar a chave); a chave (decifrar ou cifrar); a chave K, para a inversa mod 37 | a chave, o texto claro, o cifrado ou a inversa |
| Leontief | Z, X e d (dá A e a produção x); ou A e x (dá a produção líquida); ou L e x (dá a mão de obra usada) | A, x, a produção líquida ou a mão de obra |
| Markov (clima) | a sequência observada do clima (dá P estimada); P, o estado atual e os passos k (dá a previsão) | P, a previsão e a distribuição estacionária |
| Triangulação | as coordenadas das estações e as distâncias | x, y e a quadrícula |
| Regressão | as observações (ou o CSV), a lista das variáveis explicativas e o alvo | os coeficientes e o R² |
| Lanchester | A0, B0, α, β e T | o vencedor, os sobreviventes e a trajetória |

**Da Mesa para o questionário.** Cada resultado vai para a **fita de resultados**, à direita da gaveta. Nos resultados que respondem ao questionário da sua seção (o x do Leontief, a probabilidade de tempestade do Markov, a posição ou a quadrícula da Triangulação e o coeficiente da propaganda da Regressão), a fita traz o botão **usar no questionário**: ele escreve a resposta, já no formato pedido, no campo certo, fecha a gaveta e deixa tudo pronto para você conferir e enviar. O botão **copiar** continua valendo para levar números a outro lugar.

**Mapa de Operações.** Use a roda do mouse para aproximar, arraste para mover a carta e dê duplo clique (ou clique em **Enquadrar**) para ver o continente inteiro. Os botões **+** e **−** fazem o mesmo.

**Para quem prefere programar:** o arquivo `tools/toolkit.py` tem as mesmas funções em Python, usando só NumPy. Coloque o arquivo na pasta do seu script e importe as funções. Ele também sabe ler os CSVs baixados do jogo.

---

## 12. Glossário

- **ALI, ACO, COM:** Alimento, Aço e Combustível. São os três recursos do jogo.
- **Batalhão:** a unidade de tropa. Não há outra unidade.
- **Capacidade:** o máximo que um setor da sua nação consegue produzir, de acordo com os territórios que você controla.
- **Chave de Hill:** a matriz 2×2 que cifra as mensagens de uma nação. Muda a cada dois turnos.
- **Clima:** limpo, chuva ou tempestade. Cada região tem o seu.
- **Crib (trecho conhecido):** o começo fixo "URGENTE " das mensagens, usado para recuperar a chave.
- **Dossiê:** o conjunto de dados e desafios que chega a cada seção, em cada turno.
- **Depósito de suprimentos:** cada nação tem um. Ele fica num dos seus territórios e muda de lugar a cada turno. É o alvo da Inteligência.
- **Estado de Lanchester:** o número de batalhões e a eficácia (α ou β) de cada lado.
- **Estoque:** a quantidade de ALI, ACO e COM que a nação tem.
- **Moral:** de 0 a 100. Afeta a eficácia de combate e a mão de obra.
- **Névoa de guerra:** a informação limitada sobre os territórios que você não controla.
- **PV:** Pontos de Vitória.
- **Relâmpago:** o telegrama interceptado no meio do turno, com as ordens de operações de um inimigo.
- **T (tempo de combate):** o tempo fixo de cada batalha, igual a 0,9.
- **Território:** uma das 34 áreas do mapa.
- **W (mão de obra):** a força de trabalho disponível para produzir, informada no dossiê.
