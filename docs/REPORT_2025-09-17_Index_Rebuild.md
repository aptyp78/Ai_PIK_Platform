# Index rebuild — Playbook + Frames (OpenAI Embeddings)

Дата (UTC): 2025-09-17 19:18:37Z

## Шаги
1. Скачаны JSON из `gs://pik_result_bucket/Qdrant_Destination/{playbooks,frames}` → `data/results/` (Playbook: 3 файла, Frames: 55 файлов).
2. Пересобран текстовый индекс (Unstructured → OpenAI `text-embedding-3-large`).
   - `python scripts/rebuild_index.py --out out/openai_embeddings.ndjson ...`
   - Чанкование по умолчанию (≈1400 символов, overlap 180).
   - Итог: 162 текстовых чанка (NarrativeText/Title/Image/Table).
3. Инжест визуальных артефактов:
   - CV регионы `out/visual/cv_regions/` → +1 750 записей `VisualFact`.
   - Grounded регионы `out/visual/grounded_regions/` → +137 записей `VisualFact`.
4. Публикация индекса:
   - Локальный файл: `out/openai_embeddings.ndjson` (2 049 записей).
   - Загрузка в GCS: `gs://pik-artifacts-dev/embeddings/openai_embeddings.ndjson`.
5. Метрики (eval/queries.jsonl, prefer-visual):
   - recall@1=0.000, recall@3=0.000, recall@5=0.000
   - ndcg@1=0.000, ndcg@3=0.000, ndcg@5=0.000
   - MRR=0.023 (78 запросов)

## Статистика индекса (по meta.type)
- VisualFact: 1 887
- NarrativeText: 78
- Image: 41
- Title: 34
- Table: 9

## Комментарии
- После очистки бакетов текстовые чанки пересчитаны заново (162). Визуальные записи доминируют — стоит либо добрать текстовые источники (остальные документы), либо переиндексировать более широкий корпус.
- Нулевые метрики ожидаемы при отсутствии текстового покрытия и без retune весов. Следующий шаг — настроить `--type-weights` / `TAG_WEIGHTS` или расширить текстовый индекс.
- Индекс переупакован и опубликован в GCS, готов к дальнейшим экспериментах и QA.
