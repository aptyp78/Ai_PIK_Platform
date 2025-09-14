#!/usr/bin/env python3
import argparse
import glob
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


WANTED_TYPES = {
    "Title",
    "NarrativeText",
    "ListItem",
    "Header",
    "Footer",
    "Table",
    "Image",
}


def iter_text_elements(path: Path) -> Iterable[Dict]:
    data = json.loads(path.read_text())
    for el in data:
        if el.get("type") in WANTED_TYPES:
            t = (el.get("text") or "").strip()
            if t:
                md = el.get("metadata", {}) or {}
                yield {
                    "text": t,
                    "page": md.get("page_number"),
                    "element_id": el.get("element_id"),
                    "filename": md.get("filename") or path.name,
                    "type": el.get("type"),
                    "source_file": str(path),
                }


def chunk_elements(elems: Iterable[Dict], max_chars: int = 2500) -> Iterable[Dict]:
    buf: List[Dict] = []
    size = 0
    for el in elems:
        t = el["text"]
        if size and size + 1 + len(t) > max_chars:
            yield {
                "text": "\n".join(x["text"] for x in buf),
                "meta": {**{k: buf[0].get(k) for k in ("page", "element_id", "filename", "type", "source_file")}, "span": len(buf)},
            }
            buf, size = [], 0
        buf.append(el)
        size += len(t) + 1
    if buf:
        yield {
            "text": "\n".join(x["text"] for x in buf),
            "meta": {**{k: buf[0].get(k) for k in ("page", "element_id", "filename", "type", "source_file")}, "span": len(buf)},
        }


def embed_openai_texts(chunks: List[Dict], model: str = "text-embedding-3-large", batch: int = 64) -> List[List[float]]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required in env")
    client = OpenAI(api_key=api_key)

    inputs = [c["text"] for c in chunks]
    vectors: List[List[float]] = []
    for i in range(0, len(inputs), batch):
        resp = client.embeddings.create(model=model, input=inputs[i : i + batch])
        vectors.extend([d.embedding for d in resp.data])
    return vectors


def load_existing(out_path: Path) -> Tuple[List[Dict], int]:
    existing = []
    next_id = 0
    if out_path.exists():
        with open(out_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                existing.append(obj)
        if existing:
            next_id = max(int(o.get("id", -1)) for o in existing) + 1
    return existing, next_id


def main() -> None:
    ap = argparse.ArgumentParser(description="Embed multiple Unstructured JSONs and append to index")
    ap.add_argument("--out", default="out/openai_embeddings.ndjson")
    ap.add_argument("--max-chars", type=int, default=2500)
    ap.add_argument("--model", default="text-embedding-3-large")
    ap.add_argument("files", nargs="+", help="File paths or globs to JSONs")
    args = ap.parse_args()

    # Resolve files
    file_list: List[Path] = []
    for pat in args.files:
        for p in glob.glob(pat):
            file_list.append(Path(p))
    if not file_list:
        raise SystemExit("No files matched")

    # Collect new chunks
    all_chunks: List[Dict] = []
    for fp in file_list:
        elems = list(iter_text_elements(fp))
        chunks = list(chunk_elements(elems, max_chars=args.max_chars))
        all_chunks.extend(chunks)
    print(f"Collected {len(all_chunks)} chunks from {len(file_list)} files")

    # Embed
    vectors = embed_openai_texts(all_chunks, model=args.model)
    if len(vectors) != len(all_chunks):
        raise SystemExit("Embedding count mismatch")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing, next_id = load_existing(out_path)

    with open(out_path, "a") as f:
        for c, vec in zip(all_chunks, vectors):
            rec = {
                "id": next_id,
                "text": c["text"],
                "vector": vec,
                "meta": c["meta"],
                "provider": "openai",
                "model": args.model,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            next_id += 1
    print(f"Appended {len(all_chunks)} chunks to {out_path}")


if __name__ == "__main__":
    main()
