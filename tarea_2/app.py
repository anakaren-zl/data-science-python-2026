"""Task 2 dashboard: Peruvian voices and documents, from scanned archive to searchable text.

The app only reads the CSV files produced by the two notebooks. No OCR, ASR or LLM model runs
on the server, so it stays light enough for Streamlit Community Cloud.

    streamlit run app.py
"""
import html
import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATOS = Path(__file__).parent / "datos"
EJEMPLOS = DATOS / "ejemplos"

# Visual identity: deep purples and warm golds, with soft 3D depth.
MORADO, MORADO_OSCURO, LAVANDA, DORADO, AMBAR = "#5b2a86", "#2e1350", "#9b6dd6", "#f5b700", "#ff9f1c"
TINTA, GRIS = "#241a33", "#7d7489"
ETIQUETAS_TIPO = {"impreso": "Printed", "foto": "Photographed", "manuscrito": "Handwritten"}
COLORES_TIPO = {"Printed": MORADO, "Photographed": DORADO, "Handwritten": LAVANDA}
COLORES_MODELO = [MORADO, DORADO, LAVANDA]
ICONOS_TIPO = {"Printed": "📰", "Photographed": "📸", "Handwritten": "✍️"}

st.set_page_config(page_title="Peruvian voices and documents", page_icon="🎙️", layout="wide")

# ───────────────────────────────────────────────────────── styles
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, p, li {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
[data-testid="stAppViewContainer"] > .main, [data-testid="stMain"] {{
    background: radial-gradient(1200px 500px at 85% -10%, #fff4cc 0%, rgba(255,244,204,0) 60%),
                radial-gradient(900px 500px at -10% 30%, #efe6fb 0%, rgba(239,230,251,0) 60%), #faf8fd; }}
.block-container {{ padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1350px; }}
p {{ text-align: justify; }}

/* Gradient display titles */
.titulo {{ font-family: 'Fraunces', serif; font-weight: 800; letter-spacing: -.01em;
           background: linear-gradient(90deg, {MORADO} 0%, #a14fc9 50%, {AMBAR} 100%);
           -webkit-background-clip: text; background-clip: text; color: transparent !important; }}
.seccion {{ font-family: 'Fraunces', serif; font-weight: 800; font-size: 1.3rem; margin: .3rem 0 .25rem; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: linear-gradient(185deg, {MORADO_OSCURO} 0%, {MORADO} 70%, #7a3fb0 100%);
                             box-shadow: 8px 0 30px -12px rgba(46,19,80,.6); }}
[data-testid="stSidebar"] * {{ color: #f7f1ff !important; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] .stTextInput [data-baseweb="input"], [data-testid="stSidebar"] .stTextInput [data-baseweb="base-input"] {{ background: rgba(255,255,255,.10) !important;
    border: 1px solid rgba(255,255,255,.25) !important; border-radius: 14px !important; }}
[data-testid="stSidebar"] input {{ color: #fff !important; background: transparent !important; }}
[data-testid="stSidebar"] input::placeholder {{ color: rgba(255,255,255,.6) !important; }}
[data-testid="stSidebar"] [data-baseweb="tag"] {{ background: linear-gradient(135deg, {DORADO}, {AMBAR}) !important;
    border-radius: 999px; box-shadow: 0 3px 8px -3px rgba(0,0,0,.4); }}
[data-testid="stSidebar"] [data-baseweb="tag"] * {{ color: {MORADO_OSCURO} !important; font-weight: 700; }}
[data-testid="stSidebar"] svg {{ fill: #fff !important; }}
.logo {{ font-family: 'Fraunces', serif; font-weight: 800; font-size: 1.6rem; line-height: 1.1; }}
.logo span {{ color: {DORADO} !important; }}

/* Hero banner */
.hero {{ background: linear-gradient(125deg, {MORADO_OSCURO} 0%, {MORADO} 45%, #8e44ad 75%, #c77dff 100%);
         border-radius: 30px; padding: 2.3rem 2.6rem; color: #fff; position: relative; overflow: hidden;
         box-shadow: 0 30px 60px -28px rgba(46,19,80,.85), inset 0 1px 0 rgba(255,255,255,.25); margin-bottom: 1.5rem; }}
.hero::before {{ content: ""; position: absolute; width: 380px; height: 380px; right: -90px; top: -150px;
                 background: radial-gradient(circle, rgba(245,183,0,.55) 0%, rgba(245,183,0,0) 65%); }}
.hero::after {{ content: "🎙️"; position: absolute; right: 2.4rem; bottom: 1.2rem; font-size: 5rem;
                filter: drop-shadow(0 12px 18px rgba(0,0,0,.35)); }}
.hero .kicker {{ text-transform: uppercase; letter-spacing: .18em; font-size: .74rem; font-weight: 800; color: {DORADO} !important; }}
.hero h1, .hero h1 span, .hero h1 a {{ color: #fff !important; -webkit-text-fill-color: #fff; }}
.hero h1 {{ font-family: 'Fraunces', serif; color: #fff !important; font-size: 2.35rem; line-height: 1.12; font-weight: 800;
            margin: .4rem 0 .8rem; max-width: 880px; text-shadow: 0 4px 18px rgba(0,0,0,.25); }}
.hero p {{ color: rgba(255,255,255,.92) !important; font-size: 1.02rem; max-width: 860px; margin-bottom: 1.1rem; }}
.chip {{ display: inline-block; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.3);
         border-radius: 999px; padding: .38rem .95rem; margin: .2rem .4rem .2rem 0; font-size: .86rem; font-weight: 700;
         color: #fff !important; box-shadow: 0 6px 14px -8px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.3);
         backdrop-filter: blur(4px); }}

/* 3D KPI cards (st.metric) */
[data-testid="stMetric"] {{ background: linear-gradient(160deg, #ffffff 0%, #f6f0ff 100%);
    border: 1px solid rgba(91,42,134,.12); border-radius: 22px; padding: 1.05rem 1.25rem;
    box-shadow: 0 1px 0 rgba(255,255,255,.9) inset, 0 14px 28px -16px rgba(91,42,134,.55), 0 3px 6px -3px rgba(91,42,134,.25);
    transition: transform .18s ease, box-shadow .18s ease; position: relative; overflow: hidden; }}
[data-testid="stMetric"]::after {{ content: ""; position: absolute; left: 0; top: 0; height: 5px; width: 100%;
    background: linear-gradient(90deg, {MORADO}, {DORADO}); }}
[data-testid="stMetric"]:hover {{ transform: translateY(-5px) scale(1.01);
    box-shadow: 0 22px 36px -18px rgba(91,42,134,.6), 0 4px 8px -4px rgba(91,42,134,.3); }}
[data-testid="stMetricLabel"] p {{ font-weight: 700; color: {GRIS} !important; text-align: left; }}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {{ font-family: 'Fraunces', serif; font-weight: 800;
    color: {MORADO} !important; }}

/* 3D pill tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: .6rem; border-bottom: none; }}
.stTabs [data-baseweb="tab"] {{ background: linear-gradient(180deg, #ffffff, #f1eaf9); border-radius: 999px;
    padding: .55rem 1.25rem; height: auto; font-weight: 700; border: 1px solid rgba(91,42,134,.12);
    box-shadow: 0 6px 14px -10px rgba(91,42,134,.6), inset 0 1px 0 #fff; }}
.stTabs [aria-selected="true"] {{ background: linear-gradient(135deg, {MORADO}, #8e44ad) !important;
    box-shadow: 0 10px 20px -10px rgba(91,42,134,.9), inset 0 1px 0 rgba(255,255,255,.3) !important; }}
.stTabs [aria-selected="true"] p {{ color: #fff !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* 3D cards */
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 26px !important; }}
.card {{ background: linear-gradient(165deg, #ffffff 0%, #faf6ff 100%); border: 1px solid rgba(91,42,134,.1);
         border-radius: 22px; padding: 1.1rem 1.3rem; margin-bottom: .9rem;
         box-shadow: 0 1px 0 #fff inset, 0 16px 30px -22px rgba(91,42,134,.55); }}
.card h4 {{ font-family: 'Fraunces', serif; margin: 0 0 .5rem; font-size: 1.02rem; font-weight: 800; color: {MORADO} !important; }}
.texto {{ max-height: 320px; overflow-y: auto; line-height: 1.6; font-size: .93rem; white-space: pre-wrap;
          text-align: justify; color: {TINTA}; padding-right: .4rem; }}
mark {{ background: linear-gradient(180deg, rgba(245,183,0,0) 45%, rgba(245,183,0,.65) 45%); color: inherit; padding: 0 .1rem; }}
.etiqueta {{ display: inline-block; border-radius: 999px; padding: .28rem .8rem; margin: .15rem .35rem .3rem 0;
             font-size: .8rem; font-weight: 700; color: {MORADO_OSCURO} !important;
             background: linear-gradient(135deg, #f3e8ff, #fff4cc); border: 1px solid rgba(91,42,134,.12);
             box-shadow: 0 4px 10px -7px rgba(91,42,134,.6); }}
.campo {{ margin-bottom: .65rem; text-align: justify; color: {TINTA}; }}
.campo b {{ display: block; font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; color: {AMBAR} !important; }}
.nulo {{ opacity: .45; font-style: italic; }}
.nota {{ color: {GRIS} !important; font-size: .86rem; text-align: justify; }}

/* iMessage-style bubbles */
.chat {{ background: #ffffff; border-radius: 26px; padding: 1rem 1.1rem 1.2rem; border: 1px solid rgba(0,0,0,.06);
         box-shadow: 0 18px 36px -24px rgba(46,19,80,.55); font-family: -apple-system, 'SF Pro Text', 'Plus Jakarta Sans', sans-serif; }}
.chat-top {{ text-align: center; font-size: .72rem; color: #8e8e93 !important; margin-bottom: .6rem; font-weight: 600; }}
.burbuja {{ position: relative; max-width: 76%; padding: .6rem .95rem; border-radius: 20px; margin: .25rem .4rem .6rem;
            line-height: 1.42; font-size: .93rem; text-align: left; word-wrap: break-word; clear: both; }}
.burbuja small {{ display: block; font-size: .66rem; letter-spacing: .04em; font-weight: 700; margin-bottom: .15rem; opacity: .7; }}
.burbuja::before, .burbuja::after {{ content: ""; position: absolute; bottom: 0; height: 22px; }}
.recibido {{ background: #e9e9eb; color: #000 !important; float: left; }}
.recibido::before {{ left: -7px; width: 20px; background: #e9e9eb; border-bottom-right-radius: 16px 14px; }}
.recibido::after {{ left: -26px; width: 26px; background: #fff; border-bottom-right-radius: 10px; }}
.enviado {{ background: linear-gradient(180deg, #2b9bff 0%, #0a7cff 100%); color: #fff !important; float: right;
            box-shadow: 0 6px 14px -8px rgba(10,124,255,.8); }}
.enviado::before {{ right: -7px; width: 20px; background: #0a7cff; border-bottom-left-radius: 16px 14px; }}
.enviado::after {{ right: -26px; width: 26px; background: #fff; border-bottom-left-radius: 10px; }}
.enviado small, .enviado mark {{ color: #fff !important; }}
.tercero {{ background: linear-gradient(180deg, #b388eb 0%, {MORADO} 100%); color: #fff !important; float: left; }}
.tercero::before {{ left: -7px; width: 20px; background: {MORADO}; border-bottom-right-radius: 16px 14px; }}
.tercero::after {{ left: -26px; width: 26px; background: #fff; border-bottom-right-radius: 10px; }}
.chat {{ overflow: hidden; }}
.limpiar {{ clear: both; }}

/* Buttons and selection accents */
.stDownloadButton button, .stButton button {{ background: linear-gradient(135deg, {MORADO}, #8e44ad) !important;
    color: #fff !important; border: none !important; border-radius: 999px !important; padding: .55rem 1.3rem !important;
    box-shadow: 0 10px 20px -10px rgba(91,42,134,.9), inset 0 1px 0 rgba(255,255,255,.3) !important; }}
.stDownloadButton button p, .stButton button p {{ color: #fff !important; font-weight: 700; }}
.stDownloadButton button:hover {{ transform: translateY(-2px); }}
[data-testid="stMain"] [data-baseweb="tag"] {{ background: linear-gradient(135deg, {DORADO}, {AMBAR}) !important; }}

/* ── Motion ───────────────────────────────────────── */
@keyframes subir {{ from {{ opacity: 0; transform: translateY(18px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes flotar {{ 0%, 100% {{ transform: translateY(0) rotate(-6deg); }} 50% {{ transform: translateY(-12px) rotate(4deg); }} }}
@keyframes fluir {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}
@keyframes brillo {{ from {{ background-position: -200% 0; }} to {{ background-position: 200% 0; }} }}
@keyframes llegar {{ from {{ opacity: 0; transform: translateY(10px) scale(.96); }} to {{ opacity: 1; transform: none; }} }}
@keyframes latido {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(245,183,0,.45); }} 50% {{ box-shadow: 0 0 0 6px rgba(245,183,0,0); }} }}
.hero {{ background-size: 220% 220% !important; animation: fluir 14s ease infinite, subir .7s ease both; }}
.hero::after {{ animation: flotar 4.5s ease-in-out infinite; }}
.chip {{ animation: subir .6s ease both; transition: transform .2s ease, background .2s ease; }}
.chip:nth-of-type(1) {{ animation-delay: .25s; }} .chip:nth-of-type(2) {{ animation-delay: .35s; }}
.chip:nth-of-type(3) {{ animation-delay: .45s; }} .chip:nth-of-type(4) {{ animation-delay: .55s; }}
.chip:hover {{ transform: translateY(-3px) scale(1.04); background: rgba(255,255,255,.26); }}
[data-testid="stMetric"] {{ animation: subir .6s ease both; }}
[data-testid="column"]:nth-child(2) [data-testid="stMetric"] {{ animation-delay: .08s; }}
[data-testid="column"]:nth-child(3) [data-testid="stMetric"] {{ animation-delay: .16s; }}
[data-testid="column"]:nth-child(4) [data-testid="stMetric"] {{ animation-delay: .24s; }}
[data-testid="column"]:nth-child(5) [data-testid="stMetric"] {{ animation-delay: .32s; }}
[data-testid="stMetric"]::after {{ background: linear-gradient(90deg, {MORADO}, {DORADO}, #fff6cc, {DORADO}, {MORADO}) !important;
    background-size: 200% 100% !important; animation: brillo 3.5s linear infinite; }}
[data-testid="stMetricDelta"] {{ animation: latido 2.4s ease-in-out infinite; border-radius: 999px; }}
.card, .chat, [data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {{ animation: subir .55s ease both;
    transition: transform .2s ease, box-shadow .2s ease; }}
.card:hover {{ transform: translateY(-4px); box-shadow: 0 1px 0 #fff inset, 0 24px 40px -24px rgba(91,42,134,.7); }}
.etiqueta {{ transition: transform .18s ease; }} .etiqueta:hover {{ transform: translateY(-2px) scale(1.05); }}
.burbuja {{ animation: llegar .45s ease both; }}
.burbuja:nth-of-type(2) {{ animation-delay: .15s; }} .burbuja:nth-of-type(3) {{ animation-delay: .5s; }}
.burbuja:nth-of-type(4) {{ animation-delay: .85s; }} .burbuja:nth-of-type(5) {{ animation-delay: 1.2s; }}
.burbuja:nth-of-type(6) {{ animation-delay: 1.55s; }} .burbuja:nth-of-type(n+7) {{ animation-delay: 1.9s; }}
.stTabs [data-baseweb="tab"] {{ transition: transform .18s ease; }} .stTabs [data-baseweb="tab"]:hover {{ transform: translateY(-2px); }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation: none !important; transition: none !important; }} }}
</style>
""", unsafe_allow_html=True)


# ───────────────────────────────────────────────────────── data loading
@st.cache_data
def leer(nombre: str) -> pd.DataFrame:
    """Read a CSV from datos/; return an empty table if the file does not exist yet."""
    ruta = DATOS / nombre
    if not ruta.exists():
        return pd.DataFrame()
    return pd.read_csv(ruta, keep_default_na=False)


documentos = leer("documentos.csv")
transcripciones = leer("transcripciones.csv")
eval_ocr = leer("evaluacion_ocr.csv")
eval_asr = leer("evaluacion_asr.csv")
comparativa = leer("comparativa.csv")
extraccion = leer("extraccion_llm.csv")
auditoria = leer("auditoria_llm.csv")

documentos["Type"] = documentos["tipo"].map(ETIQUETAS_TIPO)
documentos["n_caracteres"] = documentos["texto_ocr"].str.len()
transcripciones["minutos"] = pd.to_numeric(transcripciones["duracion_seg"]) / 60
transcripciones["Interview"] = "Interview " + transcripciones["entrevista"].str[-2:].str.lstrip("0")


# ───────────────────────────────────────────────────────── helpers
def estilo(fig, titulo, subtitulo, alto=380):
    """Common chart layout: bold headline, grey subtitle, transparent background, rounded bars."""
    fig.update_layout(
        title=dict(text=f"<b>{titulo}</b><br><span style='font-size:12px;color:{GRIS}'>{subtitulo}</span>",
                   x=0.01, xanchor="left", font=dict(size=17, family="Fraunces, Georgia, serif", color=MORADO)),
        font=dict(family="Plus Jakarta Sans, Segoe UI, Arial", size=12, color=TINTA),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=78, b=10), height=alto, bargap=0.3, barcornerradius=6,
        legend=dict(orientation="h", y=-0.18, x=0, title_text=""), hoverlabel=dict(font_size=12),
    )
    fig.update_yaxes(gridcolor="rgba(91,42,134,.10)", zeroline=False, ticks="")
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    fig.update_xaxes(showgrid=False, ticks="")
    return fig


def resaltar(texto: str, termino: str) -> str:
    """Escape the text for HTML and highlight the search term."""
    seguro = html.escape(texto)
    if termino:
        seguro = re.sub(f"({re.escape(html.escape(termino))})", r"<mark>\1</mark>", seguro, flags=re.IGNORECASE)
    return seguro


def campos_llm(id_registro: str):
    """Structured fields extracted by the LLM for one record, or None."""
    if extraccion.empty:
        return None
    fila = extraccion[extraccion["id"] == id_registro]
    if fila.empty:
        return None
    try:
        return json.loads(fila.iloc[0]["campos_json"])
    except (ValueError, TypeError):
        return None


def tarjeta_campos(campos: dict) -> str:
    """Render the LLM fields as a card with labels and chips instead of raw JSON."""
    partes = ["<div class='card'><h4>🤖 Fields extracted by the LLM</h4>"]
    for clave, valor in campos.items():
        if clave == "modalidad":
            continue
        if valor in (None, "", []):
            contenido = "<span class='nulo'>null — not present in the text</span>"
        elif isinstance(valor, list):
            contenido = "".join(f"<span class='etiqueta'>“{html.escape(str(v))}”</span>" for v in valor)
        else:
            contenido = html.escape(str(valor))
        partes.append(f"<div class='campo'><b>{html.escape(clave.replace('_', ' '))}</b>{contenido}</div>")
    partes.append("</div>")
    return "".join(partes)


def burbujas(texto_asr: str, termino: str, cabecera: str) -> str:
    """Render '[HABLANTE_n] ...' turns as an iMessage-style conversation, one side per speaker."""
    turnos = re.split(r"\[HABLANTE_(\d+)\]", texto_asr)
    salida = [f"<div class='chat'><div class='chat-top'>{html.escape(cabecera)}</div>"]
    for i in range(1, len(turnos), 2):
        n = int(turnos[i])
        clase = "recibido" if n == 1 else ("enviado" if n == 2 else "tercero")
        salida.append(f"<div class='burbuja {clase}'><small>Speaker {n}</small>"
                      f"{resaltar(turnos[i + 1].strip(), termino)}</div>")
    if len(turnos) == 1:
        salida.append(f"<div class='burbuja recibido'>{resaltar(texto_asr, termino)}</div>")
    salida.append("<div class='limpiar'></div></div>")
    return "".join(salida)


# ───────────────────────────────────────────────────────── sidebar filters
with st.sidebar:
    st.markdown("<div class='logo'>Voces <span>&</span><br>Documentos</div>", unsafe_allow_html=True)
    st.caption("Peruvian archive · OCR + ASR + LLM")
    st.divider()
    busqueda = st.text_input("🔍 Search the OCR and ASR texts", placeholder="e.g. biblioteca, ambiental")
    tipos = st.multiselect("📄 Document type", list(COLORES_TIPO), default=list(COLORES_TIPO))
    modelos_disponibles = sorted(comparativa["modelo"].unique()) if not comparativa.empty else []
    modelos = st.multiselect("🧠 Evaluated models", modelos_disponibles, default=modelos_disponibles)
    entrevistas = st.multiselect("🎙️ Interview", sorted(transcripciones["Interview"].unique()),
                                 default=sorted(transcripciones["Interview"].unique()))
    st.divider()
    st.caption("🔒 Names and direct identifiers appear as labels such as [PERSONA_3] or [TELEFONO]. "
               "Interview audio is confidential and never published.")

docs_f = documentos[documentos["Type"].isin(tipos)]
clips_f = transcripciones[transcripciones["Interview"].isin(entrevistas)]
if busqueda:
    docs_f = docs_f[docs_f["texto_ocr"].str.contains(busqueda, case=False, regex=False)]
    clips_f = clips_f[clips_f["texto_asr"].str.contains(busqueda, case=False, regex=False)]
comp_f = comparativa[comparativa["modelo"].isin(modelos)] if not comparativa.empty else comparativa

# ───────────────────────────────────────────────────────── hero
st.markdown(f"""
<div class="hero">
  <div class="kicker">Data Science with Python · Task 2</div>
  <h1>Can scanned documents and recorded interviews become a searchable text archive?</h1>
  <p>An open-model pipeline turns Peruvian documents and research interviews into structured text:
  PaddleOCR reads the images, faster-whisper transcribes the voices, personal data are pseudonymized,
  every model is scored against manual transcriptions, and an LLM catalogues each record.</p>
  <span class="chip">📄 {len(documentos)} documents</span>
  <span class="chip">🎙️ {transcripciones['minutos'].sum():.0f} min of interviews</span>
  <span class="chip">🧪 {comparativa['modelo'].nunique() if not comparativa.empty else 0} models compared</span>
  <span class="chip">✅ human-audited LLM fields</span>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────── key indicators
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📄 Documents", len(docs_f), help="Documents processed, after applying the sidebar filters")
c2.metric("🎙️ Minutes", f"{clips_f['minutos'].sum():.1f}", help="Minutes of interview audio transcribed")
if not comp_f.empty:
    cer = comp_f[comp_f["metrica"] == "CER"]
    wer = comp_f[comp_f["metrica"] == "WER"]
    if not cer.empty:
        mejor = cer.loc[cer["valor"].idxmin()]
        c3.metric("🔤 Best CER", f"{mejor['valor']:.1%}", help=f"Pooled CER on 10 documents · {mejor['modelo']}")
    if not wer.empty:
        mejor = wer.loc[wer["valor"].idxmin()]
        c4.metric("🗣️ Best WER", f"{mejor['valor']:.1%}", help=f"Pooled WER on 10 clips · {mejor['modelo']}")
if not auditoria.empty:
    correctas = int(pd.to_numeric(auditoria["correcta"]).sum())
    c5.metric("🤝 LLM audit", f"{correctas}/{len(auditoria)}", f"{correctas / len(auditoria):.0%} agreement",
              help="Extractions judged completely correct by a human reviewer")

if busqueda:
    st.info(f"🔍 **“{busqueda}”** appears in **{len(docs_f)} documents** and **{len(clips_f)} audio clips**. "
            "Matches are highlighted in the explorers.")

st.write("")
tab_resumen, tab_docs, tab_audio, tab_datos = st.tabs(
    ["📊  Results", "📄  Documents", "🎙️  Audio", "🗂️  Data"])

# ───────────────────────────────────────────────────────── results
with tab_resumen:
    izq, der = st.columns(2)
    with izq, st.container(border=True):
        conteo = docs_f["Type"].value_counts().reindex(COLORES_TIPO).dropna().rename_axis("Type")
        conteo = conteo.reset_index(name="n")
        fig = px.bar(conteo, x="Type", y="n", color="Type", text="n", color_discrete_map=COLORES_TIPO)
        fig.update_traces(showlegend=False, textposition="outside", cliponaxis=False,
                          hovertemplate="%{x}: %{y} documents<extra></extra>")
        fig.update_layout(xaxis_title="", yaxis_title="Documents", yaxis_range=[0, conteo["n"].max() * 1.25])
        st.plotly_chart(estilo(fig, "Three kinds of Peruvian documents",
                               "Documents per type matching the current filters"),
                        use_container_width=True, theme="streamlit")
    with der, st.container(border=True):
        minutos = clips_f.groupby("Interview", as_index=False)["minutos"].sum()
        fig = px.bar(minutos, x="Interview", y="minutos", text_auto=".1f")
        fig.update_traces(marker_color=MORADO, textposition="outside", cliponaxis=False,
                          hovertemplate="%{x}: %{y:.1f} min<extra></extra>")
        fig.update_layout(xaxis_title="", yaxis_title="Minutes", yaxis_range=[0, minutos["minutos"].max() * 1.25])
        st.plotly_chart(estilo(fig, "Six interviews, evenly weighted",
                               "Minutes of transcribed audio per interview"),
                        use_container_width=True, theme="streamlit")

    if not eval_ocr.empty:
        izq, der = st.columns(2)
        with izq, st.container(border=True):
            ocr = eval_ocr[eval_ocr["modelo"].isin(modelos)].copy()
            ocr["Type"] = ocr["tipo"].map(ETIQUETAS_TIPO)
            por_tipo = ocr.groupby(["Type", "modelo"], as_index=False)["cer"].mean()
            fig = px.bar(por_tipo, x="Type", y="cer", color="modelo", barmode="group",
                         category_orders={"Type": list(COLORES_TIPO)},
                         color_discrete_sequence=COLORES_MODELO, text_auto=".0%")
            fig.update_traces(textposition="outside", textangle=0, cliponaxis=False)
            fig.update_layout(xaxis_title="", yaxis_title="Mean CER", yaxis_tickformat=".0%",
                              yaxis_range=[0, por_tipo["cer"].max() * 1.18])
            st.plotly_chart(estilo(fig, "No single OCR model wins every document type",
                                   "Character error rate by type and model · lower is better", alto=420),
                            use_container_width=True, theme="streamlit")
        with der, st.container(border=True):
            asr = eval_asr[eval_asr["modelo"].isin(modelos)]
            por_clip = asr.groupby(["id", "modelo"], as_index=False)["wer"].mean()
            fig = px.bar(por_clip, x="id", y="wer", color="modelo", barmode="group",
                         color_discrete_sequence=COLORES_MODELO)
            fig.update_layout(xaxis_title="", yaxis_title="WER", yaxis_tickformat=".0%",
                              yaxis_range=[0, por_clip["wer"].max() * 1.15])
            st.plotly_chart(estilo(fig, "Recording quality matters more than the model",
                                   "Word error rate per evaluation clip · lower is better", alto=420),
                            use_container_width=True, theme="streamlit")

    if not comp_f.empty:
        with st.container(border=True):
            st.markdown("<div class='seccion titulo'>🏆 Model comparison on the same evaluation samples</div>",
                        unsafe_allow_html=True)
            st.markdown("<div class='nota'>Pooled error over 10 documents (CER) or 10 clips (WER), "
                        "mean processing time per file and real-time factor (processing time ÷ audio duration).</div>",
                        unsafe_allow_html=True)
            tabla = comp_f.rename(columns={"modalidad": "Modality", "modelo": "Model", "metrica": "Metric",
                                           "valor": "Error", "segundos_por_archivo": "Seconds per file",
                                           "rtf": "RTF", "ejecucion": "Runs on"})
            tabla["RTF"] = tabla["RTF"].map(lambda v: "—" if v in ("", None) or pd.isna(v) else f"{float(v):.2f}")
            st.dataframe(tabla, use_container_width=True, hide_index=True, column_config={
                "Error": st.column_config.ProgressColumn("Error (lower is better)", format="%.3f",
                                                         min_value=0, max_value=1),
                "Seconds per file": st.column_config.NumberColumn(format="%.1f s"),
            })

# ───────────────────────────────────────────────────────── document explorer
with tab_docs:
    if docs_f.empty:
        st.warning("No document matches the current filters.")
    else:
        indice_docs = docs_f.set_index("id")
        elegido = st.selectbox("Choose a document", docs_f["id"],
                               format_func=lambda i: f"{ICONOS_TIPO[indice_docs.loc[i, 'Type']]}  {i} · {indice_docs.loc[i, 'Type']}")
        doc = indice_docs.loc[elegido]
        izq, der = st.columns([3, 2])
        with izq:
            st.markdown(f"<span class='etiqueta'>{ICONOS_TIPO[doc['Type']]} {doc['Type']}</span>"
                        f"<span class='etiqueta'>⚙️ {html.escape(doc['modelo_ocr'])}</span>"
                        f"<span class='etiqueta'>🔤 {len(doc['texto_ocr']):,} characters</span>",
                        unsafe_allow_html=True)
            st.markdown(f"<div class='card'><h4>📝 OCR text (pseudonymized)</h4>"
                        f"<div class='texto'>{resaltar(doc['texto_ocr'], busqueda)}</div></div>",
                        unsafe_allow_html=True)
            if doc["texto_referencia"]:
                st.markdown(f"<div class='card'><h4>✍️ Manual reference transcription</h4>"
                            f"<div class='texto'>{resaltar(doc['texto_referencia'], busqueda)}</div></div>",
                            unsafe_allow_html=True)
                fila = eval_ocr[eval_ocr["id"] == elegido] if not eval_ocr.empty else pd.DataFrame()
                if not fila.empty:
                    columnas = st.columns(len(fila))
                    for col, (_, r) in zip(columnas, fila.iterrows()):
                        col.metric(f"CER · {r['modelo']}", f"{r['cer']:.1%}")
            st.caption(f"Source: {doc['fuente']}")
        with der:
            imagen = next(iter(sorted(EJEMPLOS.glob(f"{elegido}.*"))), None) if EJEMPLOS.exists() else None
            if imagen is not None and imagen.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                st.image(str(imagen), caption="Original photograph, published with no personal data",
                         use_container_width=True)
            else:
                st.markdown("<div class='card nota'>🖼️ Image not published: it may contain personal data "
                            "or third-party content. Text and metadata remain available.</div>",
                            unsafe_allow_html=True)
            campos = campos_llm(elegido)
            if campos:
                st.markdown(tarjeta_campos(campos), unsafe_allow_html=True)

# ───────────────────────────────────────────────────────── audio explorer
with tab_audio:
    demo = next((p for p in sorted(EJEMPLOS.glob("demo_voz.*")) if p.suffix != ".txt"), None) \
        if EJEMPLOS.exists() else None
    if demo is not None:
        with st.container(border=True):
            st.markdown("<div class='seccion titulo'>🎧 Authorized example · self-recorded voice</div>", unsafe_allow_html=True)
            st.audio(str(demo))
            texto_demo = EJEMPLOS / "demo_voz.txt"
            if texto_demo.exists():
                st.markdown(burbujas("[HABLANTE_2] " + texto_demo.read_text(encoding="utf-8"), "",
                                     "Transcribed by faster-whisper small"), unsafe_allow_html=True)
    st.caption("🔒 The research interviews are confidential: their audio is never published. "
               "Their pseudonymized transcripts can be explored below.")

    if clips_f.empty:
        st.warning("No clip matches the current filters.")
    else:
        indice_clips = clips_f.set_index("id")
        elegido = st.selectbox("Choose a clip", clips_f["id"],
                               format_func=lambda i: f"🎙️  {i} · {indice_clips.loc[i, 'Interview']}"
                                                     + ("  ✍️ evaluated" if indice_clips.loc[i, "texto_referencia"] else ""))
        clip = indice_clips.loc[elegido]
        a, b, c, d = st.columns(4)
        a.metric("⏱️ Duration", f"{float(clip['duracion_seg']):.0f} s")
        b.metric("👥 Speakers detected", int(clip["n_hablantes"]))
        c.metric("💬 Words", len(re.sub(r"\[HABLANTE_\d+\]", "", clip["texto_asr"]).split()))
        d.metric("🎙️ Interview", clip["Interview"].replace("Interview ", "#"))
        izq, der = st.columns([3, 2])
        with izq:
            st.markdown("<div class='seccion titulo'>💬 Transcript with speaker turns</div>", unsafe_allow_html=True)
            st.markdown(burbujas(clip["texto_asr"], busqueda,
                                 f"{clip['Interview']} · {clip['modelo_asr']} · pseudonymized"),
                        unsafe_allow_html=True)
        with der:
            if clip["texto_referencia"]:
                st.markdown(f"<div class='card'><h4>✍️ Manual reference</h4>"
                            f"<div class='texto'>{resaltar(clip['texto_referencia'], busqueda)}</div></div>",
                            unsafe_allow_html=True)
            if not eval_asr.empty:
                fila = eval_asr[eval_asr["id"] == elegido]
                if not fila.empty:
                    st.markdown("<div class='seccion titulo'>⚖️ Model comparison on this clip</div>", unsafe_allow_html=True)
                    for _, r in fila.iterrows():
                        st.markdown(f"<div class='card'><h4>{html.escape(r['modelo'])} · WER {r['wer']:.1%}</h4>"
                                    f"<div class='texto'>{resaltar(r['texto'], busqueda)}</div></div>",
                                    unsafe_allow_html=True)
            campos = campos_llm(elegido)
            if campos:
                st.markdown(tarjeta_campos(campos), unsafe_allow_html=True)

# ───────────────────────────────────────────────────────── data table
with tab_datos:
    vista = st.radio("Table", ["📄 Documents", "🎙️ Audio clips"], horizontal=True, label_visibility="collapsed")
    if vista.endswith("Documents"):
        tabla = docs_f[["id", "tipo", "fuente", "texto_ocr", "modelo_ocr", "texto_referencia"]]
        nombre = "documentos_filtrados.csv"
    else:
        tabla = clips_f[["id", "entrevista", "duracion_seg", "n_hablantes", "texto_asr",
                         "modelo_asr", "texto_referencia"]]
        nombre = "transcripciones_filtradas.csv"
    st.dataframe(tabla, use_container_width=True, hide_index=True, height=460)
    st.download_button("⬇️ Download filtered CSV", tabla.to_csv(index=False).encode("utf-8"),
                       file_name=nombre, mime="text/csv", type="primary")
    st.caption("Only reviewed and pseudonymized texts are published.")
