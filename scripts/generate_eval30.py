#!/usr/bin/env python3
import json
import math
from pathlib import Path
from typing import List, Dict, Tuple

QS = [
    "Что такое Platform IT Architecture и зачем она нужна?",
    "Какие основные слои платформа включает (value stack/layers)?",
    "Что такое Platform Architecture Canvas и для чего он используется?",
    "Какие ключевые компоненты уровня Ecosystem Connectivity?",
    "Какие ключевые компоненты уровня Operational Excellence?",
    "Какие ключевые компоненты уровня Security?",
    "Какие ключевые компоненты уровня Reliability?",
    "Какие ключевые компоненты уровня Performance?",
    "Какие ключевые компоненты уровня Cost Optimization?",
    "Как определить необходимые IT-компоненты на основе 4 слоёв value stack?",
    "Какие существуют рекомендации по проектированию архитектуры (design decisions)?",
    "Какие типичные ошибки при проектировании и как их избежать?",
    "Какие метрики/критерии оценки архитектуры указаны в документе?",
    "Как оценивается операционная зрелость платформы (операции/оперуправление)?",
    "Какие рекомендации даны по развертыванию/миграции?",
    "Какая роль Canvas в согласовании архитектуры с бизнес-целями?",
    "Как документ предлагает работать с нагрузкой и масштабированием?",
    "Какие упоминаются подходы к мониторингу и наблюдаемости?",
    "Какие есть рекомендации по безопасности (security) платформы?",
    "Как документ описывает взаимодействие с экосистемой (пользователи, партнёры, IoT)?",
    "Какие таблицы или артефакты для скоринга/оценки присутствуют?",
    "Какие примеры артефактов или иллюстраций приводятся?",
    "Где упомянуты авторские права (copyright) и год?",
    "Как связаны уровни core и sub value layers?",
    "Чем отличаются базовая и расширенная (superior) ценность платформы?",
    "Какие рекомендации по управлению затратами (cost optimization)?",
    "Как документ трактует надёжность (reliability) и связанные практики?",
    "Какие подходы к производительности (performance) упоминаются?",
    "Какой общий процесс оценки архитектуры предлагает документ?",
    "Какие ключевые выводы/резюме документа?",
]


def load_ndjson(path: Path):
    items = []
    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine_sim(a: List[float], b: List[float]) -> float:
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot(a, b) / (na * nb)


def embed_openai_batch(texts: List[str], model: str) -> List[List[float]]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def main():
    index_path = Path("out/openai_embeddings.ndjson")
    out_path = Path("eval/queries.jsonl")
    model = "text-embedding-3-large"

    items = load_ndjson(index_path)
    qvecs = embed_openai_batch(QS, model=model)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as w:
        for q, qv in zip(QS, qvecs):
            scored: List[Tuple[float, Dict]] = []
            for it in items:
                sim = cosine_sim(qv, it["vector"])  # type: ignore
                scored.append((sim, it))
            scored.sort(key=lambda x: x[0], reverse=True)

            # Positive ids: включим все результаты с sim>=0.35 (если нет — возьмём топ1), максимум 3.
            positives: List[int] = []
            for sim, it in scored[:5]:
                if sim >= 0.35 and len(positives) < 3:
                    positives.append(int(it["id"]))
            if not positives:
                positives = [int(scored[0][1]["id"])]
            suggested = [
                {
                    "id": int(it["id"]),
                    "sim": float(sim),
                    "page": it.get("meta", {}).get("page"),
                    "type": it.get("meta", {}).get("type"),
                    "span": it.get("meta", {}).get("span"),
                    "filename": it.get("meta", {}).get("filename"),
                }
                for sim, it in scored[:5]
            ]
            rec = {"query": q, "suggested_topk": suggested, "positive_ids": positives}
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote 30 queries with positive_ids -> {out_path}")


if __name__ == "__main__":
    main()
