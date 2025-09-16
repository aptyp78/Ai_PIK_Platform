#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Dict, Tuple
import math


def load_ndjson(path: Path):
    items = []
    with open(path, "r") as f:
        for line in f:
            if line.strip():
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


DEFAULT_QUERIES = [
    "Какие слои включает Platform Architecture Canvas?",
    "Что входит в слой Engagement (Engagement Layer)?",
    "Что входит в слой Intelligence (Intelligence Layer)?",
    "Что входит в слой Infrastructure (Infrastructure Layer)?",
    "Что входит в слой Ecosystem Connectivity?",
    "Какие типовые компоненты Canvas на уровне Engagement?",
    "Какие сущности и связи обычно показаны на диаграммах платформы?",
    "Какие роли/персоны учитывает Canvas?",
    "Как строится пользовательский путь (journey) в Canvas?",
    "Что такое Assessment и какие артефакты он включает?",
    "Какие есть столпы (pillars) оценивания?",
    "Какие критерии у столпа Security?",
    "Какие критерии у столпа Reliability?",
    "Какие критерии у столпа Operational Excellence?",
    "Какие критерии у столпа Performance Efficiency?",
    "Какие критерии у столпа Cost Optimization?",
    "Что такое Platform Architecture Framework?",
    "Чем отличается Core Value Layer от Sub Value Layer?",
    "Где посмотреть Table View Canvas?",
    "Какие компоненты относятся к Data Platform?",
    "Что включает Monitoring/Observability?",
    "Какую роль играет Identity and Access Management (IAM)?",
    "Где описан API Gateway/Management?",
    "Какие компоненты Edge/IoT на уровне Ecosystem Connectivity?",
    "Какие метрики используются для оценки качества поиска?",
    "Как формируются Visual Facts из структур?",
    "Как собрать контекст для RAG ответа и указать источники?",
    "Как фильтровать по тегам Pillar/Layer при поиске?",
    "Какой процесс построения Platform IT Architecture?",
    "Какие источники данных и артефактов используются в пайплайне?",
    "Как включить GroundedDINO+SAM2 и где хранить веса?",
    "Как просмотреть визуальный обзор артефактов?",
    "Какие шаги для миграции индекса в Qdrant?",
]


def main():
    ap = argparse.ArgumentParser(description="Generate eval queries with suggested_topk from index")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--out", default="eval/queries_additions.jsonl")
    ap.add_argument("--embed-model", default="text-embedding-3-large")
    ap.add_argument("--prefer-visual", action="store_true")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--in", dest="infile", default=None, help="Optional text file with one query per line")
    args = ap.parse_args()

    items = load_ndjson(Path(args.index))
    id_to = {it["id"]: it for it in items}
    if args.infile:
        qpath = Path(args.infile)
        queries = [ln.strip() for ln in qpath.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    else:
        queries = DEFAULT_QUERIES
    qvecs = embed_openai_batch(queries, model=args.embed_model)

    # type weights
    type_w = {"Text": 1.0, "VisualCaption": 1.0, "VisualFact": 1.0, "Image": 0.95, "Table": 1.0}
    if args.prefer_visual:
        type_w.update({"VisualCaption": 1.1, "VisualFact": 1.05})

    with open(args.out, "w", encoding="utf-8") as f:
        for q, qv in zip(queries, qvecs):
            scored: List[Tuple[float, Dict]] = []
            for it in items:
                sim = cosine_sim(qv, it["vector"])  # type: ignore
                t = (it.get("meta", {}) or {}).get("type")
                w = type_w.get(t, 1.0)
                scored.append((sim * w, it))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = []
            for s, it in scored[: args.k]:
                m = it.get("meta", {})
                top.append({
                    "id": it.get("id"),
                    "sim": s,
                    "page": m.get("page"),
                    "type": m.get("type"),
                    "span": m.get("span"),
                    "filename": m.get("filename"),
                })
            rec = {"query": q, "suggested_topk": top, "positive_ids": []}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(queries)} query candidates to {args.out}")


if __name__ == "__main__":
    main()
