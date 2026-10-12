"""Caixa de ferramentas do ESTADO-MAIOR, para quem prefere programar (opcional).

Só depende de NumPy. Não importa o servidor do jogo: cada função é uma cópia fiel da lógica
do motor (server/app/engine), para que os resultados batam com os da Mesa de Cálculo.

Uso:
    python toolkit.py                       # demonstra cada função com os exemplos do manual
    from toolkit import leontief_A, ...     # num script seu, com toolkit.py na mesma pasta

Convenções do jogo:
- Matrizes: listas de listas ou arrays NumPy.
- Clima: 0 = limpo, 1 = chuva, 2 = tempestade (também aceita os nomes, com ou sem acento).
- Cifra de Hill: alfabeto de 37 símbolos, A–Z = 0–25, 0–9 = 26–35, espaço = 36; tudo módulo 37.
- Quadrícula do mapa: coluna = letra (x // 50), linha = y // 50 + 1. Ex.: (525, 310) = K7.
- CSV baixado do jogo: separador vírgula, ponto decimal, com BOM UTF-8.
"""

from __future__ import annotations

import csv
import itertools
import math
import tempfile
import unicodedata
from pathlib import Path

import numpy as np

SETORES = ["ALI", "ACO", "COM"]
CLIMAS = ["limpo", "chuva", "tempestade"]
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
MODULO = 37
COLUNAS = "ABCDEFGHIJKLMNOPQRSTUVWX"
CELULA = 50
FEATURES_PESQUISA = ["racao", "propaganda", "horas_extra", "baixas", "saldo_territorial"]


# ----------------------------------------------------------------------------- auxiliares
def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _clima(estado) -> int:
    """Aceita 0/1/2 ou o nome do clima ('limpo', 'chuva', 'tempestade')."""
    if isinstance(estado, str) and not estado.strip().lstrip("-+").isdigit():
        chave = _sem_acento(estado.strip().lower())
        if chave not in CLIMAS:
            raise ValueError(f"Clima desconhecido: {estado!r}. Use limpo, chuva ou tempestade.")
        return CLIMAS.index(chave)
    return int(estado)


def _numero(valor):
    """Converte para float quando dá; senão devolve o texto limpo."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return valor.strip() if isinstance(valor, str) else valor


def _normalizar(texto: str) -> str:
    """Maiúsculas, sem acentos, símbolos fora do alfabeto viram espaço, espaços repetidos colapsam.

    Como no motor, as bordas não são apagadas: "URGENTE " conserva o espaço final.
    """
    base = _sem_acento(str(texto).upper())
    saida = []
    for ch in base:
        ch = ch if ch in ALFABETO else " "
        if ch == " " and saida and saida[-1] == " ":
            continue
        saida.append(ch)
    return "".join(saida)


def _simbolos(texto: str) -> str:
    """Como _normalizar, mas sem colapsar espaços (criptogramas: o espaço é um símbolo)."""
    base = _sem_acento(str(texto).upper())
    return "".join(ch if ch in ALFABETO else " " for ch in base)


def _det_inteiro(M: list[list[int]]) -> int:
    n = len(M)
    if n == 1:
        return M[0][0]
    if n == 2:
        return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    total = 0
    for j in range(n):
        menor = [linha[:j] + linha[j + 1:] for linha in M[1:]]
        total += ((-1) ** j) * M[0][j] * _det_inteiro(menor)
    return total


def inversa_mod(K, m: int = MODULO) -> np.ndarray:
    """Inversa de uma matriz inteira módulo m (m primo): K⁻¹ = det⁻¹·adj(K) mod m.

    Para o inverso de um número só: pow(a, -1, m). Ex.: 15⁻¹ mod 37 = 5, porque 15·5 = 75 = 2·37 + 1.
    Levanta ValueError se o determinante for múltiplo de m.
    """
    M = np.array(K, dtype=float)
    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise ValueError("A chave deve ser uma matriz quadrada")
    if not np.allclose(M, np.rint(M)):
        raise ValueError("A chave deve conter apenas inteiros")
    Ki = [[int(round(v)) for v in linha] for linha in M]
    n = len(Ki)
    det = _det_inteiro(Ki) % m
    if det == 0:
        raise ValueError(f"Determinante ≡ 0 mod {m}: a chave não é invertível")
    det_inv = pow(det, -1, m)
    adj = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            menor = [linha[:j] + linha[j + 1:] for k, linha in enumerate(Ki) if k != i]
            cof = ((-1) ** (i + j)) * (_det_inteiro(menor) if n > 1 else 1)
            adj[j][i] = cof
    return np.array([[(det_inv * adj[i][j]) % m for j in range(n)] for i in range(n)], dtype=np.int64)


# ----------------------------------------------------------------------------- Intendência
def leontief_A(Z, X) -> np.ndarray:
    """Matriz técnica A = Z·diag(X)⁻¹: divida cada COLUNA j de Z pelo X_j.

    Z[i][j] é o insumo do setor i consumido pelo setor j; X é a produção total de cada setor.
    """
    Zm = np.array(Z, dtype=float)
    Xv = np.array(X, dtype=float).reshape(-1)
    if Zm.shape != (Xv.size, Xv.size):
        raise ValueError("Z deve ser n×n e X ter n valores")
    if np.any(Xv == 0):
        raise ValueError("A produção total X não pode ter zeros")
    return Zm / Xv[np.newaxis, :]


def leontief_x(A, d) -> np.ndarray:
    """Produção bruta x que entrega a demanda líquida d, ou seja, resolve (I − A)·x = d."""
    Am = np.array(A, dtype=float)
    dv = np.array(d, dtype=float).reshape(-1)
    if Am.shape != (dv.size, dv.size):
        raise ValueError("A deve ser n×n e d ter n valores")
    try:
        return np.linalg.solve(np.eye(dv.size) - Am, dv)
    except np.linalg.LinAlgError as exc:
        raise ValueError("I − A é singular: o sistema não tem solução única") from exc


# ----------------------------------------------------------------------------- Operações
def lanchester(A0: float, B0: float, alpha: float, beta: float, T: float = 0.9, steps: int = 60) -> dict:
    """Lei quadrática de Lanchester: A' = −β·B e B' = −α·A, até o tempo T.

    alpha = eficácia do atacante A; beta = eficácia do defensor B.
    Solução fechada, com w = sqrt(α·β):
        A(t) = A0·cosh(wt) − sqrt(β/α)·B0·sinh(wt)
        B(t) = B0·cosh(wt) − sqrt(α/β)·A0·sinh(wt)
    Para no primeiro instante em que um dos lados zera, ou em T.
    Retorna {"a_final", "b_final", "t_end", "winner", "trajectory"}; winner é "attacker",
    "defender" ou "none" (ninguém zerou até T).
    """
    if A0 < 0 or B0 < 0:
        raise ValueError("As forças iniciais não podem ser negativas")
    if alpha <= 0 or beta <= 0:
        raise ValueError("As eficácias alpha e beta devem ser positivas")
    if T < 0:
        raise ValueError("O tempo T não pode ser negativo")
    if steps < 2:
        raise ValueError("steps deve ser ≥ 2")

    w = math.sqrt(alpha * beta)
    if A0 <= 0 and B0 <= 0:
        return {"a_final": 0.0, "b_final": 0.0, "t_end": 0.0, "winner": "none",
                "trajectory": [[0.0, 0.0, 0.0] for _ in range(steps)]}

    def _tempo_zero(x: float) -> float:
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return math.inf
        return math.atanh(x) / w

    # B zera quando tanh(wt) = B0 / (sqrt(α/β)·A0); A zera quando tanh(wt) = A0 / (sqrt(β/α)·B0)
    t_B = 0.0 if B0 <= 0 else (math.inf if A0 <= 0 else _tempo_zero(B0 / (math.sqrt(alpha / beta) * A0)))
    t_A = 0.0 if A0 <= 0 else (math.inf if B0 <= 0 else _tempo_zero(A0 / (math.sqrt(beta / alpha) * B0)))

    if t_B <= T and t_B <= t_A:
        vencedor, t_fim = "attacker", t_B
    elif t_A <= T and t_A < t_B:
        vencedor, t_fim = "defender", t_A
    else:
        vencedor, t_fim = "none", T

    def estado(t: float) -> tuple[float, float]:
        if t_fim == 0.0:
            return A0, B0
        ch, sh = math.cosh(w * t), math.sinh(w * t)
        return (A0 * ch - math.sqrt(beta / alpha) * B0 * sh,
                B0 * ch - math.sqrt(alpha / beta) * A0 * sh)

    a_fim, b_fim = estado(t_fim)
    if vencedor == "attacker":
        b_fim = 0.0
    elif vencedor == "defender":
        a_fim = 0.0
    a_fim, b_fim = max(0.0, a_fim), max(0.0, b_fim)

    trajetoria = []
    for i in range(steps):
        t = t_fim * i / (steps - 1)
        a, b = (a_fim, b_fim) if i == steps - 1 else estado(t)
        trajetoria.append([t, max(0.0, a), max(0.0, b)])
    return {"a_final": a_fim, "b_final": b_fim, "t_end": t_fim, "winner": vencedor,
            "trajectory": trajetoria}


def markov_estimate(seq, n: int = 3) -> np.ndarray:
    """Estima a matriz de transição P contando as transições consecutivas da sequência.

    P[i][j] = (nº de vezes que i foi seguido de j) / (nº de vezes que i apareceu, exceto no fim).
    Linhas sem nenhuma transição ficam uniformes. Aceita 0/1/2 ou os nomes dos climas.
    """
    estados = [_clima(s) for s in seq]
    for e in estados:
        if not 0 <= e < n:
            raise ValueError("Estado fora do intervalo na sequência")
    contagem = np.zeros((n, n))
    for a, b in zip(estados[:-1], estados[1:]):
        contagem[a, b] += 1
    P = np.empty((n, n))
    for i in range(n):
        total = contagem[i].sum()
        P[i] = contagem[i] / total if total > 0 else 1.0 / n
    return P


def markov_forecast(P, state, k: int = 1) -> np.ndarray:
    """Distribuição do estado após k passos a partir de `state`: linha `state` de P^k.

    Para o próximo turno (k = 1), é simplesmente a linha do estado atual de P.
    """
    M = np.asarray(P, dtype=float)
    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise ValueError("P deve ser quadrada")
    e = _clima(state)
    if not 0 <= e < M.shape[0]:
        raise ValueError("Estado fora do intervalo")
    if k < 0:
        raise ValueError("k deve ser ≥ 0")
    return np.linalg.matrix_power(M, int(k))[e]


# ----------------------------------------------------------------------------- Inteligência
def hill_recover(plain: str, cipher: str, n: int = 2) -> np.ndarray:
    """Recupera a chave K a partir de um trecho conhecido: K = C·P⁻¹ (mod 37).

    `plain` é o trecho claro (ex.: "URGENTE ") e `cipher` o trecho cifrado correspondente,
    com o mesmo comprimento. Usa blocos de n símbolos; tenta combinações até achar P invertível.
    """
    p_txt = _normalizar(plain)
    c_txt = _simbolos(cipher)
    if len(p_txt) != len(c_txt):
        raise ValueError("O trecho claro e o cifrado devem ter o mesmo comprimento")
    cheio = (len(p_txt) // n) * n
    if cheio < n:
        raise ValueError(f"O trecho deve ter pelo menos {n} símbolos")

    def blocos(txt: str) -> np.ndarray:
        nums = [ALFABETO.index(ch) for ch in txt]
        return np.array(nums, dtype=np.int64).reshape(-1, n).T

    P_todos = blocos(p_txt[:cheio])
    C_todos = blocos(c_txt[:cheio])
    for combo in _combinacoes(P_todos.shape[1], n):
        P = P_todos[:, combo]
        C = C_todos[:, combo]
        try:
            P_inv = inversa_mod(P, MODULO)
        except ValueError:
            continue
        K = (C @ P_inv) % MODULO
        if np.array_equal((K @ P_todos) % MODULO, C_todos):
            return K.astype(np.int64)
    raise ValueError("Não foi possível recuperar a chave: nenhum bloco do trecho é invertível "
                     "mod 37, ou o cifrado não corresponde ao trecho")


def _combinacoes(total: int, n: int):
    return [list(c) for c in itertools.combinations(range(total), n)]


def hill_encrypt(plain: str, K) -> str:
    """Cifra: c = K·p (mod 37), bloco a bloco. Completa com espaços até múltiplo de n."""
    Km = np.array(K, dtype=np.int64) % MODULO
    n = Km.shape[0]
    txt = _normalizar(plain)
    if not txt:
        raise ValueError("Mensagem vazia")
    txt = txt + " " * ((-len(txt)) % n)
    P = np.array([ALFABETO.index(ch) for ch in txt], dtype=np.int64).reshape(-1, n).T
    C = (Km @ P) % MODULO
    return "".join(ALFABETO[int(v)] for v in C.T.reshape(-1))


def hill_decrypt(cipher: str, K) -> str:
    """Decifra: p = K⁻¹·c (mod 37), bloco a bloco. A chave precisa ser invertível mod 37."""
    Km = np.array(K, dtype=np.int64) % MODULO
    n = Km.shape[0]
    Kinv = inversa_mod(Km, MODULO)
    txt = _simbolos(cipher)
    if not txt:
        raise ValueError("Criptograma vazio")
    if len(txt) % n:
        raise ValueError(f"O criptograma deve ter comprimento múltiplo de {n}")
    C = np.array([ALFABETO.index(ch) for ch in txt], dtype=np.int64).reshape(-1, n).T
    P = (Kinv @ C) % MODULO
    return "".join(ALFABETO[int(v)] for v in P.T.reshape(-1))


def trilaterate(stations, distances) -> tuple[float, float]:
    """Posição (x, y) a partir de pelo menos 3 estações e das distâncias medidas (mínimos quadrados).

    Subtrai a 1ª equação (xi−x1)² + (yi−y1)² = ri² das demais, o que dá um sistema linear:
        2(xi−x1)·x + 2(yi−y1)·y = r1² − ri² + xi² − x1² + yi² − y1²
    Esse sistema é resolvido por mínimos quadrados, porque as distâncias têm ruído.
    """
    S = np.asarray(stations, dtype=float)
    r = np.asarray(distances, dtype=float).reshape(-1)
    if S.ndim != 2 or S.shape[1] != 2:
        raise ValueError("Cada estação deve ser um par [x, y]")
    if S.shape[0] < 3:
        raise ValueError("São necessárias pelo menos 3 estações")
    if r.size != S.shape[0]:
        raise ValueError("Há que informar uma distância para cada estação")
    x1, y1 = S[0]
    r1 = r[0]
    A = 2.0 * (S[1:] - S[0])
    b = (r1 ** 2 - r[1:] ** 2 + (S[1:, 0] ** 2 - x1 ** 2) + (S[1:, 1] ** 2 - y1 ** 2))
    if np.linalg.matrix_rank(A) < 2:
        raise ValueError("Estações colineares: a triangulação não tem solução única")
    sol = np.linalg.lstsq(A, b, rcond=None)[0]
    return float(sol[0]), float(sol[1])


def grid_label(x: float, y: float) -> str:
    """Quadrícula do mapa para um ponto: (525, 310) -> 'K7'. Coluna = letra (x // 50); linha = y // 50 + 1."""
    c = min(max(int(math.floor(float(x) / CELULA)), 0), len(COLUNAS) - 1)
    r = min(max(int(math.floor(float(y) / CELULA)) + 1, 1), 16)
    return f"{COLUNAS[c]}{r}"


# ----------------------------------------------------------------------------- Governo
def ols(rows, features, target: str = "delta_moral") -> np.ndarray:
    """Regressão linear múltipla por equações normais: (XᵀX)·β = Xᵀy, com intercepto.

    rows: lista de dicionários (um por observação). features: nomes das variáveis explicativas.
    Retorna [β0, β1, ..., βk], na ordem do intercepto e depois das variáveis.
    Use FEATURES_PESQUISA para a pesquisa de opinião, e não inclua a coluna 'obs'.
    """
    features = list(features)
    if not rows:
        raise ValueError("Não há observações")
    X = np.array([[1.0] + [float(r[f]) for f in features] for r in rows], dtype=float)
    y = np.array([float(r[target]) for r in rows], dtype=float)
    if X.shape[0] <= X.shape[1]:
        raise ValueError("São necessárias mais observações do que variáveis")
    try:
        return np.linalg.solve(X.T @ X, X.T @ y)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Equações normais singulares: variáveis colineares ou constantes") from exc


# ----------------------------------------------------------------------------- arquivos
def read_csv(path) -> list[dict]:
    """Lê um CSV baixado do jogo e devolve uma lista de dicionários, com números convertidos.

    Aceita BOM UTF-8 (o arquivo do jogo tem), separador vírgula (ou ponto e vírgula) e
    ponto como separador decimal.
    """
    texto = Path(path).read_text(encoding="utf-8-sig")
    linhas = [ln for ln in texto.splitlines() if ln.strip()]
    if len(linhas) < 2:
        raise ValueError("O CSV precisa de cabeçalho e ao menos uma linha de dados")
    separador = ";" if ";" in linhas[0] else ","
    leitor = csv.DictReader(linhas, delimiter=separador)
    return [{(k or "").strip(): _numero(v) for k, v in linha.items()} for linha in leitor]


# ----------------------------------------------------------------------------- demonstração
def _demonstracao() -> None:
    print("== Leontief (Intendência) ==")
    A_ex = [[0.1, 0.2, 0.0], [0.2, 0.1, 0.1], [0.1, 0.0, 0.2]]
    X_ex = [30, 20, 10]
    Z_ex = [[3, 4, 0], [6, 2, 1], [3, 0, 2]]
    print("A = Z/X =\n", np.round(leontief_A(Z_ex, X_ex), 4))
    print("x para d = (23, 11, 5):", np.round(leontief_x(A_ex, [23, 11, 5]), 4))

    print("\n== Lanchester (Operações) ==")
    alpha = 1.2                   # moral 70 -> 0,5 + 0,7
    beta = 1.2 * 1.5              # defensor com moral 70 em montanha (×1,5)
    r = lanchester(12, 6, alpha, beta, T=0.9)
    print("12 contra 6 em montanha:", r["winner"], "| sobram:", round(r["a_final"], 2),
          "| t =", round(r["t_end"], 3))

    print("\n== Markov (Operações) ==")
    seq = "limpo chuva chuva tempestade chuva limpo limpo chuva tempestade tempestade chuva limpo " \
          "chuva chuva limpo tempestade chuva limpo limpo chuva"
    P = markov_estimate(seq.split(), 3)
    print("P estimada =\n", np.round(P, 4))
    print("prob. de tempestade após chuva:", round(float(markov_forecast(P, "chuva", 1)[2]), 4))

    print("\n== Hill (Inteligência) ==")
    K_ex = [[3, 5], [2, 7]]
    cifrado = hill_encrypt("URGENTE ATACA K7", K_ex)
    print("cifrado:", cifrado)
    K_rec = hill_recover("URGENTE ", cifrado[:8])
    print("chave recuperada:", K_rec.tolist())
    print("decifrado:", hill_decrypt(cifrado, K_rec))
    print("inverso de 15 mod 37:", pow(15, -1, 37))

    print("\n== Triangulação (Inteligência) ==")
    estacoes = [[100, 100], [700, 150], [300, 650]]
    dist = [394.1, 332.9, 341.8]
    x, y = trilaterate(estacoes, dist)
    print("posição:", round(x, 1), round(y, 1), "->", grid_label(x, y))

    print("\n== Regressão (Governo) ==")
    linhas = [
        {"racao": 0, "propaganda": 0, "delta_moral": 2.0},
        {"racao": 0, "propaganda": 2, "delta_moral": 4.9},
        {"racao": 1, "propaganda": 1, "delta_moral": 1.9},
        {"racao": 1, "propaganda": 3, "delta_moral": 4.2},
        {"racao": 2, "propaganda": 0, "delta_moral": -2.1},
        {"racao": 2, "propaganda": 4, "delta_moral": 2.9},
    ]
    beta_ols = ols(linhas, ["racao", "propaganda"], "delta_moral")
    print("β (intercepto, racao, propaganda):", np.round(beta_ols, 4))

    print("\n== Leitura de CSV ==")
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "pesquisa.csv"
        caminho.write_text("﻿obs,racao,propaganda,delta_moral\n1,0,2,4.9\n2,1,3,4.2\n", encoding="utf-8")
        print(read_csv(caminho))


if __name__ == "__main__":
    _demonstracao()
