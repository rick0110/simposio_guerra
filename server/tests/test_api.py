"""Testes da camada HTTP/WebSocket, contra um FakeGame que implementa a interface do contrato (§4).

Não usa o núcleo do jogo: DATA_DIR, WEB_DIR, MAP_PATH e SECRET_KEY apontam para diretórios temporários.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from contextlib import ExitStack

# Configuração antes de importar app: evita criar data/ e secret.key dentro do repositório.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="em_test_import_")
os.environ["SECRET_KEY"] = "chave-de-importacao-dos-testes"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app import auth, persistence  # noqa: E402
from app.config import settings  # noqa: E402
from app.hub import Hub  # noqa: E402
from app.main import create_app  # noqa: E402

CREDENTIALS = {"GAU": "senha-gau", "EUL": "senha-eul"}
ADMIN_PASSWORD = "arbitro-teste"


def ev(channel: str, type_: str, data: dict | None = None) -> dict:
    return {"channel": channel, "type": type_, "data": data or {}}


class FakeGame:
    """Implementação mínima da interface `Game` (contrato §4), com respostas fixas."""

    def __init__(self) -> None:
        self.turn = 1
        self.status = "lobby"
        self.calls: list[tuple] = []

    # persistência
    def to_dict(self) -> dict:
        return {"turn": self.turn, "status": self.status}

    @classmethod
    def from_dict(cls, d: dict, map_data: dict) -> "FakeGame":
        game = cls()
        game.turn = d["turn"]
        game.status = d["status"]
        return game

    # ciclo de vida
    def tick(self, now_ms: int) -> list[dict]:
        return []

    def start(self, now_ms: int) -> list[dict]:
        self.status = "running"
        return [ev("public", "phase", {"status": "running"})]

    def pause(self, now_ms: int) -> list[dict]:
        return []

    def resume(self, now_ms: int) -> list[dict]:
        return []

    def extend(self, now_ms: int, minutes: float) -> list[dict]:
        if minutes <= 0:
            raise ValueError("Minutos devem ser positivos.")
        return []

    def resolve_turn(self, now_ms: int) -> list[dict]:
        resolved = self.turn
        self.turn += 1
        return [ev("public", "resolution", {"turn": resolved, "battles": []})]

    # visões
    def public_view(self, now_ms: int) -> dict:
        return {"game": {"status": self.status, "turn": self.turn}, "factions": []}

    def faction_view(self, fid: str, now_ms: int) -> dict:
        self.calls.append(("faction_view", fid))
        return {"faction": {"id": fid}, "territories": []}

    def dossier_view(self, fid: str, section: str) -> dict:
        self.calls.append(("dossier_view", fid, section))
        return {"section": section, "faction": fid, "datasets": []}

    def dataset_csv(self, fid: str, section: str, dataset_id: str) -> str:
        if dataset_id == "nao-existe":
            raise KeyError("Conjunto de dados não encontrado.")
        return f"área;valor\n{fid};1\n"

    def admin_view(self, now_ms: int) -> dict:
        return {"status": self.status, "turn": self.turn, "segredos": {"GAU": "senha-gau"}}

    # ações
    def check_password(self, fid: str, password: str) -> bool:
        if fid not in CREDENTIALS:
            raise KeyError("Facção desconhecida.")
        return CREDENTIALS[fid] == password

    def credentials(self) -> dict:
        return dict(CREDENTIALS)

    def submit_orders(self, fid: str, section: str, payload: dict, now_ms: int) -> dict:
        self.calls.append(("submit_orders", fid, section))
        return {"ok": True, "errors": [], "warnings": [], "order": {"section": section, "payload": payload}}

    def answer_challenge(self, fid: str, challenge_id: str, answer: str, now_ms: int) -> dict:
        return {"correct": answer == "42", "message": "ok", "attempts_left": 2, "reward": None}

    def send_message(self, fid: str, to_fid: str, text: str, now_ms: int) -> list[dict]:
        return [ev(f"faction:{to_fid}", "message", {"from": fid, "text": text})]

    def admin_broadcast(self, text: str, to: str, now_ms: int) -> list[dict]:
        channel = "public" if to == "all" else f"faction:{to}"
        return [ev(channel, "broadcast", {"text": text})]

    def admin_edit_faction(self, fid: str, patch: dict, now_ms: int) -> list[dict]:
        return [ev("admin", "state", {"faction": fid, "patch": patch})]

    def admin_trigger_event(self, event_id: str, now_ms: int) -> list[dict]:
        if event_id == "privado":
            return [ev("faction:EUL", "telegram", {"title": "Interceptação"}), ev("public", "news", {"headline": "Público"})]
        return []


def _headers(payload: dict) -> dict:
    return {"cookie": f"{auth.COOKIE_NAME}={auth.make_cookie(payload)}"}


def gau() -> dict:
    return _headers({"fid": "GAU"})


def eul() -> dict:
    return _headers({"fid": "EUL"})


def adm() -> dict:
    return _headers({"admin": True})


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>idx</title>", encoding="utf-8")
    (web / "teatro.html").write_text("<!doctype html><title>teatro</title>", encoding="utf-8")
    map_file = tmp_path / "map.json"
    map_file.write_text(json.dumps({"width": 1200, "height": 800, "territories": []}), encoding="utf-8")

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(settings, "WEB_DIR", web)
    monkeypatch.setattr(settings, "MAP_PATH", map_file)
    monkeypatch.setattr(settings, "SECRET_KEY", "chave-de-teste")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", ADMIN_PASSWORD)
    return tmp_path


@pytest.fixture
def client(app_env):
    app = create_app(game_factory=lambda m: FakeGame())
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------- cookies e sessão

def test_cookie_assinado_e_validade(app_env, monkeypatch):
    token = auth.make_cookie({"fid": "GAU"})
    assert auth.read_cookie(token) == {"fid": "GAU"}

    body, signature = token.rsplit(".", 1)
    forged_sig = ("A" if signature[0] != "A" else "B") + signature[1:]
    assert auth.read_cookie(f"{body}.{forged_sig}") is None
    assert auth.read_cookie("lixo") is None
    assert auth.read_cookie(None) is None

    monkeypatch.setattr(auth, "MAX_AGE", -5)
    assert auth.read_cookie(auth.make_cookie({"fid": "GAU"})) is None


def test_login_correto_define_cookie_e_me(client):
    r = client.post("/api/login", json={"faction_id": "gau", "password": "senha-gau"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "faction_id": "GAU"}
    set_cookie = r.headers["set-cookie"].lower()
    assert "em_session=" in set_cookie and "httponly" in set_cookie
    assert "samesite=lax" in set_cookie and "path=/" in set_cookie and "max-age=43200" in set_cookie

    # o cookie da resposta vale para as próximas chamadas do mesmo cliente
    assert client.get("/api/me").json() == {"faction_id": "GAU", "admin": False}


def test_login_errado_e_facao_desconhecida_dao_401(client):
    r = client.post("/api/login", json={"faction_id": "GAU", "password": "errada"})
    assert r.status_code == 401
    r = client.post("/api/login", json={"faction_id": "XXX", "password": "qualquer"})
    assert r.status_code == 401


def test_logout_limpa_sessao(client):
    client.post("/api/login", json={"faction_id": "GAU", "password": "senha-gau"})
    assert client.post("/api/logout").json() == {"ok": True}
    assert client.get("/api/me").json() == {"faction_id": None, "admin": False}


def test_rotas_de_faccao_exigem_sessao_valida(client, monkeypatch):
    r = client.get("/api/faction/state")
    assert r.status_code == 401
    assert r.json()["detail"] == "Sessão expirada: faça login novamente"

    # sessão de árbitro não serve para rota de facção
    assert client.get("/api/faction/state", headers=adm()).status_code == 401

    # cookie assinado com outra chave é recusado
    original = settings.SECRET_KEY
    settings.SECRET_KEY = "outra-chave"
    try:
        forged = _headers({"fid": "GAU"})
    finally:
        settings.SECRET_KEY = original
    assert client.get("/api/faction/state", headers=forged).status_code == 401


def test_faccao_so_recebe_os_proprios_dados(client):
    r = client.get("/api/faction/state", headers=gau())
    assert r.status_code == 200 and r.json()["faction"]["id"] == "GAU"
    assert client.app.state.game.calls[-1] == ("faction_view", "GAU")

    r = client.get("/api/faction/dossier/governo", headers=eul())
    assert r.json()["faction"] == "EUL"
    assert client.app.state.game.calls[-1] == ("dossier_view", "EUL", "governo")


def test_secao_desconhecida_da_404(client):
    assert client.get("/api/faction/dossier/espiao", headers=gau()).status_code == 404
    assert client.post("/api/faction/orders/espiao", json={}, headers=gau()).status_code == 404


# ---------------------------------------------------------------- facção: ordens, CSV, snapshot

def test_ordens_retornam_dict_e_salvam_snapshot(client):
    snapshot_file = settings.DATA_DIR / "state.json"
    assert not snapshot_file.exists()

    r = client.post(
        "/api/faction/orders/intendencia",
        json={"production": {"ALI": 30, "ACO": 12, "COM": 10}, "recruit": 3},
        headers=gau(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["errors"] == []
    assert body["order"]["payload"]["recruit"] == 3
    assert client.app.state.game.calls[-1] == ("submit_orders", "GAU", "intendencia")

    assert json.loads(snapshot_file.read_text(encoding="utf-8")) == client.app.state.game.to_dict()


def test_csv_do_dossie_com_content_type_certo(client):
    r = client.get("/api/faction/dossier/intendencia/transacoes.csv", headers=gau())
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"].startswith("attachment; filename=")
    assert r.text == "área;valor\nGAU;1\n"


def test_erro_de_conjunto_de_dados_vira_400(client):
    r = client.get("/api/faction/dossier/intendencia/nao-existe.csv", headers=gau())
    assert r.status_code == 400
    assert r.json() == {"detail": "Conjunto de dados não encontrado."}


def test_desafio_e_mensagem_da_faccao(client):
    r = client.post("/api/faction/challenge/c3-intendencia", json={"answer": "42"}, headers=gau())
    assert r.json()["correct"] is True
    assert client.post("/api/faction/challenge/c3-intendencia", json={}, headers=gau()).status_code == 400

    r = client.post("/api/faction/message", json={"to_faction": "EUL", "text": "olá"}, headers=gau())
    assert r.json() == {"ok": True}


# ---------------------------------------------------------------- árbitro

def test_login_do_arbitro_e_acao_administrativa(client):
    assert client.post("/api/admin/login", json={"password": "errada"}).status_code == 401
    assert client.post("/api/admin/start").status_code == 401
    assert client.get("/api/admin/state").status_code == 401

    r = client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200
    assert client.get("/api/me").json() == {"faction_id": None, "admin": True}

    assert client.post("/api/admin/start").json() == {"ok": True}
    assert client.app.state.game.status == "running"
    assert client.get("/api/admin/state").json()["status"] == "running"
    assert client.get("/api/admin/credentials").json() == CREDENTIALS
    assert isinstance(client.get("/api/admin/events").json(), list)


def test_erro_do_jogo_vira_400_com_mensagem(client):
    client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    r = client.post("/api/admin/extend", json={"minutes": 0})
    assert r.status_code == 400
    assert r.json() == {"detail": "Minutos devem ser positivos."}
    assert client.post("/api/admin/extend", json={"minutes": "dez"}).status_code == 400


def test_resolucao_arquiva_o_turno(client):
    client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert client.post("/api/admin/resolve_now").json() == {"ok": True}
    assert persistence.list_turn_archives() == [1]
    assert persistence.load_turn_archive(1) == client.app.state.game.to_dict()


def test_rollback_restaura_o_turno_arquivado(client):
    client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    client.post("/api/admin/start")
    persistence.save_turn_archive(1, {"turn": 1, "status": "finished"})

    r = client.post("/api/admin/rollback", json={"turn": 1})
    assert r.status_code == 200
    assert client.app.state.game.status == "finished"
    assert client.app.state.game.turn == 1

    assert client.post("/api/admin/rollback", json={"turn": 9}).status_code == 404


def test_novo_jogo_substitui_o_estado(client):
    client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    client.post("/api/admin/start")
    old = client.app.state.game
    r = client.post("/api/admin/new_game", json={"n_factions": 3, "seed": 7})
    assert r.json() == {"ok": True}
    assert client.app.state.game is not old
    assert client.app.state.game.status == "lobby"
    assert json.loads((settings.DATA_DIR / "state.json").read_text(encoding="utf-8"))["status"] == "lobby"


# ---------------------------------------------------------------- WebSocket

def test_websocket_publico_recebe_evento_publicado(client):
    client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    with client.websocket_connect("/ws?ch=public") as ws:
        assert client.post("/api/admin/broadcast", json={"text": "Atenção", "to": "all"}).status_code == 200
        assert ws.receive_json() == {"type": "broadcast", "data": {"text": "Atenção"}}


def test_canais_privados_ficam_isolados(client):
    with ExitStack() as stack:
        pub = stack.enter_context(client.websocket_connect("/ws?ch=public"))
        ws_gau = stack.enter_context(client.websocket_connect("/ws?ch=faction", headers=gau()))
        ws_eul = stack.enter_context(client.websocket_connect("/ws?ch=faction", headers=eul()))
        ws_adm = stack.enter_context(client.websocket_connect("/ws?ch=admin", headers=adm()))

        # evento de facção EUL + evento público
        assert client.post("/api/admin/event", json={"event_id": "privado"}, headers=adm()).status_code == 200
        assert pub.receive_json() == {"type": "news", "data": {"headline": "Público"}}
        assert ws_gau.receive_json() == {"type": "news", "data": {"headline": "Público"}}
        assert ws_eul.receive_json() == {"type": "telegram", "data": {"title": "Interceptação"}}
        assert ws_eul.receive_json() == {"type": "news", "data": {"headline": "Público"}}
        assert ws_adm.receive_json() == {"type": "telegram", "data": {"title": "Interceptação"}}
        assert ws_adm.receive_json() == {"type": "news", "data": {"headline": "Público"}}

        # evento só do árbitro
        client.post("/api/admin/edit_faction", json={"faction_id": "GAU", "patch": {"morale": 80}}, headers=adm())
        assert ws_adm.receive_json() == {"type": "state", "data": {"faction": "GAU", "patch": {"morale": 80}}}

        # aviso geral chega a todos; se algum canal privado vazasse, apareceria antes do aviso
        client.post("/api/admin/broadcast", json={"text": "fim", "to": "all"}, headers=adm())
        expected = {"type": "broadcast", "data": {"text": "fim"}}
        assert pub.receive_json() == expected
        assert ws_gau.receive_json() == expected
        assert ws_eul.receive_json() == expected
        assert ws_adm.receive_json() == expected


def test_websocket_sem_autenticacao_fecha_4401(client):
    for url, headers in (
        ("/ws?ch=faction", {}),
        ("/ws?ch=admin", gau()),
        ("/ws?ch=canal-inexistente", {}),
    ):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(url, headers=headers) as ws:
                ws.receive_json()
        assert exc.value.code == 4401


def test_hub_remove_socket_morto_e_respeita_o_canal_da_facao():
    class Recorder:
        def __init__(self):
            self.sent = []

        async def send_json(self, message):
            self.sent.append(message)

    class Dead:
        async def send_json(self, message):
            raise RuntimeError("conexão fechada")

    async def scenario():
        hub = Hub()
        gau, eul, dead = Recorder(), Recorder(), Dead()
        hub.register(gau, "faction", "GAU")
        hub.register(eul, "faction", "EUL")
        hub.register(dead, "public")

        await hub.publish(ev("faction:GAU", "telegram", {"n": 1}))
        assert gau.sent == [{"type": "telegram", "data": {"n": 1}}]
        assert eul.sent == []
        assert len(hub) == 3  # o socket público não recebe evento de facção, portanto ainda não falhou

        # evento público alcança o socket morto: ele é removido, sem derrubar o hub
        await hub.publish(ev("public", "state", {}))
        assert len(gau.sent) == 2 and len(eul.sent) == 1
        assert len(hub) == 2

    asyncio.run(scenario())


# ---------------------------------------------------------------- persistência, estáticos, público

def test_persistencia_atomica_e_arquivos_de_turno(app_env):
    persistence.save_snapshot({"turn": 1, "nome": "Gáussia"})
    assert persistence.load_snapshot() == {"turn": 1, "nome": "Gáussia"}
    raw = (settings.DATA_DIR / "state.json").read_text(encoding="utf-8")
    assert "Gáussia" in raw  # ensure_ascii=False
    assert not (settings.DATA_DIR / "state.json.tmp").exists()

    persistence.save_turn_archive(2, {"turn": 2})
    persistence.save_turn_archive(1, {"turn": 1})
    assert persistence.list_turn_archives() == [1, 2]
    assert persistence.load_turn_archive(3) is None


def test_estaticos_paginas_e_relogio(client):
    r = client.get("/")
    assert r.status_code == 200 and "idx" in r.text
    assert r.headers["cache-control"] == "no-cache"

    r = client.get("/teatro")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    assert client.get("/qg").status_code == 404  # arquivo ainda não existe

    now = int(time.time() * 1000)
    server_time = client.get("/api/server_time").json()["now_ms"]
    assert abs(server_time - now) < 60_000


def test_estado_publico_e_mapa(client):
    assert client.get("/api/public/state").json()["game"]["status"] == "lobby"
    assert client.get("/api/public/map").json()["width"] == 1200


def test_mapa_ausente_com_factory_da_404(app_env, monkeypatch):
    monkeypatch.setattr(settings, "MAP_PATH", app_env / "nao-existe.json")
    app = create_app(game_factory=lambda m: FakeGame())
    with TestClient(app) as c:
        assert c.get("/api/public/map").status_code == 404
