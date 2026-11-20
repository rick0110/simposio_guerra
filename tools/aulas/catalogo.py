"""Gera web/videos/index.json (o catálogo que o QG lê) a partir dos vídeos que existem em web/videos.

Uso (raiz do repositório):  python tools/aulas/catalogo.py
Nomes esperados: <seção>-*.mp4 (ver SECOES) e briefing-<NAÇÃO>.mp4 (partida de 4 nações).
"""
import json
import subprocess
from pathlib import Path

V = Path(__file__).resolve().parents[2] / "web" / "videos"
SECOES = [("intendencia", "intendencia-leontief.mp4", "Intendência · O modelo de Leontief"),
          ("operacoes", "operacoes-markov-lanchester.mp4", "Operações · Markov e Lanchester"),
          ("inteligencia", "inteligencia-hill-mmq.mp4", "Inteligência · Cifra de Hill e mínimos quadrados"),
          ("governo", "governo-regressao.mp4", "Governo · Regressão linear")]
NACOES = {"GAU": "República de Gáussia", "EUL": "Império de Eulerândia", "HIL": "Federação de Hilbertânia",
          "NOE": "Reino de Noethéria", "CAU": "Principado de Cauchýria", "RIE": "Confederação de Riemânnia"}


def duracao(p):
    s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                             capture_output=True, text=True, check=True).stdout)
    return f"{int(s // 60)}:{int(s % 60):02d}"


def main():
    cat = {"secoes": {}, "briefing": {"4": {}}}
    for sec, arq, tit in SECOES:
        if (V / arq).exists():
            cat["secoes"][sec] = {"arquivo": arq, "titulo": tit, "duracao": duracao(V / arq)}
    for fid, nome in NACOES.items():
        arq = f"briefing-{fid}.mp4"
        if (V / arq).exists():
            cat["briefing"]["4"][fid] = {"arquivo": arq, "titulo": f"Briefing · {nome}", "duracao": duracao(V / arq)}
    (V / "index.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cat['secoes'])} instruções de seção, {len(cat['briefing']['4'])} briefings")


if __name__ == "__main__":
    main()
