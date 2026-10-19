# Task 1 — Peruvian news: from headline to classifier

**Author:** Ana Karen Zamalloa Lima ([@anakaren-zl](https://github.com/anakaren-zl))
**Course:** Data Science with Python — Diplomado PUCP 2026

## 1. Research question

> **Can Peruvian news headlines be transformed into a reliable news classifier?**

The automated categorization of news constitutes a classic problem in text classification; nevertheless, headlines pose a particular challenge, since their brevity and their frequent reliance on proper names and implicit references provide limited contextual information. In light of this difficulty, the present project examines whether headlines from a Peruvian outlet can be classified reliably into four fixed categories (`politica`, `economia`, `deportes`, `ciencia_tecnologia`), and which strategy offers the most adequate balance between accuracy, cost and feasibility.

To this end, the study adopts a three-stage design in which each stage builds upon the outputs of the preceding one. First, a corpus of real headlines is constructed and normalized. Second, three approaches of increasing task specificity are compared under identical conditions: a zero-shot model based on natural language inference (Yin et al., 2019), a general-purpose large language model (LLM) employed as a weak annotator (Ratner et al., 2017), and a multilingual DistilBERT adapted to the task through fine-tuning (Sanh et al., 2019). Third, the selected model is operationalized in an interactive dashboard, thereby demonstrating its applicability to unseen headlines.

| Stage | Methodological focus | Deliverables |
|---|---|---|
| Part 1 | Data collection, cleaning and exploratory analysis | `01_recoleccion.ipynb`, `datos/noticias.csv` |
| Part 2 | Weak supervision, fine-tuning and evaluation | `02_clasificacion.ipynb`, `datos/etiquetas_llm.csv`, `modelo/` |
| Part 3 | Deployment and documentation | `app.py`, `requirements.txt`, `README.md` |
| Innovation | Named entity recognition | `03_innovacion_ner.ipynb`, `datos/entidades.csv` |

## 2. Outlet and extraction dates

| Parameter | Value |
|---|---|
| **Outlet** | Option B — *El Comercio* (`elcomercio.pe`) |
| **Source** | Official section sitemaps (`politica`, `economia`, `deporte-total`, `tecnologia`) and the Open Graph metadata of each article |
| **Download date** | 18 October 2026 |
| **Publication period** | 6–18 October 2026 |
| **Volume** | 400 articles collected; 383 retained after cleaning |

It is worth noting that the selection of the outlet was not established a priori but resulted from an empirical assessment of data availability. *La República* (Option A) was initially considered; however, its RSS feeds exposed only about 21 items per section, a volume insufficient to reach the required 90–100 news items per category. By contrast, the sitemaps of *El Comercio* list approximately 100 articles per section, which made it possible to meet the target volume through official distribution channels. The subsequent cleaning process removed one duplicate and sixteen articles falling outside the four categories, and each exclusion was documented in order to ensure the transparency of the procedure. Furthermore, the collection complied with the outlet's `robots.txt` and introduced a pause of 1.5 seconds between consecutive requests, in accordance with responsible web-scraping practices (Mitchell, 2018).

## 3. Key findings

**Finding 1 — A lightweight, locally executed model performs on par with a large language model.** On an isolated test set of 58 headlines, the fine-tuned DistilBERT attained a macro F1 of **0.88**, a value identical to that of Gemini Flash-Lite and 0.29 higher than the zero-shot baseline.

| Approach | Evaluation sample | Accuracy | Macro F1 |
|---|---|---|---|
| Zero-shot (BERT-XNLI) | 40 stratified headlines | 0.62 | 0.59 |
| LLM weak labels (Gemini Flash-Lite) | Test set (58 headlines) | 0.88 | 0.88 |
| **Fine-tuned DistilBERT** | **Test set (58 headlines)** | **0.88** | **0.88** |

Given the equivalence in predictive performance, the comparison between both approaches necessarily shifts towards considerations of cost, latency and reliability. In this regard, the fine-tuned model holds a decisive advantage: it operates locally at no marginal cost per prediction, responds within milliseconds, and remains independent of external services. The relevance of this last criterion became evident during the project itself, as the standard Gemini model repeatedly returned `503 UNAVAILABLE` errors owing to high demand, a degree of instability that would arguably be unacceptable in a production setting. It follows that the local model constitutes the preferable option for deployment, whereas the LLM appears better suited to a complementary role as an efficient weak annotator capable of generating or auditing labels for future retraining.

**Finding 2 — Classification errors concentrate at the boundary between politics and economy.** Far from being randomly distributed, the classifier's errors cluster at a specific thematic boundary. Whereas sports headlines are classified flawlessly (F1 = 1.00), presumably owing to their highly distinctive vocabulary of teams, athletes and competitions, political headlines exhibit the lowest recall (0.69), since a substantial share of them is predicted as economic news. Notably, the same boundary accounts for most of the disagreements between the LLM labels and the section-based labels, whose overall agreement reaches 91%. The model's confidence scores in the dashboard reinforce this interpretation: a sports headline such as *"Alianza Lima gana el clásico ante Universitario en Matute"* is classified with 97% confidence, whereas a fiscal headline such as *"MEF anuncia recorte de presupuesto para gobiernos regionales"* is assigned to politics with only 73% confidence. Taken together, these observations suggest that the difficulty is inherent to the categories rather than attributable to a particular model, insofar as Peruvian political coverage frequently revolves around budgets, taxation and public investment, and consequently shares much of its vocabulary with economic news.

## Innovation — Named entity recognition

As an optional extension, a Spanish named entity recognition model (`mrm8488/bert-spanish-cased-finetuned-ner`) was applied to the headline and summary of each news item, yielding 1,413 high-confidence mentions of people, organizations and locations (717 unique entities). The analysis reveals that each category is anchored by a distinct set of actors: politics is dominated by legislative institutions, such as the Senate and its Constitutional Committee, together with President Keiko Fujimori; sports revolves around football clubs; and science and technology is characterized by global firms such as Google, Apple and Microsoft. These patterns offer a substantive explanation for the classifier's behavior, since sports entities are highly distinctive, whereas generic entities such as *Perú* or *Gobierno* recur across categories. The results are available in `03_innovacion_ner.ipynb` and in the "Who makes the news?" section of the dashboard.

## 4. Technical limitations

**Limitation 1 — Temporal and source concentration of the corpus.** The corpus is drawn from a single outlet and a two-week window, given that the sitemaps only expose the most recent articles of each section. Consequently, the vocabulary associated with each category may reflect the specific events of that period, such as the parliamentary debate on legislative powers, which constrains both the temporal and the editorial generalizability of the classifier. In addition, the test set comprises only 58 headlines; the reported metrics are therefore subject to considerable sampling variability and should be regarded as indicative rather than conclusive.

**Limitation 2 — Storage constraints prevent a fully public deployment.** The fine-tuned weights (`modelo/model.safetensors`) exceed 500 MB, well beyond GitHub's 100 MB file limit, and are thus excluded from version control through `.gitignore`. As a result, the live classifier becomes operational only after `02_clasificacion.ipynb` has been executed locally, and the dashboard cannot be deployed on Streamlit Community Cloud without recourse to an external model repository, such as the Hugging Face Hub (Wolf et al., 2020). This notwithstanding, hosting the weights externally would constitute a straightforward next step towards a publicly accessible application.

## 5. How to run the project locally

The following procedure reproduces the entire workflow, from data collection to the deployment of the dashboard. All dependencies are pinned to the exact versions used during development, so as to guarantee the reproducibility of the results.

**Step 1.** Clone the repository and enter the task folder:
```bash
git clone https://github.com/anakaren-zl/data-science-python-2026.git
cd data-science-python-2026/tarea_1
```

**Step 2.** Install the pinned dependencies:
```bash
pip install -r requirements.txt
```

**Step 3.** Provide a Gemini API key, which is required only to reproduce the LLM labeling. To this end, create a file named `.env` inside `tarea_1/` with the content below; for security reasons, this file is excluded from version control:
```
GEMINI_API_KEY=your_api_key_here
```

**Step 4.** Execute the notebooks sequentially; the second one trains the classifier and stores it in `modelo/`, whereas the third one, which is optional, extracts the named entities displayed in the dashboard:
```bash
jupyter nbconvert --to notebook --execute --inplace 01_recoleccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 02_clasificacion.ipynb
jupyter nbconvert --to notebook --execute --inplace 03_innovacion_ner.ipynb
```

**Step 5.** Launch the dashboard, which becomes available at `http://localhost:8501`:
```bash
streamlit run app.py
```

## AI use statement

In accordance with the course guidelines, which explicitly permit the use of AI assistants, Claude (Anthropic) was employed as a tutoring and coding support tool, whereas Gemini (Google) served as the weak annotator required by the assignment. Nevertheless, all methodological decisions, the manual audit of the LLM labels, and the interpretation of the results were made and verified by the author.

## References

Mitchell, R. (2018). *Web scraping with Python: Collecting more data from the modern web* (2nd ed.). O'Reilly Media.

Ratner, A., Bach, S. H., Ehrenberg, H., Fries, J., Wu, S., & Ré, C. (2017). Snorkel: Rapid training data creation with weak supervision. *Proceedings of the VLDB Endowment, 11*(3), 269–282. https://doi.org/10.14778/3157794.3157797

Romero, M. (2020). *bert-spanish-cased-finetuned-ner* [Pretrained model]. Hugging Face. https://huggingface.co/mrm8488/bert-spanish-cased-finetuned-ner

Sanh, V., Debut, L., Chaumond, J., & Wolf, T. (2019). DistilBERT, a distilled version of BERT: Smaller, faster, cheaper and lighter. *arXiv preprint arXiv:1910.01108*. https://arxiv.org/abs/1910.01108

Wolf, T., Debut, L., Sanh, V., Chaumond, J., Delangue, C., Moi, A., Cistac, P., Rault, T., Louf, R., Funtowicz, M., Davison, J., Shleifer, S., von Platen, P., Ma, C., Jernite, Y., Plu, J., Xu, C., Le Scao, T., Gugger, S., Drame, M., Lhoest, Q., & Rush, A. M. (2020). Transformers: State-of-the-art natural language processing. In *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing: System Demonstrations* (pp. 38–45). https://doi.org/10.18653/v1/2020.emnlp-demos.6

Yin, W., Hay, J., & Roth, D. (2019). Benchmarking zero-shot text classification: Datasets, evaluation and entailment approach. In *Proceedings of EMNLP-IJCNLP 2019* (pp. 3914–3923). https://doi.org/10.18653/v1/D19-1404