"""Roteiro da aula "Inteligência · Cifra de Hill e mínimos quadrados" (texto na forma falada).

Exemplos (os mesmos do manual, conferidos com o motor do jogo):
  Hill: K = [[3, 5], [2, 7]] (mod 37); "URGENTE ATACA K7" -> "8LBDXLHBVWKO64K3"
        P = [[20, 6], [17, 4]] ("UR", "GE"), C = [[34, 1], [11, 3]] ("8L", "BD")
        det P = −22 ≡ 15; 15⁻¹ = 5; P⁻¹ ≡ [[20, 7], [26, 26]]; K = C·P⁻¹ ≡ [[3, 5], [2, 7]]
  Triangulação: E1 = (100; 100), E2 = (700; 150), E3 = (300; 650); distâncias 394,1; 332,9; 341,8
        1200x + 100y = 536 992,4 e 400x + 1100y = 530 987,6  ->  (420; 330), quadrícula I7
"""

TITULO = "Inteligência · Cifra de Hill e mínimos quadrados"
CLIPE_ROTULO = "NO JOGO · ABA INTELIGÊNCIA"

CENAS = [
    ("abertura", [
        "Sala de Inteligência. Os rádios chiam a noite inteira, e as mensagens do inimigo chegam como uma "
        "sopa de letras e números.",
        "Vocês têm duas missões: ler o que o inimigo escreve, e descobrir onde ele guarda os suprimentos. "
        "A primeira se resolve com matrizes. A segunda, com mínimos quadrados.",
    ]),
    ("hill_ideia", [
        "A cifra do inimigo é a cifra de Ríl. Primeiro, cada símbolo vira um número: as letras de zero a "
        "vinte e cinco, os algarismos de vinte e seis a trinta e cinco, e o espaço é trinta e seis. "
        "Trinta e sete símbolos.",
        "A mensagem é cortada em pares, e cada par vira um vetor. A chave é uma matriz dois por dois, K. "
        "O vetor cifrado é K vezes o vetor claro.",
        "Só que as contas são feitas módulo trinta e sete: como num relógio de trinta e sete horas, "
        "passou de trinta e seis, volta para o zero. Fica só o resto da divisão por trinta e sete.",
        "Sem a chave, a mensagem é ilegível. Com a chave, basta multiplicar pela inversa. "
        "O problema é descobrir K.",
    ]),
    ("hill_chave", [
        "E aqui está a falha do inimigo: toda mensagem começa com a palavra urgente, seguida de um espaço. "
        "Nós conhecemos o começo do texto claro. Essa é a nossa pedra de Roseta.",
        "Os dois primeiros pares, u-erre e gê-é, formam as colunas da matriz P. Os dois primeiros pares cifrados, "
        "oito-éle e bê-dê, formam as colunas de C. Como C é igual a K vezes P, a chave é C vezes a inversa de P.",
        "Para inverter P módulo trinta e sete: o determinante é menos vinte e dois, que vale quinze. "
        "E o inverso de quinze é cinco, porque quinze vezes cinco dá setenta e cinco, "
        "que é duas vezes trinta e sete, mais um.",
        "Multiplicando tudo e reduzindo módulo trinta e sete, sai a chave: três, cinco, dois, sete.",
    ]),
    ("hill_decifrar", [
        "Com a chave na mão, a Mesa de Cálculo decifra o resto: urgente, ataca cá sete. "
        "A mensagem mostra tropas, estoques e moral de verdade do inimigo.",
        "E a chave de cada nação vale por dois turnos. O telegrama-relâmpago usa a mesma chave: "
        "quem já tem a chave lê as ordens do inimigo na hora.",
    ]),
    ("deposito", [
        "Segunda missão: o depósito. Quatro estações de escuta medem a distância até ele, com algum ruído. "
        "Cada medida diz que o depósito está num círculo em volta da estação.",
        "A equação de um círculo tem quadrados. Mas, subtraindo a equação da primeira estação das outras, "
        "os quadrados de xis e de ípsilon se cancelam, e sobra um sistema linear.",
        "Com três estações, o sistema tem solução exata. No exemplo, o depósito está em quatrocentos e vinte, "
        "trezentos e trinta.",
        "Com quatro estações, há mais equações do que incógnitas, e o ruído impede uma solução exata. "
        "Então usamos mínimos quadrados: as equações normais, A transposta A vezes p, igual a A transposta b.",
    ]),
    ("recompensa", [
        "A resposta pode ser dada em coordenadas ou em quadrícula: a letra é a coluna, o número é a linha. "
        "Quatrocentos e vinte, trezentos e trinta, é a quadrícula i sete.",
        "Quem acerta descobre as tropas exatas daquele território, e libera o bombardeio: por quatro de "
        "combustível, o inimigo perde um quarto do seu maior estoque, e a economia dele piora no turno seguinte.",
    ]),
    ("jogo", [
        "No jogo, abra a aba Inteligência. Nos criptogramas, clique em abrir na Mesa: a ferramenta de Ríl "
        "já vem com o texto cifrado e a palavra urgente.",
        "Recupere a chave, e decifre a mensagem.",
        "Para o desafio, abra na Mesa as leituras das estações, calcule a triangulação, use o resultado "
        "no questionário, e envie.",
        "Com o depósito localizado, a ordem de bombardeio fica liberada. Escolha o alvo, assine e carimbe.",
    ]),
    ("fim", [
        "Uma matriz que esconde, uma inversa que revela, e um sistema que não tem solução exata, "
        "mas tem a melhor solução possível.",
        "Boa sorte, agente.",
    ]),
]

SEQUENCIA = [("Titulo", None), ("Abertura", "abertura"), ("HillIdeia", "hill_ideia"), ("HillChave", "hill_chave"),
             ("HillDecifrar", "hill_decifrar"), ("Deposito", "deposito"), ("Recompensa", "recompensa"),
             ("JOGO", "jogo"), ("Fim", "fim"), ("Creditos", None)]
