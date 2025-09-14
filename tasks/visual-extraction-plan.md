# Visual Extraction Plan — Playbook & Frames (Using GPT‑4o)

## Objectives
- Extract semantic visual knowledge from the Playbook pages and key frames (canvases, diagrams, tables) to improve retrieval and Q/A.
- Produce three artifact types per target page/frame: caption (rich natural language), struct (normalized JSON), facts (atomic textual assertions).

## Scope
- Playbook printed pages: 5, 6, 7, 8, 10, 11, 17, 18, 20, 21, 22, 23, 24, 26, 27, 29, 30, 33, 34, 41, 42, 43, 45, 46, 47, 49.
- Frames (PDF JSON already in corpus): Canvas Table View, Canvases, Assessment/Scoring.

## Model & Settings
- Vision LLM: OpenAI GPT‑4o (confirmed).
- Temperature: low (0.1–0.2) for factual consistency.
- Output contracts: strictly defined JSON schema per artifact type + concise textual facts.

## Method
1. Page materialization
   - From Unstructured JSON, collect page elements and any `image_base64` regions for target pages.
   - Save page/region images into `out/visual/pages/<page>.png` where possible.
2. Visual captioning (GPT‑4o)
   - Prompt to describe the diagram/canvas/table, including layers/pillars, components, relations, headings.
   - Save to `out/visual/pages/<page>.caption.txt`.
3. Structural extraction (GPT‑4o)
   - Use schema‑guided prompts to output normalized JSON:
     - Canvas: `{layers, components, personas, journey, relations}`
     - Assessment: `{pillars, criteria, questions, scoring_fields}`
     - Diagram: `{entities, edges, legend, groups}`
   - Save to `out/visual/pages/<page>.struct.json`.
4. Visual facts synthesis
   - Linearize key JSON tuples into single‑line assertions (e.g., `Pillar=Security; Criterion="Protect data in transit and at rest"`).
   - Save to `out/visual/pages/<page>.facts.txt`.
5. Index integration
   - Extend `scripts/rebuild_index.py` to ingest caption/facts as items with meta `type=VisualCaption|VisualFact`, `page`, `filename`, `tags`.
   - Rebuild embeddings index and recompute metrics; update Q/A.
6. Review & QA
   - Generate `eval/visual_review.md` with examples of struct JSON and deltas in top‑1 matches.
   - Manual spot checks for core pages (42–47, 45, 49, 10).

## Deliverables
- `out/visual/pages/<page>.caption.txt`
- `out/visual/pages/<page>.struct.json`
- `out/visual/pages/<page>.facts.txt`
- Updated `out/openai_embeddings.ndjson`, `eval/qa.md`, `eval/qa.jsonl`.
- `eval/visual_review.md` (impact report).

## Quality & Risks
- OCR noise: mitigated by GPT‑4o captioning and structured extraction.
- Diagram complexity: if needed, add object grounding (GroundingDINO + SAM) later.
- Schema drift: keep prompts stable; validate JSON; allow manual corrections.

## Timeline (indicative)
- Day 1: Implement extraction script and run for pages 42–47, 45, 49.
- Day 2: Extend to remaining pages; integrate into index; compute metrics; report.
- Day 3: Apply to 3 frames; final review and next‑step recommendations.

Owner: aso • Date: 2025‑09‑14

