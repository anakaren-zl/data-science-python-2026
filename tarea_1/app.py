import html
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# =============================================
#  CONFIGURATION
# =============================================

st.set_page_config(page_title="Peruvian News Classifier", page_icon="📰", layout="wide")

ruta_noticias = "datos/noticias.csv"
ruta_metricas = "modelo/metricas.json"
ruta_modelo = "modelo"

# Readable names for the interface; the official labels remain unchanged in the data.
nombres_categorias = {
    "politica": "Politics",
    "economia": "Economy",
    "deportes": "Sports",
    "ciencia_tecnologia": "Science & technology",
}

# Same blue scale used in the notebooks, so the dashboard keeps a consistent style.
escala_azules = ["#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]


# =============================================
#  VISUAL STYLE
# =============================================

# Custom CSS gives the dashboard a clean, minimalist look:
# a sans-serif font, generous white space, soft cards, tinted section titles and a moving news ticker.
estilo = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"], [data-testid="stMarkdownContainer"] p, button, input, textarea {
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stAppViewContainer"] { background-color: #fafaf9; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background-color: #f4f5f7; border-right: 1px solid #e5e7eb; }
[data-testid="stMarkdownContainer"] p { color: #475569; line-height: 1.7; }

/* Elements fade in softly when the page loads */
@keyframes aparecer { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.block-container { animation: aparecer 0.7s ease-out; max-width: 1150px; }

/* Header */
.cabecera { margin: 10px 0 6px 0; }
.cabecera .etiqueta-superior { font-size: 0.75rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: #1c5cab; }
.cabecera .titulo { font-size: 2.6rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.15; color: #0f172a; margin-top: 8px; }
.cabecera .subtitulo { font-size: 1.05rem; font-weight: 300; color: #64748b; margin-top: 6px; }

/* Moving news ticker */
.cinta { display: flex; align-items: center; overflow: hidden; background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 999px; margin: 22px 0 18px 0; }
.cinta .etiqueta { display: flex; align-items: center; gap: 8px; background-color: #0d366b; color: #ffffff; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em; padding: 9px 16px; border-radius: 999px; white-space: nowrap; z-index: 1; }
.cinta .punto { width: 7px; height: 7px; border-radius: 50%; background-color: #5598e7; animation: latido 1.6s ease-in-out infinite; }
.cinta .texto { white-space: nowrap; font-size: 0.88rem; color: #334155; padding: 9px 0; animation: desplazar 100s linear infinite; }
.cinta:hover .texto { animation-play-state: paused; }
@keyframes desplazar { from { transform: translateX(100vw); } to { transform: translateX(-100%); } }
@keyframes latido { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Tinted section titles */
.seccion { display: inline-block; background-color: #eef3fb; color: #0d366b; font-size: 0.95rem; font-weight: 600; letter-spacing: 0.02em; padding: 8px 16px; border-radius: 10px; margin: 30px 0 14px 0; }

/* Key indicators as soft cards */
[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px 22px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04); transition: transform 0.25s, box-shadow 0.25s; }
[data-testid="stMetric"]:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(13, 54, 107, 0.08); }
[data-testid="stMetricLabel"] p { color: #64748b; font-size: 0.85rem; }
[data-testid="stMetricValue"] { color: #0d366b; font-weight: 600; }

/* Result card of the live classifier */
.resultado { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 18px 22px; margin: 14px 0; animation: aparecer 0.5s ease-out; }
.resultado .rotulo { font-size: 0.75rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: #94a3b8; }
.resultado .categoria { font-size: 1.9rem; font-weight: 700; letter-spacing: -0.02em; color: #0d366b; margin: 4px 0; }
.resultado .confianza { color: #475569; }
/* News cards of the reading view, where long texts wrap naturally */
.noticia { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 16px 20px; margin-bottom: 12px; transition: box-shadow 0.25s; }
.noticia:hover { box-shadow: 0 6px 18px rgba(13, 54, 107, 0.07); }
.noticia .meta { font-size: 0.78rem; color: #94a3b8; margin-bottom: 6px; }
.noticia .pastilla { background-color: #eef3fb; color: #0d366b; font-weight: 600; padding: 3px 10px; border-radius: 999px; margin-right: 10px; }
.noticia .titular { font-size: 1.05rem; font-weight: 600; color: #0f172a; line-height: 1.45; }
.noticia .bajada { font-size: 0.9rem; color: #64748b; line-height: 1.6; margin: 6px 0 8px 0; }
.noticia a { font-size: 0.85rem; font-weight: 500; color: #1c5cab; text-decoration: none; }

/* Primary buttons in navy with white text, for strong contrast */
button[kind="primary"], [data-testid="stBaseButton-primary"] { background-color: #0d366b !important; border: none !important; color: #ffffff !important; font-weight: 600 !important; border-radius: 10px !important; padding: 0.55rem 1.4rem !important; transition: transform 0.2s, box-shadow 0.2s; }
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(13, 54, 107, 0.25); }

/* Blue block of the live classifier */
.st-key-clasificador { background: linear-gradient(135deg, #0d366b 0%, #1c5cab 100%); border-radius: 22px; padding: 30px 32px 26px 32px; margin-top: 34px; box-shadow: 0 12px 30px rgba(13, 54, 107, 0.18); }
.clasificador-titulo { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; color: #ffffff; }
.clasificador-subtitulo { font-size: 0.95rem; font-weight: 300; color: #c7d8f0; margin: 4px 0 8px 0; }
.st-key-clasificador label p { color: #dbe7f7 !important; }
.st-key-clasificador textarea { background-color: #ffffff !important; color: #0f172a !important; border-radius: 12px !important; }
.st-key-clasificador button[kind="primary"], .st-key-clasificador [data-testid="stBaseButton-primary"] { background-color: #ffffff !important; color: #0d366b !important; }

/* Probability bars that fill up from zero */
@keyframes llenar { from { width: 0; } }
.barras { margin-top: 14px; }
.barra-fila { display: flex; align-items: center; gap: 12px; margin: 9px 0; }
.barra-nombre { width: 170px; font-size: 0.9rem; color: #334155; }
.barra-pista { flex: 1; height: 10px; background-color: #eef3fb; border-radius: 999px; overflow: hidden; }
.barra-relleno { height: 100%; background: linear-gradient(90deg, #5598e7, #0d366b); border-radius: 999px; animation: llenar 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
.barra-valor { width: 44px; text-align: right; font-size: 0.9rem; font-weight: 600; color: #0d366b; }
</style>
"""
st.markdown(estilo, unsafe_allow_html=True)


def titulo_seccion(texto):
    """Display a section title inside a soft tinted box."""
    st.markdown(f'<div class="seccion">{texto}</div>', unsafe_allow_html=True)


# =============================================
#  DATA AND MODEL LOADING
# =============================================

# Cached functions run only once, instead of reloading the data on every interaction.
@st.cache_data
def cargar_noticias():
    """Read the dataset built in Part 1."""
    return pd.read_csv(ruta_noticias)


@st.cache_data
def cargar_metricas():
    """Read the metrics computed in Part 2."""
    with open(ruta_metricas) as archivo:
        return json.load(archivo)


@st.cache_resource
def cargar_clasificador():
    """Load the fine-tuned DistilBERT model saved in Part 2."""
    from transformers import pipeline
    return pipeline("text-classification", model=ruta_modelo, tokenizer=ruta_modelo, top_k=None)


noticias = cargar_noticias()
metricas = cargar_metricas()


# =============================================
#  HEADER
# =============================================

st.markdown(
    """
    <div class="cabecera">
        <div class="etiqueta-superior">Data Science with Python · Diplomado PUCP 2026</div>
        <div class="titulo">Can Peruvian news headlines be turned into a news classifier?</div>
        <div class="subtitulo">383 headlines from El Comercio · 6–18 October 2026 · Fine-tuned DistilBERT</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# The ten most recent headlines scroll across the screen, like a news ticker.
ultimos_titulares = noticias.sort_values("fecha", ascending=False)["titular"].head(10)
texto_cinta = "  ◆  ".join(html.escape(titular) for titular in ultimos_titulares)
st.markdown(
    f'<div class="cinta"><div class="etiqueta"><span class="punto"></span>LATEST</div><div class="texto">{texto_cinta}</div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    This dashboard presents the results of a three-stage project. First, **383 headlines** were collected
    from the section sitemaps of **El Comercio** (6–18 October 2026) and mapped onto four categories.
    Subsequently, a zero-shot model and an LLM (Gemini) were evaluated as reference approaches, and the
    LLM labels were audited manually. Finally, a lightweight **DistilBERT** model was fine-tuned on the
    headlines and evaluated on an isolated test set. The classifier below lets you test it live.
    """
)


# =============================================
#  SIDEBAR FILTERS
# =============================================

st.sidebar.header("Filters")

medios_disponibles = sorted(noticias["medio"].unique())
medios_elegidos = st.sidebar.multiselect("Outlet", medios_disponibles, default=medios_disponibles)

categorias_disponibles = list(nombres_categorias.keys())
categorias_elegidas = st.sidebar.multiselect(
    "Category",
    categorias_disponibles,
    default=categorias_disponibles,
    format_func=lambda etiqueta: nombres_categorias[etiqueta],
)

noticias_filtradas = noticias[
    noticias["medio"].isin(medios_elegidos) & noticias["etiqueta"].isin(categorias_elegidas)
]

st.sidebar.caption(f"{len(noticias_filtradas)} of {len(noticias)} news items selected.")


# =============================================
#  KEY INDICATORS
# =============================================

titulo_seccion("Key indicators")

columna_1, columna_2, columna_3 = st.columns(3)
columna_1.metric("News items collected", len(noticias))
columna_2.metric("Macro F1 on the test set", f"{metricas['f1_macro_modelo']:.2f}")
columna_3.metric("LLM–human agreement (audit)", f"{metricas['acuerdo_llm_humano']:.0%}")


# =============================================
#  CHART AND DATA TABLE
# =============================================

titulo_seccion("Distribution of the selected news by category")

conteo_categorias = noticias_filtradas["etiqueta"].map(nombres_categorias).value_counts().reset_index()
conteo_categorias.columns = ["categoria", "noticias"]

valores = conteo_categorias["noticias"].tolist()
nombres = conteo_categorias["categoria"].tolist()
colores = dict(color=valores, colorscale=escala_azules)

# The chart starts with empty bars and a single animation frame raises them to their real values,
# so the bars grow every time the page loads or a filter changes.
fig = go.Figure(
    data=[go.Bar(x=nombres, y=[0] * len(valores), marker=colores, hoverinfo="skip")],
    frames=[go.Frame(data=[go.Bar(
        x=nombres, y=valores, text=valores, marker=colores,
        textposition="inside", insidetextanchor="middle", textfont=dict(size=18, color="white"),
        hovertemplate="%{x}: %{y} news items<extra></extra>",
    )])],
)
fig.update_layout(
    template="plotly_white", height=430, margin=dict(l=40, r=20, t=20, b=40),
    yaxis=dict(title="Number of news items", range=[0, max(valores + [1]) * 1.12], gridcolor="#eeeeee"),
    paper_bgcolor="#fafaf9", plot_bgcolor="#fafaf9",
    font=dict(family="Inter, sans-serif", size=13, color="#334155"),
)

# Plotly's own HTML export can play the animation automatically, unlike st.plotly_chart.
grafico_html = fig.to_html(
    include_plotlyjs="cdn",
    auto_play=True,
    animation_opts={"frame": {"duration": 900}, "transition": {"duration": 900, "easing": "cubic-out"}},
    config={"displayModeBar": False},
)
components.html(grafico_html, height=450)

titulo_seccion("Explore the news")

# Two views: an interactive table to sort and search, and a reading view where long texts wrap.
pestana_tabla, pestana_lectura = st.tabs(["Table", "Reading view"])

with pestana_tabla:
    columnas_tabla = ["titular", "etiqueta", "fecha", "url", "bajada", "seccion_original"]
    st.dataframe(
        noticias_filtradas[columnas_tabla],
        width="stretch",
        hide_index=True,
        # Readable headers and a wide headline column; the URL becomes a clickable link.
        column_config={
            "titular": st.column_config.TextColumn("Headline", width="large"),
            "etiqueta": st.column_config.TextColumn("Category", width="small"),
            "fecha": st.column_config.TextColumn("Date", width="small"),
            "url": st.column_config.LinkColumn("Link", display_text="Open article", width="small"),
            "bajada": st.column_config.TextColumn("Summary", width="large"),
            "seccion_original": st.column_config.TextColumn("Section", width="medium"),
        },
    )
    st.caption("Tip: hover over a cell to read its full text, or switch to the reading view.")

with pestana_lectura:
    noticias_recientes = noticias_filtradas.sort_values("fecha", ascending=False).head(30)
    st.caption(f"The {len(noticias_recientes)} most recent news items of the current selection.")

    for _, fila in noticias_recientes.iterrows():
        st.markdown(
            f"""
            <div class="noticia">
                <div class="meta"><span class="pastilla">{nombres_categorias[fila['etiqueta']]}</span>{fila['fecha']}</div>
                <div class="titular">{html.escape(fila['titular'])}</div>
                <div class="bajada">{html.escape(str(fila['bajada']))}</div>
                <a href="{fila['url']}" target="_blank">Read the full article →</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.download_button(
    "Download the selected news (CSV)",
    data=noticias_filtradas.to_csv(index=False).encode("utf-8"),
    file_name="noticias_filtradas.csv",
    mime="text/csv",
)


# =============================================
#  LIVE CLASSIFIER
# =============================================

# The key turns into a CSS class, which paints this whole block in blue.
with st.container(key="clasificador"):
    st.markdown(
        """
        <div class="clasificador-titulo">Try the classifier with a new headline</div>
        <div class="clasificador-subtitulo">Write any headline in Spanish and the fine-tuned DistilBERT will predict its category.</div>
        """,
        unsafe_allow_html=True,
    )

    titular_nuevo = st.text_area(
        "Write or paste a headline in Spanish:",
        placeholder="Ej.: Congreso aprueba nuevo retiro de fondos de AFP",
    )

    if st.button("Classify headline", type="primary"):
        if titular_nuevo.strip() == "":
            st.warning("Please write a headline first.")
        else:
            # The model weights are not stored on GitHub (>100 MB), so they must exist locally.
            try:
                clasificador = cargar_clasificador()
            except Exception:
                st.error(
                    "The model could not be loaded. Run `02_clasificacion.ipynb` first, "
                    "so that the trained weights are saved in the `modelo/` folder."
                )
                st.stop()

            # A one-item list always returns one list of scores per headline.
            resultados = clasificador([titular_nuevo])[0]
            probabilidades = pd.DataFrame(resultados)
            probabilidades["categoria"] = probabilidades["label"].map(nombres_categorias)
            probabilidades = probabilidades.sort_values("score", ascending=False)

            # Each probability is drawn as a bar that fills up from zero when it appears.
            barras = ""
            for _, fila in probabilidades.iterrows():
                barras += (
                    f'<div class="barra-fila"><span class="barra-nombre">{fila["categoria"]}</span>'
                    f'<div class="barra-pista"><div class="barra-relleno" style="width: {fila["score"]:.1%};"></div></div>'
                    f'<span class="barra-valor">{fila["score"]:.0%}</span></div>'
                )

            mejor = probabilidades.iloc[0]
            st.markdown(
                f"""
                <div class="resultado">
                    <div class="rotulo">Predicted category</div>
                    <div class="categoria">{mejor['categoria']}</div>
                    <div class="confianza">Confidence: <b>{mejor['score']:.0%}</b></div>
                    <div class="barras">{barras}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.caption(
    "Source: El Comercio section sitemaps, downloaded on 18 October 2026. "
    "Model: distilbert-base-multilingual-cased, fine-tuned on 268 headlines."
)