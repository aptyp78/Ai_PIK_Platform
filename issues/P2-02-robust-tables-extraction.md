# P2: Robust tables extraction and validation

Labels: priority/P2, area/ocr, area/struct

Summary:
- Strengthen table extraction via DocAI Tables/Form Recognizer, or Tabula/Camelot fallback, validate structure and ingest as facts.

Current achievements:
- Tables path described in TECH_STACK; ingest supports facts from pages/regions.

Tasks:
- Add table-specific extractor and validation script; normalize headers/cells; generate facts.
- Integrate into ingest and tag tables accordingly for boosts/filters.

Acceptance criteria:
- Structured tables present for target docs; table-related queries improve.

