"""Reel de la tarea: el reel de la sesión 15 con una imagen del dashboard en cada escena, zoom lento y música de fondo.

Usa el código del profesor (sessions/15-texto-a-reel/reel.py) sin modificarlo; solo cambia los colores, la letra
(Montserrat) y cómo se dibuja cada cuadro: cifras que cuentan desde cero, tarjetas que entran con movimiento,
acercamiento lento de cada imagen y una barra de avance por escenas. Cada escena de guion.json trae su "imagen" (ruta relativa a reel/).

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
p.add_argument("--fuente", default="INEI (2025, 2026), ENAHO 2024 y 2025 · Gráficos y mapa propios (mapa base © OpenStreetMap y CARTO) · Imágenes generadas con IA (Canva) · Música generada con Python")
p.add_argument("--device", default="cpu")
p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-1.7B-Base")
p.add_argument("--velocidad", type=float, default=1.0)
p.add_argument("--musica", default="generada",
               help="'generada' = fondo suave creado con numpy (sin derechos de autor); una ruta = mp3 libre de derechos; 'no'")
p.add_argument("--volumen-musica", type=float, default=-22, help="dB de la música respecto a la voz")
p.add_argument("--solo-portadas", action="store_true", help="dibuja un cuadro por escena, sin voz, para revisar el diseño")
p.add_argument("--vista-previa", action="store_true", help="además arma un video mudo para revisar las animaciones")
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

# ---------------------------------------------------------------------------------------------------------------
# Diseño propio de cada cuadro (9:16, 1080 × 1920). Se aprovecha toda la altura en cinco franjas:
#   barra de avance y título (110 a 230) · cifra animada y etiqueta (270 a 760) · imagen del dashboard (790 a 1370)
#   · subtítulos (1420 a 1530) · autoría, fuente y créditos (1600 a 1720), por encima de la zona que tapan las apps.
# ---------------------------------------------------------------------------------------------------------------
import math  # noqa: E402
import re  # noqa: E402

W, H, M = reel.ANCHO, reel.ALTO, 72
LILA, NARANJA, BLANCO, SUAVE, CAJA = "#D9C2FF", "#F28A3C", "#FFFFFF", "#CDBEEA", "#3D1C73"
CIFRA_Y0, CIFRA_Y1 = 270, 760
IMG_CAJA = (M, 790, W - M, 1370)
SUB_Y = 1440
ZOOM = 0.08          # acercamiento lento de la imagen a lo largo de la escena
ENTRADA = 0.55       # segundos de la animación de entrada
CONTEO = 1.1         # segundos que tarda la cifra en contar desde cero


def F(tam, peso=900):
    return _montserrat("Montserrat", tam, peso)


def suave(x):        # curva de aceleración (ease-out) para que el movimiento frene al final
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def _fondo(titulo, fuente_datos, autor):
    """Fondo fijo: degradado morado, brillo naranja como en el dashboard, título, aviso de IA y créditos."""
    import numpy as np
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    c0, c1 = np.array([42, 17, 80]), np.array([74, 33, 140])
    t = (0.65 * y + 0.35 * x)[..., None]
    rgb = c0 * (1 - t) + c1 * t
    brillo = np.exp(-(((x - 0.95) / 0.35) ** 2 + ((y - 0.04) / 0.16) ** 2))[..., None]
    rgb = rgb * (1 - 0.55 * brillo) + np.array([217, 102, 31]) * 0.55 * brillo
    img = Image.fromarray(rgb.clip(0, 255).astype("uint8"), "RGB")
    _MARCO["capa"] = _marco(titulo, fuente_datos, autor)
    return img


_MARCO = {}


def _marco(titulo, fuente_datos, autor):
    """Capa transparente con el título, el aviso de voz generada con IA y los créditos, que va sobre todo."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((M, 205), titulo.upper(), font=F(30, 800), fill=NARANJA, anchor="ls")
    aviso, fa = "VOZ GENERADA CON IA", F(22, 700)
    wa = d.textlength(aviso, font=fa)
    d.rounded_rectangle((W - M - wa - 36, 172, W - M, 216), radius=22, outline=SUAVE, width=2)
    d.text((W - M - wa - 18, 194), aviso, font=fa, fill=SUAVE, anchor="lm")
    pie = F(25, 500)
    for i, linea in enumerate(reel._envolver(d, f"{autor} · Fuente: {fuente_datos}", pie, W - 2 * M)):
        d.text((W / 2, 1625 + i * 36), linea, font=pie, fill=SUAVE, anchor="mm")
    return img


def _numero(cifra, avance):
    """Reescribe la cifra contando desde cero: «54 mil», «2,1 %», «14 %» conservan su formato y decimales."""
    def rep(m):
        txt = m.group(0)
        dec = len(txt.split(",")[1]) if "," in txt else 0
        v = float(txt.replace(",", ".")) * avance
        return f"{v:.{dec}f}".replace(".", ",")
    return re.sub(r"\d+(?:,\d+)?", rep, cifra)


def _ajustar(d, texto, ancho, maximo, minimo=90, peso=900):
    for tam in range(maximo, minimo, -6):
        if d.textlength(texto, font=F(tam, peso)) <= ancho:
            return F(tam, peso)
    return F(minimo, peso)


def _bloque_cifra(img, e, t):
    """Cifra grande que cuenta desde cero, una barra naranja que crece y la etiqueta que aparece después."""
    d = ImageDraw.Draw(img)
    ancho = W - 2 * M
    conteo = suave(t / CONTEO)
    aparece = suave((t - 0.25) / 0.5)
    fe = F(34, 500) if e.get("cita") else F(42, 600)   # la cita del cierre va más pequeña, como epígrafe
    etiqueta = [l for parte in (e["etiqueta"].split(" · ") if e.get("cita") else [e["etiqueta"]])
                for l in reel._envolver(d, parte, fe, ancho)]
    alto_et = len(etiqueta) * 54

    if e.get("titular"):      # escena de cierre: frase en lugar de cifra
        ft = F(68, 900)
        lineas = reel._envolver(d, e["titular"], ft, ancho)
        alto = len(lineas) * 88 + 40 + alto_et
        y = (CIFRA_Y0 + CIFRA_Y1 - alto) / 2
        for k, linea in enumerate(lineas):
            a = suave((t - 0.15 * k) / 0.5)
            col = BLANCO if e.get("cita") else (NARANJA if k == len(lineas) - 1 else BLANCO)
            capa = Image.new("RGBA", (W, 110), (0, 0, 0, 0))
            ImageDraw.Draw(capa).text((M, 88), linea, font=ft, fill=col, anchor="ls")
            capa.putalpha(capa.getchannel("A").point(lambda v: int(v * a)))
            img.paste(capa, (0, int(y + 30 * (1 - a))), capa)
            y += 88
        y += 40
    else:
        partes = [p.strip() for p in e["cifra"].split("·")]
        if len(partes) == 2:  # dos cifras lado a lado, cada una con su grupo
            fc = _ajustar(d, max(partes, key=len), ancho / 2 - 30, 230)
            nombres = e.get("cifras_etiquetas", ["", ""])
            colores = [LILA, NARANJA]
            alto = 230 + 100 + 50 + alto_et
            y = (CIFRA_Y0 + CIFRA_Y1 - alto) / 2
            for k, (p, nom) in enumerate(zip(partes, nombres)):
                x = M + k * (ancho / 2 + 30)
                fondo_num = d.textbbox((x, y + 200), p, font=fc, anchor="ls")[3]
                d.text((x, y + 200), _numero(p, conteo), font=fc, fill=colores[k], anchor="ls")
                d.rounded_rectangle((x, fondo_num + 14, x + (ancho / 2 - 60) * conteo, fondo_num + 24), radius=5, fill=colores[k])
                d.text((x, fondo_num + 72), nom, font=F(34, 700), fill=BLANCO, anchor="ls")
            y = fondo_num + 72 + 50
        else:
            fc = _ajustar(d, e["cifra"], ancho, 270)
            alto = 250 + 70 + alto_et
            y = (CIFRA_Y0 + CIFRA_Y1 - alto) / 2
            fondo_num = d.textbbox((M, y + 220), e["cifra"], font=fc, anchor="ls")[3]
            d.text((M, y + 220), _numero(e["cifra"], conteo), font=fc, fill=LILA, anchor="ls")
            d.rounded_rectangle((M, fondo_num + 18, M + 260 * conteo, fondo_num + 30), radius=6, fill=NARANJA)
            y = fondo_num + 30 + 34
    capa = Image.new("RGBA", (W, alto_et + 20), (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    for k, linea in enumerate(etiqueta):
        dc.text((M, 44 + k * 54), linea, font=fe, fill=LILA if e.get("cita") else BLANCO, anchor="ls")
    capa.putalpha(capa.getchannel("A").point(lambda v: int(v * aparece)))
    img.paste(capa, (0, int(y + 20 * (1 - aparece))), capa)


_CACHE = {}


def _imagen(ruta):
    """La imagen del dashboard ajustada a la tarjeta (se calcula una sola vez por escena)."""
    if ruta not in _CACHE:
        x0, y0, x1, y1 = IMG_CAJA
        w, h, pad = x1 - x0, y1 - y0, 20
        im = Image.open(ruta).convert("RGB")
        esc = min((w - 2 * pad) / im.width, (h - 2 * pad) / im.height) * (1 + ZOOM)
        _CACHE[ruta] = im.resize((int(im.width * esc), int(im.height * esc)), Image.LANCZOS)
    return _CACHE[ruta]


def _tarjeta(img, ruta, t, dur):
    """Tarjeta blanca que entra deslizándose desde abajo y cuya imagen se acerca lentamente (efecto Ken Burns)."""
    x0, y0, x1, y1 = IMG_CAJA
    w, h, pad = x1 - x0, y1 - y0, 20
    im = _imagen(ruta)
    z = 1 + ZOOM * min(1.0, t / max(dur, 0.1))
    base_w, base_h = im.width / (1 + ZOOM), im.height / (1 + ZOOM)
    cw, ch = base_w * (1 + ZOOM) / z, base_h * (1 + ZOOM) / z
    cx, cy = im.width / 2, im.height / 2
    vista = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize(
        (int(base_w), int(base_h)), Image.BILINEAR)
    # la tarjeta se ajusta al alto real de la imagen para no dejar bandas blancas
    th = int(base_h) + 2 * pad
    tarjeta = Image.new("RGBA", (w, th), (0, 0, 0, 0))
    ImageDraw.Draw(tarjeta).rounded_rectangle((0, 0, w - 1, th - 1), radius=30, fill="#FFFFFF")
    mascara = Image.new("L", vista.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, vista.width - 1, vista.height - 1), radius=16, fill=255)
    tarjeta.paste(vista, ((w - vista.width) // 2, pad), mascara)
    a = suave(t / ENTRADA)
    tarjeta.putalpha(tarjeta.getchannel("A").point(lambda v: int(v * a)))
    sombra = Image.new("RGBA", (w + 40, th + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((20, 28, w + 20, th + 20), radius=30, fill=(20, 6, 40, int(90 * a)))
    yy = y0 + (h - th) // 2 + int(90 * (1 - a))
    img.paste(sombra, (x0 - 20, yy - 20), sombra)
    img.paste(tarjeta, (x0, yy), tarjeta)


def _foto(img, ruta, t, dur, bajar=0):
    """Fotografía a pantalla completa con acercamiento lento y un degradado oscuro que deja leer el texto."""
    import numpy as np
    clave = ("foto", ruta)
    if clave not in _CACHE:
        im = Image.open(ruta).convert("RGB")
        esc = max(W / im.width, H / im.height) * (1 + ZOOM)
        im = im.resize((int(im.width * esc), int(im.height * esc)), Image.LANCZOS)
        y = np.linspace(0, 1, H)[:, None]
        # oscuro arriba (cifra), más claro al centro (foto) y oscuro abajo (subtítulos y créditos)
        a = np.clip((0.42 - y) / 0.16, 0, 1) * 0.94 + np.clip((y - 0.64) / 0.36, 0, 1) * 0.9
        sombra = np.zeros((H, W, 4), "uint8")
        sombra[..., :3] = (30, 10, 60)
        sombra[..., 3] = (np.broadcast_to(a, (H, W)) * 255).astype("uint8")
        _CACHE[clave] = (im, Image.fromarray(sombra, "RGBA"))
    im, sombra = _CACHE[clave]
    z = 1 + ZOOM * min(1.0, t / max(dur, 0.1))
    cw, ch = im.width / z, im.height / z
    cx, cy = im.width / 2, im.height / 2
    vista = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.BILINEAR)
    lienzo = img.copy()
    lienzo.paste(vista, (0, bajar))   # «bajar» desplaza la foto para que las caras no queden bajo la cifra
    a = suave(t / ENTRADA)
    img.paste(Image.blend(img, lienzo, a))
    img.paste(sombra, (0, 0), sombra)


def _barra(img, narracion, t):
    """Barra de avance por escenas, como en las historias de Instagram."""
    d = ImageDraw.Draw(img)
    n, hueco = len(narracion.escenas), 10
    ancho = (W - 2 * M - hueco * (n - 1)) / n
    for k, (ini, fin) in enumerate(narracion.escenas):
        x = M + k * (ancho + hueco)
        d.rounded_rectangle((x, 112, x + ancho, 120), radius=4, fill="#5B3A92")
        p = min(1.0, max(0.0, (t - ini + reel.PAUSA) / max(fin - ini + reel.PAUSA, 0.1)))
        if p > 0:
            d.rounded_rectangle((x, 112, x + ancho * p, 120), radius=4, fill=NARANJA)


def _subtitulo(img, bloques, t, fuente_sub):
    """El bloque que se está diciendo, centrado, con la palabra actual en naranja."""
    b = next((b for b in bloques if b[0][0] - 0.1 <= t <= b[-1][1] + 0.25), None)
    if not b:
        return
    d = ImageDraw.Draw(img)
    texto = " ".join(p[2] for p in b)
    w = d.textlength(texto, font=fuente_sub)
    x = (W - w) / 2
    d.rounded_rectangle((x - 34, SUB_Y - 24, x + w + 34, SUB_Y + fuente_sub.size + 30), radius=30, fill=CAJA)
    for ini, fin, palabra in b:
        d.text((x, SUB_Y), palabra, font=fuente_sub, fill=NARANJA if ini <= t <= fin + 0.05 else BLANCO)
        x += d.textlength(palabra + " ", font=fuente_sub)


def _cuadro(base, capas, narracion, t, bloques, fuente_sub):
    img = base.copy()
    i = max([k for k, (ini, _) in enumerate(narracion.escenas) if ini - reel.PAUSA <= t] or [0])
    ini, fin = narracion.escenas[i]
    te = t - ini + reel.PAUSA
    e = _GUION["escenas"][i]
    # una escena puede tener varios fondos ("visuales") que cambian a mitad de la frase para dar ritmo
    dur = fin - ini + reel.PAUSA
    vis = e.get("visuales") or [{"imagen": e["imagen"], "foto": e.get("foto", False), "bajar": e.get("bajar", 0)}]
    cortes = [0] + [c * dur for c in e.get("cortes", [k / len(vis) for k in range(1, len(vis))])] + [dur]
    k = max(j for j in range(len(vis)) if cortes[j] <= max(te, 0))

    def pinta(j):
        v, t0, t1 = vis[j], cortes[j], cortes[j + 1]
        if v.get("foto"):
            _foto(img, AQUI / v["imagen"], te - t0, t1 - t0, v.get("bajar", 0))
        else:
            _tarjeta(img, AQUI / v["imagen"], te - t0, t1 - t0)
    if k > 0 and te - cortes[k] < ENTRADA:
        pinta(k - 1)          # el fondo anterior queda debajo mientras entra el nuevo
    pinta(k)
    img.paste(_MARCO["capa"], (0, 0), _MARCO["capa"])
    _barra(img, narracion, t)
    _bloque_cifra(img, e, te)
    _subtitulo(img, bloques, t, F(56, 800))
    return img


_GUION = {}
reel._base = _fondo
reel._escena = lambda e: None
reel._cuadro = _cuadro


class _Ensayo:
    """Narración ficticia (sin voz) para revisar el diseño y el movimiento antes de usar la GPU."""
    def __init__(self, guion, seg=5.0):
        self.escenas, self.palabras, t = [], [], reel.INICIO
        for e in guion["escenas"]:
            pal = e["frase"].split()
            dur = max(seg, 0.32 * len(pal))
            self.escenas.append((t, t + dur))
            paso = dur / len(pal)
            self.palabras += [(t + k * paso, t + (k + 1) * paso, p) for k, p in enumerate(pal)]
            t += dur + reel.PAUSA
        self.duracion = t + reel.FINAL


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
for e in guion["escenas"]:
    print(f"   {e['cifra'] or '-':>12} | {e['imagen']:<34} | {e['frase'][:60]}")

if a.solo_portadas or a.vista_previa:
    ensayo = _Ensayo(guion)
    base = reel._base(guion["titulo"], a.fuente, a.autor)
    bloques = reel._bloques(ensayo.palabras)
    for i, (ini, fin) in enumerate(ensayo.escenas, 1):
        _cuadro(base, [], ensayo, ini + 2.2, bloques, None).save(AQUI / f"prueba_escena_{i}.png")
    if a.vista_previa:   # video mudo con tiempos aproximados, para ver las animaciones
        import subprocess
        cmd = [reel.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30",
               "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
               str(AQUI / "prueba_movimiento.mp4")]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for k in range(int(ensayo.duracion * 30)):
            proc.stdin.write(_cuadro(base, [], ensayo, k / 30, bloques, None).tobytes())
        proc.stdin.close()
        proc.wait()
    print("listo: prueba_escena_*.png" + (" y prueba_movimiento.mp4" if a.vista_previa else ""), "en", AQUI)
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
