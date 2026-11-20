"""Grava a cena "jogo" do briefing: um passeio pelo QG da nação, no ritmo da narração.

Uso: NACAO=NOE N_NACOES=4 python tools/aulas/briefing/clip_jogo.py <pasta_da_voz> <saida.mp4>
"""
import asyncio
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ritmo  # noqa: E402
from gravacao import CURSOR_JS, SENHA_ARBITRO, ate, cortar, point, post, servidor  # noqa: E402

VOZ, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
FID = os.environ.get("NACAO", "NOE")
N = int(os.environ.get("N_NACOES", "4"))
W, H = 1366, 768

# na gravação, o catálogo mostra todos os botões de vídeo (os arquivos podem ainda não existir)
CATALOGO = {
    "secoes": {s: {"arquivo": f"{s}.mp4", "titulo": s.capitalize(), "duracao": "6:00"}
               for s in ("intendencia", "operacoes", "inteligencia", "governo")},
    "briefing": {str(N): {FID: {"arquivo": "briefing.mp4", "titulo": "Briefing", "duracao": "5:00"}}},
}


async def main():
    dur = json.loads((VOZ / "duracoes.json").read_text())["jogo"]
    ini = ritmo.inicios(dur)
    total = ritmo.duracao_cena(dur)
    marca = lambda i, frac: ini[i] + dur[i] * frac  # noqa: E731
    with servidor() as base:
        chrome = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
        async with async_playwright() as pw:
            b = await pw.chromium.launch(**({"executable_path": chrome[-1]} if chrome else {}))
            adm = await b.new_context()
            await post(adm, base, "/api/admin/login", {"password": SENHA_ARBITRO})
            await post(adm, base, "/api/admin/new_game", {"n_factions": N, "turn_minutes": 12, "max_turns": 8, "seed": 7})
            await post(adm, base, "/api/admin/start", {})
            senha = (await (await adm.request.get(base + "/api/admin/credentials")).json())[FID]
            work = Path(tempfile.mkdtemp(prefix=f"clip_briefing_{FID}_"))
            ctx = await b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(work),
                                      record_video_size={"width": W, "height": H}, locale="pt-BR")
            await ctx.add_init_script(CURSOR_JS)
            # o briefing "já foi visto": sem o telegrama de boas-vindas cobrindo a tela
            await ctx.add_init_script(f"try {{ localStorage.setItem('em_qg_briefing_visto_{FID}', '1'); }} catch (e) {{}}")
            await ctx.route("**/videos/index.json", lambda r: r.fulfill(
                status=200, content_type="application/json", body=json.dumps(CATALOGO)))
            await post(ctx, base, "/api/login", {"faction_id": FID, "password": senha})
            page = await ctx.new_page()
            criado = time.monotonic()
            await page.goto(base + "/qg#intendencia")
            await page.wait_for_selector("body[data-status=ready]", timeout=15000)
            await asyncio.sleep(1.5)
            t0 = time.monotonic()
            # fala 0: o timbre — estoques, tropas, PV, territórios
            await ate(t0, ini[0] + 0.4)
            tags = page.locator("#ledger .tag")
            k = await tags.count()
            for i in range(k):
                await ate(t0, marca(0, 0.22 + 0.7 * i / max(1, k - 1)))
                await point(page, tags.nth(i), click=False, steps=12)
            # fala 1: moral e relógio
            await ate(t0, ini[1] + 0.2)
            await point(page, page.locator("#moral"), click=False)
            await ate(t0, marca(1, 0.45))
            await point(page, page.locator("#clock"), click=False)
            # fala 2: a pasta — dossiê, tabelas, desafio, ordem
            await ate(t0, ini[2] + 0.2)
            await point(page, page.locator("#tab-intendencia"))
            await ate(t0, marca(2, 0.35))
            await point(page, page.locator("#sec-intendencia table.ledger").first, click=False)
            await ate(t0, marca(2, 0.6))
            await point(page, page.locator("#sec-intendencia .chal__input").first, click=False)
            await ate(t0, marca(2, 0.8))
            await point(page, page.locator("#sec-intendencia .order__send").first, click=False)
            # fala 3: Operações — o mapa com névoa de guerra
            await ate(t0, ini[3])
            await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            await asyncio.sleep(0.5)
            await point(page, page.locator("#tab-operacoes"))
            await asyncio.sleep(0.4)
            await point(page, page.locator("#sec-operacoes .mapwrap").first, click=False)
            await page.mouse.move(W * 0.62, H * 0.45, steps=30)
            # fala 4: a Mesa de Cálculo
            await ate(t0, ini[4])
            await point(page, page.locator(".calc-handle__btn"))
            for i, tool in enumerate(("leontief", "lanchester", "hill", "regression")):
                await ate(t0, marca(4, 0.3 + 0.16 * i))
                await point(page, page.locator(f'.calc-index__tab[data-tool="{tool}"]'), steps=14)
            await ate(t0, marca(4, 0.97))
            await point(page, page.locator(".calc-handle__btn"))
            # fala 5: o botão de instrução em vídeo e o de briefing
            await ate(t0, ini[5])
            await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            await asyncio.sleep(0.5)
            await point(page, page.locator("#tab-governo"))
            await asyncio.sleep(0.3)
            await point(page, page.locator("#b-instrucao"), click=False)
            await ate(t0, marca(5, 0.72))
            await point(page, page.locator("#b-briefing"), click=False)
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
