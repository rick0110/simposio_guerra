"""Roteiro da aula "Intendência · O modelo de Leontief" (texto na forma falada).

Exemplo numérico (o mesmo do manual, conferido com o motor do jogo):
    Z = [[3, 4, 0], [6, 2, 1], [3, 0, 2]], X = (30, 20, 10)
    A = [[0,1; 0,2; 0], [0,2; 0,1; 0,1], [0,1; 0; 0,2]]
    d = (23, 11, 5)  ->  x = (30, 20, 10)
"""

TITULO = "Intendência · O modelo de Leontief"
CLIPE_ROTULO = "NO JOGO · ABA INTENDÊNCIA"

CENAS = [
    ("abertura", [
        "Inverno no Continente de Lebêg. No porão do Quartel-General, a Intendência faz a conta mais importante "
        "da guerra: quanto produzir.",
        "A nação tem três setores: alimento, aço e combustível. E nenhum deles trabalha sozinho. A fazenda precisa "
        "de trator, que é aço. O trator precisa de combustível. E quem trabalha na usina precisa comer.",
        "Por isso, a pergunta não é só quanto a tropa precisa. É quanto a nação inteira precisa produzir, "
        "para que, no fim, sobre o que a tropa precisa.",
    ]),
    ("tabela", [
        "O dossiê traz a tabela de transações do turno anterior. Cada linha mostra para onde foi a produção "
        "de um setor.",
        "Na linha do alimento, coluna do aço, está o número quatro. Quer dizer: quatro unidades de alimento "
        "foram consumidas pelo setor de aço. Comida dos operários da siderúrgica.",
        "E a última linha, xis maiúsculo, é a produção total de cada setor: trinta de alimento, vinte de aço "
        "e dez de combustível.",
    ]),
    ("matriz_a", [
        "Mas o que interessa é a receita: quanto de cada insumo um setor gasta por unidade que produz. "
        "Para isso, dividimos cada coluna pela produção do próprio setor.",
        "A coluna do alimento, dividimos por trinta. A do aço, por vinte. A do combustível, por dez. "
        "O resultado é a matriz técnica, A.",
        "Leia assim: o zero vírgula dois, na linha do alimento e na coluna do aço, diz que cada unidade de aço "
        "consome dois décimos de unidade de alimento.",
    ]),
    ("equacao", [
        "Agora chame de xis a produção bruta: o quanto cada setor produz. Uma parte dela é consumida pelos "
        "próprios setores, como insumo. Essa parte é A vezes xis.",
        "O que sobra é a entrega líquida, d: o que fica de verdade para a nação, para as tropas e para o estoque. "
        "Então: xis menos A xis é igual a d.",
        "Colocando xis em evidência: a identidade menos A, vezes xis, igual a d. "
        "Um sistema linear, com três equações e três incógnitas.",
        "E cuidado com a confusão mais comum: d é o que vocês querem entregar. Xis é o que vocês mandam produzir. "
        "A ordem pede xis.",
    ]),
    ("resolver", [
        "Vamos ao exemplo. O Gabinete exige uma entrega de vinte e três de alimento, onze de aço "
        "e cinco de combustível.",
        "A matriz identidade menos A tem uns na diagonal, menos os números de A. Cada linha vira uma equação.",
        "Escalonando o sistema, ou resolvendo na Mesa de Cálculo, chegamos a: xis igual a trinta, vinte e dez.",
        "E conferimos a primeira linha: zero vírgula nove vezes trinta, menos zero vírgula dois vezes vinte, "
        "dá vinte e três. Bate. Para entregar vinte e três de comida, a nação precisa produzir trinta.",
    ]),
    ("limites", [
        "Mas a produção tem limites. Cada setor tem uma capacidade máxima, e cada unidade produzida gasta "
        "mão de obra. Se faltar gente, o servidor corta a produção na mesma proporção.",
        "E o alimento sustenta as tropas e o povo. Cada batalhão come meia unidade por turno. "
        "Se faltar comida, a moral despenca, e um décimo das tropas deserta.",
        "Quem resolve o desafio do turno ganha dez por cento a mais de produtividade. Vale o esforço.",
    ]),
    ("jogo", [
        "No jogo, abra a aba Intendência. O dossiê traz a tabela de transações, e o desafio traz a entrega "
        "exigida pelo Gabinete.",
        "Clique em abrir na Mesa de Cálculo. A ferramenta Leontief recebe a tabela. Digite a entrega d "
        "e clique em calcular.",
        "Use o resultado no questionário, e envie. Se a resposta estiver certa, o bônus está garantido.",
        "Depois, copie a produção para a ordem, escolha quantos batalhões recrutar, "
        "e clique em assinar e carimbar.",
    ]),
    ("fim", [
        "Uma tabela, uma divisão por colunas e um sistema linear. É assim que se planeja uma economia inteira. "
        "Foi com essa ideia que Vassíli Leôntief ganhou o prêmio Nobel.",
        "Boa sorte, intendente.",
    ]),
]

SEQUENCIA = [("Titulo", None), ("Abertura", "abertura"), ("Tabela", "tabela"), ("MatrizA", "matriz_a"),
             ("Equacao", "equacao"), ("Resolver", "resolver"), ("Limites", "limites"), ("JOGO", "jogo"),
             ("Fim", "fim"), ("Creditos", None)]
