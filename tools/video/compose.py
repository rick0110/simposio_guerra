"""Monta o vídeo final a partir das 6 gravações e da linha do tempo de director.py.

Uso (a partir da raiz do repositório):
    python tools/video/compose.py <pasta_de_trabalho> <saida.mp4>
Precisa de ffmpeg (com libass) e fontTools + brotli (converte as fontes do jogo para as legendas).

Layout 1920×1080:
- modo "foco": a tela em destaque grande (1440×810) e, à direita, as 6 telas pequenas (a em destaque com moldura);
- modo "grade": as 6 telas lado a lado (3×2);
- faixa inferior (1920×270): a legenda que explica o passo.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
TL = json.loads((WORK / "timeline.json").read_text())
ORDER = ["arbitro", "teatro", "gau", "eul", "hil", "noe"]
FPS = 25
DUR = TL["duration"]
CAPS = TL["captions"]

BIG = (1440, 810)
TH = (236, 133)
TILE = (640, 360)
THUMB_POS = {n: (1440 + 2 + (i % 2) * 240, 30 + (i // 2) * (133 + 32)) for i, n in enumerate(ORDER)}
GRID_POS = {n: ((i % 3) * 640, 30 + (i // 3) * (360 + 32)) for i, n in enumerate(ORDER)}

intervals = []
for i, c in enumerate(CAPS):
    b = CAPS[i + 1]["t"] if i + 1 < len(CAPS) else DUR
    intervals.append((c["t"], b, c["focus"], c["text"]))

SHORT = {"arbitro": "ÁRBITRO", "teatro": "PROJETOR · TEATRO", "gau": "SALA 1 · GÁUSSIA · INTENDÊNCIA",
         "eul": "SALA 2 · EULERÂNDIA · OPERAÇÕES", "hil": "SALA 3 · HILBERTÂNIA · INTELIGÊNCIA",
         "noe": "SALA 4 · NOETHÉRIA · GOVERNO"}
SHORT_T = {"arbitro": "Árbitro", "teatro": "Projetor", "gau": "Sala 1 · Intendência",
           "eul": "Sala 2 · Operações", "hil": "Sala 3 · Inteligência", "noe": "Sala 4 · Governo"}


def enable(pred):
    parts = [f"between(t,{a:.2f},{b:.2f})" for a, b, f, _ in intervals if pred(f)]
    return "+".join(parts) if parts else "0"


def fonts_dir():
    """Converte as fontes do jogo (woff2) em TTF, que o gerador de legendas (libass) lê."""
    from fontTools.merge import Merger
    from fontTools.ttLib import TTFont
    out = WORK / "fonts"
    out.mkdir(exist_ok=True)
    for name in ("ibm-plex-sans-condensed-500", "ibm-plex-sans-condensed-700"):
        parts = []
        for sub in ("latin", "latin-ext"):
            f = TTFont(ROOT / "web" / "fonts" / f"{name}-{sub}.woff2")
            f.flavor = None
            p = out / f"{name}-{sub}.tmp.ttf"
            f.save(p)
            parts.append(str(p))
        Merger().merge(parts).save(out / f"{name}.ttf")
        for p in parts:
            Path(p).unlink()
    return out


def ts(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def esc(s):
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def ass_file():
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,IBM Plex Sans Condensed Medium,42,&H00F2EBDA,&H00F2EBDA,&H00141A16,&H00141A16,0,0,0,0,100,100,0,0,1,0,0,7,60,60,842,1
Style: Lbl,IBM Plex Sans Condensed,20,&H00C8D4D9,&H00C8D4D9,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,0,0,7,0,0,0,1
Style: Focus,IBM Plex Sans Condensed,30,&H0080C8E8,&H0080C8E8,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,0,0,7,1452,16,578,1
Style: Step,IBM Plex Sans Condensed,24,&H006E9EB8,&H006E9EB8,&H00000000,&H00000000,-1,0,0,0,100,100,3,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for a, b, f, text in intervals:
        ev.append(f"Dialogue: 2,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\q0\\fad(150,0)}}{esc(text)}")
        if f == "grid":
            for n in ORDER:
                x, y = GRID_POS[n]
                ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Lbl,,0,0,0,,{{\\pos({x + 8},{y - 26})}}{esc(SHORT[n])}")
        else:
            for n in ORDER:
                x, y = THUMB_POS[n]
                ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Lbl,,0,0,0,,{{\\pos({x + 2},{y - 25})\\fs17}}{esc(SHORT_T[n])}")
            ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Step,,0,0,0,,{{\\pos(1452,540)}}EM DESTAQUE")
            ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Focus,,0,0,0,,{{\\q0}}{esc(TL['labels'][f])}")
    ev.append(f"Dialogue: 3,{ts(0)},{ts(DUR)},Step,,0,0,0,,{{\\pos(1452,1046)\\fs20}}ESTADO-MAIOR · demonstração")
    p = WORK / "captions.ass"
    p.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return p


def build():
    ass = ass_file()
    fdir = fonts_dir()
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for n in ORDER:
        args += ["-i", TL["videos"][n]]
    f = [f"color=c=0x141a16:s=1920x1080:r={FPS}:d={DUR:.2f}[bg0]"]
    for i, n in enumerate(ORDER):
        off = max(0.0, TL["offsets"][n])
        f.append(f"[{i}:v]trim=start={off:.3f},setpts=PTS-STARTPTS,fps={FPS},split=3[b{i}][s{i}][g{i}]")
        f.append(f"[b{i}]scale={BIG[0]}:{BIG[1]}:flags=lanczos[B{i}]")
        f.append(f"[s{i}]scale={TH[0]}:{TH[1]}:flags=bicubic[S{i}]")
        f.append(f"[g{i}]scale={TILE[0]}:{TILE[1]}:flags=lanczos[G{i}]")
    f.append("[bg0]drawbox=x=0:y=810:w=1920:h=270:color=0x0f1411@1:t=fill,"
             "drawbox=x=0:y=810:w=1920:h=3:color=0xb08d3c@1:t=fill[o0]")
    cur, k = "o0", 1
    for i, n in enumerate(ORDER):
        x, y = THUMB_POS[n]
        gx, gy = GRID_POS[n]
        steps = [
            f"[S{i}]overlay=x={x}:y={y}:enable='{enable(lambda fo: fo != 'grid')}':eof_action=repeat",
            f"[G{i}]overlay=x={gx}:y={gy}:enable='{enable(lambda fo: fo == 'grid')}':eof_action=repeat",
            f"[B{i}]overlay=x=0:y=0:enable='{enable(lambda fo, n=n: fo == n)}':eof_action=repeat",
        ]
        for s in steps:
            f.append(f"[{cur}]{s}[o{k}]")
            cur, k = f"o{k}", k + 1
        f.append(f"[{cur}]drawbox=x={x - 3}:y={y - 3}:w={TH[0] + 6}:h={TH[1] + 6}:color=0xe0a040@1:t=3:"
                 f"enable='{enable(lambda fo, n=n: fo == n)}'[o{k}]")
        cur, k = f"o{k}", k + 1
    f.append(f"[{cur}]drawbox=x=1440:y=0:w=2:h=810:color=0x3a4a3e@1:t=fill:"
             f"enable='{enable(lambda fo: fo != 'grid')}'[o{k}]")
    cur = f"o{k}"
    fd = str(fdir).replace(":", "\\:")
    f.append(f"[{cur}]subtitles=filename='{ass}':fontsdir='{fd}',format=yuv420p[vout]")
    script = WORK / "filter.txt"
    script.write_text(";\n".join(f))
    args += ["-filter_complex_script", str(script), "-map", "[vout]", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-tune", "stillimage",
             "-movflags", "+faststart", "-t", f"{DUR:.2f}", str(OUT)]
    print(f"montando {DUR:.0f} s de vídeo...", flush=True)
    subprocess.run(args, check=True)
    print("pronto:", OUT)


if __name__ == "__main__":
    build()
