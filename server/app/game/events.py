"""Eventos globais (DESIGN §8): 8 eventos com efeito concreto, de duração limitada.

Um efeito é um dict `{"event", "target": "all"|fid, "key", "value", "until_turn"}` guardado em
`game.effects`; vale para as resoluções dos turnos `<= until_turn` e depois é removido
(reversível no tempo). Efeitos imediatos (estoque, moral) são aplicados na hora.
"""

from __future__ import annotations

from app.game import balance as B
from app.game import news as N
from app.game.model import num


def _pick(rng, options: list):
    return options[int(rng.integers(0, len(options)))]

# chave do efeito → "mult" (multiplicativo) ou "add" (aditivo)
EFFECT_KINDS = {
    "prod_ALI": "mult", "prod_ACO": "mult", "prod_COM": "mult",
    "workforce": "mult", "move_cost": "mult", "attack": "mult",
    "civil_ali": "add",
}

CATALOG = [
    {"id": "greve_siderurgia", "name": "Greve na siderurgia",
     "description": "Parada nas usinas: a produção de Aço de todas as nações cai 30% neste turno."},
    {"id": "colheita_recorde", "name": "Colheita recorde",
     "description": "Safra excepcional: a produção de Alimento de todas as nações sobe 30% neste turno."},
    {"id": "epidemia_gripe", "name": "Epidemia de gripe",
     "description": "Surto de gripe: a mão de obra de todas as nações cai 15% por 2 turnos."},
    {"id": "descoberta_petroleo", "name": "Descoberta de petróleo",
     "description": "Uma nação sorteada descobre jazidas e recebe 18 de Combustível de imediato."},
    {"id": "inverno_precoce", "name": "Inverno precoce",
     "description": "Frio antecipado por 2 turnos: +2 de consumo civil de Alimento, movimentos custam 50% mais "
                    "Combustível e os ataques perdem 10% de eficácia."},
    {"id": "sabotagem_ferroviaria", "name": "Sabotagem ferroviária",
     "description": "Uma nação sorteada perde 25% do Combustível e seus movimentos custam o dobro neste turno."},
    {"id": "ajuda_estrangeira", "name": "Ajuda estrangeira",
     "description": "A nação mais fraca (menos pontos) recebe 12 Alimento, 8 Aço e 8 Combustível."},
    {"id": "motim", "name": "Motim nas tropas",
     "description": "A nação de moral mais baixa sofre um motim: moral −12."},
]
BY_ID = {e["id"]: e for e in CATALOG}


def list_events() -> list[dict]:
    return [{"id": e["id"], "name": e["name"], "description": e["description"]} for e in CATALOG]


# ------------------------------------------------------------------------------------------------
def _add_effect(game, event_id: str, target: str, key: str, value: float, duration: int) -> None:
    game.effects.append({
        "event": event_id, "target": target, "key": key, "value": float(value),
        "until_turn": int(game.turn + duration - 1),
    })


def _line(game, fid: str, text: str) -> None:
    game.event_lines.setdefault(fid, []).append(text)


def _pick_faction(game, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    return candidates[int(game.rng.integers(0, len(candidates)))]


def apply_event(game, event_id: str) -> dict:
    """Aplica o evento ao estado do jogo (turno atual) e devolve o item de notícia."""
    if event_id not in BY_ID:
        raise ValueError(f"Evento desconhecido: {event_id!r}. Use um dos ids de /api/admin/events.")
    alive = [f for f in game.order if not game.factions[f].capitulated]
    if not alive:
        raise ValueError("Não há nações em campo para sofrer o evento.")
    turn = game.turn
    rng = game.rng

    if event_id == "greve_siderurgia":
        _add_effect(game, event_id, "all", "prod_ACO", 0.7, 1)
        for f in alive:
            _line(game, f, "Evento: greve na siderurgia (produção de Aço −30% neste turno).")
        item = N.event(turn, _pick(rng, ["Greve paralisa as siderúrgicas do continente",
                                         "Operários cruzam os braços nas usinas de aço"]),
                       "Greve geral nas siderúrgicas reduz em 30% a produção de Aço de todas as nações neste turno.")
    elif event_id == "colheita_recorde":
        _add_effect(game, event_id, "all", "prod_ALI", 1.3, 1)
        for f in alive:
            _line(game, f, "Evento: colheita recorde (produção de Alimento +30% neste turno).")
        item = N.event(turn, _pick(rng, ["Colheita recorde enche os celeiros", "Safra excepcional anima o continente"]),
                       "Clima favorável rende safra excepcional: produção de Alimento 30% maior em todas as nações neste turno.")
    elif event_id == "epidemia_gripe":
        _add_effect(game, event_id, "all", "workforce", 0.85, 2)
        for f in alive:
            _line(game, f, "Evento: epidemia de gripe (mão de obra −15% por 2 turnos).")
        item = N.event(turn, _pick(rng, ["Gripe espalha-se pelas fábricas", "Epidemia de gripe esvazia as oficinas"]),
                       "Surto de gripe reduz em 15% a mão de obra disponível em todas as nações durante 2 turnos.")
    elif event_id == "descoberta_petroleo":
        fid = _pick_faction(game, alive)
        game.factions[fid].stock["COM"] += 18.0
        _line(game, fid, "Evento: descoberta de petróleo (+18 de Combustível).")
        nm = game.factions[fid].short
        item = N.event(turn, _pick(rng, [f"Petróleo jorra em solo de {nm}", f"{nm} descobre jazida de petróleo"]),
                       f"Prospectores de {nm} anunciaram nova jazida: 18 unidades de Combustível entram no estoque.")
    elif event_id == "inverno_precoce":
        _add_effect(game, event_id, "all", "civil_ali", 2.0, 2)
        _add_effect(game, event_id, "all", "move_cost", 1.5, 2)
        _add_effect(game, event_id, "all", "attack", 0.9, 2)
        for f in alive:
            _line(game, f, "Evento: inverno precoce (consumo civil +2 ALI, movimentos 50% mais caros, ataques −10%).")
        item = N.event(turn, _pick(rng, ["Inverno precoce gela o continente", "Geada antecipada ameaça as operações"]),
                       "O frio chegou antes do tempo: mais alimento para aquecer a população, estradas difíceis e "
                       "ataques menos eficazes por 2 turnos.")
    elif event_id == "sabotagem_ferroviaria":
        fid = _pick_faction(game, alive)
        f = game.factions[fid]
        lost = round(f.stock["COM"] * 0.25, 2)
        f.stock["COM"] = round(f.stock["COM"] - lost, 2)
        _add_effect(game, event_id, fid, "move_cost", 2.0, 1)
        _line(game, fid, f"Evento: sabotagem ferroviária (−{num(lost)} COM; movimentos custam o dobro neste turno).")
        item = N.event(turn, _pick(rng, [f"Sabotadores explodem ferrovias de {f.short}",
                                         f"Sabotagem paralisa os trens de {f.short}"]),
                       f"Agentes inimigos destruíram trilhos em {f.short}: perda de combustível e transporte mais caro neste turno.")
    elif event_id == "ajuda_estrangeira":
        vps = {f: game.vp(f) for f in alive}
        low = min(vps.values())
        fid = _pick_faction(game, [f for f in alive if vps[f] == low])
        st = game.factions[fid].stock
        st["ALI"] += 12.0
        st["ACO"] += 8.0
        st["COM"] += 8.0
        _line(game, fid, "Evento: ajuda estrangeira (+12 ALI, +8 ACO, +8 COM).")
        nm = game.factions[fid].short
        item = N.event(turn, _pick(rng, [f"Ajuda estrangeira chega a {nm}", f"Navios de socorro aportam em {nm}"]),
                       f"Um comboio de nações amigas entregou suprimentos a {nm}: 12 de Alimento, 8 de Aço e 8 de Combustível.")
    else:  # motim
        lows = {f: game.factions[f].morale for f in alive}
        low = min(lows.values())
        fid = _pick_faction(game, [f for f in alive if lows[f] == low])
        game.factions[fid].morale = max(0.0, game.factions[fid].morale - 12.0)
        _line(game, fid, "Evento: motim nas tropas (moral −12).")
        nm = game.factions[fid].short
        item = N.event(turn, _pick(rng, [f"Motim abala as tropas de {nm}", f"Soldados de {nm} se amotinam"]),
                       f"Descontentes com a situação, parte das tropas de {nm} se amotinou. A moral sofre um golpe severo.")
    game.event_log.append({"turn": turn, "id": event_id, "name": BY_ID[event_id]["name"]})
    return item


def roll_event(game) -> dict | None:
    """Sorteia (prob. EVENT_PROB, a partir do turno 2) e aplica um evento; devolve a notícia ou None."""
    if game.turn < B.EVENT_FIRST_TURN:
        return None
    if float(game.rng.random()) >= B.EVENT_PROB:
        return None
    ids = [e["id"] for e in CATALOG]
    last = game.event_log[-1]["id"] if game.event_log else None
    ids = [i for i in ids if i != last] or ids
    event_id = ids[int(game.rng.integers(0, len(ids)))]
    return apply_event(game, event_id)


def expire(game, resolved_turn: int) -> None:
    game.effects = [e for e in game.effects if e["until_turn"] > resolved_turn]
