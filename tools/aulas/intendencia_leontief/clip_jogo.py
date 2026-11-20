"""Grava a cena "jogo" da aula da Intendência: resolver o desafio de Leontief e enviar a ordem, no ritmo da narração.

Uso: python tools/aulas/intendencia_leontief/clip_jogo.py <pasta_da_voz> <saida.mp4>
"""
import asyncio
import glob
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ritmo  # noqa: E402
from gravacao import CURSOR_JS, SENHA_ARBITRO, ate, cortar, point, post, servidor  # noqa: E402

VOZ, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
FID = "NOE"
W, H = 1366, 768


def resolver(dossie):
    """d do desafio e x = (I − A)⁻¹ d com A = Z·diag(X)⁻¹ da tabela do dossiê (o que a ferramenta faz)."""
    ds = next(x for x in dossie["datasets"] if x["id"] == "transacoes")
    Xr = next(r for r in ds["rows"] if r[0] == "X")
    Zr = [r for r in ds["rows"] if r is not Xr]
    Z = np.array([[float(v) for v in r[1:4]] for r in Zr])
    X = np.array([float(v) for v in Xr[1:4]])
    A = Z / X
    prompt = dossie["challenges"][0]["prompt"]
    d = [float(v) for v in re.search(r"\((\d+) ALI; (\d+) ACO; (\d+) COM\)", prompt).groups()]
    return d, np.linalg.solve(np.eye(3) - A, d)


async def main():
    dur = json.loads((VOZ / "duracoes.json").read_text())["jogo"]
    ini = ritmo.inicios(dur)
    total = ritmo.duracao_cena(dur)
    marca = lambda i, frac: ini[i] + dur[i] * frac  # noqa: E731
    with servidor(8812) as base:
        chrome = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
        async with async_playwright() as pw:
            b = await pw.chromium.launch(**({"executable_path": chrome[-1]} if chrome else {}))
            adm = await b.new_context()
            await post(adm, base, "/api/admin/login", {"password": SENHA_ARBITRO})
            await post(adm, base, "/api/admin/new_game", {"n_factions": 4, "turn_minutes": 12, "max_turns": 8, "seed": 7})
            await post(adm, base, "/api/admin/start", {})
            senha = (await (await adm.request.get(base + "/api/admin/credentials")).json())[FID]
            ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir=tempfile.mkdtemp(prefix="clip_int_"),
                                      record_video_size={"width": W, "height": H}, locale="pt-BR")
            await ctx.add_init_script(CURSOR_JS)
            await ctx.add_init_script(f"try {{ localStorage.setItem('em_qg_briefing_visto_{FID}', '1'); }} catch (e) {{}}")
            await post(ctx, base, "/api/login", {"faction_id": FID, "password": senha})
            dossie = await (await ctx.request.get(base + "/api/faction/dossier/intendencia")).json()
            d, x = resolver(dossie)
            page = await ctx.new_page()
            criado = time.monotonic()
            await page.goto(base + "/qg#intendencia")
            await page.wait_for_selector("body[data-status=ready]", timeout=15000)
            await asyncio.sleep(1.5)
            sec = page.locator("#sec-intendencia")
            t0 = time.monotonic()
            # fala 0: a tabela de transações e o desafio
            await ate(t0, ini[0] + 0.3)
            await point(page, sec.locator("table.ledger").first, click=False)
            await ate(t0, marca(0, 0.6))
            await point(page, sec.locator(".chal__input").first, click=False)
            # fala 1: abrir na Mesa, digitar d, calcular
            await ate(t0, ini[1] + 0.2)
            await point(page, sec.locator('button:has-text("Abrir na Mesa de Cálculo")').first)
            await asyncio.sleep(0.8)
            panel = page.locator('#calc-drawer [data-tool="leontief"]')
            for i, v in enumerate(d):
                await ate(t0, marca(1, 0.45 + 0.1 * i))
                cel = panel.locator(f'[aria-label="d (demanda final), linha {i + 1}, coluna 1"]')
                await point(page, cel, steps=10)
                await cel.fill(str(int(v)))
            await ate(t0, marca(1, 0.85))
            await point(page, panel.locator('button.calc-run:has-text("Calcular")').first)
            # fala 2: usar no questionário e enviar
            await ate(t0, ini[2] + 0.3)
            await point(page, page.locator('#calc-drawer button:has-text("usar no questionário")').first)
            await ate(t0, marca(2, 0.45))
            for _ in range(3):
                await point(page, sec.locator(".chal__send").first)
                await asyncio.sleep(1.2)
                dd = await (await ctx.request.get(base + "/api/faction/dossier/intendencia")).json()
                if all(c.get("solved") for c in dd.get("challenges", [])):
                    break
            else:
                raise RuntimeError("o desafio da Intendência não foi resolvido na gravação")
            # fala 3: a ordem — produção x, recrutamento, assinar e carimbar
            await ate(t0, ini[3])
            if await page.locator("#calc-drawer .calc-handle__btn[aria-expanded=true]").count():
                await point(page, page.locator(".calc-handle__btn"))
            for i, s in enumerate(("ALI", "ACO", "COM")):
                await ate(t0, marca(3, 0.12 + 0.12 * i))
                campo = page.locator(f"#int-x-{s}")
                await point(page, campo, steps=12)
                await campo.fill(f"{x[i]:.1f}")
            await ate(t0, marca(3, 0.55))
            await point(page, page.locator("#int-rec"), steps=12)
            await page.locator("#int-rec").fill("2")
            await ate(t0, marca(3, 0.78))
            await point(page, sec.locator(".order__send").first)
            await ate(t0, total + 0.3)
            off = t0 - criado
            vid = page.video
            await ctx.close()
            bruto = await vid.path()
            await b.close()
    cortar(bruto, SAIDA, off, total)
    print("clipe:", SAIDA, f"{total:.2f} s")


if __name__ == "__main__":
    asyncio.run(main())
