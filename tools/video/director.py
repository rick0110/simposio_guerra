"""Roteiro do vídeo de demonstração: joga uma partida real pela interface, com 6 telas abertas.

Abre árbitro, projetor (Teatro) e um QG por nação, grava cada tela com o Playwright e anota,
em timeline.json, quando cada legenda entra e qual tela fica em destaque. A montagem é feita
por compose.py.

Uso (a partir da raiz do repositório):
    python tools/video/director.py <pasta_de_trabalho> [--dry]
  --dry  não grava vídeo; tira uma captura da tela em foco a cada legenda (para conferir os cliques).
Precisa de: dependências do servidor (server/requirements.txt), playwright (pip) e um Chromium.
"""
import asyncio
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(sys.argv[1]).resolve()
DRY = "--dry" in sys.argv
PORT = int(os.environ.get("VIDEO_PORT", "8800"))
BASE = f"http://127.0.0.1:{PORT}"


def chrome_path():
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    return found[-1] if found else None  # None = Chromium do próprio Playwright


SCREENS = {  # nome -> (url inicial, viewport, rótulo no vídeo)
    "arbitro": ("/arbitro", (1366, 768), "Árbitro (organizador)"),
    "teatro": ("/teatro", (1920, 1080), "Projetor: Teatro de Operações"),
    "gau": ("/", (1366, 768), "Sala 1: Gáussia, seção Intendência"),
    "eul": ("/", (1366, 768), "Sala 2: Eulerândia, seção Operações"),
    "hil": ("/", (1366, 768), "Sala 3: Hilbertânia, seção Inteligência"),
    "noe": ("/", (1366, 768), "Sala 4: Noethéria, seção Governo"),
}
FID = {"gau": "GAU", "eul": "EUL", "hil": "HIL", "noe": "NOE"}
SECTION = {"gau": "intendencia", "eul": "operacoes", "hil": "inteligencia", "noe": "governo"}
KEY_OF_SECTION = {v: k for k, v in SECTION.items()}

# cursor visível (o vídeo do navegador sem interface não mostra o ponteiro do mouse)
CURSOR_JS = r"""
(() => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;left:-60px;top:-60px;width:26px;height:26px;margin:-13px 0 0 -13px;' +
      'border-radius:50%;background:rgba(230,40,30,.45);border:3px solid #fff;box-shadow:0 0 0 3px rgba(200,30,20,.9),0 2px 8px rgba(0,0,0,.6);' +
      'z-index:2147483647;pointer-events:none;transition:transform .12s ease-out';
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { c.style.transform = 'scale(1.9)'; }, true);
    addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', mk); else mk();
})();
"""

T0 = None
TIMELINE = []
CREATED = {}
PAGES = {}
CTX = {}
SHOT = [0]
ERRORS = []
MAP = json.loads((ROOT / "server/app/data/map.json").read_text())
TER = {t["id"]: t for t in MAP["territories"]}


def now():
    return time.monotonic()


async def say(text, focus="grid", hold=None):
    """Legenda nova + tela em destaque ("grid" = as seis lado a lado). Vale até a próxima legenda."""
    t = now() - T0
    TIMELINE.append({"t": round(t, 2), "text": text, "focus": focus})
    print(f"[{t:6.1f}s] ({focus}) {text}", flush=True)
    if DRY and focus in PAGES:
        SHOT[0] += 1
        try:
            await PAGES[focus].screenshot(path=str(WORK / "dry" / f"{SHOT[0]:02d}_{focus}.png"))
        except Exception as e:  # noqa: BLE001
            print("   captura falhou:", e)
    if hold is None:
        hold = max(3.5, len(text) / 15)
    await asyncio.sleep(hold if not DRY else min(hold, 1.0))


async def pause(s):
    await asyncio.sleep(s if not DRY else min(s, 0.6))


async def point(page, loc, click=True, steps=20, wait=0.35):
    """Leva o cursor até o elemento (centralizado na tela) e clica."""
    await loc.wait_for(state="visible", timeout=10000)
    # centraliza: evita alvos escondidos atrás da alça fixa da Mesa de Cálculo, no rodapé
    await loc.evaluate("e => e.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'smooth'})")
    prev, box = None, None
    for _ in range(40):  # espera a rolagem terminar (posição estável)
        await asyncio.sleep(0.1)
        box = await loc.bounding_box()
        if box and prev and abs(box["y"] - prev["y"]) < 0.5 and abs(box["x"] - prev["x"]) < 0.5:
            break
        prev = box
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y, steps=steps)
    await asyncio.sleep(wait)
    # a página pode ter se mexido durante o movimento (gaveta fechando, rolagem): confere de novo
    box2 = await loc.bounding_box()
    if box2:
        x2, y2 = box2["x"] + box2["width"] / 2, box2["y"] + box2["height"] / 2
        if abs(x2 - x) > 2 or abs(y2 - y) > 2:
            x, y = x2, y2
            await page.mouse.move(x, y, steps=6)
            await asyncio.sleep(0.2)
    if click:
        await page.mouse.click(x, y)


async def point_xy(page, x, y, click=True, steps=20):
    await page.mouse.move(x, y, steps=steps)
    await asyncio.sleep(0.35)
    if click:
        await page.mouse.click(x, y)


async def type_in(page, loc, text, delay=55):
    await point(page, loc)
    await loc.fill("")
    await page.keyboard.type(str(text), delay=delay if not DRY else 5)


async def step(label, coro):
    """Executa um passo; se falhar, registra e segue (o relatório final lista os erros)."""
    try:
        return await coro
    except Exception as e:  # noqa: BLE001
        msg = f"{label}: {type(e).__name__}: {str(e).splitlines()[0][:200]}"
        print("   !!", msg, flush=True)
        ERRORS.append(msg)
        return None


async def api(ctx_name, method, path, body=None):
    """Chamada HTTP com a sessão (cookies) daquela tela."""
    req = CTX[ctx_name].request
    if method == "GET":
        r = await req.get(BASE + path)
    else:
        r = await req.post(BASE + path, data=json.dumps(body or {}), headers={"Content-Type": "application/json"})
    try:
        return await r.json()
    except Exception:  # noqa: BLE001
        return {"status": r.status}


def fmt(v):
    return (f"{v:.2f}").rstrip("0").rstrip(".").replace(".", ",")


# ----------------------------------------------------------------------------- ações de tela
async def calc_run(page, tool, label="Calcular"):
    btn = page.locator(f'#calc-drawer [data-tool="{tool}"] button.calc-run:has-text("{label}")').first
    await point(page, btn)
    await pause(2.0)


async def mesa_use_and_answer(page, sec):
    """'usar no questionário' na fita da Mesa, envia a resposta e confere no servidor."""
    use = page.locator('#calc-drawer button:has-text("usar no questionário")').first
    await use.wait_for(timeout=10000)
    await point(page, use)
    await pause(2.0)
    send = page.locator(f"#sec-{sec} .chal__send").first
    k = KEY_OF_SECTION[sec]
    for tentativa in range(3):
        await point(page, send)
        await pause(2.5)
        d = await api(k, "GET", f"/api/faction/dossier/{sec}")
        if all(c.get("solved") for c in d.get("challenges", [])):
            return
        print(f"   desafio de {sec} ainda não resolvido (tentativa {tentativa + 1})", flush=True)
    raise RuntimeError(f"desafio de {sec} não foi resolvido")


async def map_point(page, sec, tid):
    """Ponto de tela de um território do mapa (coordenada do mapa convertida pela matriz do SVG)."""
    lx, ly = TER[tid]["label_pos"]
    cx, cy = TER[tid]["centroid"]
    js = """([sec, tid, cands]) => {
      const hit = document.querySelector(`#sec-${sec} svg path.hit[data-id="${tid}"]`);
      if (!hit) return null;
      const svg = hit.ownerSVGElement, m = hit.getScreenCTM();
      for (const [x, y] of cands) {
        const p = svg.createSVGPoint(); p.x = x; p.y = y; const q = p.matrixTransform(m);
        const el = document.elementFromPoint(q.x, q.y);
        if (el && el.closest && el.closest(`[data-id="${tid}"]`)) return [q.x, q.y];
      }
      const b = hit.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2];
    }"""
    cands = [[cx, cy], [lx, ly + 18], [lx, ly - 18], [lx + 20, ly], [lx - 20, ly]]
    return await page.evaluate(js, [sec, tid, cands])


def pick_attack(view, fid):
    """Origem própria e alvo vizinho (de preferência neutro) que dê para atacar."""
    terr = {t["id"]: t for t in view["territories"]}
    best = None
    for tid, t in terr.items():
        if t["owner"] != fid or not t["troops"]:
            continue
        for nb in TER[tid]["neighbors"]:
            o = terr[nb]
            if o["owner"] == fid:
                continue
            guess = {"1–5": 5, "6–10": 10, "11–20": 20, "21+": 30}.get(o.get("troops_range") or "", 6)
            n = t["troops"] - 1
            score = (o["owner"] is None, n / guess)
            if n >= 2 and n / guess >= 0.8 and (best is None or score > best[0]):
                best = (score, tid, nb, n)
    return None if best is None else {"from": best[1], "to": best[2], "troops": best[3]}


# ----------------------------------------------------------------------------- roteiro
async def scenario():
    A, TE = PAGES["arbitro"], PAGES["teatro"]
    G, E, H, N = PAGES["gau"], PAGES["eul"], PAGES["hil"], PAGES["noe"]

    await say("ESTADO-MAIOR: como se joga. Seis telas ao mesmo tempo: o árbitro, o projetor da sala principal "
              "e um computador em cada uma das quatro salas (uma nação por sala).", "grid", 9)
    await say("Um único PC roda o servidor (com Docker). Todos os outros só abrem o endereço dele no navegador: "
              "não se instala nada nos computadores das salas.", "grid", 8)

    # ---------------- árbitro cria a partida
    await say("1. O árbitro abre /arbitro e entra com a senha de árbitro.", "arbitro")
    await step("login árbitro", type_in(A, A.locator("#gate-pass"), "arbitro"))
    await step("entrar", point(A, A.locator("#gate-submit")))
    await pause(2)
    await say("Ele cria a partida: 4 nações, turnos de 8 minutos e só 2 turnos, para caber no vídeo "
              "(no evento: 12 minutos e 8 turnos).", "arbitro")
    await step("novo jogo", point(A, A.locator("#btn-new")))
    await pause(0.8)
    await step("ng-min", type_in(A, A.locator("#ng-min"), "8"))
    await step("ng-turns", type_in(A, A.locator("#ng-turns"), "2"))
    await step("ng-seed", type_in(A, A.locator("#ng-seed"), "1943"))
    await step("revisar", point(A, A.locator("#ng-submit")))
    await pause(1.2)
    await step("confirmar 1", point(A, A.locator("#ask-ok")))
    await pause(1)
    await step("APAGAR", type_in(A, A.locator("#ask-word-input"), "APAGAR"))
    await step("confirmar 2", point(A, A.locator("#ask-ok")))
    await pause(2)
    await say("Depois imprime as credenciais: um cartão por sala, com o endereço do servidor e a senha da nação.",
              "arbitro", 2)
    await step("credenciais", point(A, A.locator("#btn-cred-top")))
    await pause(5)
    await step("fechar credenciais", point(A, A.locator("#cred-close")))
    creds = await api("arbitro", "GET", "/api/admin/credentials")

    # ---------------- logins
    for k in ("gau", "eul", "hil", "noe"):
        await PAGES[k].reload()
    await pause(1.5)

    async def login(k, slow=True):
        p = PAGES[k]
        await point(p, p.locator(f'label.nation[data-faction="{FID[k]}"]'), steps=20 if slow else 8)
        await pause(0.5)
        await p.locator("#password").click()
        await p.keyboard.type(creds[FID[k]], delay=70 if (slow and not DRY) else 10)
        await pause(0.4)
        await point(p, p.locator("#go"), steps=12)
        await p.wait_for_url("**/qg**", timeout=15000)

    await say("2. Em cada sala os alunos abrem o endereço do cartão (o Portão), assinalam a nação e digitam a senha.",
              "gau", 2)
    await step("login GAU", login("gau"))
    await say("As outras três salas fazem o mesmo, cada uma com a sua senha.", "grid", 1)
    await asyncio.gather(*(step(f"login {k}", login(k, False)) for k in ("eul", "hil", "noe")))
    await pause(3)
    await say("Dentro do Quartel-General, cada grupo da sala trabalha numa aba: Intendência, Operações, "
              "Inteligência e Governo. Para mostrar as quatro, aqui cada sala está numa seção diferente.", "grid", 2)
    for k in ("gau", "eul", "hil", "noe"):
        await step(f"aba {k}", point(PAGES[k], PAGES[k].locator(f"#tab-{SECTION[k]}"), steps=12))
    await pause(5)

    # ---------------- início
    await say("3. Tudo pronto: o árbitro aperta INICIAR GUERRA. O relógio do turno começa a correr em todas as telas.",
              "arbitro", 2)
    await step("iniciar", point(A, A.locator("#btn-start")))
    await pause(3)
    await say("No projetor, o Teatro de Operações: o mapa do continente com as cores de cada nação, o jornal "
              "O Arauto do Front, o relógio do turno, o placar e o clima.", "teatro", 9)
    await say("Ao mesmo tempo cada sala recebe, por telegrama, o seu dossiê do turno: dados novos, gerados a partir "
              "da situação real da partida.", "grid", 8)

    # ---------------- Intendência (GAU)
    gd = await api("gau", "GET", "/api/faction/dossier/intendencia")
    prompt = gd["challenges"][0]["prompt"] if gd.get("challenges") else ""
    mt = re.search(r"\(([\d.,]+) ALI; ([\d.,]+) ACO; ([\d.,]+) COM\)", prompt)
    dvals = [m.replace(",", ".") for m in mt.groups()] if mt else ["20", "4", "6"]
    await say("4. INTENDÊNCIA (economia). Recebe a tabela de transações entre os setores Alimento, Aço e "
              "Combustível e decide quanto cada setor vai produzir.", "gau")
    await step("rolar dossiê", G.locator("#sec-intendencia .ds").first.scroll_into_view_if_needed())
    await pause(2)
    await say("O desafio pede a produção que entrega uma demanda d. É o modelo de Leontief: A = Z·diag(X)⁻¹ e "
              "resolver (I − A)x = d. A Mesa de Cálculo faz a conta; o aluno precisa saber qual conta fazer.", "gau", 3)
    await step("abrir mesa leontief",
               point(G, G.locator('#sec-intendencia button:has-text("Abrir na Mesa de Cálculo")').first))
    await pause(1.5)
    for i in range(3):
        cell = G.locator(f'#calc-drawer [data-tool="leontief"] input[aria-label="d (demanda final), linha {i + 1}, coluna 1"]')
        await step(f"d{i}", type_in(G, cell, dvals[i].replace(".", ",")))
    await step("calcular leontief", calc_run(G, "leontief"))
    await pause(2.5)
    await say("Resultado na fita da Mesa. Um clique em «usar no questionário» leva a resposta ao desafio.", "gau", 2)
    await step("responder intendência", mesa_use_and_answer(G, "intendencia"))
    await say("Resposta certa: carimbo CORRETO e +10% de produtividade neste turno.", "gau", 4)
    cap = (await api("gau", "GET", "/api/faction/state"))["faction"]["capacity"]
    await say("Agora a ordem: quanto produzir em cada setor e quantos batalhões recrutar. "
              "A folha mostra a mão de obra e o estoque previstos.", "gau", 2)
    prod = {"ALI": min(cap["ALI"], 26), "ACO": min(cap["ACO"], 9), "COM": min(cap["COM"], 8)}
    for s in ("ALI", "ACO", "COM"):
        await step(f"prod {s}", type_in(G, G.locator(f"#int-x-{s}"), fmt(prod[s])))
    await step("recrutas", type_in(G, G.locator("#int-rec"), "2"))
    await step("usar A", point(G, G.locator('#sec-intendencia button:has-text("Usar A da tabela")')))
    await pause(2.5)
    await say("Assina e carimba: a ordem fica guardada no servidor e só vale no fim do turno. Pode ser corrigida "
              "até o prazo; vale a última.", "gau", 2)
    await step("expedir intendência", point(G, G.locator("#sec-intendencia .order__send")))
    await pause(3)

    # ---------------- Operações (EUL)
    await say("5. OPERAÇÕES (exército). O mapa da nação tem névoa de guerra: tropas exatas só nos próprios "
              "territórios; nos vizinhos, só uma faixa; no resto, nada.", "eul")
    ev_view = await api("eul", "GET", "/api/faction/state")
    atk = pick_attack(ev_view, "EUL") or {"from": "T06", "to": "T10", "troops": 4}
    await say(f"Para atacar: clica num território seu ({TER[atk['from']]['name']}) e depois num vizinho "
              f"({TER[atk['to']]['name']}); escolhe quantos batalhões e lança a ordem.", "eul", 2)
    xy = await step("ponto origem", map_point(E, "operacoes", atk["from"]))
    if xy:
        await point_xy(E, *xy)
    await pause(1.2)
    xy = await step("ponto destino", map_point(E, "operacoes", atk["to"]))
    if xy:
        await point_xy(E, *xy)
    await pause(1.2)
    num = E.locator('input[type="range"][aria-label="Quantos batalhões"] ~ input[type="number"]').first
    await step("batalhões", type_in(E, num, str(atk["troops"])))
    await step("lançar", point(E, E.locator('button:has-text("Lançar ordem")').first))
    await pause(2)
    await say("Ao lado, a estimativa da batalha pela lei de Lanchester (equações diferenciais), no pior e no "
              "melhor caso, com terreno, clima e moral.", "eul", 2)
    await step("rolar batalha", E.locator("#bat-sel").scroll_into_view_if_needed())
    await pause(4)
    await say("O desafio de Operações é o clima: estimar a chance de tempestade contando as transições do diário "
              "meteorológico (cadeia de Markov).", "eul", 2)
    await step("abrir markov", point(E, E.locator('#sec-operacoes button:has-text("Abrir na Mesa (Markov)")').first))
    await pause(1.5)
    await step("calcular markov", calc_run(E, "markov"))
    await pause(2)
    await step("responder operações", mesa_use_and_answer(E, "operacoes"))
    await say("Acertou: como recompensa, o servidor revela o clima exato do próximo turno.", "eul", 4)
    await step("expedir operações", point(E, E.locator("#sec-operacoes .order__send")))
    await pause(3)

    # ---------------- Governo (NOE)
    await say("6. GOVERNO. Decide ração, propaganda e jornada de trabalho. Isso mexe na moral (que fortalece o "
              "exército) e na mão de obra.", "noe", 2)
    await step("ração", point(N, N.locator('#sec-governo label:has(input[name="gov-racao"][value="1"])').first))
    await pause(0.8)
    await step("jornada", point(N, N.locator('#sec-governo label:has(input[name="gov-horas"][value="10"])').first))
    await pause(0.8)
    await step("propaganda", point(N, N.locator("#gov-prop"), click=False))
    await N.evaluate("() => { const r = document.getElementById('gov-prop'); r.value = '2'; "
                     "r.dispatchEvent(new Event('input', {bubbles: true})); r.dispatchEvent(new Event('change', {bubbles: true})); }")
    await pause(2)
    await say("O desafio do Governo: uma pesquisa de opinião. Com regressão linear, estimar quanto cada ponto de "
              "propaganda muda a moral.", "noe", 2)
    await step("abrir regressão", point(N, N.locator('#sec-governo button:has-text("Abrir na Mesa (regressão)")').first))
    await pause(1.5)
    await step("calcular regressão", calc_run(N, "regression", "Estimar"))
    await pause(2)
    await step("responder governo", mesa_use_and_answer(N, "governo"))
    await say("Acertou: +5 de moral para a nação.", "noe", 3.5)
    await say("Diplomacia: propõe um pacto de não agressão a Gáussia, assina a ordem e manda um telegrama.", "noe", 2)
    await step("pacto", point(N, N.locator("#pact-p-GAU")))
    await pause(0.8)
    await step("expedir governo", point(N, N.locator("#sec-governo .order__send")))
    await pause(2)
    await step("msg-to", N.locator("#msg-to").select_option("GAU"))
    await step("msg-text", type_in(N, N.locator("#msg-text"),
                                   "Propomos paz na fronteira oeste. Aceitem o pacto e mantemos a costa livre.", 35))
    await step("transmitir", point(N, N.locator('button:has-text("Transmitir telegrama")')))
    await pause(1.5)
    await say("Em Gáussia o telegrama chega na hora, datilografado na pilha de despachos.", "gau", 5)

    # ---------------- ordens das outras seções (fora da câmera), para a guerra andar
    for k in ("gau", "hil", "noe"):
        v = await api(k, "GET", "/api/faction/state")
        mv = pick_attack(v, FID[k])
        if mv:
            await api(k, "POST", "/api/faction/orders/operacoes", {"moves": [mv]})
    for k in ("eul", "hil", "noe"):
        v = await api(k, "GET", "/api/faction/state")
        c = v["faction"]["capacity"]
        await api(k, "POST", "/api/faction/orders/intendencia",
                  {"production": {"ALI": min(c["ALI"], 24), "ACO": min(c["ACO"], 8), "COM": min(c["COM"], 8)}, "recruit": 1})

    # ---------------- árbitro
    await say("7. O ÁRBITRO acompanha tudo: o relógio, quais seções de cada nação já mandaram ordem, o diário ao "
              "vivo e as manchetes.", "arbitro", 6)
    await say("Ele pode disparar um evento global (greve, colheita recorde, epidemia...)…", "arbitro", 1.5)
    await step("aba eventos", point(A, A.locator('.folder__tab[data-tab="eventos"]')))
    await pause(1.2)
    await step("disparar evento", point(A, A.locator("#event-list [data-event]").first))
    await pause(1)
    await step("confirmar evento", point(A, A.locator("#ask-ok")))
    await pause(2)
    await say("…e mandar um aviso para todas as salas.", "arbitro", 1)
    await step("aba avisos", point(A, A.locator('.folder__tab[data-tab="avisos"]')))
    await step("texto aviso", type_in(A, A.locator("#aviso-text"), "Atenção: faltam poucos minutos. Expeçam as ordens!", 30))
    await step("enviar aviso", point(A, A.locator("#aviso-send")))
    await pause(1)
    await say("O aviso aparece em todas as telas, inclusive no projetor.", "grid", 6)

    # ---------------- Inteligência (HIL): espera o telegrama-relâmpago (metade do turno)
    for _ in range(300):
        st = await api("hil", "GET", "/api/faction/state")
        if any(t.get("kind") == "flash" for t in st.get("telegrams", [])):
            break
        await asyncio.sleep(1)
    await say("8. INTELIGÊNCIA. Recebe telegramas inimigos interceptados, cifrados com a cifra de Hill (matrizes "
              "módulo 37). Na metade do turno chega o telegrama-relâmpago, com a ordem real que um inimigo acabou de dar.",
              "hil", 3)
    await H.evaluate("""() => {
      const ds = [...document.querySelectorAll('#sec-inteligencia details')]
        .filter(d => /Decifrar com a chave/i.test((d.querySelector('summary') || {}).textContent || ''));
      for (const d of ds) {
        let n = d;
        while (n.parentElement && n.parentElement.querySelectorAll('details').length <= 2) n = n.parentElement;
        if (/rel[âa]mpago/i.test(n.textContent)) { d.setAttribute('data-flash', '1'); return true; }
      }
      if (ds.length) ds[0].setAttribute('data-flash', '1');
      return false; }""")
    det = H.locator('#sec-inteligencia details[data-flash="1"]')
    await step("rolar telegramas", point(H, det, click=False))
    await pause(2)
    await say("Todo telegrama começa com «URGENTE ». Com esse trecho conhecido se descobre a chave (K = C·P⁻¹) e se "
              "lê a mensagem.", "hil", 2)
    await step("abrir decifrar", point(H, det.locator("summary")))
    await pause(1)
    await step("obter chave", point(H, det.locator('button:has-text("Obter chave pelo cabeçalho")')))
    await pause(1.5)
    await step("decifrar", point(H, det.locator('button:has-text("Decifrar")').last))
    await say("Mensagem decifrada: agora a nação sabe o que o inimigo vai fazer.", "hil", 6)
    await say("O desafio da Inteligência: quatro estações de escuta medem a distância até o depósito inimigo. "
              "Triangulação por mínimos quadrados.", "hil", 2)
    await step("abrir triangulação",
               point(H, H.locator('#sec-inteligencia button:has-text("Abrir na Mesa (triangulação)")').first))
    await pause(1.5)
    await step("triangular", calc_run(H, "trilaterate", "Triangular"))
    await pause(2.5)
    await step("responder inteligência", mesa_use_and_answer(H, "inteligencia"))
    await say("Depósito localizado: as tropas daquele território ficam visíveis e o bombardeio é liberado.", "hil", 3)
    await step("bombardear", point(H, H.locator("label:has(#bomb-yes), #bomb-yes").first))
    await pause(0.8)
    await step("confirmo", point(H, H.locator("#bomb-ok")))
    await step("expedir inteligência", point(H, H.locator("#sec-inteligencia .order__send")))
    await pause(3)

    # ---------------- resolução
    await say("9. Quando o prazo acaba, o turno se resolve sozinho para todas as nações ao mesmo tempo. Aqui, para "
              "encurtar, o árbitro aperta RESOLVER AGORA.", "arbitro", 2)
    await step("resolver", point(A, A.locator("#btn-resolve")))
    await pause(1)
    if await A.locator("#dlg-ask[open]").count():
        await step("confirmar resolver", point(A, A.locator("#ask-ok")))
    await say("No projetor, cada batalha é animada: a seta do ataque, as baixas e o carimbo de território tomado "
              "ou ataque repelido. Depois o jornal publica as manchetes.", "teatro", 24)
    await say("Em cada sala abre o Boletim do turno: o que foi produzido, recrutado, ganho e perdido, e por quê.",
              "gau", 7)
    await say("Começa o turno 2, com dossiês novos. O jogo segue assim, turno após turno.", "grid", 6)

    # ---------------- turno 2 (rápido) e fim
    for k in ("gau", "eul", "hil", "noe"):
        v = await api(k, "GET", "/api/faction/state")
        mv = pick_attack(v, FID[k])
        if mv:
            await api(k, "POST", "/api/faction/orders/operacoes", {"moves": [mv]})
    await say("Depois do último turno, a guerra termina.", "arbitro", 1)
    await step("resolver 2", point(A, A.locator("#btn-resolve")))
    await pause(1)
    if await A.locator("#dlg-ask[open]").count():
        await step("confirmar resolver 2", point(A, A.locator("#ask-ok")))
    await say("O último turno é resolvido: o projetor anima as batalhas finais e o jornal fecha a edição.", "teatro", 1)
    for _ in range(60):  # espera o Teatro terminar a animação e mostrar a tela de fim
        if await TE.evaluate("() => /FIM DA GUERRA/i.test(document.body.innerText)"):
            break
        await asyncio.sleep(0.5)
    await pause(1.5)
    await say("FIM DA GUERRA: o projetor mostra o pódio. Vence quem tiver mais pontos de vitória: "
              "1 por território, +2 pela capital e +0,25 por desafio resolvido.", "teatro", 13)
    await say("Resumo: o servidor guarda a partida e calcula tudo; cada sala decide e calcula com a Mesa de "
              "Cálculo; o projetor mostra a guerra; o árbitro controla o tempo.", "grid", 10)


# ----------------------------------------------------------------------------- main
async def main():
    global T0
    (WORK / "raw").mkdir(parents=True, exist_ok=True)
    (WORK / "dry").mkdir(parents=True, exist_ok=True)
    data = WORK / "data"
    data.mkdir(exist_ok=True)
    for f in data.glob("**/*.json"):
        f.unlink()
    env = dict(os.environ, DATA_DIR=str(data), ADMIN_PASSWORD="arbitro", N_FACTIONS="4", TURN_MINUTES="8", MAX_TURNS="2")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT / "server"), env=env, stdout=open(WORK / "server.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/api/server_time", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        async with async_playwright() as pw:
            launch = {"args": ["--autoplay-policy=no-user-gesture-required"]}
            if chrome_path():
                launch["executable_path"] = chrome_path()
            browser = await pw.chromium.launch(**launch)
            for name, (url, (w, h), _label) in SCREENS.items():
                kw = dict(viewport={"width": w, "height": h}, device_scale_factor=1, locale="pt-BR")
                if not DRY:
                    kw.update(record_video_dir=str(WORK / "raw" / name), record_video_size={"width": w, "height": h})
                ctx = await browser.new_context(**kw)
                await ctx.add_init_script(CURSOR_JS)
                page = await ctx.new_page()
                CREATED[name] = now()
                CTX[name], PAGES[name] = ctx, page
                await page.goto(BASE + url)
            await asyncio.sleep(2.5)
            T0 = now()
            await scenario()
            end = now() - T0
            await asyncio.sleep(1.5)
            videos = {}
            for name in SCREENS:
                vid = PAGES[name].video
                await CTX[name].close()
                if vid:
                    videos[name] = await vid.path()
            await browser.close()
        out = {
            "duration": round(end + 1.0, 2),
            "captions": TIMELINE,
            "offsets": {n: round(T0 - CREATED[n], 3) for n in SCREENS},
            "videos": videos,
            "labels": {n: SCREENS[n][2] for n in SCREENS},
            "errors": ERRORS,
        }
        (WORK / "timeline.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print("ERROS:", len(ERRORS))
        for e in ERRORS:
            print(" -", e)
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
