# IPMK — Отчёт и план полного прогона (100%)

- Хост: af4e8805195b
- Контекст: визуальный конвейер (PVStack, GDINO+SAM, OCR, LLM), индекс OpenAI, «живая» витрина (eval/)
- Модель анализа (LLM): gpt-5-mini (по умолчанию)
- Embeddings: text-embedding-3-large
- Секреты: берутся из `Secrets/` (OpenAI), TMPDIR для OCR — `/tmp/tess_tmp`

## 1) Текущее состояние (high-level)
- Источники: `/root/data/playbooks` (PDF) и `/root/data/frames` (PDF/PNG) — готовы.
- Модели: `/root/models/{groundingdino,sam,sam2}` — на месте.
- Рендер (300 dpi): `out/page_images/<doc>/page-*.png` — генерируется `prepare_inputs.py`.
- Детекции (GDINO+SAM): `out/visual/grounded_regions/<page>/regions/region-*.{json,png}` — заполняются.
- Анализ (LLM+PVStack): `region-*.caption.txt|struct.json|facts.jsonl` — постепенно добавляются.
- Индекс: `out/openai_embeddings.ndjson` — наполняется инжестом.
- Витрина: `eval/visual_review.html`, `eval/progress.html` — доступны, авто‑обновление включено.

## 2) Полный прогон (100%) — план и команды

1) Подготовить входы (playbooks + frames → 300 dpi, аудит PNG)
```
python scripts/prepare_inputs.py   --playbooks /root/data/playbooks   --frames /root/data/frames   --out-root out/page_images   --dpi 300
```
- Все PDF рендерятся в 300 dpi.
- PNG из frames: если нет соответствующего PDF — копируются в out/page_images как `page-1.png`.

2) Детекции (GroundedDINO + SAM‑маски)
```
python scripts/batch_gdino_sam2.py   --pages-root out/page_images   --outdir out/visual/grounded_regions   --prompts diagram canvas table legend node arrow textbox   --grounding-model /root/models/groundingdino/groundingdino_swint_ogc.pth   --sam-model /root/models/sam/sam_vit_h_4b8939.pth
```
- На выходе `region-*.json/png` с bbox, gdino.conf/phrase, layout.zone, mask_stats.s2.

3) Анализ (LLM, PVStack, s1–s4, OCR/s3, AutoTier)
```
export OPENAI_API_KEY="$(cat 'Secrets/OpenAi API.key')"
python scripts/analyze_detected_regions.py   --detected-dir out/visual/grounded_regions   --all   --outdir out/visual/grounded_regions   --profile auto   --synonyms config/semantic_synonyms.yaml   --weights config/visual_objects_weights.yaml   --tmpdir /tmp/tess_tmp   --chat-model gpt-5-mini   --skip-existing
```
- s1=gdino.conf; s2=mask_stats; s3=OCR+лексикон; s4=layout.
- Профиль auto (DoubleLoop/keywords) → Discover/Launch | Growth/Scale | Governance.
- Итог: `Final_weight`, `Tagging.AutoTier`.

4) Инжест визуала в единый индекс
```
python scripts/ingest_visual_artifacts.py   --source-json "/root/data/playbook.json"   --regions-dir out/visual/grounded_regions   --out out/openai_embeddings.ndjson   --model text-embedding-3-large
```

5) Обзор и дашборд (auto‑refresh)
```
python scripts/generate_visual_review.py   --regions-detect out/visual/grounded_regions   --out eval/visual_review.html --inline --auto-refresh 5
python scripts/progress_dashboard.py   --playbooks /root/data/playbooks --frames /root/data/frames   --pages-dir out/page_images --regions-dir out/visual/grounded_regions   --index out/openai_embeddings.ndjson   --out eval/progress.html --auto-refresh 5
```
- HTTP сервер для просмотра:
```
python -m http.server 8000 -d eval
# http://<ip>:8000/visual_review.html и /progress.html
```
- Фоновый режим (всё сразу):
```
bash scripts/start_services.sh
# PIDs и логи: Logs/*.pid, Logs/*.log
```

6) Метрики (поиск)
```
export OPENAI_API_KEY="$(cat 'Secrets/OpenAi API.key')"
python scripts/eval_metrics.py --index out/openai_embeddings.ndjson   --eval eval/queries.jsonl --prefer-visual
```

7) Публикация в GCS (опционально)
```
# grounded_regions
gsutil -m rsync -r out/visual/grounded_regions gs://pik-artifacts-dev/grounded_regions
# витрина
gsutil cp eval/visual_review.html gs://pik-artifacts-dev/visual_review/visual_review.html
# индекс
gsutil cp out/openai_embeddings.ndjson gs://pik-artifacts-dev/embeddings/openai_embeddings.ndjson
```

## 3) Стабильность и автозапуск
- Фоновый запуск конвейера: `nohup bash scripts/run_pipeline_bg.sh >> Logs/pipeline.log 2>&1 & echo $! > Logs/pipeline.pid`
- Автозапуск сервисов: `bash scripts/start_services.sh` (поднимет конвейер, вотчер и http server)
- Безопасная загрузка `.env` (только пары ключ=значение), TMPDIR создаётся автоматически.

## 4) Риски и контроль качества
- Rate limits OpenAI: анализ перезапускаем с `--skip-existing`.
- SAM2 API: возможно подключение нативного предиктора; сейчас есть SAM v1 + эвристика.
- Frames без PDF: обработаны prepare_inputs (зеркалирование PNG).
- Калибровка весов/синонимов: дополнять `config/*.yaml` по мере ревью.

## 5) Чек‑лист «100% done»
- [ ] Все PDF → PNG (300 dpi) в `out/page_images`
- [ ] Все страницы детектированы (region‑*.json/png)
- [ ] Все регионы проанализированы (caption/struct/facts)
- [ ] Индекс `out/openai_embeddings.ndjson` актуален
- [ ] Витрина `eval/visual_review.html` отражает все страницы
- [ ] Метрики сняты; результаты сопоставлены
- [ ] (опц.) Публикация в GCS выполнена
