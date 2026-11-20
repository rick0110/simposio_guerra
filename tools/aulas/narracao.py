"""Gera a narração de um roteiro com o Kokoro (voz pm_santa): um .wav por fala + duracoes.json.

Uso:  python tools/aulas/narracao.py <pasta_do_roteiro> <pasta_de_saida> [--speed 0.95]
Ex.:  python tools/aulas/narracao.py tools/aulas/governo_regressao /tmp/governo

Requisitos (Python 3.12; o Kokoro ainda não instala no 3.13):
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install kokoro soundfile
    apt-get install espeak-ng          # fonemas do português
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

ESPEAK_LIB = "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"
ESPEAK_DATA = "/usr/lib/x86_64-linux-gnu/espeak-ng-data"


def _espeak_do_sistema():
    """O pacote espeakng-loader aponta para uma pasta que não existe; usa o espeak-ng do sistema."""
    import espeakng_loader
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    EspeakWrapper.set_library(ESPEAK_LIB)
    EspeakWrapper.set_data_path(ESPEAK_DATA)
    espeakng_loader.get_library_path = lambda: ESPEAK_LIB
    espeakng_loader.get_data_path = lambda: ESPEAK_DATA


def main():
    roteiro_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    speed = float(sys.argv[sys.argv.index("--speed") + 1]) if "--speed" in sys.argv else 0.95
    spec = importlib.util.spec_from_file_location("roteiro", roteiro_dir / "roteiro.py")
    roteiro = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(roteiro)

    os.environ.setdefault("ESPEAK_DATA_PATH", ESPEAK_DATA)
    _espeak_do_sistema()
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")
    out.mkdir(parents=True, exist_ok=True)
    duracoes, fonemas = {}, []
    for cena, falas in roteiro.CENAS:
        duracoes[cena] = []
        for i, texto in enumerate(falas):
            partes, ps = [], []
            for r in pipe(texto, voice="pm_santa", speed=speed):
                partes.append(r.audio.numpy())
                ps.append(r.phonemes)
            audio = np.concatenate(partes)
            nome = out / f"{cena}_{i:02d}.wav"
            sf.write(nome, audio, 24000)
            duracoes[cena].append(round(len(audio) / 24000, 3))
            fonemas.append(f"[{cena} {i}] {texto}\n    {' | '.join(ps)}")
            print(f"{cena} {i}: {duracoes[cena][-1]:.2f} s", flush=True)
    (out / "duracoes.json").write_text(json.dumps(duracoes, indent=1))
    (out / "fonemas.txt").write_text("\n".join(fonemas), encoding="utf-8")
    total = sum(sum(v) for v in duracoes.values())
    print(f"total de fala: {total / 60:.1f} min")


if __name__ == "__main__":
    main()
