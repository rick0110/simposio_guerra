"""A classe `Game`: interface do CONTRATO §4 (ciclo de vida, visões e ações), sem FastAPI."""

from __future__ import annotations

import hmac
import math
from typing import Any

import numpy as np

from app.engine import cipher, combat
from app.game import balance as B
from app.game import dossiers, events as EV, news as N, resolution, setup
from app.game.model import Faction, clean, deep, ev, num, troops_range

PHASE_NAMES = {"lobby": "espera", "running": "planejamento", "paused": "pausa", "finished": "encerrado"}
SNAPSHOT_VERSION = 1


class Game:
    # ------------------------------------------------------------------ construção
    def __init__(self, map_data: dict):
        self.map = map_data
        self.TER = {t["id"]: t for t in map_data["territories"]}
        self.order_tids = [t["id"] for t in map_data["territories"]]
        adj = {t: set(self.TER[t].get("neighbors", [])) for t in self.order_tids}
        sea = {t: set(self.TER[t].get("sea_neighbors", [])) for t in self.order_tids}
        for t in self.order_tids:           # simetria defensiva
            for u in list(adj[t]):
                if u in adj:
                    adj[u].add(t)
            for u in list(sea[t]):
                if u in sea:
                    sea[u].add(t)
        self._land = adj
        self._sea = sea
        self.slot_home = {h["slot"]: h for h in map_data["home_slots"]}
        # estado dinâmico (tudo abaixo é serializado)
        self.seed = 0
        self.rng = np.random.Generator(np.random.PCG64(0))
        self.n_factions = 0
        self.turn_ms = B.TURN_MINUTES * 60000
        self.max_turns = B.MAX_TURNS
        self.status = "lobby"
        self.turn = 0
        self.deadline_ms = 0
        self.paused_remaining_ms = 0
        self.turn_started_ms = 0
        self.flash_sent = False
        self.last_ms = 0
        self._stale = False
        self.order: list[str] = []
        self.slot_fid: dict[str, str] = {}
        self.factions: dict[str, Faction] = {}
        self.owner: dict[str, Any] = {}
        self.troops: dict[str, int] = {}
        self.climate: dict[str, dict] = {}
        self.weather: dict[str, int] = {}
        self.depots: dict[str, dict] = {}
        self.dossiers: dict[str, dict] = {}
        self.keys: dict[str, dict] = {}
        self.cstate: dict[str, dict] = {}
        self.plain: dict[str, dict] = {}
        self.news: list[dict] = []
        self.last_resolution: dict | None = None
        self.event_log: list[dict] = []
        self.effects: list[dict] = []
        self.event_lines: dict[str, list] = {}
        self.proposals: list[dict] = []
        self.history: list[dict] = []
        self.winner: str | None = None
        self.end_reason: str | None = None
        self.leader: str | None = None

    @classmethod
    def new(cls, map_data: dict, n_factions: int = 4, turn_minutes: float = B.TURN_MINUTES,
            max_turns: int = B.MAX_TURNS, seed: int | None = None) -> "Game":
        g = cls(map_data)
        setup.init_new(g, n_factions, turn_minutes, max_turns, seed)
        return g

    # ------------------------------------------------------------------ serialização
    def to_dict(self) -> dict:
        d = {
            "version": SNAPSHOT_VERSION,
            "seed": self.seed, "n_factions": self.n_factions, "turn_ms": self.turn_ms,
            "max_turns": self.max_turns, "status": self.status, "turn": self.turn,
            "deadline_ms": self.deadline_ms, "paused_remaining_ms": self.paused_remaining_ms,
            "turn_started_ms": self.turn_started_ms, "flash_sent": self.flash_sent, "last_ms": self.last_ms,
            "order": self.order, "slot_fid": self.slot_fid,
            "factions": {fid: f.to_dict() for fid, f in self.factions.items()},
            "owner": self.owner, "troops": self.troops, "climate": self.climate, "weather": self.weather,
            "depots": self.depots, "dossiers": self.dossiers, "keys": self.keys, "cstate": self.cstate,
            "plain": self.plain, "news": self.news, "last_resolution": self.last_resolution,
            "event_log": self.event_log, "effects": self.effects, "event_lines": self.event_lines,
            "proposals": self.proposals, "history": self.history, "winner": self.winner,
            "end_reason": self.end_reason, "leader": self.leader,
            "rng": self.rng.bit_generator.state,
        }
        return clean(d)

    @classmethod
    def from_dict(cls, d: dict, map_data: dict) -> "Game":
        g = cls(map_data)
        d = deep(d)
        for k in ("seed", "n_factions", "turn_ms", "max_turns", "status", "turn", "deadline_ms",
                  "paused_remaining_ms", "turn_started_ms", "flash_sent", "last_ms", "order", "slot_fid",
                  "owner", "troops", "climate", "weather", "depots", "dossiers", "keys", "cstate", "plain",
                  "news", "last_resolution", "event_log", "effects", "event_lines", "proposals", "history",
                  "winner", "end_reason", "leader"):
            if k in d:
                setattr(g, k, d[k])
        g.factions = {fid: Faction.from_dict(fd) for fid, fd in d["factions"].items()}
        bg = np.random.PCG64()
        bg.state = d["rng"]
        g.rng = np.random.Generator(bg)
        g._stale = True
        return g

    # ------------------------------------------------------------------ consultas auxiliares
    def adjacent(self, tid: str) -> set[str]:
        return self._land[tid] | self._sea[tid]

    def is_sea_move(self, a: str, b: str) -> bool:
        return b not in self._land[a] and b in self._sea[a]

    def idx(self, fid: str) -> int:
        return self.order.index(fid)

    slot_of = idx

    def tname(self, tid: str) -> str:
        t = self.TER[tid]
        if t.get("capital") and t.get("home_slot") is not None:
            fid = self.slot_fid.get(str(t["home_slot"]))
            if fid:
                return B.NATION_BY_ID[fid]["capital"]
        return t["name"]

    def capital_tid(self, fid: str) -> str:
        return self.slot_home[self.factions[fid].slot]["capital"]

    def is_capital_of_someone(self, tid: str) -> str | None:
        for fid in self.order:
            if self.capital_tid(fid) == tid:
                return fid
        return None

    def n_territories(self, fid: str) -> int:
        return sum(1 for t in self.order_tids if self.owner[t] == fid)

    def troops_total(self, fid: str) -> int:
        return int(sum(self.troops[t] for t in self.order_tids if self.owner[t] == fid))

    def capacity(self, fid: str) -> dict:
        cap = {s: 0.0 for s in B.SECTORS}
        for t in self.order_tids:
            if self.owner[t] == fid:
                for s in B.SECTORS:
                    cap[s] += self.TER[t]["capacity"][s] * B.CAPACITY_MULT
        return cap

    def workforce(self, fid: str, horas: int | None = None) -> float:
        f = self.factions[fid]
        h = horas if horas is not None else f.policy["horas"]
        w = (B.LABOR_PER_TERRITORY * self.n_territories(fid) * B.HOURS_MULT[h]
             * (0.6 + 0.4 * f.morale / 100.0))
        return float(w * self.effect_mult(fid, "workforce"))

    def nominal_x(self, fid: str) -> np.ndarray:
        cap = self.capacity(fid)
        n = max(1, self.n_territories(fid))
        base = np.array([22.0, 9.0, 10.0]) * n / 4.0
        return np.array([min(base[i], cap[s]) for i, s in enumerate(B.SECTORS)])

    def effect_mult(self, fid: str, key: str) -> float:
        m = 1.0
        for e in self.effects:
            if e["key"] == key and e["target"] in ("all", fid) and e["until_turn"] >= self.turn:
                m *= e["value"]
        return m

    def effect_add(self, fid: str, key: str) -> float:
        a = 0.0
        for e in self.effects:
            if e["key"] == key and e["target"] in ("all", fid) and e["until_turn"] >= self.turn:
                a += e["value"]
        return a

    def recruit_site(self, fid: str) -> str | None:
        cap = self.capital_tid(fid)
        if self.owner[cap] == fid:
            return cap
        own = [t for t in self.order_tids if self.owner[t] == fid]
        return max(own, key=lambda t: (self.troops[t], t)) if own else None

    def attrition(self, fid: str, k: int) -> int:
        removed = 0
        for _ in range(max(0, int(k))):
            own = [t for t in self.order_tids if self.owner[t] == fid and self.troops[t] > 0]
            if not own:
                break
            t = max(own, key=lambda t: (self.troops[t], t))
            self.troops[t] -= 1
            removed += 1
        return removed

    def vp(self, fid: str) -> float:
        caps = {self.capital_tid(f) for f in self.order}
        n_caps = sum(1 for c in caps if self.owner[c] == fid)
        return (self.n_territories(fid) + B.CAPITAL_VP_EXTRA * n_caps
                + B.CHALLENGE_VP * self.factions[fid].challenges_solved)

    def standings(self) -> list[dict]:
        rows = [{"id": f, "vp": self.vp(f), "territories": self.n_territories(f),
                 "troops": self.troops_total(f)} for f in self.order]
        rows.sort(key=lambda r: (-r["vp"], -r["territories"], -r["troops"], self.order.index(r["id"])))
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows

    def owner_label(self, owner: str | None) -> str:
        return self.factions[owner].short if owner else "Neutro"

    def terrain_mod(self, tid: str) -> float:
        return combat.TERRAIN_DEFENSE[self.TER[tid]["terrain"]]

    def add_news(self, item: dict) -> None:
        self.news.append(item)
        if len(self.news) > B.MAX_NEWS:
            self.news = self.news[-B.MAX_NEWS:]

    def add_telegram(self, fid: str, kind: str, from_: str | None, title: str, body: str,
                     section: str | None, now_ms: int, plain: str | None = None) -> dict:
        f = self.factions[fid]
        used = {t["id"] for t in f.telegrams}
        k = 1
        while f"tg-{self.turn}-{k}" in used:
            k += 1
        tg = {"id": f"tg-{self.turn}-{k}", "turn": self.turn, "at_ms": int(now_ms), "kind": kind,
              "from": from_, "title": title, "body": body, "section": section}
        f.telegrams.append(tg)
        if len(f.telegrams) > B.MAX_TELEGRAMS:
            f.telegrams = f.telegrams[-B.MAX_TELEGRAMS:]
        if plain is not None:
            self.plain.setdefault(fid, {})[tg["id"]] = plain
        return tg

    # ------------------------------------------------------------------ relógio
    def _remaining(self, now_ms: int) -> int:
        if self.status == "running":
            return max(0, int(self.deadline_ms - now_ms))
        if self.status == "paused":
            return int(self.paused_remaining_ms)
        if self.status == "lobby":
            return int(self.turn_ms)
        return 0

    def game_dict(self, now_ms: int) -> dict:
        rem = self._remaining(now_ms)
        deadline = self.deadline_ms if self.status == "running" else int(now_ms + rem)
        return {
            "status": self.status, "turn": self.turn, "max_turns": self.max_turns,
            "phase": PHASE_NAMES[self.status], "deadline_ms": int(deadline), "remaining_ms": rem,
            "turn_ms": int(self.turn_ms), "now_ms": int(now_ms), "n_factions": self.n_factions,
            "winner": self.winner, "end_reason": self.end_reason,
        }

    def phase_data(self, now_ms: int) -> dict:
        return self.game_dict(now_ms)

    def _phase_events(self, now_ms: int) -> list[dict]:
        return [ev("public", "phase", self.game_dict(now_ms)), ev("public", "state", {})]

    # ------------------------------------------------------------------ ciclo de vida
    def start(self, now_ms: int) -> list[dict]:
        if self.status != "lobby":
            raise ValueError("A guerra já começou: use «Nova partida» para recomeçar.")
        self.last_ms = now_ms
        self.status = "running"
        self.turn = 1
        self.turn_started_ms = now_ms
        self.deadline_ms = now_ms + self.turn_ms
        self.flash_sent = False
        item = N.opening(self.rng, 1, self.n_factions)
        self.add_news(item)
        events = [ev("public", "news", item)]
        events.extend(resolution.prepare_turn(self, now_ms))
        events.extend(self._phase_events(now_ms))
        return events

    def pause(self, now_ms: int) -> list[dict]:
        if self.status != "running":
            raise ValueError("Só é possível pausar uma partida em andamento.")
        self.last_ms = now_ms
        self.paused_remaining_ms = max(0, int(self.deadline_ms - now_ms))
        self.status = "paused"
        return self._phase_events(now_ms)

    def resume(self, now_ms: int) -> list[dict]:
        if self.status != "paused":
            raise ValueError("A partida não está pausada.")
        self.last_ms = now_ms
        self.status = "running"
        self.deadline_ms = now_ms + int(self.paused_remaining_ms)
        return self._phase_events(now_ms)

    def extend(self, now_ms: int, minutes: float) -> list[dict]:
        try:
            ms = int(round(float(minutes) * 60000))
        except (TypeError, ValueError):
            raise ValueError("Informe os minutos como número.")
        if ms == 0 or not math.isfinite(float(minutes)):
            raise ValueError("Informe um número de minutos diferente de zero.")
        if self.status == "running":
            self.deadline_ms = max(int(now_ms) + 1000, int(self.deadline_ms) + ms)
        elif self.status == "paused":
            self.paused_remaining_ms = max(1000, int(self.paused_remaining_ms) + ms)
        else:
            raise ValueError("Só é possível estender o prazo de uma partida em andamento ou pausada.")
        self.last_ms = now_ms
        return self._phase_events(now_ms)

    def tick(self, now_ms: int) -> list[dict]:
        prev_ms = self.last_ms
        self.last_ms = now_ms
        if self._stale:
            self._stale = False
            if self.status == "running" and self.deadline_ms <= now_ms:
                # reinício do servidor / rollback: devolve o tempo que restava quando o estado foi salvo
                left = max(30000, min(int(self.turn_ms), int(self.deadline_ms - prev_ms)))
                self.deadline_ms = now_ms + left
                return self._phase_events(now_ms)
        if self.status != "running":
            return []
        events: list[dict] = []
        if not self.flash_sent and self.deadline_ms - now_ms <= self.turn_ms / 2:
            self.flash_sent = True
            events.extend(self._send_flash(now_ms))
        if now_ms >= self.deadline_ms:
            events.extend(self.resolve_turn(now_ms))
        return events

    def resolve_turn(self, now_ms: int) -> list[dict]:
        if self.status not in ("running", "paused"):
            raise ValueError("Não há turno em andamento para resolver.")
        self.last_ms = now_ms
        return resolution.resolve(self, now_ms)

    def _send_flash(self, now_ms: int) -> list[dict]:
        events = []
        for fid in self.order:
            f = self.factions[fid]
            if f.capitulated:
                continue
            tgt = dossiers.flash_target(self, fid)
            if tgt is None:
                continue
            plain = dossiers.flash_plain(self, fid, tgt)
            p, c = dossiers.encrypt_safe(plain, self.factions[tgt].cipher_key)
            tg = self.add_telegram(fid, "flash", tgt, f"TELEGRAMA-RELÂMPAGO — {self.factions[tgt].short.upper()}",
                                   c, "inteligencia", now_ms, plain=p)
            d = self.dossiers.get(fid, {}).get("inteligencia")
            if d is not None:
                d["extras"]["intercepts"].append({
                    "id": tg["id"], "from": tgt, "from_name": self.factions[tgt].short, "turn": self.turn,
                    "kind": "flash", "cipher": c, "codes": dossiers._codes(c)})
                for ds in d["datasets"]:
                    if ds["id"] == "criptogramas":
                        ds["rows"].append([tg["id"], self.factions[tgt].short, self.turn, c])
            events.append(ev(f"faction:{fid}", "telegram", deep(tg)))
        return events

    # ------------------------------------------------------------------ visões
    def public_map(self) -> dict:
        m = deep(self.map)
        for t in m["territories"]:
            t["name"] = self.tname(t["id"])
        return m

    def _public_faction(self, fid: str) -> dict:
        f = self.factions[fid]
        return {"id": fid, "name": f.name, "short": f.short, "color": f.nation["color"], "emblem": f.nation["emblem"],
                "capital": self.capital_tid(fid), "capital_name": f.nation["capital"],
                "capitulated": f.capitulated, "vp": round(self.vp(fid), 2), "territories": self.n_territories(fid)}

    def public_view(self, now_ms: int) -> dict:
        return {
            "game": self.game_dict(now_ms),
            "factions": [self._public_faction(f) for f in self.order],
            "territories": [{"id": t, "owner": self.owner[t]} for t in self.order_tids],
            "weather": dict(self.weather),
            "standings": [{k: r[k] for k in ("id", "vp", "territories", "rank")} for r in self.standings()],
            "news": [deep(n) for n in reversed(self.news[-20:])],
            "last_resolution": deep(self.last_resolution),
        }

    def _visibility(self, fid: str) -> dict[str, str]:
        mine = {t for t in self.order_tids if self.owner[t] == fid}
        vis = {}
        loc = self.factions[fid].bonuses.get("depot_located")
        for t in self.order_tids:
            if t in mine:
                vis[t] = "own"
            elif loc and loc.get("territory") == t:
                vis[t] = "revealed"
            elif any(t in self.adjacent(m) for m in mine):
                vis[t] = "adjacent"
            else:
                vis[t] = "hidden"
        return vis

    def faction_view(self, fid: str, now_ms: int) -> dict:
        f = self._need_faction(fid)
        vis = self._visibility(fid)
        terr = []
        for t in self.order_tids:
            v = vis[t]
            if v in ("own", "revealed"):
                terr.append({"id": t, "owner": self.owner[t], "troops": int(self.troops[t]),
                             "troops_range": None, "visibility": v})
            elif v == "adjacent":
                terr.append({"id": t, "owner": self.owner[t], "troops": None,
                             "troops_range": troops_range(self.troops[t]), "visibility": v})
            else:
                terr.append({"id": t, "owner": self.owner[t], "troops": None, "troops_range": None,
                             "visibility": v})
        loc = f.bonuses.get("depot_located")
        bonuses = {"productivity": bool(f.bonuses.get("productivity")),
                   "weather_revealed": bool(f.bonuses.get("weather_revealed")),
                   "depot_located": ({"territory": loc["territory"], "name": self.tname(loc["territory"]),
                                      "owner": self.owner[loc["territory"]]} if loc else None)}
        faction = {
            "id": fid, "name": f.name, "short": f.short, "color": f.nation["color"], "emblem": f.nation["emblem"],
            "capital": self.capital_tid(fid), "capital_name": f.nation["capital"],
            "stock": {s: round(float(f.stock[s]), 1) for s in B.SECTORS},
            "morale": round(float(f.morale), 1), "troops_total": self.troops_total(fid),
            "workforce": round(self.workforce(fid), 1), "labor": dict(B.LABOR),
            "capacity": {s: round(v, 1) for s, v in self.capacity(fid).items()},
            "vp": round(self.vp(fid), 2), "policy": dict(f.policy),
            "pacts": [dict(p) for p in f.pacts if p["until_turn"] >= self.turn],
            "pact_proposals_received": [p["from"] for p in self.proposals
                                        if p["to"] == fid and p["turn"] == self.turn - 1
                                        and not self.factions[p["from"]].capitulated],
            "capitulated": f.capitulated, "bonuses": bonuses, "challenges_solved": f.challenges_solved,
            "territories": self.n_territories(fid),
        }
        forecast = None
        if f.bonuses.get("weather_revealed"):
            forecast = {r: int(self.climate[r]["next"]) for r in B.REGIONS}
        return {
            "faction": faction,
            "territories": terr,
            "orders": {s: deep(f.orders.get(s)) for s in B.SECTIONS},
            "telegrams": deep(f.telegrams),
            "messages": deep(f.messages),
            "last_report": deep(f.last_report),
            "game": self.game_dict(now_ms),
            "weather_forecast": forecast,
            "weather": dict(self.weather),
            "factions": [self._public_faction(g) for g in self.order],
        }

    def dossier_view(self, fid: str, section: str) -> dict:
        self._need_faction(fid)
        return dossiers.dossier_view(self, fid, section)

    def dataset_csv(self, fid: str, section: str, dataset_id: str) -> str:
        self._need_faction(fid)
        if section not in B.SECTIONS:
            raise ValueError(f"Seção desconhecida: {section}")
        return dossiers.dataset_csv(self, fid, section, dataset_id)

    def admin_view(self, now_ms: int) -> dict:
        facs = {}
        for fid in self.order:
            f = self.factions[fid]
            d = f.to_dict()
            d.update({"name": f.name, "short": f.short, "vp": round(self.vp(fid), 2),
                      "territories": self.n_territories(fid), "troops_total": self.troops_total(fid),
                      "capital": self.capital_tid(fid), "workforce": round(self.workforce(fid), 1),
                      "capacity": self.capacity(fid),
                      "orders_submitted": {s: f.orders.get(s) is not None for s in B.SECTIONS}})
            d["telegrams_plain"] = deep(self.plain.get(fid, {}))
            facs[fid] = d
        return {
            "game": self.game_dict(now_ms), "seed": self.seed,
            "factions": facs, "credentials": self.credentials(),
            "territories": [{"id": t, "name": self.tname(t), "owner": self.owner[t], "troops": int(self.troops[t]),
                             "terrain": self.TER[t]["terrain"]} for t in self.order_tids],
            "climate": deep(self.climate), "depots": deep(self.depots), "challenge_keys": deep(self.keys),
            "challenge_state": deep(self.cstate), "effects": deep(self.effects), "event_log": deep(self.event_log),
            "proposals": deep(self.proposals), "history": deep(self.history), "standings": self.standings(),
            "news": deep(self.news[-20:][::-1]), "last_resolution": deep(self.last_resolution),
            "events": EV.list_events(),
            # compatibilidade com o painel simples
            "status": self.status, "turn": self.turn,
        }

    # ------------------------------------------------------------------ ações
    def _need_faction(self, fid: str) -> Faction:
        f = self.factions.get(fid)
        if f is None:
            raise ValueError(f"Nação desconhecida: {fid}")
        return f

    def _need_running(self, what: str) -> None:
        if self.status == "lobby":
            raise ValueError(f"A guerra ainda não começou: aguarde o sinal do árbitro para {what}.")
        if self.status == "paused":
            raise ValueError(f"A partida está pausada pelo árbitro: não é possível {what} agora.")
        if self.status == "finished":
            raise ValueError(f"A guerra terminou: não é mais possível {what}.")

    def check_password(self, fid: str, password: str) -> bool:
        f = self.factions.get(str(fid).upper())
        if f is None:
            return False
        a = str(password or "").strip().lower().encode("utf-8")
        b = f.password.lower().encode("utf-8")
        return hmac.compare_digest(a, b)

    def credentials(self) -> dict:
        return {fid: self.factions[fid].password for fid in self.order}

    def submit_orders(self, fid: str, section: str, payload: dict, now_ms: int) -> dict:
        f = self._need_faction(fid)
        if section not in B.SECTIONS:
            raise ValueError(f"Seção desconhecida: {section}")
        self._need_running("enviar ordens")
        if f.capitulated:
            raise ValueError("Sua nação capitulou: não há mais ordens a dar.")
        errors, warnings, norm = resolution.validate_orders(self, fid, section, payload)
        if errors:
            return {"ok": False, "errors": errors, "warnings": warnings}
        f.orders[section] = norm
        f.orders_at[section] = int(now_ms)
        self.last_ms = now_ms
        return {"ok": True, "errors": [], "warnings": warnings, "order": deep(norm)}

    def answer_challenge(self, fid: str, challenge_id: str, answer: str, now_ms: int) -> dict:
        f = self._need_faction(fid)
        self._need_running("responder desafios")
        if f.capitulated:
            raise ValueError("Sua nação capitulou.")
        st = self.cstate.get(fid, {}).get(challenge_id)
        if st is None:
            raise ValueError("Desafio inexistente ou de um turno anterior.")
        if st["solved"]:
            return {"correct": True, "message": "Este desafio já foi resolvido neste turno.",
                    "attempts_left": st["attempts_left"], "reward": None}
        if st["attempts_left"] <= 0:
            return {"correct": False, "message": "Não restam tentativas para este desafio.",
                    "attempts_left": 0, "reward": None}
        key = self.keys[fid][challenge_id]
        res = dossiers.check_answer(self, fid, key, answer)
        if res["status"] == "format":
            return {"correct": False, "message": res["message"], "attempts_left": st["attempts_left"],
                    "reward": None}
        if res["status"] == "wrong":
            st["attempts_left"] -= 1
            msg = res["message"] + (f" Restam {st['attempts_left']} tentativa(s)." if st["attempts_left"]
                                    else " Sem mais tentativas.")
            return {"correct": False, "message": msg, "attempts_left": st["attempts_left"], "reward": None}
        st["solved"] = True
        f.challenges_solved += 1
        reward = self._apply_reward(fid, key)
        reward["vp"] = B.CHALLENGE_VP
        return {"correct": True, "message": res["message"], "attempts_left": st["attempts_left"],
                "reward": reward}

    def _apply_reward(self, fid: str, key: dict) -> dict:
        f = self.factions[fid]
        kind = key["kind"]
        if kind == "leontief":
            f.bonuses["productivity"] = True
            return {"type": "productivity", "text": "+10% de produtividade neste turno"}
        if kind == "markov":
            f.bonuses["weather_revealed"] = True
            fc = {r: int(self.climate[r]["next"]) for r in B.REGIONS}
            return {"type": "weather", "text": "Clima exato da resolução deste turno: " + ", ".join(
                f"{dossiers.region_name(self, r)} {B.WEATHER_NAMES[v]}" for r, v in fc.items()), "forecast": fc}
        if kind == "depot":
            terr = key["territory"]
            f.bonuses["depot_located"] = {"territory": terr, "target": key["target"]}
            return {"type": "depot", "territory": terr, "text": (
                f"Depósito localizado em {self.tname(terr)} ({terr}). As tropas do território foram reveladas e a "
                "ordem «Bombardear depósito» foi liberada.")}
        f.morale = float(min(100.0, f.morale + B.CHALLENGE_REWARD_MORALE))
        return {"type": "morale", "text": f"+{B.CHALLENGE_REWARD_MORALE} de moral", "morale": round(f.morale, 1)}

    def send_message(self, fid: str, to_fid: str, text: str, now_ms: int) -> list[dict]:
        f = self._need_faction(fid)
        to_fid = str(to_fid).upper()
        g = self.factions.get(to_fid)
        if g is None:
            raise ValueError(f"Nação destinatária desconhecida: {to_fid}")
        if to_fid == fid:
            raise ValueError("Não é possível enviar telegrama a si mesmo.")
        if self.status in ("lobby", "finished"):
            raise ValueError("Telegramas diplomáticos só circulam com a guerra em andamento.")
        if f.capitulated:
            raise ValueError("Sua nação capitulou.")
        text = str(text or "").strip()
        if not text:
            raise ValueError("O telegrama está vazio.")
        if len(text) > B.MAX_MESSAGE_CHARS:
            raise ValueError(f"Telegrama longo demais (máximo de {B.MAX_MESSAGE_CHARS} caracteres).")
        msg = {"from": fid, "to": to_fid, "turn": self.turn, "text": text, "at_ms": int(now_ms)}
        for h in (f, g):
            h.messages.append(dict(msg))
            h.messages[:] = h.messages[-100:]
        return [ev(f"faction:{to_fid}", "message", dict(msg)), ev(f"faction:{fid}", "message", dict(msg))]

    def admin_broadcast(self, text: str, to: str, now_ms: int) -> list[dict]:
        text = str(text or "").strip()
        if not text:
            raise ValueError("O aviso está vazio.")
        to = str(to or "all")
        targets = self.order if to == "all" else [to.upper()]
        for t in targets:
            if t not in self.factions:
                raise ValueError(f"Destinatário desconhecido: {to}")
        out = []
        for t in targets:
            tg = self.add_telegram(t, "broadcast", None, "AVISO DO ÁRBITRO", text, None, now_ms)
        data = {"text": text, "to": to, "turn": self.turn, "at_ms": int(now_ms),
                "title": "AVISO DO ÁRBITRO"}
        channel = "public" if to == "all" else f"faction:{to.upper()}"
        out.append(ev(channel, "broadcast", data))
        return out

    def admin_edit_faction(self, fid: str, patch: dict, now_ms: int) -> list[dict]:
        f = self._need_faction(str(fid).upper())
        fid = f.id
        if not isinstance(patch, dict):
            raise ValueError("O ajuste deve ser um objeto.")
        known = {"stock", "morale", "troops", "owner", "capitulated"}
        extra = set(patch) - known
        if extra:
            raise ValueError("Campos desconhecidos no ajuste: " + ", ".join(sorted(extra))
                             + ". Use stock, morale, troops, owner ou capitulated.")
        # valida tudo antes de aplicar
        stock_p, morale_p = {}, None
        if "stock" in patch:
            if not isinstance(patch["stock"], dict):
                raise ValueError("stock deve ser um objeto {ALI, ACO, COM}.")
            for s, v in patch["stock"].items():
                if s not in B.SECTORS:
                    raise ValueError(f"Recurso desconhecido: {s}")
                x = _num(v, f"stock.{s}")
                if x < 0:
                    raise ValueError(f"stock.{s} não pode ser negativo.")
                stock_p[s] = x
        if "morale" in patch:
            morale_p = _num(patch["morale"], "morale")
            if not 0 <= morale_p <= 100:
                raise ValueError("A moral deve estar entre 0 e 100.")
        owner_p, troops_p = {}, {}
        if "owner" in patch:
            if not isinstance(patch["owner"], dict):
                raise ValueError("owner deve ser um objeto {território: nação|null}.")
            for t, o in patch["owner"].items():
                t = str(t).upper()
                if t not in self.TER:
                    raise ValueError(f"Território inexistente: {t}")
                if o in ("", "null", "neutro", "NEUTRO"):
                    o = None
                if o is not None:
                    o = str(o).upper()
                    if o not in self.factions:
                        raise ValueError(f"Nação desconhecida: {o}")
                owner_p[t] = o
        if "troops" in patch:
            if not isinstance(patch["troops"], dict):
                raise ValueError("troops deve ser um objeto {território: batalhões}.")
            for t, n in patch["troops"].items():
                t = str(t).upper()
                if t not in self.TER:
                    raise ValueError(f"Território inexistente: {t}")
                x = _num(n, f"troops.{t}")
                if x < 0 or abs(x - round(x)) > 1e-9:
                    raise ValueError(f"troops.{t} deve ser um inteiro não negativo.")
                troops_p[t] = int(round(x))
        for s, x in stock_p.items():
            f.stock[s] = float(x)
        if morale_p is not None:
            f.morale = float(morale_p)
        for t, o in owner_p.items():
            self.owner[t] = o
        for t, n in troops_p.items():
            self.troops[t] = n
        if "capitulated" in patch:
            f.capitulated = bool(patch["capitulated"])
        self.last_ms = now_ms
        return [ev("public", "state", {"faction": fid, "edited": sorted(patch)})]

    def admin_trigger_event(self, event_id: str, now_ms: int) -> list[dict]:
        if self.status not in ("running", "paused"):
            raise ValueError("Eventos só podem ser disparados com a partida em andamento.")
        item = EV.apply_event(self, event_id)
        self.add_news(item)
        self.last_ms = now_ms
        return [ev("public", "news", deep(item)), ev("public", "state", {})]


def _num(v: Any, name: str) -> float:
    if isinstance(v, bool):
        raise ValueError(f"{name}: valor inválido.")
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: «{v}» não é um número.")
    if not math.isfinite(x):
        raise ValueError(f"{name}: valor inválido.")
    return x
