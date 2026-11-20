"""Gravação de telas do jogo para as aulas (Playwright): servidor temporário, cursor visível e sincronia.

    with servidor() as base:            # sobe o servidor do jogo numa pasta de dados temporária
        ...                             # partida nova, login, gravação
"""
import asyncio
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SENHA_ARBITRO = "arbitro"

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


@contextlib.contextmanager
def servidor(port=8811):
    work = Path(tempfile.mkdtemp(prefix="grav_"))
    env = dict(os.environ, DATA_DIR=str(work / "data"), ADMIN_PASSWORD=SENHA_ARBITRO)
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
                           cwd=RAIZ / "server", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/api/server_time", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        yield base
    finally:
        srv.terminate()
        srv.wait(timeout=10)


def post(ctx, base, path, data):
    return ctx.request.post(base + path, data=json.dumps(data), headers={"Content-Type": "application/json"})


async def point(page, loc, click=True, steps=22):
    """Leva o cursor (visível no vídeo) até o elemento, com rolagem suave, e clica se pedido."""
    await loc.wait_for(state="visible", timeout=10000)
    await loc.evaluate("e => e.scrollIntoView({block: 'center', behavior: 'smooth'})")
    prev = box = None
    for _ in range(40):
        await asyncio.sleep(0.1)
        box = await loc.bounding_box()
        if box and prev and abs(box["y"] - prev["y"]) < 0.5:
            break
        prev = box
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y, steps=steps)
    await asyncio.sleep(0.3)
    b2 = await loc.bounding_box()      # a página pode ter se mexido: confere x e y
    if b2:
        x2, y2 = b2["x"] + b2["width"] / 2, b2["y"] + b2["height"] / 2
        if abs(x2 - x) > 2 or abs(y2 - y) > 2:
            x, y = x2, y2
            await page.mouse.move(x, y, steps=8)
            await asyncio.sleep(0.2)
    if click:
        await page.mouse.click(x, y)


async def ate(t0, t):
    """Espera até o instante t (s) da cena, contado de t0 (time.monotonic())."""
    falta = t - (time.monotonic() - t0)
    if falta > 0:
        await asyncio.sleep(falta)
    elif falta < -0.3:
        print(f"   [atraso] gravação {-falta:.2f} s depois do previsto", flush=True)


def cortar(bruto, saida, inicio, duracao):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-i", str(bruto), "-t", f"{duracao:.3f}",
                    "-r", "30", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(saida)], check=True)
