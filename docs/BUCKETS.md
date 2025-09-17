# GCS Buckets — структура и назначение

## Обзор
- `pik_source_bucket` — входные данные (сырьё): PDF, PNG/TIFF/JPEG, предварительные JSON выгрузки.
- `pik_result_bucket` — обработанные JSON (Unstructured) для индексации.
- `pik-artifacts-dev` — артефакты визуального пайплайна (детекции, обзоры, индексы, зеркала весов).
- `pik-artifacts-logs` — логи доступа/аудита для `pik-artifacts-dev` (GCS logging).

## Структуры

### pik_source_bucket
- `playbooks/` — исходные PDF
- `frames/` — исходные кадры (PNG/TIFF/JPEG)
- `vlm_unstructured/` — [УДАЛИТЬ] экспериментальный вывод VLM‑partitioner (не использовать)
- `raw_json/` — сырые JSON (опционально)

### pik_result_bucket
- `Qdrant_Destination/playbooks/` — финальные JSON для индексации (по документам)
- `Qdrant_Destination/frames/` — финальные JSON по кадрам

### pik-artifacts-dev
- `grounded_regions/<unit>/regions/region-*.{json,png,caption.txt,struct.json,facts.jsonl}` — GroundedDINO+SAM(2)
- `cv_regions/<page>/regions/…` — классическое CV‑сегментирование
- `cv_frames/` — регионы по кадрам
- `visual_review/visual_review.html` — сводный обзор
- `embeddings/openai_embeddings.ndjson` — опубликованная версия индекса (опционально)
- `models/{groundingdino,sam,sam2}/…` — зеркала весов (оставляем при чистках)
- `colab_runs/` — логи прогона из ноутбука (опционально)

### pik-artifacts-logs
- Логи GCS для `pik-artifacts-dev` (читать с правами аудитора).

## Политики и практики
- `pik-artifacts-dev`: UBLA + PAP, включено versioning, CORS загружен, logging → `pik-artifacts-logs`.
- Чистка результатов: удалять всё, кроме `models/`.
- Публикация результатов только в префиксах из этого документа.

## Утилиты
- Очистка (опасно): `python scripts/gcs_cleanup.py --dry` (просмотр) → без `--dry` (удаление).
- Инвентаризация (пример gsutil):
  - `gsutil ls -r gs://pik_source_bucket/{playbooks,frames}`
  - `gsutil ls -r gs://pik_result_bucket/Qdrant_Destination/{playbooks,frames}`
  - `gsutil du -s gs://pik-artifacts-dev/{grounded_regions,cv_regions,visual_review,models}`

