"""Manchetes do jornal "O Arauto do Front" (tom de 1943, vários modelos por tipo).

Cada função devolve um dict `{turn, headline, body, kind}`; a escolha do modelo usa o gerador
do jogo, de modo que a mesma semente produz o mesmo jornal.
"""

from __future__ import annotations

from app.game.model import num

PAPER = "O Arauto do Front"

REGION_NAMES = {"norte": "o Norte", "centro": "o Centro", "sul": "o Sul"}
REGION_IN = {"norte": "no Norte", "centro": "no Centro", "sul": "no Sul"}


def _pick(rng, options: list):
    return options[int(rng.integers(0, len(options)))]


def _item(turn: int, headline: str, body: str, kind: str) -> dict:
    return {"turn": int(turn), "headline": headline, "body": body, "kind": kind}


def opening(rng, turn: int, n_nations: int) -> dict:
    return _item(
        turn,
        _pick(rng, [
            "Eclode a guerra no Continente de Lebesgue",
            "Estado-Maior ordena mobilização geral",
            "Soam os clarins: começa a campanha de Lebesgue",
        ]),
        f"{n_nations} nações entram em campanha pelo controle do continente. "
        "Os estados-maiores recebem os primeiros dossiês; o prazo corre contra todos.",
        "politics",
    )


def capture(rng, turn, att, defender, terr, is_capital, att_before, def_before, att_after, losses) -> dict:
    """`defender` é o nome curto do dono anterior, ou None (território neutro)."""
    if is_capital and defender:
        head = _pick(rng, [
            f"Capital de {defender} cai: {att} hasteia bandeira em {terr}",
            f"{terr}, capital de {defender}, rende-se a {att}",
            f"Golpe mortal: {att} ocupa {terr}, coração de {defender}",
        ])
        body = (f"Em ataque de {att_before} batalhões contra {def_before}, as forças de {att} "
                f"tomaram a capital {terr}. Sobraram {att_after} atacantes. O governo de {defender} "
                f"tenta conter o pânico; a moral das tropas despenca.")
        return _item(turn, head, body, "capture")
    if defender:
        head = _pick(rng, [
            f"{att} toma {terr} de assalto",
            f"{terr} cai em mãos de {att}",
            f"Bandeira de {att} sobre {terr}",
            f"{att} arrebata {terr} a {defender}",
            f"Frente de {defender} cede em {terr}",
        ])
        body = _pick(rng, [
            f"Depois de combate encarniçado ({att_before} contra {def_before} batalhões), {att} "
            f"dominou {terr}, até ontem sob a bandeira de {defender}. As baixas somam {losses} batalhões.",
            f"As tropas de {att} romperam as linhas de {defender} em {terr} e mantêm o terreno "
            f"com {att_after} batalhões. Fontes do front falam em {losses} baixas nos dois lados.",
        ])
        return _item(turn, head, body, "capture")
    head = _pick(rng, [
        f"{att} ocupa {terr}, até então neutro",
        f"Milícias de {terr} depõem armas diante de {att}",
        f"{terr} passa ao controle de {att}",
    ])
    body = (f"As milícias locais, com {def_before} homens, não resistiram ao avanço de {att}, "
            f"que guarnece {terr} com {att_after} batalhões.")
    return _item(turn, head, body, "capture")


def repelled(rng, turn, att, defender, terr, att_before, def_before, def_after) -> dict:
    who = defender or "as milícias locais"
    head = _pick(rng, [
        f"{who[0].upper() + who[1:]} rechaça ataque a {terr}",
        f"Ofensiva de {att} quebra-se diante de {terr}",
        f"{terr} resiste: {att} recua em desordem",
        f"Defesa firme em {terr} detém {att}",
    ])
    body = _pick(rng, [
        f"{att} lançou {att_before} batalhões contra {terr}, defendida por {def_before}. O ataque foi "
        f"repelido; restam {def_after} defensores em posição.",
        f"Após duras horas de fogo, o assalto de {att} sobre {terr} fracassou. "
        f"Os defensores mantêm o terreno com {def_after} batalhões.",
    ])
    return _item(turn, head, body, "battle")


def stalemate(rng, turn, att, defender, terr, att_after, def_after) -> dict:
    who = defender or "as milícias locais"
    head = _pick(rng, [
        f"Combate indeciso em {terr}",
        f"Nem {att} nem {who} cedem em {terr}",
        f"Empate sangrento diante de {terr}",
    ])
    body = (f"{att} e {who} trocaram fogo sem decisão. {att} retira {att_after} batalhões; "
            f"restam {def_after} na posição defendida.")
    return _item(turn, head, body, "battle")


def bloodbath(rng, turn, a, d, terr, loss_a, loss_d) -> dict:
    head = _pick(rng, [
        f"Carnificina em {terr}: dois exércitos sangram",
        f"Batalha de {terr} custa caro a {a} e a {d}",
    ])
    body = (f"As baixas da batalha de {terr} são pesadas: {loss_a} batalhões perdidos por {a} "
            f"e {loss_d} por {d}. Os estados-maiores contam os mortos.")
    return _item(turn, head, body, "battle")


def calm(rng, turn) -> dict:
    return _item(
        turn,
        _pick(rng, ["Calmaria no front", "Dia sem combates em Lebesgue", "Silêncio nas trincheiras"]),
        "Nenhum choque armado foi registrado no turno. Os estados-maiores aproveitam para reorganizar "
        "tropas e estoques.",
        "politics",
    )


def weather(rng, turn, severe: list[str], rainy: list[str]) -> dict | None:
    if severe:
        r = severe[0]
        others = len(severe) > 1
        head = _pick(rng, [
            f"Tempestade castiga {REGION_NAMES[r]} do continente",
            f"Mar fechado: temporal {REGION_IN[r]}",
            f"Temporal forte {REGION_IN[r]} paralisa comboios",
        ])
        body = ("Tormentas assolam " + " e ".join(REGION_NAMES[x] for x in severe) +
                ". Travessias marítimas suspensas e ataques prejudicados pela chuva e pelo vento"
                + ("." if not others else "; a situação é geral."))
        return _item(turn, head, body, "weather")
    if len(rainy) == 3:
        return _item(turn, "Chuva sobre todo o continente",
                     "Chuvas persistentes em todas as regiões atrasam as colunas de marcha.", "weather")
    return None


def starvation(rng, turn, nation) -> dict:
    head = _pick(rng, [
        f"Fome no front: {nation} sem alimento",
        f"Racionamento extremo em {nation}; tropas desertam",
        f"Intendência de {nation} falha: soldados com fome",
    ])
    body = (f"Falta de víveres em {nation}. O moral cai e cerca de um décimo da tropa abandona as fileiras. "
            "Exige-se do Governo medidas imediatas.")
    return _item(turn, head, body, "politics")


def rationing(rng, turn, nation, level) -> dict:
    if level >= 2:
        head = _pick(rng, [f"{nation} decreta racionamento severo",
                           f"Cartões de racionamento rigoroso em {nation}"])
        body = f"O governo de {nation} impôs ração severa à população civil para poupar alimento para a tropa."
    else:
        head = _pick(rng, [f"{nation} reduz ração da população",
                           f"Racionamento em {nation}: cintos mais apertados"])
        body = f"Racionamento moderado foi decretado em {nation}; o governo pede paciência e sacrifício."
    return _item(turn, head, body, "politics")


def pact_formed(rng, turn, a, b, until_turn) -> dict:
    head = _pick(rng, [
        f"Pacto de não agressão entre {a} e {b}",
        f"{a} e {b} apertam as mãos: trégua assinada",
        f"Diplomatas de {a} e {b} selam acordo de paz",
    ])
    body = (f"Os governos de {a} e {b} firmaram pacto de não agressão, válido até o turno {until_turn}. "
            "Observadores notam que pactos são feitos para durar... até deixarem de interessar.")
    return _item(turn, head, body, "politics")


def pact_denounced(rng, turn, a, b) -> dict:
    head = _pick(rng, [
        f"{a} denuncia pacto com {b}",
        f"Traição à vista? {a} rasga acordo com {b}",
        f"Crise diplomática: {a} rompe com {b}",
    ])
    body = (f"O governo de {a} comunicou o fim do pacto de não agressão com {b}. "
            "O gesto custou ao governo denunciante o respeito da opinião pública.")
    return _item(turn, head, body, "politics")


def bombard(rng, turn, att, victim, terr) -> dict:
    head = _pick(rng, [
        f"Depósitos de {victim} atingidos em {terr}",
        f"Bombardeio fulmina suprimentos de {victim}",
    ])
    body = (f"Aviões de {att} atingiram o depósito de suprimentos de {victim} em {terr}. "
            "Estoques destruídos e a produção sofrerá nos próximos dias.")
    return _item(turn, head, body, "battle")


def capitulation(rng, turn, nation, capital) -> dict:
    head = _pick(rng, [
        f"{nation} capitula",
        f"Bandeira branca em {capital}: {nation} se rende",
        f"Fim de {nation}: governo assina a rendição",
    ])
    body = f"Sem meios de prosseguir a luta, {nation} depôs as armas. Seus territórios passam a ser disputados."
    return _item(turn, head, body, "capture")


def leader(rng, turn, name, vp, second_name, second_vp) -> dict:
    head = _pick(rng, [
        f"{name} lidera o placar de guerra",
        f"Na frente do placar: {name}",
        f"{name} desponta como favorita ao final da guerra",
    ])
    body = (f"Com {num(vp, 2)} pontos de vitória, {name} ultrapassa {second_name} ({num(second_vp, 2)}). "
            "A corrida pelo continente está longe de decidida.")
    return _item(turn, head, body, "politics")


def event(turn, headline, body) -> dict:
    return _item(turn, headline, body, "event")


def final(rng, turn, winner_name, vp, standings: list[tuple[str, float]], reason: str) -> dict:
    if reason == "domination":
        head = f"{winner_name} domina o continente: fim da guerra"
        lead = f"Com mais de 60% dos territórios, {winner_name} encerrou a guerra por dominação."
    elif reason == "last_standing":
        head = f"{winner_name} é a última nação de pé"
        lead = f"Todas as rivais capitularam; {winner_name} é senhora do continente."
    else:
        head = _pick(rng, [f"Cessar-fogo geral: {winner_name} vence a guerra de Lebesgue",
                           f"Fim da guerra: {winner_name} no topo do placar"])
        lead = f"Terminado o último turno, {winner_name} conquista a vitória com {num(vp, 2)} pontos."
    table = "; ".join(f"{i + 1}º {n} ({num(v, 2)})" for i, (n, v) in enumerate(standings))
    return _item(turn, head, f"{lead} Classificação final: {table}.", "event")
