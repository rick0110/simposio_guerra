"""Monta o vídeo final de uma aula: cenas (Manim + clipe do jogo), narração, trilha e mixagem.

Uso:
  python tools/aulas/montar.py <pasta_do_roteiro> <pasta_da_voz> <pasta_das_cenas> <clipe_jogo.mp4> <saida.mp4>

<pasta_das_cenas> contém um .mp4 por cena do Manim (nome da classe). A ordem e o mapeamento
cena -> classe estão em SEQUENCIA (o clipe do jogo entra no lugar de "jogo").
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ritmo  # noqa: E402

SR = 48000
FUNDO = "0x1c241e"
FONTE = str(Path.home() / ".local/share/fonts/estado-maior/ibm-plex-sans-condensed-700.ttf")

# (classe do Manim ou "JOGO", cena do roteiro com narração ou None). Um roteiro pode trazer a própria
# SEQUENCIA e o CLIPE_ROTULO (texto acima do clipe do jogo).
SEQUENCIA_PADRAO = [("Titulo", None), ("Abertura", "abertura"), ("Dados", "dados"), ("Reta", "reta"),
             ("Leitura", "leitura"), ("Plano", "plano"), ("Matriz", "matriz"), ("Projecao", "projecao"),
             ("Decisao", "decisao"), ("JOGO", "jogo"), ("Fim", "fim"), ("Creditos", None)]


def dur_video(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ler_wav(p):
    """Lê um .wav (via ffmpeg) já reamostrado para SR, mono, float32."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trilha(n, seed=1943):
    """Trilha ambiente sintetizada: acordes lentos (Lá menor, Fá, Dó, Sol), graves suaves e um eco leve."""
    t = np.arange(n) / SR
    acordes = [[57, 60, 64], [53, 57, 60], [48, 55, 60, 64], [55, 59, 62]]   # MIDI
    dur_acorde = 7.5
    out = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(seed)
    hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
    k = 0
    inicio = 0.0
    while inicio < n / SR:
        notas = acordes[k % len(acordes)]
        a, b = int(inicio * SR), min(n, int((inicio + dur_acorde + 3.0) * SR))
        tt = t[a:b] - inicio
        env = np.minimum(1, tt / 2.5) * np.clip((dur_acorde + 3.0 - tt) / 3.0, 0, 1)
        som = np.zeros_like(tt)
        for m in notas:
            f = hz(m)
            for det in (-0.12, 0.0, 0.13):           # leve desafinação: som "cheio"
                som += np.sin(2 * np.pi * f * (1 + det / 100) * tt + rng.uniform(0, 6.28)) / 3
        grave = 0.8 * np.sin(2 * np.pi * hz(notas[0] - 12) * tt)
        out[a:b] += (som / len(notas) + grave * 0.6) * env
        inicio += dur_acorde
        k += 1
    # passa-baixa suave no domínio da frequência (som "abafado", de fundo) e eco
    espectro = np.fft.rfft(out)
    f = np.fft.rfftfreq(n, 1 / SR)
    y = np.fft.irfft(espectro / np.sqrt(1 + (f / 1500.0) ** 4), n)
    for atraso, g in ((0.29, 0.35), (0.61, 0.22), (1.1, 0.12)):
        d = int(atraso * SR)
        y[d:] += g * y[:-d]
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def carregar_roteiro(pasta):
    spec = importlib.util.spec_from_file_location("roteiro", pasta / "roteiro.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    roteiro_dir, voz, cenas_dir, clipe, saida = map(Path, sys.argv[1:6])
    roteiro = carregar_roteiro(roteiro_dir)
    sequencia = getattr(roteiro, "SEQUENCIA", SEQUENCIA_PADRAO)
    rotulo = getattr(roteiro, "CLIPE_ROTULO", "NO JOGO · ABA GOVERNO")
    dur = json.loads((voz / "duracoes.json").read_text())
    work = Path(tempfile.mkdtemp(prefix="montar_"))

    # 1. vídeo de cada bloco, na ordem
    blocos = []
    for classe, cena in sequencia:
        if classe == "JOGO":
            p = work / "jogo.mp4"
            filtro = (f"color=c={FUNDO}:s=1920x1080:r=30:d={dur_video(clipe):.3f}[bg];"
                      f"[0:v]scale=1600:900,setsar=1[c];[bg][c]overlay=160:140,"
                      f"drawtext=fontfile='{FONTE}':text='{rotulo}':fontcolor=0xb08d3c:fontsize=34:"
                      f"x=(w-text_w)/2:y=62,drawbox=x=158:y=138:w=1604:h=904:color=0xb08d3c@0.8:t=2,"
                      f"fade=t=in:st=0:d=0.5,fade=t=out:st={dur_video(clipe) - 0.6:.3f}:d=0.6,format=yuv420p")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clipe), "-filter_complex", filtro,
                            "-r", "30", "-c:v", "libx264", "-crf", "18", "-an", str(p)], check=True)
        else:
            p = next(cenas_dir.rglob(f"{classe}.mp4"))
        blocos.append((p, cena, dur_video(p)))

    # 2. narração posicionada no instante exato de cada fala
    total = sum(d for _, _, d in blocos)
    n = int(total * SR) + SR
    voz_trilha = np.zeros(n, dtype=np.float32)
    t0 = 0.0
    for p, cena, d in blocos:
        if cena:
            for i, ini in enumerate(ritmo.inicios(dur[cena])):
                w = ler_wav(voz / f"{cena}_{i:02d}.wav")
                a = int((t0 + ini) * SR)
                voz_trilha[a:a + len(w)] += w[: max(0, n - a)]
        t0 += d

    # 3. trilha com "ducking": baixa quando há voz
    mus = trilha(n)
    env = np.abs(voz_trilha)
    janela = int(0.35 * SR)
    env = np.convolve(env, np.ones(janela) / janela, mode="same")
    fala = np.clip(env / (env.max() * 0.08 + 1e-9), 0, 1)
    ganho = 0.16 - 0.11 * fala                     # 0,16 sem voz; 0,05 com voz
    mix = voz_trilha / (np.max(np.abs(voz_trilha)) + 1e-9) * 0.9 + mus * ganho
    (work / "mix.f32").write_bytes(mix.astype(np.float32).tobytes())

    # 4. junta vídeos + áudio, normaliza volume (padrão de internet: −16 LUFS)
    lista = work / "lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p, _, _ in blocos))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(work / "mix.f32"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ac", "2",
                    "-shortest", "-movflags", "+faststart", str(saida)], check=True)
    print(f"pronto: {saida} ({total / 60:.1f} min)")


if __name__ == "__main__":
    main()
