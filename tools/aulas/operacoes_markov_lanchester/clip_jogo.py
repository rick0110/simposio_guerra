"""Grava a cena "jogo" da aula de Operações: desafio de Markov e uma ordem de ataque pelo mapa.

Uso: python tools/aulas/operacoes_markov_lanchester/clip_jogo.py <pasta_da_voz> <saida.mp4>
"""
import asyncio
import glob
import json
import sys
import tempfile
import time
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ritmo  # noqa: E402
from gravacao import CURSOR_JS, SENHA_ARBITRO, ate, cortar, point, post, servidor  # noqa: E402
from jogo_dados import mapa_json, nacao  # noqa: E402

VOZ, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
FID = "NOE"
W, H = 1366, 768


def alvo():
    """(origem, destino): o território da nação com um vizinho neutro por terra (a capital, se der)."""
    D = nacao(FID, 4)
    T = {t["id"]: t for t in mapa_json()["territories"]}
    neutros = {v["id"] for v in D["neutros_vizinhos"]}
    meus = sorted((t["id"] for t in D["territorios"]), key=lambda t: t != D["capital_tid"])
    for t in meus:
        for v in T[t]["neighbors"]:
            if v in neutros:
                return t, v
    raise RuntimeError("sem vizinho neutro por terra")


async def clicar_territorio(page, tid):
    """Leva o cursor até o território na carta e dispara o clique nele (o centro da caixa pode cair fora do polígono)."""
    hit = page.locator(f'#sec-operacoes path.hit[data-id="{tid}"]')
    box = await hit.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y, steps=20)
    await asyncio.sleep(0.25)
    await hit.dispatch_event("click", {"clientX": x, "clientY": y, "bubbles": True})


async def main():
    dur = json.loads((VOZ / "duracoes.json").read_text())["jogo"]
    ini = ritmo.inicios(dur)
    total = ritmo.duracao_cena(dur)
    marca = lambda i, frac: ini[i] + dur[i] * frac  # noqa: E731
    origem, destino = alvo()
    with servidor(8813) as base:
        chrome = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
        async with async_playwright() as pw:
            b = await pw.chromium.launch(**({"executable_path": chrome[-1]} if chrome else {}))
            adm = await b.new_context()
            await post(adm, base, "/api/admin/login", {"password": SENHA_ARBITRO})
            await post(adm, base, "/api/admin/new_game", {"n_factions": 4, "turn_minutes": 12, "max_turns": 8, "seed": 7})
            await post(adm, base, "/api/admin/start", {})
            senha = (await (await adm.request.get(base + "/api/admin/credentials")).json())[FID]
            ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir=tempfile.mkdtemp(prefix="clip_ops_"),
                                      record_video_size={"width": W, "height": H}, locale="pt-BR")
            await ctx.add_init_script(CURSOR_JS)
            await ctx.add_init_script(f"try {{ localStorage.setItem('em_qg_briefing_visto_{FID}', '1'); }} catch (e) {{}}")
            await post(ctx, base, "/api/login", {"faction_id": FID, "password": senha})
            page = await ctx.new_page()
            criado = time.monotonic()
            await page.goto(base + "/qg#operacoes")
            await page.wait_for_selector("body[data-status=ready]", timeout=15000)
            await asyncio.sleep(1.5)
            sec = page.locator("#sec-operacoes")
            t0 = time.monotonic()
            # fala 0: o desafio e o botão do diário
            await ate(t0, ini[0] + 0.3)
            await point(page, sec.locator(".chal__input").first, click=False)
            await ate(t0, marca(0, 0.55))
            await point(page, sec.locator('select[aria-label="Região do diário meteorológico"]').first, click=False)
            await ate(t0, marca(0, 0.8))
            await point(page, sec.locator('button:has-text("Abrir na Mesa (Markov)")').first)
            # fala 1: a ferramenta Markov
            panel = page.locator('#calc-drawer [data-tool="markov"]')
            await ate(t0, ini[1] + 0.3)
            await point(page, panel.locator("textarea").first, click=False)
            await ate(t0, marca(1, 0.45))
            await point(page, panel.locator('select[aria-label="estado atual"]').first, click=False)
            await ate(t0, marca(1, 0.7))
            await point(page, panel.locator('button.calc-run:has-text("Calcular")').first)
            # fala 2: usar no questionário e enviar
            await ate(t0, ini[2] + 0.2)
            await point(page, page.locator('#calc-drawer button:has-text("usar no questionário")').first)
            await ate(t0, marca(2, 0.5))
            for _ in range(3):
                await point(page, sec.locator(".chal__send").first)
                await asyncio.sleep(1.2)
                dd = await (await ctx.request.get(base + "/api/faction/dossier/operacoes")).json()
                if all(c.get("solved") for c in dd.get("challenges", [])):
                    break
            else:
                raise RuntimeError("o desafio de Operações não foi resolvido na gravação")
            # fala 3: a ordem de ataque pelo mapa
            await ate(t0, ini[3])
            if await page.locator("#calc-drawer .calc-handle__btn[aria-expanded=true]").count():
                await point(page, page.locator(".calc-handle__btn"))
            await point(page, sec.locator(".mapwrap").first, click=False)
            await ate(t0, marca(3, 0.12))
            await clicar_territorio(page, origem)
            await ate(t0, marca(3, 0.25))
            await clicar_territorio(page, destino)
            await asyncio.sleep(0.6)
            num = sec.locator('.pop input[aria-label="Batalhões"]')
            await ate(t0, marca(3, 0.4))
            await point(page, num, steps=10)
            await num.fill("4")
            await num.dispatch_event("input")
            await ate(t0, marca(3, 0.5))
            await point(page, sec.locator('.pop button:has-text("Lançar ordem")'))
            await ate(t0, marca(3, 0.65))
            await point(page, sec.locator(".move").first, click=False)
            await ate(t0, marca(3, 0.85))
            await point(page, sec.locator(".order__send").first)
            await ate(t0, total + 0.3)
            off = t0 - criado
            vid = page.video
            await ctx.close()
            bruto = await vid.path()
            await b.close()
    cortar(bruto, SAIDA, off, total)
    print("clipe:", SAIDA, f"{total:.2f} s", "ordem:", origem, "->", destino)


if __name__ == "__main__":
    asyncio.run(main())
