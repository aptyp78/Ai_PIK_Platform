# Методика интеллектуального визуального парсинга

Цель: извлекать из визуальных артефактов (диаграмм, канвасов, таблиц) структурированные факты и описания, пригодные для индексации и ответов (RAG).

## Шаги методики

1) Подготовка изображений
- Рендер PDF → PNG (150–300 DPI), нормализация размера и контраста при необходимости.
- Разбиение на кандидаты‑регионы:
  - Базово: CV (морфология + контуры) для быстрого охвата.
  - Полный режим: GroundedDINO (open‑vocab detection по списку prompts) → SAM/SAM‑2 для уточнения границ.

2) Детектирование сущностей (GroundedDINO)
- Промпты по типам артефактов: `diagram, canvas, table, legend, node, arrow, textbox`.
- Пороги: `box_threshold≈0.3`, `text_threshold≈0.25` (подбирать на материале).
- Выход: bounding boxes + фразы‑ярлыки (phrases) на региональном уровне.

3) Сегментация (SAM‑2)
- По каждому bbox уточнить маску; для целей RAG достаточно bbox+crop, маску можно хранить отдельно.
- Сохранять crops в PNG и базовые метаданные: `{bbox, score, label}`.

4) OCR/текстовые подсказки (опционально)
- Для регионов с текстом — OCR (DocAI/Azure FR/Tesseract) → подсказка для LLM‑анализа.

5) LLM‑анализ региона
- Модель: gpt‑4o (vision), режим детерминированный.
- Шаблон: 1) краткий caption (1–2 предложения), 2) строгий JSON‑объект по типам артефактов:
  - Canvas: `{layers[], components[], personas[], journey[], relations[]}`
  - Assessment: `{pillars{}, criteria[], questions[], scoring_fields[]}`
  - Diagram: `{entities[], edges[], legend[], groups[]}`

6) Нормализация и факты
- Канонизация: переименование столпов/слоёв (Pillars/Layers) к фиксированным именам.
- PVStack (канон слоёв Canvas): `Experience, Interactions, Data, Infrastructure`.
- Синонимы для канонизации и текстовых подсказок берём из `config/semantic_synonyms.yaml`.
- Выдача фактографики в JSONL‑виде: triples `{subject, predicate, object, tags}`.

7) Индексация
- Тексты: OpenAI `text-embedding-3-large` (caption + facts + текстовые чанки).
- Изображения (опционально): OpenCLIP (ImageVec) для мультимодального поиска.
- Метаданные: `{type, filename, page, region_id, bbox, tags, preview}`.

8) Валидация
- Визуальный обзор (`eval/visual_review.html`): изображение региона + caption + тип + ссылка на facts.
- Метрики поиска: Recall@k, nDCG, MRR; аудит флагов (miss@1, low_sim, image_top1).

## Практические замечания
- Для диалоговых/сложных канвасов полезно подмешивать OCR‑фразы в подсказку к LLM, но избегать прямого копирования длинного текста.
- Для больших схем оптимальна итеративная детекция: сначала крупные блоки (diagram/canvas/table), затем узлы/стрелки.
- Параметры порогов GroundedDINO подбираются под конкретный корпус.
 - Маски SAM‑2 повышают качество нарезки, но для RAG‑фактов достаточно bbox+crop. В детекторе сохраняем `mask_stats` (solidity, fill_ratio, edge_density, s2) — пока эвристика по crop; при наличии SAM2 используйте реальные маски.

## Confidence и веса (по весовой политике)
- Сигналы уверенности: `s₁=DINO`, `s₂=SAM2/контур`, `s₃=Текст(OCR)`, `s₄=Макет` (каждый в [0;1]).
- Профили (веса сигналов):
  - Discover/Launch: `0.45, 0.15, 0.30, 0.10`
  - Growth/Scale: `0.55, 0.25, 0.15, 0.05`
  - Governance/Риски: `0.40, 0.20, 0.35, 0.05`
- Агрегат уверенности: `Confidence_visual = s₁*w₁ + s₂*w₂ + s₃*w₃ + s₄*w₄`.
- Итоговый вес тега: `Weight_final = Weight_base * Confidence_visual * (1 + bonuses - penalties)`; отсечка [0;1].
- Пороги фиксации: Major≥0.70 · Secondary≥0.60 · Hint≥0.55.

Примечания:
- Профиль определяется автоматически из `Tagging.DoubleLoop` (Discover/Launch, Growth/Scale) или по ключевым словам (Governance/Risk); можно переопределить CLI `--profile`.
- Контекстные надбавки: 3P/SDG `+0.1`; при наличии Role/Zone `+0.02/+0.02`; стоп‑фактор: «дырявый» контур + отсутствие лексики `−0.2`.

## Конфигурация
 - Синонимы (PVStack, роли, объекты, ключевые слова): `config/semantic_synonyms.yaml`.
 - База весов 50 объектов: `config/visual_objects_weights.yaml` (машиночитаемое зеркало policy, значения можно уточнять со временем).
 - CLI для анализа: `python scripts/analyze_detected_regions.py --profile auto --synonyms config/semantic_synonyms.yaml --weights config/visual_objects_weights.yaml`.

## Публикация артефактов
- `gs://pik-artifacts-dev/grounded_regions/<unit>/regions/region-*.{json,png,caption.txt,struct.json,facts.jsonl}`
- Keep‑политика: `models/` — не удалять при общем клине результатов.
