"""Cifra de Hill sobre ℤ₃₇ (alfabeto A–Z, 0–9, espaço)."""

from __future__ import annotations

import itertools
import unicodedata

import numpy as np

from app.engine import linalg

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "  # 37 símbolos, espaço = 36
M = 37
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


def normalize(text: str) -> str:
    """Maiúsculas, sem acentos (Ç→C), símbolos fora do alfabeto → espaço, espaços colapsados.

    Não remove espaços das bordas: "URGENTE " continua com o espaço final (ele faz parte do crib).
    """
    decomposed = unicodedata.normalize("NFKD", str(text).upper())
    base = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    out = []
    for ch in base:
        out.append(ch if ch in _INDEX else " ")
    collapsed = []
    for ch in out:
        if ch == " " and collapsed and collapsed[-1] == " ":
            continue
        collapsed.append(ch)
    return "".join(collapsed)


def symbols(text: str) -> str:
    """Como `normalize`, mas SEM colapsar espaços: usado para criptogramas, em que o espaço é símbolo."""
    decomposed = unicodedata.normalize("NFKD", str(text).upper())
    base = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(ch if ch in _INDEX else " " for ch in base)


def to_nums(text: str) -> list[int]:
    return [_INDEX[ch] for ch in normalize(text)]


def to_text(nums) -> str:
    return "".join(ALPHABET[int(v) % M] for v in nums)


def _key_matrix(K) -> np.ndarray:
    """Converte a chave em matriz quadrada de inteiros reduzidos mod 37."""
    try:
        arr = np.array(K, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("A chave deve ser uma matriz numérica") from exc
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1] or arr.size == 0:
        raise ValueError("A chave deve ser uma matriz quadrada")
    if not np.allclose(arr, np.rint(arr)):
        raise ValueError("A chave deve conter apenas inteiros")
    return np.rint(arr).astype(np.int64) % M


def random_key(rng: np.random.Generator, n: int = 2) -> np.ndarray:
    """Matriz n×n de inteiros com determinante invertível mod 37."""
    if n < 1:
        raise ValueError("O tamanho do bloco deve ser ≥ 1")
    while True:
        K = rng.integers(0, M, size=(n, n), dtype=np.int64)
        try:
            linalg.mod_inv_matrix(K, M)
        except ValueError:
            continue
        return K


def _blocks(nums: list[int], n: int) -> np.ndarray:
    """Vetores-coluna consecutivos: matriz n × (nº de blocos)."""
    return np.array(nums, dtype=np.int64).reshape(-1, n).T


def encrypt(plain: str, K) -> str:
    """c = K·p (mod 37) para cada bloco consecutivo p de n símbolos."""
    Km = _key_matrix(K)
    n = Km.shape[0]
    text = normalize(plain)
    if not text:
        raise ValueError("Mensagem vazia")
    text = text + " " * ((-len(text)) % n)  # completa com espaço (sem renormalizar: não colapsar)
    P = _blocks([_INDEX[ch] for ch in text], n)
    C = (Km @ P) % M
    return to_text(C.T.reshape(-1))


def decrypt(cipher: str, K) -> str:
    """p = K⁻¹·c (mod 37) para cada bloco. Exige K invertível mod 37."""
    Km = _key_matrix(K)
    n = Km.shape[0]
    Kinv = linalg.mod_inv_matrix(Km, M)
    text = symbols(cipher)
    if not text:
        raise ValueError("Criptograma vazio")
    if len(text) % n != 0:
        raise ValueError(f"O criptograma deve ter comprimento múltiplo de {n}")
    C = _blocks([_INDEX[ch] for ch in text], n)
    P = (Kinv @ C) % M
    return to_text(P.T.reshape(-1))


def recover_key(plain_crib: str, cipher_crib: str, n: int = 2) -> np.ndarray:
    """Recupera K a partir de um crib conhecido: K = C·P⁻¹ (mod 37).

    Monta P e C com blocos (colunas) do crib; se P não for invertível, tenta outras combinações
    de blocos. A chave candidata é confirmada contra todos os blocos completos do crib.
    """
    if n < 1:
        raise ValueError("O tamanho do bloco deve ser ≥ 1")
    p_text = normalize(plain_crib)      # texto claro: mesma normalização do encrypt
    c_text = symbols(cipher_crib)       # criptograma: símbolos crus (espaço é símbolo)
    if len(p_text) != len(c_text):
        raise ValueError("Crib claro e cifrado devem ter o mesmo comprimento")
    full = (len(p_text) // n) * n
    if full < n:
        raise ValueError(f"O crib deve ter pelo menos {n} símbolos")
    p_all = _blocks([_INDEX[ch] for ch in p_text[:full]], n)
    c_all = _blocks([_INDEX[ch] for ch in c_text[:full]], n)
    n_blocks = p_all.shape[1]

    for combo in itertools.combinations(range(n_blocks), n):
        idx = list(combo)
        P = p_all[:, idx]
        C = c_all[:, idx]
        try:
            Pinv = linalg.mod_inv_matrix(P, M)
        except ValueError:
            continue
        K = (C @ Pinv) % M
        # confere K contra todos os blocos do crib
        if np.array_equal((K @ p_all) % M, c_all):
            return K.astype(np.int64)
    raise ValueError(
        "Não foi possível recuperar a chave: nenhuma combinação de blocos do crib é invertível "
        "mod 37, ou o criptograma não corresponde ao crib"
    )
