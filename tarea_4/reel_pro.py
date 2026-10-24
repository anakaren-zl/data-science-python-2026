"""Reel "pro" de la Tarea 4: el reel de la sesión 15 con una imagen del dashboard o de los mapas de la Tarea 3 en cada escena.

Usa el código del profesor (sessions/15-texto-a-reel/reel.py) sin modificarlo: solo cambia cómo se dibuja cada escena.
Cada escena de salidas/guion.json puede traer "imagen": una ruta relativa a la carpeta tarea_4/.

    python reel_pro.py --curso "C:/.../Data-Science-Python" --voz mi_voz.ogg --autor "..." --fuente "..."
"""
import argparse
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent

p = argparse.ArgumentParser()
p.add_argument("--curso", required=True, help="carpeta del repo d2cml-ai/Data-Science-Python")
p.add_argument("--voz", default=str(AQUI / "mi_voz.ogg"))
p.add_argument("--autor", required=True)
p.add_argument("--fuente", required=True)
p.add_argument("--device", default="cpu")
p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
p.add_argument("--velocidad", type=float, default=1.0)
p.add_argument("--salidas", default=str(AQUI / "salidas"))
p.add_argument("--musica", default="generada",
               help="'generada' = fondo suave creado con numpy (sin derechos de autor); una ruta = tu mp3 libre de derechos; 'no' = sin música")
p.add_argument("--volumen-musica", type=float, default=-24, help="dB de la música respecto a la voz")
p.add_argument("--solo-portadas", action="store_true", help="dibuja un cuadro por escena, sin voz, para revisar el diseño")
a = p.parse_args()

sys.path.insert(0, str(Path(a.curso) / "sessions" / "15-texto-a-reel"))
import reel  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

# Zona de la imagen (entre el aviso de IA y la cifra) y zona del texto (antes de los subtítulos)
IMG_CAJA = (reel.MARGEN, 410, reel.ANCHO - reel.MARGEN, 900)
TEXTO_Y0, TEXTO_Y1 = 930, 1250


def _imagen(ruta):
    """La imagen completa (sin recortar) dentro de una tarjeta oscura con esquinas redondeadas."""
    x0, y0, x1, y1 = IMG_CAJA
    w, h = x1 - x0, y1 - y0
    tarjeta = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tarjeta).rounded_rectangle((0, 0, w - 1, h - 1), radius=28, fill=reel.CAJA)
    im = Image.open(ruta).convert("RGB")
    pad = 18
    escala = min((w - 2 * pad) / im.width, (h - 2 * pad) / im.height)
    im = im.resize((int(im.width * escala), int(im.height * escala)), Image.LANCZOS)
    mascara = Image.new("L", im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=16, fill=255)
    tarjeta.paste(im, ((w - im.width) // 2, (h - im.height) // 2), mascara)
    return tarjeta


def _escena(e):
    """Como reel._escena, pero con la imagen arriba y la cifra y la etiqueta debajo."""
    if not e.get("imagen"):
        return _escena_original(e)
    capa = Image.new("RGBA", (reel.ANCHO, reel.ALTO), (0, 0, 0, 0))
    capa.paste(_imagen(AQUI / e["imagen"]), IMG_CAJA[:2])
    d = ImageDraw.Draw(capa)
    ancho = reel.ANCHO - 2 * reel.MARGEN

    def alto(texto, f):
        return -d.textbbox((0, 0), texto, font=f, anchor="ls")[1]

    lineas = []
    if e.get("cifra"):
        f = reel._ajustar(d, e["cifra"], "Oswald", 700, ancho, 190)
        lineas.append((e["cifra"], f, reel.ACENTO, alto(e["cifra"], f), 40))
        fe, color = reel._fuente("PublicSans", 46, 600), reel.TEXTO
    else:
        fe, color = reel._fuente("Oswald", 76, 600), reel.TEXTO
    lineas += [(x, fe, color, alto("H", fe), int(fe.size * 0.4)) for x in reel._envolver(d, e["etiqueta"], fe, ancho)]
    y = (TEXTO_Y0 + TEXTO_Y1 - sum(h + g for *_, h, g in lineas) + lineas[-1][4]) / 2
    for texto, f, c, h, g in lineas:
        y += h
        d.text((reel.MARGEN, y), texto, font=f, fill=c, anchor="ls")
        y += g
    return capa


def _musica_generada(segundos, sr):
    """Fondo ambiental suave: acordes lentos Lam-Fa-Do-Sol con ondas senoidales. Lo crea el código, así que no tiene derechos de autor."""
    import numpy as np
    acordes = [(220.00, 261.63, 329.63), (174.61, 220.00, 261.63), (196.00, 261.63, 329.63), (196.00, 246.94, 293.66)]
    dur = 4.0                                   # segundos por acorde
    t = np.arange(int(dur * sr)) / sr
    env = np.minimum(1, t / 1.2) * np.minimum(1, (dur - t) / 1.2)   # cada acorde entra y sale suave
    bloques = []
    for k in range(int(np.ceil(segundos / dur))):
        notas = acordes[k % len(acordes)]
        x = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in notas)
        x += 0.6 * np.sin(2 * np.pi * notas[0] / 2 * t)                # bajo
        bloques.append(x * env)
    return np.concatenate(bloques)[: int(segundos * sr)].astype("float32")


def _mezclar_musica(narracion):
    import numpy as np
    n = len(narracion.audio)
    if a.musica == "no":
        return
    if a.musica == "generada":
        m = _musica_generada(n / narracion.sr, narracion.sr)
    else:
        m = reel.cargar_audio(a.musica, narracion.sr)
        m = np.tile(m, int(np.ceil(n / len(m))))[:n]
    m = m[:n]
    fade = int(1.5 * narracion.sr)
    rampa = np.ones(n, "float32")
    rampa[:fade] = np.linspace(0, 1, fade)
    rampa[-fade:] = np.linspace(1, 0, fade)
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)) + 1e-9)
    m = m * rampa * (rms(narracion.audio) / rms(m)) * 10 ** (a.volumen_musica / 20)
    mezcla = narracion.audio + m
    narracion.audio = (mezcla / max(1.0, float(np.abs(mezcla).max()))).astype("float32")


_escena_original = reel._escena
reel._escena = _escena   # video() y portada() llaman a reel._escena

t0 = time.time()
salidas = Path(a.salidas)
guion = json.loads((salidas / "guion.json").read_text(encoding="utf-8"))
for e in guion["escenas"]:
    print(f"   {e['cifra'] or '-':>10} | {e.get('imagen', '-'):<28} | {e['frase'][:70]}")

if a.solo_portadas:
    base = reel._base(guion["titulo"], a.fuente, a.autor)
    for i, e in enumerate(guion["escenas"], 1):
        img = base.copy()
        capa = _escena(e)
        img.paste(capa, (0, 0), capa)
        img.save(salidas / f"prueba_escena_{i}.png")
    print("listo: prueba_escena_*.png en", salidas)
    sys.exit()

voz = reel.Voz(a.voz, modelo=a.tts, device=a.device)
reel._reloj(f"voz cargada; referencia: «{voz.texto_ref}»", t0)
narracion = reel.narrar(voz, guion, velocidad=a.velocidad)
(salidas / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
reel._reloj(f"narración: {narracion.duracion:.1f} s; WER por escena: "
            + ", ".join(f"{e['wer']:.2f}" for e in guion["escenas"]), t0)
reel.subtitulos(narracion, guion)
reel.a_srt(narracion, salidas / "reel.srt")
_mezclar_musica(narracion)   # después de los subtítulos: Whisper escucha solo la voz
reel.portada(guion, narracion, salidas / "portada.png", a.fuente, a.autor)
reel.video(guion, narracion, salidas / "reel.mp4", a.fuente, a.autor)
reel.posts(guion, salidas / "posts.md")
reel._reloj(f"listo: {salidas / 'reel.mp4'}", t0)
