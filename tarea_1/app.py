import json

import pandas as pd
import plotly.express as px
import streamlit as st

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

st.title("📰 Can Peruvian news headlines be turned into a news classifier?")

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

columna_1, columna_2, columna_3 = st.columns(3)
columna_1.metric("News items collected", len(noticias))
columna_2.metric("Macro F1 on the test set", f"{metricas['f1_macro_modelo']:.2f}")
columna_3.metric("LLM–human agreement (audit)", f"{metricas['acuerdo_llm_humano']:.0%}")


# =============================================
#  CHART AND DATA TABLE
# =============================================

st.subheader("Distribution of the selected news by category")

conteo_categorias = noticias_filtradas["etiqueta"].map(nombres_categorias).value_counts().reset_index()
conteo_categorias.columns = ["categoria", "noticias"]

fig = px.bar(
    conteo_categorias, x="categoria", y="noticias", color="noticias", text="noticias",
    color_continuous_scale=escala_azules,
    labels={"categoria": "Category", "noticias": "Number of news items"},
)
fig.update_traces(textposition="inside", insidetextanchor="middle", textfont=dict(size=18, color="white"))
fig.update_layout(template="plotly_white", coloraxis_showscale=False, xaxis_title=None)
st.plotly_chart(fig, width="stretch")

st.subheader("Explore the news")

columnas_tabla = ["titular", "bajada", "seccion_original", "fecha", "etiqueta", "url"]
st.dataframe(noticias_filtradas[columnas_tabla], width="stretch", hide_index=True)

st.download_button(
    "⬇️ Download the selected news (CSV)",
    data=noticias_filtradas.to_csv(index=False).encode("utf-8"),
    file_name="noticias_filtradas.csv",
    mime="text/csv",
)


# =============================================
#  LIVE CLASSIFIER
# =============================================

st.subheader("🔎 Try the classifier with a new headline")

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

        mejor = probabilidades.iloc[0]
        st.success(f"Predicted category: **{mejor['categoria']}** (confidence: {mejor['score']:.0%})")

        fig_probabilidades = px.bar(
            probabilidades, x="score", y="categoria", orientation="h", color="score",
            color_continuous_scale=escala_azules, range_color=[0, 1],
            labels={"score": "Probability", "categoria": ""},
        )
        fig_probabilidades.update_layout(
            template="plotly_white", coloraxis_showscale=False,
            yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, 1], tickformat=".0%"),
            height=260,
        )
        st.plotly_chart(fig_probabilidades, width="stretch")

st.caption(
    "Source: El Comercio section sitemaps, downloaded on 18 October 2026. "
    "Model: distilbert-base-multilingual-cased, fine-tuned on 268 headlines."
)