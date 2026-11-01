"""Reel de la tarea: el reel de la sesión 15 con una imagen del dashboard en cada escena, zoom lento y música de fondo.

Usa el código del profesor (sessions/15-texto-a-reel/reel.py) sin modificarlo; solo cambia los colores, la letra
(Montserrat) y cómo se dibuja cada escena. Cada escena de guion.json trae su "imagen" (ruta relativa a reel/).

    python hacer_reel.py --curso RUTA/Data-Science-Python --voz mi_voz.ogg --device cuda
    python hacer_reel.py --curso RUTA/Data-Science-Python --solo-portadas     # revisa el diseño sin generar voz

Guarda en reel/ los archivos reel.mp4, subtitulos.srt, portada.png y posts.md.
"""
import argparse
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FUENTES_MONTSERRAT = AQUI.parent / "web" / "assets" / "fuentes"

p = argparse.ArgumentParser()
p.add_argument("--curso", required=True, help="carpeta del repo d2cml-ai/Data-Science-Python")
p.add_argument("--voz", default=str(AQUI / "mi_voz.ogg"))
p.add_argument("--autor", default="Ana Karen Zamalloa Lima")
p.add_argument("--fuente", default="INEI (2025, 2026), ENAHO 2024 y 2025 · Gráficos y mapa propios (mapa base © OpenStreetMap y CARTO) · Música generada con Python")
p.add_argument("--device", default="cpu")
p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-1.7B-Base")
p.add_argument("--velocidad", type=float, default=1.0)
p.add_argument("--musica", default="generada",
               help="'generada' = fondo suave creado con numpy (sin derechos de autor); una ruta = mp3 libre de derechos; 'no'")
p.add_argument("--volumen-musica", type=float, default=-22, help="dB de la música respecto a la voz")
p.add_argument("--solo-portadas", action="store_true", help="dibuja un cuadro por escena, sin voz, para revisar el diseño")
a = p.parse_args()

sys.path.insert(0, str(Path(a.curso) / "sessions" / "15-texto-a-reel"))
import reel  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

# Paleta del dashboard: morado (mujeres) y naranja (varones)
reel.FONDO, reel.TEXTO, reel.SUAVE, reel.ACENTO, reel.CAJA = "#2A1150", "#FFFFFF", "#CDBEEA", "#F28A3C", "#3D1C73"

# Montserrat en lugar de Oswald y Public Sans: Black para cifras y títulos, pesos menores para el resto
PESOS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}


def _montserrat(nombre, tam, peso):
    if nombre == "Oswald":
        peso = 900
    peso = min(PESOS, key=lambda k: abs(k - peso))
    return ImageFont.truetype(str(FUENTES_MONTSERRAT / f"Montserrat-{PESOS[peso]}.ttf"), tam)


reel._fuente = _montserrat

# Zona de la imagen (entre el aviso de IA y la cifra) y zona del texto (antes de los subtítulos)
IMG_CAJA = (reel.MARGEN, 400, reel.ANCHO - reel.MARGEN, 1010)
TEXTO_Y0, TEXTO_Y1 = 1030, 1245
ZOOM = 0.07   # cuánto se acerca la imagen a lo largo de la escena (7 %)


def _tarjeta(ruta, zoom=0.0):
    """La imagen completa dentro de una tarjeta blanca con esquinas redondeadas, con un acercamiento opcional."""
    x0, y0, x1, y1 = IMG_CAJA
    w, h = x1 - x0, y1 - y0
    tarjeta = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tarjeta).rounded_rectangle((0, 0, w - 1, h - 1), radius=28, fill="#FFFFFF")
    im = Image.open(ruta).convert("RGB")
    if zoom > 0:   # recorta los bordes y vuelve al tamaño original: efecto de cámara que se acerca
        dx, dy = im.width * zoom / 2, im.height * zoom / 2
        im = im.crop((dx, dy, im.width - dx, im.height - dy))
    pad = 22
    escala = min((w - 2 * pad) / im.width, (h - 2 * pad) / im.height)
    im = im.resize((int(im.width * escala), int(im.height * escala)), Image.LANCZOS)
    mascara = Image.new("L", im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=16, fill=255)
    tarjeta.paste(im, ((w - im.width) // 2, (h - im.height) // 2), mascara)
    return tarjeta


def _texto(e):
    """Capa transparente con la cifra grande (naranja) y su etiqueta, debajo de la imagen."""
    capa = Image.new("RGBA", (reel.ANCHO, reel.ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    ancho = reel.ANCHO - 2 * reel.MARGEN

    def alto(texto, f):
        return -d.textbbox((0, 0), texto, font=f, anchor="ls")[1]

    lineas = []
    if e.get("cifra"):
        f = reel._ajustar(d, e["cifra"], "Oswald", 900, ancho, 140)
        lineas.append((e["cifra"], f, reel.ACENTO, alto(e["cifra"], f), 40))
        fe, color = reel._fuente("PublicSans", 38, 600), reel.TEXTO
    else:
        fe, color = reel._fuente("Oswald", 66, 900), reel.TEXTO
    lineas += [(x, fe, color, alto("H", fe), int(fe.size * 0.42)) for x in reel._envolver(d, e["etiqueta"], fe, ancho)]
    y = (TEXTO_Y0 + TEXTO_Y1 - sum(h + g for *_, h, g in lineas) + lineas[-1][4]) / 2
    for texto, f, c, h, g in lineas:
        y += h
        d.text((reel.MARGEN, y), texto, font=f, fill=c, anchor="ls")
        y += g
    return capa


def _escena(e, zoom=0.0):
    capa = _texto(e)
    capa.paste(_tarjeta(AQUI / e["imagen"], zoom), IMG_CAJA[:2])
    return capa


# El cuadro del profesor pega una capa fija por escena; aquí la capa se redibuja con un zoom que avanza con el tiempo
_cuadro_original = reel._cuadro
_GUION = {}


def _cuadro(base, capas, narracion, t, bloques, fuente_sub):
    i = max([k for k, (ini, _) in enumerate(narracion.escenas) if ini - reel.PAUSA <= t] or [0])
    ini, fin = narracion.escenas[i]
    avance = min(1.0, max(0.0, (t - ini) / max(fin - ini, 0.1)))
    capas = list(capas)
    capas[i] = _escena(_GUION["escenas"][i], ZOOM * avance)
    return _cuadro_original(base, capas, narracion, t, bloques, fuente_sub)


def _musica_generada(segundos, sr):
    """Fondo suave: acordes lentos con ondas senoidales. Lo crea el código, así que no tiene derechos de autor."""
    import numpy as np
    acordes = [(220.00, 261.63, 329.63), (174.61, 220.00, 261.63), (196.00, 261.63, 329.63), (196.00, 246.94, 293.66)]
    dur = 4.0
    t = np.arange(int(dur * sr)) / sr
    env = np.minimum(1, t / 1.2) * np.minimum(1, (dur - t) / 1.2)
    bloques = []
    for k in range(int(np.ceil(segundos / dur))):
        notas = acordes[k % len(acordes)]
        x = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in notas)
        x += 0.6 * np.sin(2 * np.pi * notas[0] / 2 * t)
        bloques.append(x * env)
    return np.concatenate(bloques)[: int(segundos * sr)].astype("float32")


def _mezclar_musica(narracion):
    """La música queda 22 dB por debajo de la voz, con entrada y salida suaves."""
    import numpy as np
    if a.musica == "no":
        return
    n = len(narracion.audio)
    if a.musica == "generada":
        m = _musica_generada(n / narracion.sr, narracion.sr)
    else:
        m = reel.cargar_audio(a.musica, narracion.sr)
        m = np.tile(m, int(np.ceil(n / len(m))))[:n]
    fade = int(1.5 * narracion.sr)
    rampa = np.ones(n, "float32")
    rampa[:fade] = np.linspace(0, 1, fade)
    rampa[-fade:] = np.linspace(1, 0, fade)
    rms = lambda x: float(np.sqrt(np.mean(x ** 2)) + 1e-9)
    m = m[:n] * rampa * (rms(narracion.audio) / rms(m)) * 10 ** (a.volumen_musica / 20)
    mezcla = narracion.audio + m
    narracion.audio = (mezcla / max(1.0, float(np.abs(mezcla).max()))).astype("float32")


t0 = time.time()
guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
_GUION.update(guion)
reel._escena = _escena
reel._cuadro = _cuadro
for e in guion["escenas"]:
    print(f"   {e['cifra'] or '-':>12} | {e['imagen']:<34} | {e['frase'][:60]}")

if a.solo_portadas:
    base = reel._base(guion["titulo"], a.fuente, a.autor)
    for i, e in enumerate(guion["escenas"], 1):
        img = base.copy()
        capa = _escena(e)
        img.paste(capa, (0, 0), capa)
        img.save(AQUI / f"prueba_escena_{i}.png")
    print("listo: prueba_escena_*.png en", AQUI)
    sys.exit()

voz = reel.Voz(a.voz, modelo=a.tts, device=a.device)
reel._reloj(f"voz cargada; referencia: «{voz.texto_ref}»", t0)
narracion = reel.narrar(voz, guion, velocidad=a.velocidad)
(AQUI / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
reel._reloj(f"narración de {narracion.duracion:.1f} s; WER por escena "
            + ", ".join(f"{e['wer']:.2f}" for e in guion["escenas"]), t0)
reel.subtitulos(narracion, guion)
reel.a_srt(narracion, AQUI / "subtitulos.srt")
_mezclar_musica(narracion)   # después de los subtítulos, para que Whisper escuche solo la voz
reel.portada(guion, narracion, AQUI / "portada.png", a.fuente, a.autor)
reel.video(guion, narracion, AQUI / "reel.mp4", a.fuente, a.autor)
reel.posts(guion, AQUI / "posts.md")
reel._reloj(f"listo: {AQUI / 'reel.mp4'}", t0)
# Control de la rúbrica: el reel debe durar entre 45 y 75 segundos y tener entre 5 y 7 escenas
print(f"Duración {narracion.duracion:.1f} s · {len(guion['escenas'])} escenas · "
      + ("OK" if 45 <= narracion.duracion <= 75 else "FUERA DEL RANGO DE 45 A 75 s: ajusta --velocidad"))
