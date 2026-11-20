"""Ritmo comum à animação e ao áudio: assim os dois ficam sincronizados por construção.

Uma cena dura: INICIO + soma(duração da fala + PAUSA) + FIM.
"""
INICIO = 0.6    # respiro antes da primeira fala da cena
PAUSA = 0.55    # silêncio depois de cada fala
FIM = 0.9       # respiro depois da última fala (a cena some nesse intervalo)


def inicios(duracoes):
    """Instante (s, dentro da cena) em que cada fala começa."""
    t, out = INICIO, []
    for d in duracoes:
        out.append(round(t, 3))
        t += d + PAUSA
    return out


def duracao_cena(duracoes):
    return INICIO + sum(d + PAUSA for d in duracoes) + FIM
