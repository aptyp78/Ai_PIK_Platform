# Multimodal RAG Stack for Platform IT Documents and Frames

This document fixes the target technology stack for building a multimodal retrieval-and-generation (RAG) system over textual documents and visual frames (canvases, diagrams, tables). It includes the full design with the proposed extensions (structural extraction, visual facts, hybrid retrieval, reranking, and graph layer). No MVP simplifications are listed here.

## 1. Ingest Layer

- **Sources:** PDF, PNG/TIFF/JPEG from GCS `pik_source_bucket` and processed JSON frames from `pik_result_bucket` (Unstructured outputs).
- **Normalization:** `pdfimages`/Poppler, ImageMagick, `ocrmypdf` for consistent DPI, grayscale/binarization where helpful.
- **Storage:** GCS (raw), workspace cache (local) for intermediate artifacts.

## 2. OCR + Layout

- **Cloud OCR/Layout (primary choices):**
  - Google Document AI (OCR, layout, tables)
  - AWS Textract (AnalyzeDocument)
  - Azure Form Recognizer / Document Intelligence
- **Open‑source fallback:** Tesseract + PaddleOCR (multilingual) with LayoutParser/DocTR for block detection and reading order.
- **Output:** Per‑page blocks with text, coordinates, reading order, table cell structure.

## 3. Visual Understanding (Frames)

- **Vision LLM (caption + structure):** OpenAI `gpt‑4o` or `gpt‑4o‑mini` (vision) to produce:
  - Rich caption (semantic description) per frame
  - Structured JSON by artifact type:
    - Canvas: `{layers: [Engagement, Integration, Intelligence, Infrastructure], components: [...], personas: [...], journey: [...], relations: [...]}`
    - Assessment: `{pillars: {Operational, Security, Reliability, Performance, Cost}, criteria: [...], questions: [...], scoring_fields: [...]}`
    - Diagrams: `{entities: [...], edges: [...], legend: [...], groups: [...]}`
- **Object grounding (optional, for complex diagrams):** GroundingDINO/OWL‑ViT + Segment Anything (SAM) to detect labeled regions; associate OCR text with regions; export bounding boxes into structured JSON.
- **Tables (alternate/augment):** Cloud table extractors (DocAI Tables / FR) or Camelot/Tabula for PDF; Deep table models for robust cell structure.

## 4. Structuralization + Visual Facts

- **Normalization:** Map extracted entities to controlled vocabularies (e.g., pillar/layer names) and generate canonical tags.
- **Visual Facts:** Convert JSON structures into human‑readable atomic assertions, e.g.:
  - `Pillar=Security; Criterion="Protect data in transit and at rest"`
  - `Layer=Engagement; Component="Mobile App"`
- **Outputs saved alongside frames:**
  - `*.caption.txt` (rich caption)
  - `*.struct.json` (normalized structure)
  - `*.facts.txt` (one fact per line)

## 5. Embeddings

- **Text embeddings (primary):** OpenAI `text‑embedding‑3‑large`
  - Applied to: textual chunks from documents, `VisualCaption`, and `VisualFact` items.
- **Image embeddings (optional hybrid):** CLIP/OpenCLIP (e.g., ViT‑H/14) on frame images; store alongside text vectors for multimodal retrieval.
- **Chunking policy:** ~1,200–1,500 chars, ~10–15% overlap; filter `PageBreak`; include `Image` OCR only if sufficiently informative (text length ≥ ~180 chars) to minimize noise.

## 6. Storage & Index

- **Vector DB:** Qdrant (preferred) or Weaviate / PGVector for production.
- **Metadata fields:** `type` (`Text`, `VisualCaption`, `VisualFact`), `filename`, `page`, `source_file`, `span`, `tags` (pillar/layer/component), optional `bbox`/`region_id` for visual items.
- **Object storage:** retain original images, Unstructured JSON, and generated `caption/struct/facts` in GCS for traceability.

## 7. Retrieval & Reranking

- **Hybrid retrieval:**
  - Dense search (cosine over text embeddings)
  - Optional image‑query or image‑augmented search via CLIP vectors
  - Lightweight tag filters/boosts (e.g., if query mentions `Security`, upweight items with `tag:pillar=Security`)
- **LLM reranker (optional):** Rerank top‑k candidates via LLM scoring prompt (faithfulness + topicality) to improve top‑1 precision.

## 8. Answering (RAG)

- **Context builder:** assemble top‑k mixed contexts (text chunks + captions + facts) with source attributions.
- **Generator:** OpenAI `gpt‑4o` / `gpt‑4o‑mini` in deterministic mode for factual answers; cite sources (file/page/id).
- **Cite visual evidence:** when answers rely on frames, prefer `VisualFact`/`VisualCaption` and include the originating frame reference.

## 9. Graph Layer (Optional Extension)

- **Graph model:** Build a knowledge graph from `*.struct.json` across frames.
- **Storage:** NetworkX (in‑memory) for dev; Neo4j for production.
- **Usage:**
  - Pre‑filter candidates by graph traversal (e.g., all components under `Layer=Intelligence`)
  - Answer sub‑queries requiring relationships (e.g., journey steps → related components)
  - Enrich RAG context with graph‑derived facts

## 10. Orchestration, Review, and Quality

- **Pipelines:** Airflow / Prefect / Dagster for scheduled and on‑demand jobs (ingest → OCR → vision extraction → embeddings → index → QA build).
- **Human‑in‑the‑loop:** Label Studio / Prodigy to review and correct `*.struct.json` and `*.facts.txt` for key frames; store diffs and versions.
- **Evaluation:**
  - Retrieval metrics (Recall@k, MRR, nDCG)
  - Per‑query audit (top‑k, flags: `miss@1`, `low_sim`, `image_top1`)
  - RAG answer quality via spot‑checks and guided prompts
- **Observability:** Prometheus + Grafana; logging and tracing for pipeline stages and latency; drift alerts (sudden changes in match scores).
- **Security & Compliance:** secrets in `.env`/Vault; GCS IAM; PII handling policies if needed.

## 11. Interfaces & Artifacts

- **Inputs:** Unstructured JSONs (documents/frames), raw PDFs/PNGs.
- **Derived artifacts:** `caption.txt`, `struct.json`, `facts.txt`, embeddings index, per‑query reports, QA exports (`eval/qa.md`, `.jsonl`).
- **APIs (production):**
  - Indexing service (batch/stream)
  - Query API (retrieve, rerank, answer) with options: `k`, filters, prefer visual.

## 12. Technology Choices (Summary)

- **Vision & LLM:** OpenAI `gpt‑4o`, `gpt‑4o‑mini` (vision)
- **OCR/Layout:** Google Document AI / AWS Textract / Azure Form Recognizer; or Tesseract + LayoutParser
- **Tables:** DocAI Tables / Form Recognizer; Camelot/Tabula
- **Object grounding (optional):** GroundingDINO, Segment Anything
- **Embeddings:** OpenAI `text‑embedding‑3‑large`; CLIP/OpenCLIP (optional images)
- **Vector DB:** Qdrant (preferred), Weaviate, PGVector
- **Graph:** NetworkX (dev), Neo4j (prod)
- **Orchestration:** Airflow / Prefect / Dagster
- **Annotation:** Label Studio / Prodigy
- **Monitoring:** Prometheus, Grafana

---

Notes:
- The stack is compatible with current repository utilities (`scripts/rebuild_index.py`, `scripts/build_qa.py`, etc.). Adding visual extraction scripts (`visual_extract.py`) and hybrid retrieval (tag boosts, optional reranker) completes the extended design.

