#!/usr/bin/env python3
import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError
try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


class BBox(BaseModel):
    x: float
    y: float
    w: float
    h: float
    unit: str = Field(default="pixel")


class CanvasStruct(BaseModel):
    artifact_type: str = Field(default="Canvas")
    Canvas: Dict[str, Any] = Field(default_factory=lambda: {
        "layers": [],
        "components": [],
        "personas": [],
        "journey": [],
        "relations": [],
    })


class AssessmentStruct(BaseModel):
    artifact_type: str = Field(default="Assessment")
    Assessment: Dict[str, Any] = Field(default_factory=lambda: {
        "pillars": {},
        "criteria": [],
        "questions": [],
        "scoring_fields": [],
    })


class DiagramStruct(BaseModel):
    artifact_type: str = Field(default="Diagram")
    Diagram: Dict[str, Any] = Field(default_factory=lambda: {
        "entities": [],
        "edges": [],
        "legend": [],
        "groups": [],
    })


def openai_client():
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise SystemExit(f"openai package not installed: {e}. Try: pip install openai>=1.40.0")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY env var is required")
    return OpenAI(api_key=api_key)


def decode_bbox(el: Dict[str, Any]) -> Optional[BBox]:
    md = el.get("metadata", {}) or {}
    # Try common patterns from Unstructured
    # 1) coordinates: {"points": [[x1,y1],[x2,y2],...]} (assume rectangle)
    coords = md.get("coordinates") or el.get("coordinates")
    if isinstance(coords, dict) and isinstance(coords.get("points"), list) and coords["points"]:
        pts = coords["points"]
        xs = [p[0] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
        ys = [p[1] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2]
        if xs and ys:
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            return BBox(x=float(x0), y=float(y0), w=float(x1 - x0), h=float(y1 - y0), unit="pixel")
    # 2) bbox dict: {x,y,width,height}
    bbox = md.get("bbox") or el.get("bbox")
    if isinstance(bbox, dict):
        try:
            return BBox(x=float(bbox.get("x", 0)), y=float(bbox.get("y", 0)), w=float(bbox.get("width", 0)), h=float(bbox.get("height", 0)), unit="pixel")
        except Exception:
            pass
    return None


def extract_regions(path: Path, pages: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    data = json.loads(path.read_text())
    regions: Dict[int, List[Dict[str, Any]]] = {}
    rid = 0
    wanted = {"Image", "Table", "Diagram", "Title", "NarrativeText", "ListItem"}
    for el in data:
        md = el.get("metadata", {}) or {}
        page = md.get("page_number")
        if page is None:
            continue
        page = int(page)
        if pages and page not in pages:
            continue
        etype = (el.get("type") or "").strip()
        if etype not in wanted:
            continue
        text = (el.get("text") or "").strip()
        img_b64 = None
        if isinstance(el.get("image_base64"), str):
            img_b64 = el.get("image_base64")
        elif isinstance(md.get("image_base64"), str):
            img_b64 = md.get("image_base64")
        bbox = decode_bbox(el)
        rid += 1
        reg = {
            "region_id": rid,
            "type": etype,
            "text": text,
            "image_b64": img_b64,
            "bbox": bbox.dict() if bbox else None,
        }
        regions.setdefault(page, []).append(reg)
    return regions


def llm_analyze_region(client, text: str, img_b64: Optional[str], model: str = "gpt-4o") -> Tuple[str, Dict[str, Any]]:
    sys_prompt = (
        "You are a vision+text analyst. For the provided region, produce: (1) a concise caption (1-2 sentences) and (2) a normalized JSON structure."
    )
    content: List[Dict[str, Any]] = []
    if img_b64:
        data_url = f"data:image/png;base64,{img_b64}"
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    if text:
        content.append({"type": "text", "text": f"Region OCR/Text:\n{text[:4000]}"})

    # Caption
    cap = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": content + [{"type": "text", "text": "Task 1: Return a 1-2 sentence caption."}]},
        ],
    )
    caption = (cap.choices[0].message.content or "").strip()

    # Struct
    struct_instr = (
        "Task 2: Return ONLY a JSON object with one of the following shapes: \n"
        "CanvasStruct, AssessmentStruct, or DiagramStruct as described:\n"
        "Canvas: {artifact_type:'Canvas', Canvas:{layers:[], components:[], personas:[], journey:[], relations:[]}}\n"
        "Assessment: {artifact_type:'Assessment', Assessment:{pillars:{...}, criteria:[], questions:[], scoring_fields:[]}}\n"
        "Diagram: {artifact_type:'Diagram', Diagram:{entities:[], edges:[], legend:[], groups:[]}}\n"
    )
    st = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": sys_prompt},
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


def validate_struct(struct: Dict[str, Any]) -> Dict[str, Any]:
    at = (struct.get("artifact_type") or "").strip()
    try:
        if at == "Canvas":
            return CanvasStruct(**struct).dict()
        if at == "Assessment":
            return AssessmentStruct(**struct).dict()
        if at == "Diagram":
            return DiagramStruct(**struct).dict()
    except ValidationError:
        pass
    return struct


def synthesize_triples(struct: Dict[str, Any], page: int, region_id: int) -> List[Dict[str, Any]]:
    """
    Produce strict triples with ids and confidence.
    ID format: t-p{page}-r{region}-n{idx}
    """
    triples: List[Dict[str, Any]] = []
    at = (struct.get("artifact_type") or "").strip()
    idx = 0
    def next_id() -> str:
        nonlocal idx
        idx += 1
        return f"t-p{page}-r{region_id}-n{idx}"

    if at == "Canvas":
        canvas = struct.get("Canvas", {}) if isinstance(struct.get("Canvas"), dict) else {}
        for l in canvas.get("layers", []) or []:
            triples.append({
                "id": next_id(),
                "subject": {"name": l, "type": "Layer"},
                "predicate": "is_a",
                "object": {"name": "Layer", "type": "Class"},
                "tags": ["Canvas"],
                "confidence": 0.80,
            })
        for c in canvas.get("components", []) or []:
            triples.append({
                "id": next_id(),
                "subject": {"name": c, "type": "Component"},
                "predicate": "appears_in",
                "object": {"name": "Canvas", "type": "Artifact"},
                "tags": ["Canvas"],
                "confidence": 0.75,
            })
    elif at == "Assessment":
        assess = struct.get("Assessment", {}) if isinstance(struct.get("Assessment"), dict) else {}
        for p in (assess.get("pillars", {}) or {}).keys():
            triples.append({
                "id": next_id(),
                "subject": {"name": p, "type": "Pillar"},
                "predicate": "is_a",
                "object": {"name": "Pillar", "type": "Class"},
                "tags": ["Assessment"],
                "confidence": 0.80,
            })
        for cr in assess.get("criteria", []) or []:
            triples.append({
                "id": next_id(),
                "subject": {"name": cr, "type": "Criterion"},
                "predicate": "belongs_to",
                "object": {"name": "Assessment", "type": "Artifact"},
                "tags": ["Assessment"],
                "confidence": 0.70,
            })
    elif at == "Diagram":
        diagram = struct.get("Diagram", {}) if isinstance(struct.get("Diagram"), dict) else {}
        for e in diagram.get("entities", []) or []:
            triples.append({
                "id": next_id(),
                "subject": {"name": e, "type": "Entity"},
                "predicate": "appears_in",
                "object": {"name": "Diagram", "type": "Artifact"},
                "tags": ["Diagram"],
                "confidence": 0.70,
            })
    return triples


def save_region_artifacts(base_dir: Path, page: int, region: Dict[str, Any], caption: str, struct: Dict[str, Any]) -> None:
    rdir = base_dir / f"{page}" / "regions"
    rdir.mkdir(parents=True, exist_ok=True)
    rid = region["region_id"]
    (rdir / f"region-{rid}.caption.txt").write_text(caption + "\n", encoding="utf-8")
    (rdir / f"region-{rid}.struct.json").write_text(json.dumps(struct, ensure_ascii=False, indent=2))
    out_png = rdir / f"region-{rid}.png"
    if region.get("image_b64"):
        try:
            img = base64.b64decode(region["image_b64"])
            out_png.write_bytes(img)
        except Exception:
            pass
    else:
        # Fallback: synthesize a simple preview image from text/caption so that counts match
        if PIL_AVAILABLE:
            try:
                text = caption or (region.get("text") or "")
                text = text.strip() or f"Region {rid} (no image)"
                # Basic card rendering
                W, H = 1000, 600
                bg = (255, 255, 255)
                fg = (20, 20, 20)
                im = Image.new("RGB", (W, H), bg)
                draw = ImageDraw.Draw(im)
                try:
                    font = ImageFont.load_default()
                except Exception:
                    font = None
                # word-wrap
                max_w = W - 80
                words = text.split()
                lines = []
                cur = ""
                for w in words:
                    test = (cur + " " + w).strip()
                    size = draw.textlength(test, font=font)
                    if size <= max_w:
                        cur = test
                    else:
                        if cur:
                            lines.append(cur)
                        cur = w
                if cur:
                    lines.append(cur)
                y = 40
                for ln in lines[:14]:
                    draw.text((40, y), ln, fill=fg, font=font)
                    y += 40
                im.save(out_png)
            except Exception:
                pass
    # Triples with provenance
    triples = synthesize_triples(struct, page=page, region_id=rid)
    if triples:
        with open(rdir / f"region-{rid}.facts.jsonl", "w", encoding="utf-8") as jf:
            for tr in triples:
                tr["provenance"] = {
                    "page": page,
                    "region_id": rid,
                    "bbox": region.get("bbox"),
                    "snippet": (region.get("text") or "")[:240],
                }
                jf.write(json.dumps(tr, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Region-level visual extraction with strict schema and provenance")
    ap.add_argument("--json", required=True, help="Path to Unstructured JSON source")
    ap.add_argument("--pages", nargs="+", type=int, help="Printed page numbers to process")
    ap.add_argument("--outdir", default="out/visual/regions", help="Output directory")
    ap.add_argument("--chat-model", default="gpt-4o", help="Vision-capable model")
    args = ap.parse_args()

    src = Path(args.json)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    pages = [int(p) for p in args.pages]

    client = openai_client()
    pages_regions = extract_regions(src, pages)

    for page, regs in sorted(pages_regions.items()):
        for reg in regs:
            caption, struct = llm_analyze_region(client, reg.get("text", ""), reg.get("image_b64"), model=args.chat_model)
            struct = validate_struct(struct)
            save_region_artifacts(outdir, page, reg, caption, struct)
        print(f"Processed page {page} with {len(regs)} regions -> {outdir}/{page}/regions/")


if __name__ == "__main__":
    main()
