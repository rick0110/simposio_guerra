"""Grava a cena "jogo": a aba Governo resolvendo o desafio de regressão, no ritmo da narração.

Uso: python tools/aulas/governo_regressao/clip_jogo.py <pasta_da_voz> <saida.mp4>
(<pasta_da_voz> é a saída de narracao.py, com duracoes.json)
"""
import asyncio
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "aulas"))
import ritmo  # noqa: E402

VOZ, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
PORT = 8810
BASE = f"http://127.0.0.1:{PORT}"
W, H = 1366, 768

CURSOR_JS = r"""(() => { const mk = () => { if (document.getElementById('__cur')) return;
  const c = document.createElement('div'); c.id = '__cur';
  c.style.cssText = 'position:fixed;left:-60px;top:-60px;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;' +
    'background:rgba(230,40,30,.45);border:3px solid #fff;box-shadow:0 0 0 3px rgba(200,30,20,.9),0 2px 8px rgba(0,0,0,.6);' +
    'z-index:2147483647;pointer-events:none;transition:transform .12s ease-out';
  document.documentElement.appendChild(c);
  addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => { c.style.transform = 'scale(1.9)'; }, true);
  addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; }, true); };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', mk); else mk(); })();"""


async def point(page, loc, click=True, steps=22):
    await loc.wait_for(state="visible", timeout=10000)
    await loc.evaluate("e => e.scrollIntoView({block: 'center', behavior: 'smooth'})")
    prev = None
    for _ in range(40):
        await asyncio.sleep(0.1)
        box = await loc.bounding_box()
        if box and prev and abs(box["y"] - prev["y"]) < 0.5:
            break
        prev = box
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y, steps=steps)
    await asyncio.sleep(0.3)
    b2 = await loc.bounding_box()  # a página pode ter se mexido (gaveta fechando): confere x e y
    if b2:
        x2, y2 = b2["x"] + b2["width"] / 2, b2["y"] + b2["height"] / 2
        if abs(x2 - x) > 2 or abs(y2 - y) > 2:
            x, y = x2, y2
            await page.mouse.move(x, y, steps=8)
            await asyncio.sleep(0.2)
    if click:
        await page.mouse.click(x, y)


async def ate(t0, t):
    """Espera até o instante t (s) da cena."""
    falta = t - (time.monotonic() - t0)
    if falta > 0:
        await asyncio.sleep(falta)


async def main():
    dur = json.loads((VOZ / "duracoes.json").read_text())["jogo"]
    ini = ritmo.inicios(dur)
    total = ritmo.duracao_cena(dur)
    work = Path(tempfile.mkdtemp(prefix="clip_gov_"))
    env = dict(os.environ, DATA_DIR=str(work / "data"), ADMIN_PASSWORD="arbitro")
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
                           cwd=ROOT / "server", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/api/server_time", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        chrome = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
        async with async_playwright() as pw:
            b = await pw.chromium.launch(**({"executable_path": chrome[-1]} if chrome else {}))
            adm = await b.new_context()
            post = lambda c, p, d: c.request.post(BASE + p, data=json.dumps(d), headers={"Content-Type": "application/json"})
            await post(adm, "/api/admin/login", {"password": "arbitro"})
            await post(adm, "/api/admin/new_game", {"n_factions": 4, "turn_minutes": 12, "max_turns": 8, "seed": 7})
            await post(adm, "/api/admin/start", {})
            senha = (await (await adm.request.get(BASE + "/api/admin/credentials")).json())["NOE"]
            ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(work / "v"),
                                      record_video_size={"width": W, "height": H}, locale="pt-BR")
            await ctx.add_init_script(CURSOR_JS)
            await post(ctx, "/api/login", {"faction_id": "NOE", "password": senha})
            page = await ctx.new_page()
            criado = time.monotonic()
            await page.goto(BASE + "/qg#governo")
            await page.wait_for_selector("#sec-governo .ds", timeout=15000)
            await asyncio.sleep(2.0)
            t0 = time.monotonic()
            # fala 0: o dossiê com a pesquisa de opinião
            await ate(t0, ini[0])
            await point(page, page.locator("#sec-governo .ds").filter(has_text="pesquisa").first, click=False)
            await page.mouse.wheel(0, 260)
            # fala 1: abrir na Mesa e estimar
            await ate(t0, ini[1] + 0.8)
            await point(page, page.locator('#sec-governo button:has-text("Abrir na Mesa (regressão)")').first)
            await ate(t0, ini[1] + 5.2)
            await point(page, page.locator('#calc-drawer [data-tool="regression"] button.calc-run:has-text("Estimar")').first)
            # fala 2: usar no questionário e enviar
            await ate(t0, ini[2] + 2.2)
            await point(page, page.locator('#calc-drawer button:has-text("usar no questionário")').first)
            await ate(t0, ini[2] + 5.0)
            for _ in range(3):  # envia e confere no servidor que o desafio foi resolvido
                await point(page, page.locator("#sec-governo .chal__send").first)
                await asyncio.sleep(1.5)
                d = await (await ctx.request.get(BASE + "/api/faction/dossier/governo")).json()
                if all(c.get("solved") for c in d.get("challenges", [])):
                    break
            else:
                raise RuntimeError("o desafio do Governo não foi resolvido na gravação")
            # fala 3: a decisão de propaganda
            await ate(t0, ini[3] + 4.5)
            await point(page, page.locator("#gov-prop"), click=False)
            await ate(t0, total + 0.3)
            off = t0 - criado
            vid = page.video
            await ctx.close()
            raw = await vid.path()
            await b.close()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{off:.3f}", "-i", raw, "-t", f"{total:.3f}",
                        "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(SAIDA)], check=True)
        print("clipe:", SAIDA, f"{total:.2f} s")
    finally:
        srv.terminate()
        srv.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
