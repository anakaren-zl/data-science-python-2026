# Task 2 — Peruvian voices and documents: from scanned archive to searchable text

**Author:** Ana Karen Zamalloa Lima ([@anakaren-zl](https://github.com/anakaren-zl))
**Course:** Data Science with Python — Diplomado PUCP 2026
**Public dashboard:** https://t2-voces-documentos-peru.streamlit.app/

## 1. Research question

> **Can scanned documents and audio interviews be converted into a structured, searchable text archive?**

Archives of public institutions, community organisations and qualitative research projects often exist only as paper, photographs and recordings. This project builds a reproducible pipeline that turns two such corpora into structured text with open models running on a standard laptop: optical character recognition (OCR) for Peruvian documents and automatic speech recognition (ASR) for research interviews in Peruvian Spanish. The pipeline then protects personal data through pseudonymization, evaluates every model against manual transcriptions, and extracts structured fields with a large language model (LLM) whose output is audited by hand.

| Stage | Methodological focus | Deliverables |
|---|---|---|
| Part 1 | Corpus construction, OCR, ASR with VAD and diarization, pseudonymization, cleaning and EDA | `01_extraccion.ipynb`, `datos/documentos.csv`, `datos/transcripciones.csv`, `datos/fuentes.csv` |
| Part 2 | Manual references, CER/WER baseline, model comparison, LLM extraction and human audit | `02_evaluacion.ipynb`, `datos/extraccion_llm.csv`, `datos/comparativa.csv` |
| Part 3 | Interactive dashboard and deployment | `app.py`, `requirements.txt`, this README |

## 2. Corpus, sources and licences

| Corpus | Content | Source and licence | Collection date |
|---|---|---|---|
| **A. Documents (25)** | 8 printed pages | *El Peruano*, Normas Legales, issue of 24/10/2026 ([link](https://busquedas.elperuano.pe/cuadernillo/NL/20261024)). Legal texts are not subject to copyright in Peru (Legislative Decree 822, art. 9). Pages rendered at 200 dpi. | 24/10/2026 |
| | 8 photographs with shadows or tilt | Original photographs of public signage, packaging, a screen and printed material, taken in Lima for this project. Only images without personal data are shown in the dashboard. | 21–25/10/2026 |
| | 9 handwritten documents | Original photographs of handwritten menus, price boards and personal notes, taken for this project. Personal data were pseudonymized. | 21–25/10/2026 |
| **B. Audio (35 min)** | 6 research interviews in Peruvian Spanish, cut into 70 clips of 30 s (2 clips without speech discarded) | Interviews conducted for an undergraduate thesis on environmental education, with **signed informed consent for academic use**. The audio is confidential and is **not** redistributed; only pseudonymized transcripts are published. | Recorded in 2026; processed 24–25/10/2026 |
| **Authorized audio example** | One short self-recorded clip | Recorded by the author for this dashboard and published with her consent (`datos/ejemplos/demo_voz.*`). | 25/10/2026 |

The file `datos/fuentes.csv` lists the source, licence and access procedure for each of the 95 files. Original images and audio are kept in `datos/raw/`, which is excluded from Git.

## 3. Pipeline

1. **OCR.** PaddleOCR 3.7 with PP-OCRv5 mobile detection and Latin recognition models on CPU. A raw backup of every recognised line and its confidence score is saved locally.
2. **ASR.** Interviews are cut into 30-second clips starting at minute one. Each clip is transcribed with faster-whisper `small` (int8, CPU) and Silero VAD, and speakers are separated with the diarization function from Session 13 (`voz.py`). Subtitles (SRT) and readable transcripts (TXT) are exported locally.
3. **Pseudonymization.** Person names are detected with a Spanish NER model (`mrm8488/bert-spanish-cased-finetuned-ner`) plus a private list of known names. E-mail addresses, mobile numbers (with or without the `+51` prefix) and eight-digit ID numbers are detected with regular expressions. Every identifier is replaced by a consistent label such as `[PERSONA_3]`, and the result was reviewed by hand.
4. **Cleaning and EDA.** Duplicates are detected by SHA-256 hash, empty outputs are discarded, and three Plotly charts with analytical titles describe the corpus.
5. **Evaluation.** Ten documents (all three types) and ten clips (all six interviews) were transcribed manually and fixed as the evaluation sample before any metric was computed. CER and WER are computed with the Session 13 normalization, excluding speaker labels.
6. **Structured extraction.** Gemini returns a JSON record (`modalidad`, `tema`, `resumen`, plus `emisor`/`fecha`/`monto` for documents and `citas_clave`/`numero_hablantes` for audio), with `null` for missing fields. Twenty random extractions were audited by hand.

## 4. Results on the evaluation sample

All models were evaluated on the same 10 documents and 10 clips, against manual references. Pooled scores are computed over the ten files at once, so long files weigh more.

| Modality | Model | Pooled error | Mean time per file | Real-time factor | Runs on |
|---|---|---|---|---|---|
| Documents | **PaddleOCR 3.7 default (baseline)** | **CER 0.525** | 130.1 s | — | local CPU |
| Documents | PaddleOCR PP-OCRv5 mobile (Part 1) | CER 0.540 | 33.6 s | — | local CPU |
| Documents | Gemini vision model (`gemini-flash-latest`) | CER 0.637 | 119.1 s | — | cloud API |
| Audio | **faster-whisper `small` (baseline)** | **WER 0.372** | 44.8 s | 1.49 | local CPU |
| Audio | Qwen3-ASR 0.6B | WER 0.393 | 133.3 s | 4.44 | local CPU |

| Mean CER by document type | PaddleOCR default | PaddleOCR mobile | Gemini vision |
|---|---|---|---|
| Printed (1) | 0.718 | 0.718 | 1.000 |
| Photographed (4) | 0.273 | 0.328 | **0.128** |
| Handwritten (5) | 0.267 | 0.331 | **0.241** |

**Structured extraction:** 17 of 20 randomly audited LLM extractions were completely correct (**85 %**; 8/10 documents, 9/10 clips). The three errors were two omissions on commercial images (the issuing brand and most prices were left out) and one quote that was not literal. No invented date, issuer or amount was found.

## 5. Key findings

**Finding 1 — No single OCR model wins: the best choice depends on the type of document.** The cloud vision model was by far the most accurate on photographs (CER 0.13 versus 0.27 for PaddleOCR) and the best on handwriting (0.24 versus 0.27), but it returned no usable transcription for the dense printed page of the official gazette, where both PaddleOCR configurations were more reliable. On that page, most of PaddleOCR's error comes from reading order rather than from misread characters: the three-column layout is read line by line across columns, which a character-level metric penalises heavily. The lighter mobile models were four times faster than the default ones at a cost of about six CER points on photos and handwriting.

**Finding 2 — For interviews, recording quality matters more than the choice of model.** The two ASR models differ by only two WER points (0.37 versus 0.39), and faster-whisper is three times faster on CPU. Within each model, however, the error ranges from 0.08 on a clear monologue to 0.78 on the noisy interview, where the voice activity detector also discarded two clips as silent. Domain acronyms are a systematic weakness: *BIAM* was transcribed as *bien*, *VIAM* or *VIP*, and these errors propagate to the fields extracted by the LLM.

## 6. Technical limitations

**Limitation 1 — Hardware constraints shape the choice of models.** All local models ran on a laptop CPU with limited disk space. The default PaddleOCR models needed four to seven minutes per printed page, so the lighter mobile models were adopted for the full corpus, and GPU-dependent alternatives (larger Whisper models, PaddleOCR-VL, Voxtral) were not tested. The results therefore describe what is feasible on modest hardware rather than the best attainable accuracy.

**Limitation 2 — Short clips and recording quality limit diarization and ASR.** Thirty-second clips make manual references feasible, but they cut sentences at arbitrary points and give the speaker-clustering step very little audio. Most clips correctly show two speakers, yet some report three to six, which reflects over-segmentation rather than additional participants. One interview was recorded with poor sound quality, and the VAD found no speech in two of its clips.

## 7. Running the project locally

The notebooks use the course environment ([d2cml-ai/Data-Science-Python](https://github.com/d2cml-ai/Data-Science-Python)):

```bash
# in the course repository
uv sync --group docai --group audio
# Part 2 also needs: uv pip install google-genai python-dotenv
```

A Gemini API key is required for Part 2 and must be stored in `tarea_2/.env` as `GEMINI_API_KEY=...` (this file is excluded from Git). The raw images and audio are not published, so the notebooks can be read with their saved outputs but not re-run from scratch without the original files.

The dashboard only reads the CSV files and needs no model:

```bash
cd tarea_2
pip install -r requirements.txt
streamlit run app.py
```

## 8. Repository structure

```
tarea_2/
├── 01_extraccion.ipynb      # OCR, ASR, pseudonymization, cleaning, EDA and export
├── 02_evaluacion.ipynb      # CER/WER, model comparison, LLM extraction and audit
├── app.py                   # Streamlit dashboard
├── requirements.txt         # Dependencies of the dashboard
├── README.md
├── .gitignore               # Excludes datos/raw/, model weights and .env
├── evidencias_ia/           # Screenshots of the AI-assisted development, in order
├── datos/
│   ├── documentos.csv       # 25 documents (OCR)
│   ├── transcripciones.csv  # 70 clips, 35 min (ASR)
│   ├── extraccion_llm.csv   # Structured fields extracted by the LLM
│   ├── fuentes.csv          # Source, licence and access for each file
│   ├── evaluacion_ocr.csv · evaluacion_asr.csv · comparativa.csv · auditoria_llm.csv
│   └── ejemplos/            # Publishable images and the authorized audio example
└── modelos/                 # (no heavy weights are versioned)
```

## 9. Use of AI assistance

This project was developed with the help of an AI assistant (Claude, in a chat interface and in Claude Code), as allowed by the assignment. The full conversation is documented in `evidencias_ia/`, with personal data and off-topic remarks covered. The assistant drafted most of the code and the English text of the notebooks and this README.

The author was responsible for the research design and for every decision that affects the validity of the results: collecting the corpus, securing informed consent for the interviews, photographing the documents, transcribing the 20 reference files by hand, fixing the evaluation sample before computing metrics, reviewing the pseudonymization (which revealed errors in the NER output that were then corrected), correcting the classification of a misfiled document, deciding how to treat the noisy interview, auditing the LLM extractions, and checking every result before submission.

## 10. Ethics and data protection

- No real name, ID number or phone number is published. Pseudonymization was automatic (NER, a private name list and regular expressions, plus a final case-insensitive pass) and was then reviewed by hand; this manual review replaced two residual name fragments that the automatic passes had missed.
- Interview audio and document images containing third-party or personal data are not versioned or published.
- Only texts that were reviewed and pseudonymized appear in the CSV files and the dashboard.
- Gemini only received pseudonymized text and the ten evaluation images (one official gazette page, public signage, packaging, a menu board and personal notes without identifying information). No interview audio was sent to any external service.
