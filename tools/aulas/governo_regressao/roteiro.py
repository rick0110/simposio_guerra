"""Roteiro do vídeo de instrução "Governo · Regressão linear".

Cada cena é uma lista de falas. A voz (narracao.py) gera um áudio por fala, e as animações (cenas.py)
usam a duração de cada fala para sincronizar. Os textos já estão escritos para serem FALADOS:
números por extenso, sem símbolos.
"""

TITULO = "O que faz um povo feliz? Regressão linear"

CENAS = [
    ("abertura", [
        "Inverno de mil novecentos e quarenta e três. No Gabinete de Noetéria, o ministro olha para um único "
        "número na parede: a moral do povo.",
        "Ela caiu de setenta para sessenta e dois em apenas dois turnos. E, com a moral, cai tudo: as fábricas "
        "produzem menos, e o exército luta pior.",
        "Na mesa, três propostas. Gastar aço em propaganda. Aliviar o racionamento. Reduzir a jornada de "
        "trabalho. Cada uma custa caro.",
        "A pergunta do ministro é simples: quanto cada uma dessas medidas realmente mexe na moral?",
        "Para responder, ninguém precisa adivinhar. Precisamos de dados. E de uma das ferramentas mais usadas "
        "de toda a ciência: a regressão linear.",
    ]),
    ("dados", [
        "O serviço de estatística entrega uma pesquisa de opinião. Cada linha é uma observação: uma província, "
        "numa semana.",
        "Nas colunas, o que o governo fez naquela semana: o nível de ração, os pontos de propaganda, as horas "
        "extras de trabalho. E o que aconteceu na guerra: as baixas, e os territórios ganhos ou perdidos.",
        "Na última coluna, o que queremos explicar: quanto a moral subiu, ou desceu.",
        "As primeiras colunas são as causas que suspeitamos. A última é o efeito. Na linguagem da estatística: "
        "variáveis explicativas, e variável resposta.",
    ]),
    ("reta", [
        "Vamos começar com uma causa só: a propaganda. Cada observação vira um ponto. No eixo horizontal, a "
        "propaganda. No vertical, a variação da moral.",
        "Os pontos não caem numa linha perfeita. Há o clima, há as notícias, há o acaso. Mas dá para ver uma "
        "tendência: mais propaganda, mais moral.",
        "A ideia da regressão é resumir essa tendência numa reta. A variação da moral é, aproximadamente, beta "
        "zero, mais beta um vezes a propaganda.",
        "Mas existem infinitas retas. Qual delas é a melhor?",
        "Para cada ponto, medimos o quanto a reta erra: a distância vertical até ele. Esse erro se chama "
        "resíduo.",
        "Elevamos cada resíduo ao quadrado, e somamos tudo. Ao quadrado, porque assim os erros para cima e para "
        "baixo não se cancelam, e um erro grande pesa muito mais do que um erro pequeno.",
        "A melhor reta é a que deixa essa soma a menor possível. Por isso o método se chama: mínimos quadrados.",
    ]),
    ("leitura", [
        "E agora vem a parte que interessa ao ministro. O que significam esses números?",
        "Beta um, a inclinação, é a resposta. Para cada ponto a mais de propaganda, a moral muda, em média, beta "
        "um pontos. Se beta um vale um vírgula quatro, cada ponto de propaganda rende quase um ponto e meio de "
        "moral.",
        "Beta zero, o intercepto, é quanto a moral muda quando a propaganda é zero. É a tendência de fundo: o que "
        "acontece quando o governo não faz nada.",
    ]),
    ("plano", [
        "Só que existe uma armadilha. Talvez as províncias que receberam mais propaganda também tenham tido um "
        "racionamento mais duro. Olhando só para a propaganda, misturamos os dois efeitos.",
        "A solução é colocar todas as causas na mesma equação. A variação da moral é beta zero, mais beta um "
        "vezes a ração, mais beta dois vezes a propaganda, e assim por diante: uma parcela para cada causa.",
        "Com duas causas, a reta vira um plano. Cada observação agora flutua no espaço, e procuramos o plano que "
        "passa mais perto de todas elas.",
        "E cada beta ganha um significado precioso: o efeito daquela causa, mantendo todas as outras fixas.",
    ]),
    ("matriz", [
        "Mas como calcular todos esses betas de uma vez? É aqui que entra a álgebra linear.",
        "Escrevemos uma equação para cada observação, e empilhamos tudo. As variações da moral formam um vetor, "
        "y. As causas formam uma matriz, X: uma linha por observação, uma coluna por causa. E os betas formam o "
        "vetor beta.",
        "Repare na primeira coluna de X: ela é toda de uns. É ela que carrega o beta zero, o intercepto.",
        "Em forma de matriz, a regressão diz só isto: y é aproximadamente X vezes beta.",
    ]),
    ("projecao", [
        "Agora, uma imagem. Pense em y como uma seta, num espaço com uma dimensão para cada observação.",
        "Tudo o que X vezes beta consegue produzir, variando os betas, forma um plano dentro desse espaço.",
        "Quase sempre, y está fora desse plano. Então procuramos o ponto do plano mais perto de y. E o ponto mais "
        "perto é a sombra de y: a sua projeção perpendicular.",
        "Perpendicular quer dizer que o erro, y menos X beta, faz um ângulo reto com todas as colunas de X. Em "
        "símbolos: X transposta, vezes y menos X beta, é igual a zero.",
        "Distribuindo, chegamos às equações normais: X transposta X, vezes beta, é igual a X transposta y.",
        "E, se X transposta X tem inversa, a resposta sai direto: beta é a inversa de X transposta X, vezes X "
        "transposta y.",
        "É exatamente a mesma resposta que minimiza a soma dos quadrados. A geometria e o cálculo chegam ao mesmo "
        "lugar.",
    ]),
    ("decisao", [
        "Com os betas em mãos, o ministro lê o país. O beta da ração é negativo: apertar o racionamento derruba "
        "a moral. O da propaganda é positivo. O das horas extras, negativo.",
        "E o tamanho de cada beta é o preço de cada decisão. Se um nível de ração custa três pontos de moral, e "
        "um ponto de propaganda devolve um e meio, o ministro já sabe o que está comprando.",
        "Só um cuidado: a regressão mede associações nos dados. Ela só conta uma história de causa e efeito "
        "quando nenhuma causa importante ficou de fora.",
    ]),
    ("jogo", [
        "No jogo, esse é o desafio do Governo. Na aba Governo, o dossiê traz a pesquisa de opinião da sua nação.",
        "Clique em: Abrir na Mesa, regressão. A Mesa de Cálculo monta a matriz e resolve as equações normais por "
        "você. Clique em Estimar.",
        "O desafio pede o beta da propaganda. Clique em usar no questionário, e envie. Se estiver certo, sua "
        "nação ganha cinco pontos de moral.",
        "Mas o prêmio de verdade é conhecer o número. Cada nação tem a sua cultura: em uma, a propaganda rende "
        "muito; em outra, quase nada. Quem conhece os próprios betas gasta o aço onde ele vale mais.",
    ]),
    ("fim", [
        "Uma tabela de números. Uma reta. Uma sombra, num espaço de muitas dimensões. E, no fim, uma decisão "
        "melhor no Gabinete.",
        "Boa sorte, ministro.",
    ]),
]
