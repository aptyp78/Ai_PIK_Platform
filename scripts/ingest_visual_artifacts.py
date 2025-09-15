#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


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


def openai_embed_batch(texts: List[str], model: str) -> List[List[float]]:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def main():
    ap = argparse.ArgumentParser(description="Ingest visual caption/facts into embeddings index")
    ap.add_argument("--source-json", required=True, help="Original Unstructured JSON path (for meta filename)")
    ap.add_argument("--pages-dir", default="out/visual/pages", help="Directory with per-page artifacts")
    ap.add_argument("--regions-dir", default=None, help="Optional directory with region artifacts: <dir>/<page>/regions/region-*.facts.jsonl")
    ap.add_argument("--out", default="out/openai_embeddings.ndjson", help="Embeddings index path")
    ap.add_argument("--model", default="text-embedding-3-large", help="Embedding model")
    ap.add_argument("--batch", type=int, default=256, help="Batch size for embeddings")
    args = ap.parse_args()

    src_file = Path(args.source_json)
    pages_dir = Path(args.pages_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing, next_id = load_existing(out_path)

    # Collect texts to embed: caption per page, then each fact as separate item
    items: List[Dict] = []
    for pcap in sorted(pages_dir.glob("*.caption.txt")):
        page = int(pcap.stem.split(".")[0]) if "." in pcap.name else int(pcap.stem)
        caption = pcap.read_text(encoding="utf-8").strip()
        if caption:
            items.append({
                "kind": "VisualCaption",
                "page": page,
                "text": caption,
            })
        # Prefer structured facts if available
        pfacts_jsonl = pages_dir / f"{page}.facts.jsonl"
        if pfacts_jsonl.exists():
            for line in pfacts_jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                # Flatten structured fact into an embeddable string
                text = "; ".join(
                    [
                        f"type={obj.get('type')}",
                        f"subject={obj.get('subject')}",
                        f"predicate={obj.get('predicate')}",
                        f"object={obj.get('object')}",
                        (f"tags={','.join(obj.get('tags', []))}" if obj.get('tags') else ""),
                    ]
                ).strip("; ")
                items.append({
                    "kind": "VisualFact",
                    "page": page,
                    "text": text,
                })
        else:
            # fallback to plain facts
            pfacts = pages_dir / f"{page}.facts.txt"
            if pfacts.exists():
                for line in pfacts.read_text(encoding="utf-8").splitlines():
                    t = line.strip()
                    if t:
                        items.append({
                            "kind": "VisualFact",
                            "page": page,
                            "text": t,
                        })

    # Also ingest region-level facts if present (out/visual/regions/<page>/regions/region-*.facts.jsonl)
    regions_root = Path(args.regions_dir) if args.regions_dir else Path(str(pages_dir).replace("/pages", "/regions"))
    if regions_root.exists():
        reg_dirs: List[Path] = []
        if (regions_root / "regions").exists():
            reg_dirs.append(regions_root / "regions")
        else:
            reg_dirs.extend(list(regions_root.glob("*/regions")))
        for reg_dir in reg_dirs:
            unit = reg_dir.parent.name
            try:
                page = int(unit)
            except Exception:
                page = None
            for fjsonl in reg_dir.glob("region-*.facts.jsonl"):
                for line in fjsonl.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    prov = obj.get("provenance", {})
                    bbox = prov.get("bbox")
                    rid = prov.get("region_id")
                    # try to attach preview png if present
                    preview = None
                    try:
                        rid_int = int(rid) if rid is not None else None
                    except Exception:
                        rid_int = None
                    if rid_int is not None:
                        png_path = reg_dir / f"region-{rid_int}.png"
                        if png_path.exists():
                            # store workspace-relative path for preview
                            preview = str(png_path)
                    text = "; ".join([
                        f"type={obj.get('type')}",
                        f"subject={obj.get('subject')}",
                        f"predicate={obj.get('predicate')}",
                        f"object={obj.get('object')}",
                        (f"tags={','.join(obj.get('tags', []))}" if obj.get('tags') else ""),
                    ]).strip("; ")
                    items.append({
                        "kind": "VisualFact",
                        "page": page if page is not None else prov.get("page"),
                        "text": text,
                        "region_id": rid,
                        "bbox": bbox,
                        "preview": preview,
                    })

    if not items:
        raise SystemExit(f"No visual artifacts found under {pages_dir}")

    texts = [it["text"] for it in items]
    vectors: List[List[float]] = []
    # Simple batching
    for i in range(0, len(texts), args.batch):
        vectors.extend(openai_embed_batch(texts[i:i+args.batch], model=args.model))

    with open(out_path, "a") as f:
        for it, vec in zip(items, vectors):
            rec = {
                "id": next_id,
                "text": it["text"],
                "vector": vec,
                "meta": {
                    "type": it["kind"],
                    "page": it["page"],
                    "filename": src_file.name,
                    "source_file": str(src_file),
                    "span": 1,
                    "tags": [],
                    **({"bbox": it.get("bbox")} if it.get("bbox") else {}),
                    **({"region_id": it.get("region_id")} if it.get("region_id") else {}),
                    **({"preview": it.get("preview")} if it.get("preview") else {}),
                },
                "provider": "openai",
                "model": args.model,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            next_id += 1

    print(f"Ingested {len(items)} visual items into {out_path}")


if __name__ == "__main__":
    main()
