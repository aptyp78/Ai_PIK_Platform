#!/usr/bin/env python3
import argparse
import glob
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List


WANTED_TYPES = {"Title", "NarrativeText", "ListItem", "Header", "Footer", "Table", "Image"}
SKIP_TYPES = {"PageBreak"}


def iter_text_elements(path: Path) -> Iterable[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for el in data:
        t = (el.get("type") or "").strip()
        if t in SKIP_TYPES:
            continue
        if t not in WANTED_TYPES:
            continue
        text = (el.get("text") or "").strip()
        if not text:
            continue
        if t == "Image" and len(text) < 180:
            continue
        md = el.get("metadata", {}) or {}
        yield {
            "type": t,
            "text": text,
            "page": md.get("page_number"),
            "element_id": el.get("element_id"),
            "filename": md.get("filename") or path.name,
            "source_file": str(path),
        }


def chunk_with_overlap(elems: Iterable[Dict], max_chars: int = 1400, overlap_chars: int = 180) -> Iterable[Dict]:
    buf: List[Dict] = []
    size = 0
    for el in elems:
        t = el["text"]
        add_len = len(t) + (1 if buf else 0)
        if size and size + add_len > max_chars:
            text = "\n".join(x["text"] for x in buf)
            meta = {k: buf[0].get(k) for k in ("page", "element_id", "filename", "type", "source_file")}
            meta["span"] = len(buf)
            yield {"text": text, "meta": meta}
            # overlap tail
            if overlap_chars > 0:
                tail_text = text[-overlap_chars:]
                buf = [{"text": tail_text, **buf[-1]}]
                size = len(tail_text)
            else:
                buf, size = [], 0
        if buf:
            size += 1
        buf.append(el)
        size += len(t)
    if buf:
        text = "\n".join(x["text"] for x in buf)
        meta = {k: buf[0].get(k) for k in ("page", "element_id", "filename", "type", "source_file")}
        meta["span"] = len(buf)
        yield {"text": text, "meta": meta}


def embed_openai(chunks: List[Dict], model: str, batch: int = 64) -> List[List[float]]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    client = OpenAI(api_key=api_key)
    inputs = [c["text"] for c in chunks]
    out: List[List[float]] = []
    for i in range(0, len(inputs), batch):
        resp = client.embeddings.create(model=model, input=inputs[i:i+batch])
        out.extend([d.embedding for d in resp.data])
    return out


def main():
    ap = argparse.ArgumentParser(description="Rebuild index from all Unstructured JSON under pik_source_bucket")
    ap.add_argument("--roots", nargs="*", default=[
        str(Path.home() / "GCS/pik_source_bucket/playbooks"),
        str(Path.home() / "GCS/pik_source_bucket/frames"),
        str(Path.home() / "GCS/pik_source_bucket/vlm_unstructured"),
        str(Path.home() / "GCS/pik_source_bucket/raw_json"),
        str(Path.home() / "GCS/pik_result_bucket/Qdrant_Destination/playbooks"),
        str(Path.home() / "GCS/pik_result_bucket/Qdrant_Destination/frames"),
    ], help="Directories to scan for *.json files")
    ap.add_argument("--out", default="out/openai_embeddings.ndjson")
    ap.add_argument("--model", default="text-embedding-3-large")
    ap.add_argument("--max-chars", type=int, default=1400)
    ap.add_argument("--overlap", type=int, default=180)
    args = ap.parse_args()

    # Collect all json files
    files: List[str] = []
    for root in args.roots:
        files.extend(glob.glob(os.path.join(root, "**/*.json"), recursive=True))
    files = sorted({f for f in files if f.lower().endswith('.json')})
    if not files:
        raise SystemExit("No JSON files found under given roots")

    all_chunks: List[Dict] = []
    for fp in files:
        p = Path(fp)
        try:
            elems = list(iter_text_elements(p))
        except Exception:
            continue
        if not elems:
            continue
        chunks = list(chunk_with_overlap(elems, max_chars=args.max_chars, overlap_chars=args.overlap))
        all_chunks.extend(chunks)
    if not all_chunks:
        raise SystemExit("No chunks collected from JSON files")

    vecs = embed_openai(all_chunks, model=args.model)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8") as f:
        for i, (c, v) in enumerate(zip(all_chunks, vecs)):
            rec = {
                "id": i,
                "text": c["text"],
                "vector": v,
                "meta": c["meta"],
                "provider": "openai",
                "model": args.model,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Indexed {len(all_chunks)} chunks from {len(files)} files to {outp}")


if __name__ == "__main__":
    main()

