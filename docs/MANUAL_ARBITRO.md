# ESTADO-MAIOR — Manual do árbitro

Para a equipe organizadora. Leia inteiro pelo menos uma vez, de preferência durante o ensaio.

---

## 1. Visão geral

O jogo roda num **PC servidor**. Os computadores das salas acessam pelo navegador, e o telão mostra o Teatro de Operações. Você conduz a partida pelo **painel do árbitro** (`/arbitro`), com a senha do árbitro. O painel tem abas: Nações, Diário, ao vivo, Avisos, Eventos, Ajuste de emergência, Ordens do turno, Segredos, Rollback e Credenciais.

O servidor cuida sozinho do relógio, das resoluções, dos dossiês, dos telegramas e das manchetes. O seu trabalho é:

- preparar o PC e testar antes;
- iniciar a partida e controlar o relógio (pausar, estender, resolver);
- disparar eventos e avisos quando for preciso;
- ajudar as equipes travadas, sem dar a resposta;
- encerrar a partida e anunciar o vencedor.

Recomenda-se uma dupla: **um árbitro** (conduz e fala com a sala) e **um operador** (cuida do PC, dos logs e das credenciais impressas).

---

## 2. Preparar o PC servidor

Resumo do `README.md`. O README completo tem as telas e as observações sobre Windows.

### 2.1 Instalação (uma vez)

1. Instale o **Docker**: Docker Desktop no Windows ou macOS (deixe-o aberto), ou Docker Engine com o plugin `docker compose` no Linux.
2. Copie a pasta do projeto para o PC.
3. Abra um terminal dentro da pasta e rode:

   ```
   docker compose up -d --build
   ```

   A primeira vez demora alguns minutos. Depois disso, o jogo sobe sozinho quando o PC reinicia (`restart: unless-stopped`).

### 2.2 Senha do árbitro

A senha padrão é `arbitro`. **Troque antes do evento.** Há duas formas:

- variável de ambiente: `ADMIN_PASSWORD=sua-senha-nova docker compose up -d` (macOS e Linux); no Windows (PowerShell), `$env:ADMIN_PASSWORD="sua-senha-nova"; docker compose up -d`;
- arquivo `.env` na pasta do projeto, com a linha `ADMIN_PASSWORD=sua-senha-nova`. O Docker lê esse arquivo sozinho.

O mesmo arquivo `.env` (ou as mesmas variáveis) aceita `N_FACTIONS`, `TURN_MINUTES` e `MAX_TURNS` (ver seção 3.2).

### 2.3 Endereço do PC e rede

- Descubra o IP do PC: `ipconfig` (Windows, "Endereço IPv4"), `ipconfig getifaddr en0` (macOS; tente `en1` se não aparecer nada) ou `hostname -I` (Linux).
- **Windows:** libere a porta 8000 no firewall, num PowerShell como administrador:

  ```
  netsh advfirewall firewall add rule name="Estado-Maior" dir=in action=allow protocol=TCP localport=8000
  ```

- Em macOS e Linux, normalmente nada precisa ser feito; se houver firewall ativo, libere a porta 8000.
- **Atenção à rede do evento.** Algumas redes Wi-Fi isolam os aparelhos entre si, e então um celular na mesma rede não enxerga o PC. Teste antes com um celular na rede do evento. Se não funcionar, use cabo ou um roteador próprio.
- O IP do PC pode mudar se a rede reatribuir endereços. Confirme o IP no próprio dia.

### 2.4 Endereços

Troque `IP` pelo IP do PC. No próprio PC, use `localhost`.

| Endereço | Para quem | Uso |
|---|---|---|
| `http://IP:8000/` | Equipes | Portão das nações (cada sala entra com sua senha) |
| `http://IP:8000/teatro` | Projetor | Mapa ao vivo, em tela cheia |
| `http://IP:8000/arbitro` | Árbitro | Painel de controle (senha do árbitro) |
| `http://IP:8000/api/server_time` | Operador | Teste rápido: responde com a hora do servidor |

### 2.5 Comandos do dia a dia

| O que fazer | Comando |
|---|---|
| Parar o jogo (os dados ficam guardados) | `docker compose down` |
| Ligar de novo | `docker compose up -d` |
| Reiniciar o servidor | `docker compose restart` |
| Ver o que está acontecendo | `docker compose logs -f` |
| **Zerar tudo** (apaga a partida e os arquivos de turnos) | `docker compose down -v` |

Atenção: `docker compose down -v` apaga a partida de forma definitiva. Use-o só para começar do zero. Depois dele, as equipes precisam entrar de novo, porque a chave de sessão muda.

### 2.6 Sem Docker (apenas para desenvolvimento)

Precisa de Python 3.12 ou mais novo: `pip install -r server/requirements-dev.txt`, depois `cd server` e `uvicorn app.main:app`. Os dados ficam na pasta `data/` da raiz do repositório. Para o evento, use o Docker.

---

## 3. Antes do evento

### 3.1 Checklist (dois dias antes e de novo na manhã)

- [ ] `docker compose up -d --build` sobe sem erro; `docker compose ps` mostra o serviço como saudável.
- [ ] A senha do árbitro foi trocada (e está anotada com o árbitro).
- [ ] Um celular na rede do evento abre `http://IP:8000/` e `http://IP:8000/teatro`.
- [ ] Ensaio com pelo menos duas nações: cada uma entra com a senha, envia uma ordem de cada seção, responde um desafio e vê o telegrama-relâmpago na metade do turno.
- [ ] No painel: iniciar, pausar, retomar, estender e resolver agora funcionam.
- [ ] Um rollback de teste volta ao turno anterior, e a partida continua.
- [ ] O Teatro aparece em tela cheia no projetor, na resolução real da sala.
- [ ] As credenciais foram impressas (ver 3.4).

### 3.2 Configurar a partida

Os parâmetros da partida são:

| Parâmetro | Padrão | Limite | Onde se configura |
|---|---|---|---|
| Número de nações (`N_FACTIONS`) | 4 | 2 a 6 | variável de ambiente, ou ao criar a partida |
| Duração do turno (`TURN_MINUTES`) | 12 | maior que zero | variável de ambiente, ou ao criar a partida |
| Número de turnos (`MAX_TURNS`) | 8 | 1 ou mais | variável de ambiente, ou ao criar a partida |
| Semente (`seed`) | aleatória | número inteiro | só ao criar a partida; fixa as senhas, as tropas neutras, o clima e os demais sorteios (o mapa é sempre o mesmo) |

- As nações que jogam são as **primeiras** da lista: GAU, EUL, HIL, NOE, CAU, RIE. Com 4 nações, jogam GAU, EUL, HIL e NOE. As pátrias não usadas viram território neutro (milícias).
- **Criar uma nova partida apaga a atual.** Você faz isso pelo painel, em NOVO JOGO (nações de 2 a 6, minutos por turno, número de turnos e semente opcional), ou pelo endpoint `POST /api/admin/new_game`.
- Depois de criar uma partida nova, as senhas mudam. Imprima as credenciais de novo.

### 3.3 Ensaio e limpeza

Faça um ensaio curto (dois turnos, duas nações). Depois do ensaio, **zere os dados** antes do evento:

```
docker compose down -v
docker compose up -d
```

Isso é importante: a pasta de turnos guarda os arquivos de todas as partidas anteriores (ver a seção 6.4). Um volume limpo evita rollbacks para o estado de outra partida.

### 3.4 Imprimir as credenciais

No painel, IMPRIMIR CREDENCIAIS lista, para cada nação, a sigla, o nome e a senha. Imprima uma folha por sala, com a sigla, o nome, a senha e o endereço do servidor. Entregue cada folha à sala antes do início. Guarde uma cópia com o árbitro.

Pelo endpoint, depois de entrar como árbitro: `GET /api/admin/credentials` devolve o dicionário `{sigla: senha}`.

---

## 4. Roteiro do dia

Os horários são de referência. Ajuste o que for preciso, sem perder o relógio.

### 4.1 Duração sugerida

- 8 turnos × 12 min = 96 min (1h36).
- Turno 1 mais longo: estenda em 6 min logo no início. Turno 1 com 18 min. Total: 1h42.
- Abertura de cerca de 15 min e encerramento de cerca de 10 min. **Total: cerca de 2h10**, mais uma pausa se você quiser.

### 4.2 Passo a passo

| Quando | O que fazer |
|---|---|
| 30 min antes | Ligue o PC, confirme `docker compose ps`, abra o painel e o Teatro no projetor. |
| 15 min antes | Distribua as credenciais às salas. Peça que entrem e verifiquem a senha. |
| Abertura (15 min) | Explique o objetivo, os quatro setores, o que é um turno e como ler um dossiê. Mostre um exemplo da Mesa de Cálculo. Deixe as salas explorarem por 3 minutos, sem prazo. |
| Início | No painel: **INICIAR GUERRA**. A partida passa para o turno 1. |
| Turno 1 (18 min) | Logo após iniciar, **estenda em 6 minutos** (+5 MIN e depois +1 MIN). O turno 1 é de aprendizagem. |
| Turnos 2 a 8 (12 min cada) | Acompanhe o painel. Ao meio do turno, o relâmpago chega às salas. |
| Entre turnos (opcional) | Se quiser uma pausa, **PAUSAR logo depois da resolução**. O turno seguinte começa parado, com quase todo o relógio. Retome quando quiser. |
| Fim do turno 8 | A partida encerra sozinha. Confira o vencedor no painel. |
| Encerramento (10 min) | Anuncie o vencedor e o ranking (seção 7). Converse sobre o que foi aprendido. |

---

## 5. Controles do painel do árbitro

Cada controle corresponde a uma ação do servidor. As restrições abaixo vêm do código: se a ação for recusada, a mensagem explica o motivo.

| Controle (rótulo no painel) | Efeito | Quando usar | Restrições |
|---|---|---|---|
| **INICIAR GUERRA** | Começa a guerra: turno 1, dossiês, notícia de abertura | Uma vez, quando as salas estiverem prontas | Só com a partida em espera |
| **PAUSAR** / **RETOMAR** | Para ou retoma o relógio. Com a partida pausada, ordens e desafios ficam bloqueados; telegramas diplomáticos continuam | Problema técnico, pausa, decisão de regra | Pausar só com a partida em andamento; retomar só se estiver pausada |
| **+1 MIN** / **+5 MIN** (estender) | Soma minutos ao turno atual. Não zera o relógio | Turno 1 mais longo; atraso técnico | Em andamento ou pausada |
| **RESOLVER AGORA** | Resolve o turno imediatamente e começa o próximo | Todas as salas já enviaram; ou para encerrar um turno cedo | Em andamento ou pausada. Só se desfaz com rollback |
| **Eventos** | Dispara um dos oito eventos (seção 5.1) | Para dar tensão, ou para ajudar uma nação atrasada | Só com a partida em andamento ou pausada. Vale para a próxima resolução |
| **Avisos** (ENVIAR AVISO: texto e destinatário) | Envia um telegrama "AVISO DO ÁRBITRO" a todas as nações, ou a uma só | Regras, mudanças de horário, lembretes | A qualquer momento |
| **Ajuste de emergência** (APLICAR À NAÇÃO ou APLICAR AO TERRITÓRIO) | Altera Alimento, Aço, Combustível e moral de uma nação; ou batalhões e dono de um território | Último recurso (seção 6.5) | A qualquer momento. Os dossiês já entregues não são recalculados |
| **Rollback** (VOLTAR AO TURNO) | Substitui o estado atual pelo salvo ao fim do turno escolhido. Ordens, resoluções e avisos posteriores são descartados | Resolução errada, ou erro do servidor | Só volta a turnos já resolvidos (seção 6.4) |
| **IMPRIMIR CREDENCIAIS** | Mostra a senha de cada nação | Impressão, ou quando uma sala esquece a senha | — |
| **MOSTRAR SEGREDOS** (aba Segredos) | Mostra os gabaritos, as chaves, as matrizes, os climas, os depósitos, as ordens e os telegramas em texto claro | Para conferir respostas e ajudar equipes (seção 6.3) | Nunca mostre essa tela às salas |
| **NOVO JOGO** | Cria uma partida nova e apaga a atual | Só antes do evento, ou para recomeçar | Ver seção 3.2 |

### 5.1 Os oito eventos

| Evento | Efeito |
|---|---|
| Greve na siderurgia | Produção de Aço −30%, neste turno |
| Colheita recorde | Produção de Alimento +30%, neste turno |
| Epidemia de gripe | Mão de obra −15%, por 2 turnos |
| Descoberta de petróleo | Uma nação sorteada recebe 18 de Combustível |
| Inverno precoce | Consumo civil +2 ALI, movimentos 50% mais caros, ataques −10%, por 2 turnos |
| Sabotagem ferroviária | Uma nação sorteada perde 25% do Combustível; movimentos custam o dobro, neste turno |
| Ajuda estrangeira | A nação com menos PV recebe 12 ALI, 8 ACO e 8 COM |
| Motim nas tropas | A nação de moral mais baixa perde 12 de moral |

Atenção a dois deles: **ajuda estrangeira** ajuda quem está atrás; **motim** pune quem está com a moral mais baixa, que costuma ser a nação mais fraca. Use motim com critério. Em geral, o servidor já sorteia um evento a cada turno a partir do turno 2, com 60% de chance. Você pode disparar um manualmente, e o sorteio automático continua.

### 5.2 Vencedor e fim de partida

A partida termina sozinha quando:

- o último turno é resolvido;
- uma nação chega a 21 territórios (dominação, 60%);
- só sobra uma nação de pé.

O campo `winner` (vencedor) e o campo `end_reason` (motivo: `domination`, `last_standing` ou `turns`) aparecem no estado público e no painel.

---

## 6. Se algo der errado

### 6.1 A página não abre, ou as salas perdem a conexão

1. Confira no PC: `docker compose ps` (o serviço precisa estar "running") e `docker compose logs -f`.
2. Se o serviço caiu: `docker compose up -d`.
3. Se o serviço está de pé, mas as salas não entram: confira o IP (ele pode ter mudado), o firewall (porta 8000) e se os celulares enxergam o PC (seção 2.3).
4. As salas recebem a atualização sozinhas quando a conexão volta. Se uma tela parecer parada, peça que recarreguem a página.

### 6.2 O PC reiniciou no meio da partida

- O estado da partida é salvo a cada mudança, e volta sozinho quando o servidor sobe. Não é preciso refazer nada.
- A partida **volta em andamento**, não pausada. Assim que o servidor subir, confira o relógio no painel. Se você não estiver pronto, **pause na hora**.
- Se o prazo do turno já tinha passado quando o servidor voltou, o turno recebe o tempo que restava no último registro salvo (no mínimo 30 segundos). Se o prazo ainda não passou, o relógio segue normalmente, e o tempo fora do ar conta.
- Avise as salas do que aconteceu, e peça que recarreguem a página.

### 6.3 Uma equipe travou

Ajude sem dar a resposta. O objetivo é que a equipe entenda o método.

- **Pergunte primeiro:** o que o número da tabela significa? Qual foi a primeira conta?
- **Aponte a etapa, não o resultado:** por exemplo, "a sua matriz A está dividindo as colunas ou as linhas de Z?". Use a seção do manual da equipe.
- **Use os gabaritos só para verificar:** em "Mostrar segredos" você vê a resposta correta e a sua tolerância. Não diga números. Diga o tipo de erro.

Dicas por seção, com o tipo de erro mais comum:

| Seção | Erro comum | Dica que não revela a resposta |
|---|---|---|
| Intendência | Dividir as linhas de Z em vez das colunas | "Confira em qual direção você divide: a produção de cada setor está na coluna." |
| Intendência | Responder d em vez de x | "A pergunta é a produção bruta, não a entrega final. Qual a relação entre as duas?" |
| Operações | Usar a linha do estado errado no Markov | "Qual é o estado de hoje? Use a linha dele." |
| Operações | Contar a transição da última observação | "A última observação não tem sucessor. Quantas transições existem no total?" |
| Inteligência | O cifrado não bate com o trecho claro | "O espaço conta como símbolo. Confira o comprimento dos dois trechos." |
| Inteligência | Coordenadas trocadas | "Coluna é a letra, linha é o número. Qual é o x e qual é o y?" |
| Governo | Coluna `obs` na regressão | "A coluna obs é só o número da linha. Ela entra como variável?" |
| Governo | Esquecer o intercepto | "O modelo tem termo constante? Quantas colunas o X precisa ter?" |

### 6.4 Rollback

- O rollback volta ao **estado salvo ao fim da resolução do turno N**. Esse estado já é o início do turno N+1: dossiês novos, ordens vazias e relógio do turno cheio (ou o tempo que restava, se o prazo ainda não passou).
- Tudo o que aconteceu depois daquele ponto some: ordens, mensagens, ajustes do árbitro e resoluções.
- O rollback só volta a turnos já resolvidos. Não existe arquivo do turno 0, então não é possível voltar ao início da partida. Para recomeçar, crie uma nova partida e zere os arquivos (seção 3.3).
- Use com cuidado. Se uma resolução estiver errada, é mais seguro explicar à sala o que aconteceu e corrigir com ajuste de emergência, a menos que o erro seja do servidor.
- **Cuidado com partidas anteriores:** a pasta de turnos não é apagada ao criar uma partida nova. Se você fizer rollback para um turno que a partida atual ainda não jogou, o servidor pode carregar o arquivo de outra partida. Por isso, zere os dados (seção 3.3) entre o ensaio e o evento, e não use rollback para turnos de outra partida.

### 6.5 Uma nação está muito atrás

Antes de qualquer intervenção, pense se a partida deve ser assim. Diferença grande de PV é normal num jogo com dados e sorte. Mas, se a equipe perdeu o interesse:

1. **Use os eventos:** a ajuda estrangeira vai para a nação com menos PV, sem você escolher.
2. **Use um aviso público** para contar uma história: um boato, uma oferta de paz, uma notícia do front. Isso dá motivos para a diplomacia.
3. **Ajuste de emergência, só em último caso:** aumentar a moral ou o estoque de uma nação. Anote a decisão e explique à sala, para que a intervenção não pareça favoritismo.

### 6.6 Um desafio parece errado

- Confira o gabarito em "Mostrar segredos" e refaça a conta. O motor é a fonte de verdade.
- Se o problema for real, o painel não tem como alterar o desafio. Anote o caso, compense a sala com cuidado (por exemplo, com moral) e corrija o problema na próxima partida.

### 6.7 Uma ordem está errada

- Você não pode editar ordens. A equipe pode reenviar até o prazo, e vale a última ordem válida.
- Se a equipe enviou algo que o servidor aceitou por engano, e a resolução ficou errada, use o rollback e explique.

---

## 7. Encerrar e anunciar o vencedor

1. A partida encerra sozinha quando o último turno é resolvido, ou quando há dominação. Não há comando para encerrar antes disso. Se o tempo acabar e for preciso parar mais cedo, use "resolver agora" nos turnos que faltam: cada clique resolve um turno, e a partida acaba após o último.
2. Leia o ranking no painel. O critério de ordem é: mais PV, depois mais territórios, depois mais batalhões.
3. Anuncie no Teatro e para as salas, com um aviso público. Diga a nação vencedora, o motivo (turnos, dominação ou última nação de pé) e o ranking completo.
4. Não desligue o PC nem zere os dados até que a equipe e os participantes tenham saído. `docker compose down` preserva a partida. `docker compose down -v` apaga.

---

## 8. Referência rápida dos endpoints do árbitro

Todos exigem o cookie de árbitro, obtido em `POST /api/admin/login` com `{"password": "..."}`.

| Método | Caminho | Corpo | Para que serve |
|---|---|---|---|
| GET | `/api/admin/state` | — | Estado completo, com segredos |
| GET | `/api/admin/credentials` | — | Senhas de cada nação |
| GET | `/api/admin/events` | — | Lista dos eventos disponíveis |
| POST | `/api/admin/new_game` | `{n_factions, turn_minutes, max_turns, seed?}` | Cria uma partida nova (apaga a atual) |
| POST | `/api/admin/start` | — | Inicia a guerra |
| POST | `/api/admin/pause` | — | Pausa |
| POST | `/api/admin/resume` | — | Retoma |
| POST | `/api/admin/extend` | `{minutes}` | Estende (ou encurta, se negativo) o turno atual. É o que os botões +1 MIN e +5 MIN enviam |
| POST | `/api/admin/resolve_now` | — | Resolve o turno agora |
| POST | `/api/admin/rollback` | `{turn}` | Volta ao estado salvo após a resolução do turno |
| POST | `/api/admin/broadcast` | `{text, to}` (`to` = `all` ou a sigla) | Aviso do árbitro |
| POST | `/api/admin/edit_faction` | `{faction_id, patch}` | Ajuste de emergência (`stock`, `morale`, `troops`, `owner`, `capitulated`) |
| POST | `/api/admin/event` | `{event_id}` | Dispara um evento |

Para o painel e para os operadores, `docker compose logs -f` mostra os erros do servidor. Erros do jogo voltam como `{"detail": "mensagem em português"}`.
