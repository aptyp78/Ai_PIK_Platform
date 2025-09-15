#!/usr/bin/env python3
import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List


def openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    return OpenAI(api_key=api_key)


def ensure_png(path: Path, caption: str, text: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return
    W, H = 1000, 600
    im = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    body = (caption or text or "Region (no image)").strip()
    max_w = W - 80
    words = body.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    y = 40
    for ln in lines[:14]:
        draw.text((40, y), ln, fill=(20, 20, 20), font=font)
        y += 40
    im.save(path)


def llm_analyze(client, text: str, image_b64: str, model: str) -> (str, Dict[str, Any]):
    content = []
    if image_b64:
        data_url = f"data:image/png;base64,{image_b64}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    if text:
        content.append({"type": "text", "text": f"Region OCR/Text:\n{text[:4000]}"})

    sys = (
        "You are a vision+text analyst. For the provided region, produce: (1) a concise caption (1-2 sentences) and (2) a normalized JSON structure."
    )
    # caption
    cap = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": content + [{"type": "text", "text": "Task 1: Return a 1-2 sentence caption."}]},
        ],
    )
    caption = (cap.choices[0].message.content or "").strip()

    # struct
    struct_instr = (
        "Task 2: Return ONLY a JSON object in one of shapes: Canvas/Assessment/Diagram as previously described."
    )
    st = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": content + [{"type": "text", "text": struct_instr}]},
        ],
    )
    raw = (st.choices[0].message.content or "{}").strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n").split("\n", 1)[-1]
        if raw.startswith("json\n"):
            raw = raw[5:]
    try:
        struct = json.loads(raw)
    except Exception:
        struct = {"artifact_type": "Unknown", "raw_text": raw}
    return caption, struct


def synthesize_triples(struct: Dict[str, Any], page: int, rid: int) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    at = (struct.get("artifact_type") or "").strip()
    def make_id(i):
        return f"t-p{page}-r{rid}-n{i}"
    i = 0
    if at == "Canvas":
        cv = struct.get("Canvas", {}) if isinstance(struct.get("Canvas"), dict) else {}
        for l in cv.get("layers", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": l, "type": "Layer"}, "predicate": "is_a", "object": {"name": "Layer", "type": "Class"}, "tags": ["Canvas"], "confidence": 0.80})
        for c in cv.get("components", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": c, "type": "Component"}, "predicate": "appears_in", "object": {"name": "Canvas", "type": "Artifact"}, "tags": ["Canvas"], "confidence": 0.75})
    elif at == "Assessment":
        asv = struct.get("Assessment", {}) if isinstance(struct.get("Assessment"), dict) else {}
        for p in (asv.get("pillars", {}) or {}).keys():
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": p, "type": "Pillar"}, "predicate": "is_a", "object": {"name": "Pillar", "type": "Class"}, "tags": ["Assessment"], "confidence": 0.80})
        for cr in asv.get("criteria", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": cr, "type": "Criterion"}, "predicate": "belongs_to", "object": {"name": "Assessment", "type": "Artifact"}, "tags": ["Assessment"], "confidence": 0.70})
    elif at == "Diagram":
        dg = struct.get("Diagram", {}) if isinstance(struct.get("Diagram"), dict) else {}
        for e in dg.get("entities", []) or []:
            i += 1
            triples.append({"id": make_id(i), "subject": {"name": e, "type": "Entity"}, "predicate": "appears_in", "object": {"name": "Diagram", "type": "Artifact"}, "tags": ["Diagram"], "confidence": 0.70})
    return triples


def main():
    ap = argparse.ArgumentParser(description="Analyze detected regions with LLM and write artifacts")
    ap.add_argument("--detected-dir", default="out/visual/regions_detect", help="Directory with <unit>/regions/region-*.json (pages or generic names)")
    ap.add_argument("--pages", nargs="*", type=int, help="Numeric pages to process (optional)")
    ap.add_argument("--all", action="store_true", help="Process all subdirectories found under detected-dir")
    ap.add_argument("--outdir", default="out/visual/regions_detect", help="Where to write region artifacts (same tree)")
    ap.add_argument("--chat-model", default="gpt-4o")
    args = ap.parse_args()

    client = openai_client()
    root = Path(args.detected_dir)
    if args.all or not args.pages:
        units = [d.name for d in sorted(root.iterdir()) if d.is_dir()]
    else:
        units = [str(p) for p in args.pages]

    for unit in units:
        rdir = root / unit / "regions"
        files = [p for p in sorted(rdir.glob("region-*.json")) if not p.name.endswith(".struct.json")]
        count = 0
        for jf in files:
            reg = json.loads(jf.read_text())
            try:
                rid = int(jf.stem.split("-")[-1])
            except Exception:
                continue
            caption, struct = llm_analyze(client, reg.get("text", ""), reg.get("image_b64") or "", args.chat_model)
            # save artifacts
            out_rdir = Path(args.outdir) / unit / "regions"
            out_rdir.mkdir(parents=True, exist_ok=True)
            (out_rdir / f"region-{rid}.caption.txt").write_text(caption + "\n", encoding="utf-8")
            (out_rdir / f"region-{rid}.struct.json").write_text(json.dumps(struct, ensure_ascii=False, indent=2))
            # ensure png exists
            png_path = out_rdir / f"region-{rid}.png"
            if reg.get("image_b64"):
                try:
                    png_path.write_bytes(base64.b64decode(reg["image_b64"]))
                except Exception:
                    pass
            if not png_path.exists():
                ensure_png(png_path, caption, reg.get("text", ""))
            # facts
            try:
                page_int = int(unit)
            except Exception:
                page_int = -1
            triples = synthesize_triples(struct, page=page_int, rid=rid)
            if triples:
                with open(out_rdir / f"region-{rid}.facts.jsonl", "w", encoding="utf-8") as f:
                    for tr in triples:
                        tr["provenance"] = {"page": page_int if page_int >= 0 else None, "region_id": rid, "bbox": reg.get("bbox"), "snippet": (reg.get("text") or "")[:240]}
                        f.write(json.dumps(tr, ensure_ascii=False) + "\n")
            count += 1
        print(f"Analyzed {count} detected regions in unit {unit} -> {rdir}")


if __name__ == "__main__":
    main()
