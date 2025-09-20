# Портал мониторинга и готовности (концепция)

Цель: единый статический портал (HTML+JS) для мониторинга конвейера визуального парсинга, обзора артефактов и оценки «уровня интеллектуализации» (I‑Level) с принятиями решений по готовности к публикации и поиску в Qdrant.

Аудитория: разработчики, MLOps, владельцы продукта.

## Обзор и навигация

- Главная (существует): `out/portal/index.html`
- Плейбуки и кадры (существуют):
  - `out/portal/playbooks/index.html`
  - `out/portal/frames/index.html`
- Мониторинг (новое): `out/portal/monitoring/index.html`
  - KPI, прогресс‑бары, распределения качественных метрик, I‑Level, алёрты
- Готовность/Qdrant (новое): `out/portal/readiness/index.html`
  - Текущий уровень готовности (RL0–RL3), объяснение несоответствий, CTA (push в Qdrant)
- Деталка страницы/кадра (существует): `out/portal/docs/<slug>/<pNNN>/index.html`, `out/portal/frames/<slug>/<fNNNN>/index.html`

RU/EN переключатель как в `scripts/generate_portal.py` (дублирование текстов, скрытие через CSS).

## Источники данных

- Покрытие: `out/portal/coverage.json` (формируется `scripts/generate_portal.py`)
- Индекс материалов: `out/portal/portal_index.json` (формируется `scripts/build_index.py`)
- Единая раскладка детекций: `out/visual/regions/gdino_sam2/<slug>/<pNNN|fNNNN>/`
  - `regions.json` (агрегированные регионы; есть `struct_type`, `caption`, `auto_tier`, `scoring` при наличии)
  - `overlay.png`, `meta.json`
- Суммари и переводы: `out/portal/summaries/<slug>/<item_id>.json`, `<item_id>.captions.json`
- Обзоры (существует): `eval/visual_review.html`, `eval/progress.html`
- Индекс эмбеддингов: `out/openai_embeddings.ndjson`

## I‑Level (уровень интеллектуализации)

Скаляр 0.00–1.00, отражает зрелость технологии на данных. Предлагаемая формула:

- I = 0.4 · Coverage + 0.4 · Quality + 0.2 · Understanding
- Coverage (0..1):
  - `pages_done/pages_total` (страницы) и `frames_done/frames_total` (кадры), усреднение по документу
  - доля элементов с `overlay.png`
- Quality (0..1):
  - медиана `AutoScore`
  - доля `AutoTier ∈ {Major, Secondary}`
  - медиана/среднее `Scoring.final_weight`, среднее `Scoring.confidence_visual`
- Understanding (0..1):
  - доля известных `struct_type`
  - доля непустых `summary_ru` и `summary_en`
  - доля переведённых подписей регионов (captions RU)
  - доля регионов с `VisualFacts`

Нормализация: параметрический min/max клиппинг до [0,1] с усечением выбросов; усреднение по страницам/кадрам документа, затем агрегация по всем документам.

## Readiness Levels (гейты)

- RL0 (Draft): I < 0.40 или Coverage < 0.30 → не публиковать
- RL1 (Internal): I ≥ 0.50, `analyzed_regions ≥ 60%`, `share(Major+Secondary) ≥ 0.25`, `index ≥ 500`
- RL2 (Limited): I ≥ 0.70, `analyzed_regions ≥ 80%`, `median(final_weight) ≥ 0.60`, `known_types ≥ 70%`, `index ≥ 2000`
- RL3 (Prod): I ≥ 0.85, `coverage ≥ 0.95`, стабильность метрик (≈ 7 дней), позитивный спот‑чек → публикация наружу

Пороговые значения настраиваются через `config/readiness_policy.yaml`.

## Визуализации

- KPI карточки: документы, страницы, регионы, проанализировано, размер индекса, I‑Level
- Прогресс‑бары: рендер, детекции, анализ (с ETA)
- Гистограммы: распределение AutoScore, final_weight, confidence_visual
- Теплокарта: `struct_type × AutoTier`
- Спаркбары по документам: coverage, analyzed%, I‑Level
- Scatter: AutoScore vs final_weight (окраска по типу/руху)
- Top‑N: слабые документы/страницы, проблемные типы

## JSON‑артефакт `metrics.json` (новое)

Единый снимок метрик для портала мониторинга.

Пример структуры:

```
{
  "generated_at": "2025-09-20T12:34:56Z",
  "global": {
    "docs": 12,
    "pages_total": 1234,
    "pages_done": 987,
    "frames_total": 210,
    "frames_done": 190,
    "regions_total": 32100,
    "analyzed_regions": 28500,
    "index_lines": 45678,
    "ilevel": 0.71
  },
  "documents": [
    {
      "slug": "pik-expert-guide-platform-it-architecture-playbook-v11",
      "title": "PIK - Expert Guide - Platform IT Architecture - Playbook - v11",
      "coverage": { "pages_total": 52, "pages_done": 49, "frames_total": 0, "frames_done": 0, "regions_total": 4200, "analyzed_regions": 3600, "overlays": 49 },
      "quality": { "median_auto_score": 0.64, "share_major_secondary": 0.58, "median_final_weight": 0.62, "mean_confidence": 0.73 },
      "understanding": { "known_types": 0.76, "summary_ru": 0.98, "summary_en": 0.98, "captions_ru": 0.95, "visual_facts": 0.61 },
      "ilevel": 0.74,
      "rl": "RL2",
      "unmet": ["index_lines<2000"]
    }
  ],
  "histograms": {
    "auto_score": [[0.1, 25], [0.2, 120], ...],
    "final_weight": [[0.1, 10], ...]
  }
}
```

## План внедрения (фазы)

Фаза 1 — каркас и KPI (1–2 дня)
- Собрать `out/portal/portal_index.json` (`python scripts/build_index.py`).
- В `scripts/generate_portal.py` добавить расчёт агрегатов и запись `out/portal/metrics.json` (глобальные KPI + per‑doc Coverage; без тяжёлых гистограмм).
- Сгенерировать `out/portal/monitoring/index.html`: карточки KPI, прогресс‑бары, таблица документов (coverage, analyzed%, I‑Level заглушка/эвристика). JS подгружает `coverage.json`, `metrics.json`.

Фаза 2 — качество, I‑Level, гейты (2–4 дня)
- Добавить вычисление Quality и Understanding (из `regions.json`, `summaries`, `captions`).
- Реализовать формулу I‑Level; вывести doc‑уровень, глобальный I.
- Ввести гейты RL по конфигу `config/readiness_policy.yaml`; добавить страничку `readiness/index.html` с объяснением нарушений и RL.

Фаза 3 — визуализации и Qdrant (3–5 дней)
- Inline‑SVG гистограммы/теплокарты/скаттер (без внешних зависимостей).
- CTA/кнопка «Опубликовать в Qdrant»: вызов `scripts/qdrant_push.py` (с предупреждением); журнал публикаций.
- (Опционально) секция «Поиск» (через API `/search`), sanity‑проверка качества поиска.

Фаза 4 — таймсерии и алёрты (3–5 дней)
- Лог `metrics.jsonl` в `Logs/` с периодическим снапшотом; тренды на мониторинге.
- Алёрты (эвристика): падение I‑Level, рост Hint‑регионов, деградация final_weight.

## Минимальные Acceptance Criteria

- `metrics.json` корректно описывает метрики для всех документов, глобальные KPI согласованы с `coverage.json`.
- `monitoring/index.html` отображает KPI, таблицу документов, прогресс‑бары; обновляется без перезагрузки портала сборкой заново.
- I‑Level рассчитывается детерминированно при отсутствии LLM (эвристика) и улучшается при наличии.
- `readiness/index.html` показывает текущий RL и список условий, не выполненных для RL2.

## Настройка порогов

- Файл: `config/readiness_policy.yaml`
- Параметры порогов Coverage/Quality/Understanding и требований к индексу; обеспечивают гибкость под разные датасеты.

## Риски и ограничения

- Точность метрик зависит от полноты `regions.json` и `scoring` полей; при неполных данных использовать эвристику.
- Внешние сервисы (Qdrant, OpenAI) могут быть недоступны; портал должен деградировать до офлайн‑режима.
- Производительность: избегать тяжёлого JS; агрегации делать на этапе генерации.

## Связанные документы

- `docs/PORTAL_AND_PIPELINE.md` — структура портала и пайплайн
- `README.md` — обзор проекта и запуск

