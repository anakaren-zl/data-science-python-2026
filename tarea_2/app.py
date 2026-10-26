"""Task 2 dashboard: Peruvian voices and documents, from scanned archive to searchable text.

The app only reads the CSV files produced by the two notebooks. No OCR, ASR or LLM model runs
on the server, so it stays light enough for Streamlit Community Cloud.

    streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATOS = Path(__file__).parent / "datos"
EJEMPLOS = DATOS / "ejemplos"

# Shared visual identity with the notebooks: colour-blind-safe palette, quiet axes.
ETIQUETAS_TIPO = {"impreso": "Printed", "foto": "Photographed", "manuscrito": "Handwritten"}
COLORES_TIPO = {"Printed": "#2a78d6", "Photographed": "#eb6834", "Handwritten": "#1baf7a"}
AZUL, NARANJA, GRIS, REJILLA = "#2a78d6", "#eb6834", "#52514e", "#e8e7e3"

st.set_page_config(page_title="Peruvian voices and documents", page_icon="🎙️", layout="wide")


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


def estilo(fig, titulo, subtitulo):
    """Common layout: bold analytical headline, grey subtitle, light grid, rounded bars."""
    fig.update_layout(
        template="simple_white",
        title=dict(text=f"<b>{titulo}</b>", x=0.01, xanchor="left", font=dict(size=17),
                   subtitle=dict(text=subtitulo, font=dict(size=12, color=GRIS))),
        margin=dict(l=60, r=20, t=90, b=60), bargap=0.25, barcornerradius=4,
        legend=dict(orientation="h", y=-0.25, x=0.01, title_text=""),
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_yaxes(showgrid=True, gridcolor=REJILLA, zeroline=False, ticks="")
    fig.update_xaxes(showgrid=False, ticks="")
    return fig


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


# ───────────────────────────────────────────────────────── header
st.title("Can scanned documents and recorded interviews become a searchable text archive?")
st.markdown(
    "This dashboard explores a pipeline that turns **25 Peruvian documents** (printed pages of "
    "*El Peruano*, photographs and handwritten notes) and **35 minutes of research interviews** "
    "into structured, searchable text. Text was extracted with **PaddleOCR** and **faster-whisper**, "
    "pseudonymized, evaluated against manual transcriptions (CER / WER) and summarised with an LLM. "
    "All results were computed in advance in the project notebooks."
)

# ───────────────────────────────────────────────────────── sidebar filters
with st.sidebar:
    st.header("Filters")
    busqueda = st.text_input("Search the OCR and ASR texts", placeholder="e.g. biblioteca, ambiental")
    tipos = st.multiselect("Document type", list(COLORES_TIPO), default=list(COLORES_TIPO))
    modelos_disponibles = sorted(comparativa["modelo"].unique()) if not comparativa.empty else []
    modelos = st.multiselect("Evaluated models", modelos_disponibles, default=modelos_disponibles)
    entrevistas = st.multiselect("Interview", sorted(transcripciones["Interview"].unique()),
                                 default=sorted(transcripciones["Interview"].unique()))
    st.caption("Names and direct identifiers appear as labels such as [PERSONA_3] or [TELEFONO].")

docs_f = documentos[documentos["Type"].isin(tipos)]
clips_f = transcripciones[transcripciones["Interview"].isin(entrevistas)]
if busqueda:
    docs_f = docs_f[docs_f["texto_ocr"].str.contains(busqueda, case=False, regex=False)]
    clips_f = clips_f[clips_f["texto_asr"].str.contains(busqueda, case=False, regex=False)]
comp_f = comparativa[comparativa["modelo"].isin(modelos)] if not comparativa.empty else comparativa

# ───────────────────────────────────────────────────────── key indicators
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Documents processed", len(docs_f), help="After applying the sidebar filters")
c2.metric("Minutes of audio transcribed", f"{clips_f['minutos'].sum():.1f}")
if not comp_f.empty:
    cer = comp_f[comp_f["metrica"] == "CER"]
    wer = comp_f[comp_f["metrica"] == "WER"]
    if not cer.empty:
        mejor = cer.loc[cer["valor"].idxmin()]
        c3.metric("Best CER (10 documents)", f"{mejor['valor']:.1%}", help=mejor["modelo"])
    if not wer.empty:
        mejor = wer.loc[wer["valor"].idxmin()]
        c4.metric("Best WER (10 clips)", f"{mejor['valor']:.1%}", help=mejor["modelo"])
if not auditoria.empty:
    correctas = int(pd.to_numeric(auditoria["correcta"]).sum())
    c5.metric("LLM vs human audit", f"{correctas}/{len(auditoria)}", f"{correctas / len(auditoria):.0%} agreement")

if busqueda:
    st.info(f"'{busqueda}' appears in {len(docs_f)} documents and {len(clips_f)} audio clips.")

tab_resumen, tab_docs, tab_audio, tab_datos = st.tabs(
    ["📊 Results", "📄 Documents", "🎙️ Audio", "🗂️ Data"])

# ───────────────────────────────────────────────────────── results
with tab_resumen:
    izq, der = st.columns(2)
    with izq:
        conteo = docs_f["Type"].value_counts().reindex(COLORES_TIPO).dropna().rename_axis("Type")
        conteo = conteo.reset_index(name="n")
        fig = px.bar(conteo, x="Type", y="n", color="Type", text="n", color_discrete_map=COLORES_TIPO)
        fig.update_traces(showlegend=False, hovertemplate="%{x}: %{y} documents<extra></extra>")
        fig.update_layout(xaxis_title="", yaxis_title="Documents")
        st.plotly_chart(estilo(fig, "Three kinds of Peruvian documents",
                               "Documents per type matching the current filters"), use_container_width=True)
    with der:
        minutos = clips_f.groupby("Interview", as_index=False)["minutos"].sum()
        fig = px.bar(minutos, x="Interview", y="minutos", text_auto=".1f")
        fig.update_traces(marker_color=AZUL, hovertemplate="%{x}: %{y:.1f} min<extra></extra>")
        fig.update_layout(xaxis_title="", yaxis_title="Minutes")
        st.plotly_chart(estilo(fig, "Six interviews, evenly weighted",
                               "Minutes of transcribed audio per interview"), use_container_width=True)

    if not eval_ocr.empty:
        izq, der = st.columns(2)
        with izq:
            ocr = eval_ocr[eval_ocr["modelo"].isin(modelos)].copy()
            ocr["Type"] = ocr["tipo"].map(ETIQUETAS_TIPO)
            por_tipo = ocr.groupby(["Type", "modelo"], as_index=False)["cer"].mean()
            fig = px.bar(por_tipo, x="Type", y="cer", color="modelo", barmode="group",
                         category_orders={"Type": list(COLORES_TIPO)},
                         color_discrete_sequence=[AZUL, NARANJA], text_auto=".0%")
            fig.update_layout(xaxis_title="", yaxis_title="Mean CER", yaxis_tickformat=".0%")
            st.plotly_chart(estilo(fig, "Handwriting is where OCR breaks down",
                                   "Character error rate by document type and model (lower is better)"),
                            use_container_width=True)
        with der:
            asr = eval_asr[eval_asr["modelo"].isin(modelos)]
            por_clip = asr.groupby(["id", "modelo"], as_index=False)["wer"].mean()
            fig = px.bar(por_clip, x="id", y="wer", color="modelo", barmode="group",
                         color_discrete_sequence=[AZUL, NARANJA])
            fig.update_layout(xaxis_title="", yaxis_title="WER", yaxis_tickformat=".0%")
            st.plotly_chart(estilo(fig, "Speech recognition error varies by recording",
                                   "Word error rate per evaluation clip and model (lower is better)"),
                            use_container_width=True)
    if not comp_f.empty:
        st.subheader("Model comparison on the same evaluation samples")
        st.dataframe(comp_f, use_container_width=True, hide_index=True)

# ───────────────────────────────────────────────────────── document explorer
with tab_docs:
    if docs_f.empty:
        st.warning("No document matches the current filters.")
    else:
        elegido = st.selectbox("Choose a document", docs_f["id"],
                               format_func=lambda i: f"{i} · {docs_f.set_index('id').loc[i, 'Type']}")
        doc = docs_f.set_index("id").loc[elegido]
        izq, der = st.columns([3, 2])
        with izq:
            st.markdown(f"**Type:** {doc['Type']} · **Model:** {doc['modelo_ocr']}")
            st.markdown(f"**Source:** {doc['fuente']}")
            st.text_area("OCR text (pseudonymized)", doc["texto_ocr"], height=260)
            if doc["texto_referencia"]:
                st.text_area("Manual reference transcription", doc["texto_referencia"], height=180)
                fila = eval_ocr[eval_ocr["id"] == elegido] if not eval_ocr.empty else pd.DataFrame()
                for _, r in fila.iterrows():
                    st.metric(f"CER · {r['modelo']}", f"{r['cer']:.1%}")
        with der:
            imagen = next(iter(sorted(EJEMPLOS.glob(f"{elegido}.*"))), None) if EJEMPLOS.exists() else None
            if imagen is not None and imagen.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                st.image(str(imagen), caption="Original photograph, published with no personal data")
            else:
                st.caption("Image not published (it may contain personal data or third-party content).")
            campos = campos_llm(elegido)
            st.markdown("**Fields extracted by the LLM**")
            if campos:
                st.json(campos)
            else:
                st.caption("No structured extraction available.")

# ───────────────────────────────────────────────────────── audio explorer
with tab_audio:
    st.caption("The interviews are confidential research data: their audio is never published. "
               "Their pseudonymized transcripts can be explored below, and a self-recorded, "
               "authorized example can be played.")
    demo = next(iter(sorted(EJEMPLOS.glob("demo_voz.*"))), None) if EJEMPLOS.exists() else None
    if demo is not None:
        st.markdown("**Authorized example (self-recorded voice)**")
        st.audio(str(demo))
        texto_demo = EJEMPLOS / "demo_voz.txt"
        if texto_demo.exists():
            st.text(texto_demo.read_text(encoding="utf-8"))

    if clips_f.empty:
        st.warning("No clip matches the current filters.")
    else:
        elegido = st.selectbox("Choose a clip", clips_f["id"],
                               format_func=lambda i: f"{i} · {clips_f.set_index('id').loc[i, 'Interview']}")
        clip = clips_f.set_index("id").loc[elegido]
        a, b, c = st.columns(3)
        a.metric("Duration", f"{float(clip['duracion_seg']):.0f} s")
        b.metric("Speakers detected", int(clip["n_hablantes"]))
        c.metric("Words", len(clip["texto_asr"].split()))
        st.markdown(f"**Model:** {clip['modelo_asr']}")
        # One line per speaker turn, so the diarization labels are easy to read.
        turnos = clip["texto_asr"].replace("[HABLANTE_", "\n[HABLANTE_").strip()
        st.text_area("ASR transcript with speaker labels (pseudonymized)", turnos, height=220)
        if clip["texto_referencia"]:
            st.text_area("Manual reference transcription", clip["texto_referencia"], height=150)
        if not eval_asr.empty:
            fila = eval_asr[eval_asr["id"] == elegido]
            if not fila.empty:
                st.markdown("**Model comparison on this clip**")
                for _, r in fila.iterrows():
                    st.markdown(f"*{r['modelo']}* — WER {r['wer']:.1%}")
                    if "texto" in r and r["texto"]:
                        st.caption(r["texto"])
        campos = campos_llm(elegido)
        if campos:
            st.markdown("**Fields extracted by the LLM**")
            st.json(campos)

# ───────────────────────────────────────────────────────── data table
with tab_datos:
    vista = st.radio("Table", ["Documents", "Audio clips"], horizontal=True)
    if vista == "Documents":
        tabla = docs_f[["id", "tipo", "fuente", "texto_ocr", "modelo_ocr", "texto_referencia"]]
        nombre = "documentos_filtrados.csv"
    else:
        tabla = clips_f[["id", "entrevista", "duracion_seg", "n_hablantes", "texto_asr",
                         "modelo_asr", "texto_referencia"]]
        nombre = "transcripciones_filtradas.csv"
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download CSV", tabla.to_csv(index=False).encode("utf-8"),
                       file_name=nombre, mime="text/csv")
    st.caption("Only reviewed and pseudonymized texts are published.")
