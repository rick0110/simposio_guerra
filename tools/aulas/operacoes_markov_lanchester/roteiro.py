"""Roteiro da aula "Operações · Markov e Lanchester" (texto na forma falada).

Exemplos (os mesmos do manual, conferidos com o motor do jogo):
  Markov: 20 observações  L C C T C L L C T T C L C C L T C L L C
          contagem  L:[2 4 1]  C:[4 2 2]  T:[0 3 1]  ->  P(chuva -> tempestade) = 2/8 = 0,25
  Lanchester: 12 atacantes contra 6 defensores em montanha, moral 70 dos dois lados
          α = 1,2; β = 1,2 × 1,5 = 1,8; 1,2·12² = 172,8 > 1,8·6² = 64,8 -> sobram √((172,8 − 64,8)/1,2) ≈ 9,5
"""

TITULO = "Operações · Markov e Lanchester"
CLIPE_ROTULO = "NO JOGO · ABA OPERAÇÕES"

CENAS = [
    ("abertura", [
        "Madrugada, na sala de Operações. As tropas estão prontas, e o comandante tem duas perguntas.",
        "Primeira: o tempo vai ajudar ou atrapalhar? Segunda: se atacarmos, vencemos? "
        "Para a primeira, cadeias de Márkof. Para a segunda, a lei de Lântchester.",
    ]),
    ("clima", [
        "O tempo de cada região só tem três estados: limpo, chuva e tempestade. E a regra é simples: "
        "o tempo de amanhã depende só do tempo de hoje. Isso é uma cadeia de Márkof.",
        "O dossiê traz o diário do tempo. Para estimar as chances, contamos as transições: quantas vezes "
        "a chuva foi seguida de limpo, de chuva, ou de tempestade.",
        "Neste diário, a chuva aparece oito vezes antes de outro dia. Quatro vezes virou limpo, duas continuou "
        "chuva, e duas virou tempestade.",
        "Dividindo cada linha pelo seu total, temos a matriz de transição P. Se hoje chove, a chance de "
        "tempestade amanhã é dois em oito: zero vírgula vinte e cinco. E para daqui a dois turnos, "
        "basta usar P ao quadrado.",
    ]),
    ("por_que_clima", [
        "Por que isso importa? A tempestade enfraquece quem ataca, e fecha as rotas marítimas: "
        "a travessia é cancelada, e as tropas ficam paradas no porto.",
        "Quem resolve o desafio de Operações descobre o clima exato da resolução. Saber se vai chover "
        "decide se o ataque sai hoje ou espera.",
    ]),
    ("lanchester", [
        "Agora, a batalha. Dois exércitos atirando um no outro. A cada instante, cada lado perde tropas "
        "na proporção do tamanho e da eficácia do outro.",
        "A perde na velocidade beta vezes B. B perde na velocidade alfa vezes A. É um sistema de equações "
        "diferenciais, mas ele esconde uma quantidade que nunca muda.",
        "Alfa vezes A ao quadrado, menos beta vezes B ao quadrado: esse número é o mesmo do começo ao fim "
        "da batalha. Por isso, vence quem começa com a maior força, alfa A zero ao quadrado, ou beta B zero "
        "ao quadrado.",
        "Repare no quadrado. Dobrar o exército quadruplica a força. Por isso, na guerra de Lântchester, "
        "concentrar tropas num só ataque vale muito mais do que dividir.",
    ]),
    ("exemplo", [
        "Vamos ao exemplo. Doze batalhões atacam seis, que defendem uma montanha. Os dois lados com moral setenta.",
        "A eficácia é zero vírgula cinco mais a moral sobre cem: um vírgula dois. O atacante fica com isso. "
        "O defensor ganha o bônus da montanha: um vírgula dois vezes um vírgula cinco, um vírgula oito.",
        "Força do atacante: um vírgula dois vezes doze ao quadrado, cento e setenta e dois vírgula oito. "
        "Do defensor: um vírgula oito vezes seis ao quadrado, sessenta e quatro vírgula oito. Vence o atacante.",
        "E sobram cerca de nove batalhões e meio: a raiz da diferença, dividida por alfa. "
        "Mas atenção: a batalha dura no máximo zero vírgula nove. Se ninguém zerar até lá, é indecisa, "
        "e o atacante recua.",
    ]),
    ("ordens", [
        "Para dar a ordem: cada batalhão que marcha por terra gasta um de combustível; pelo mar, dois. "
        "Território vazio é tomado sem luta, e ataques de origens diferentes ao mesmo alvo se somam.",
        "E fiquem atentos ao telegrama-relâmpago, na metade do turno: ele traz as ordens do inimigo. "
        "Com a Inteligência, dá para mudar a defesa a tempo.",
    ]),
    ("jogo", [
        "No jogo, abra a aba Operações. O desafio pede a chance de tempestade numa região. "
        "Clique em abrir na Mesa, no diário do tempo.",
        "A ferramenta Márkof conta as transições e monta P. Escolha a região e o estado de hoje, "
        "e calcule: a previsão aparece em barras.",
        "Use a probabilidade de tempestade no questionário, e envie.",
        "Para atacar, clique num território seu no mapa, depois no alvo destacado. Escolha quantos batalhões "
        "e lance a ordem. A prévia mostra o pior e o melhor caso pela lei de Lântchester. "
        "No fim, assine e carimbe.",
    ]),
    ("fim", [
        "Uma contagem que vira matriz, e uma conta que não muda durante a batalha. Com isso, vocês sabem quando "
        "atacar, e com quanto.",
        "Boa sorte, comandante.",
    ]),
]

SEQUENCIA = [("Titulo", None), ("Abertura", "abertura"), ("Clima", "clima"), ("PorQueClima", "por_que_clima"),
             ("Lanchester", "lanchester"), ("Exemplo", "exemplo"), ("Ordens", "ordens"), ("JOGO", "jogo"),
             ("Fim", "fim"), ("Creditos", None)]
