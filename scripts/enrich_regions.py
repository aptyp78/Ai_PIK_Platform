#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # type: ignore


TYPE_KEYWORDS: Dict[str, List[str]] = {
    "Table": ["table", "row", "column", "таблица"],
    "Diagram": ["diagram", "диаграм", "flow", "workflow", "process", "процесс", "map", "карта", "graph", "граф", "uml", "block", "блок-схем", "pipeline"],
    "Canvas": ["canvas", "канвас", "value network", "aarrr", "business model", "канва", "матриц"],
    "Legend": ["legend", "легенда"],
    "Node": ["node", "узел"],
    "Arrow": ["arrow", "стрелк"],
    "Chart": ["chart", "bar", "line chart", "pie", "гистограмм", "кругов", "линейн", "axis", "ось", "ось x", "ось y"],
    "Image": ["photo", "image", "изображен", "фото"],
    "Banner": ["cover", "banner", "title", "заголовок", "обложк"],
}

TYPE_SCORE_DEFAULTS: Dict[str, float] = {
    "Diagram": 0.60,
    "Canvas": 0.70,
    "Table": 0.65,
    "Legend": 0.45,
    "Node": 0.40,
    "Arrow": 0.40,
    "Chart": 0.60,
    "Image": 0.35,
    "Banner": 0.50,
}

def load_type_weights() -> Dict[str, float]:
    p = Path("tags/weights.json")
    base: Dict[str, float] = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for k, v in data.items():
                try:
                    base[str(k)] = float(v)
                except Exception:
                    pass
        except Exception:
            pass
    # Map common types to weights if present
    mapping: Dict[str, float] = {}
    for t in TYPE_SCORE_DEFAULTS.keys():
        # use highest matching weight among tags keys containing our type name
        w = None
        for k, val in base.items():
            if t.lower() in k.lower():
                w = max(val if w is None else w, val)
        if w is not None:
            mapping[t] = float(w)
    return mapping


def load_visual_type_keywords() -> Dict[str, List[str]]:
    kw = TYPE_KEYWORDS.copy()
    p = Path("config/semantic_synonyms.yaml")
    if yaml is not None and p.exists():
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            vt = data.get("VisualTypes") or {}
            if isinstance(vt, dict):
                for t, arr in vt.items():
                    cur = [*kw.get(t, [])]
                    cur.extend([str(x).lower() for x in (arr or [])])
                    # dedupe
                    seen = set(); out=[]
                    for s in cur:
                        s=s.lower()
                        if s not in seen:
                            seen.add(s); out.append(s)
                    kw[t]=out
        except Exception:
            pass
    return kw

VISUAL_KW = load_visual_type_keywords()

def infer_type(caption: str, text: str) -> str | None:
    s = (caption or "") + "\n" + (text or "")
    s = s.lower()
    for t, kws in VISUAL_KW.items():
        for k in kws:
            if k in s:
                return t
    return None


def text_signal(caption: str, text: str) -> float:
    s = (caption or "") + "\n" + (text or "")
    s = s.lower()
    hits = 0
    for arr in VISUAL_KW.values():
        for k in arr:
            if k in s:
                hits += 1
                if hits >= 10:
                    break
        if hits >= 10:
            break
    tl = len((text or "").split())
    sig = min(1.0, hits / 10.0)
    if tl > 200:
        sig *= 0.85
    return max(0.0, min(1.0, sig))

def auto_score_for(t: str, caption: str, text: str, weights: Dict[str, float], shape_score: float | None = None) -> float:
    prior = TYPE_SCORE_DEFAULTS.get(t, 0.45)
    w = weights.get(t)
    if isinstance(w, (int, float)):
        prior = 0.5 * prior + 0.5 * float(w)
    ts = text_signal(caption, text)
    ss = float(shape_score) if isinstance(shape_score, (int, float)) else 0.5
    score = 0.5 * prior + 0.3 * ts + 0.2 * ss
    return max(0.0, min(1.0, score))

def tier_for(score: float, rtype: str) -> str:
    t = (rtype or "").lower()
    if t in {"canvas", "diagram", "table", "chart"}:
        if score >= 0.70:
            return "Major"
        if score >= 0.55:
            return "Secondary"
        return "Hint"
    if score >= 0.65:
        return "Major"
    if score >= 0.50:
        return "Secondary"
    return "Hint"


def tier(score: float) -> str:
    if score >= 0.70:
        return "Major"
    if score >= 0.50:
        return "Secondary"
    return "Hint"


def extract_visual_facts(r: Dict[str, Any], rtype: str) -> Dict[str, Any]:
    cap = (r.get("caption") or "").lower()
    txt = (r.get("text") or "").lower()
    s = cap + "\n" + txt
    facts: Dict[str, Any] = {}
    # simple regex-based counts
    import re
    if "table" in rtype.lower() or "таблиц" in s:
        # heuristics: count cell/row words as proxies
        rows = len(re.findall(r"row|строк", s))
        cols = len(re.findall(r"col|column|столб", s))
        if rows or cols:
            facts["table_shape_hint"] = {"rows": rows or None, "cols": cols or None}
    arrows = len(re.findall(r"arrow|стрелк", s))
    nodes = len(re.findall(r"node|узел", s))
    if arrows:
        facts["arrows"] = arrows
    if nodes:
        facts["nodes"] = nodes
    if any(k in s for k in ["axis", "ось x", "ось y", "axis x", "axis y"]):
        facts["axes"] = True
    return facts


def process_item(item_dir: Path, weights: Dict[str, float]) -> Tuple[int, int]:
    agg = item_dir / "regions.json"
    if not agg.exists():
        return 0, 0
    try:
        js = json.loads(agg.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0
    regs: List[Dict[str, Any]] = js.get("regions") or []
    updated = 0
    for r in regs:
        cap = (r.get("caption") or "").strip()
        txt = (r.get("text") or "").strip()
        rtype = (r.get("struct_type") or "").strip()
        if not rtype:
            it = infer_type(cap, txt)
            if it:
                r["struct_type"] = it
                rtype = it
                updated += 1
        # Tagging/Scoring
        try:
            s2 = None
            ms = r.get("mask_stats") or {}
            if isinstance(ms, dict) and "s2" in ms:
                try:
                    s2 = float(ms.get("s2"))
                except Exception:
                    s2 = None
            tscore = auto_score_for(rtype or "", cap, txt, weights, shape_score=s2) if rtype else 0.35
            # attach Tagging compatible with earlier tools
            r.setdefault("Tagging", {})
            r["Tagging"]["AutoScore"] = tscore
            r["Tagging"]["AutoTier"] = tier_for(tscore, rtype or "")
            # light Scoring profile
            r.setdefault("scoring", {})
            r["scoring"]["final_weight"] = tscore
            r["scoring"]["confidence_visual"] = 0.6 if rtype else 0.4
            # attach minimal VisualFacts
            vf = extract_visual_facts(r, rtype or "")
            if vf:
                r["facts"] = vf
        except Exception:
            pass
    # write back
    try:
        js["regions"] = regs
        agg.write_text(json.dumps(js, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return len(regs), updated


def main():
    ap = argparse.ArgumentParser(description="Enrich unified regions: infer struct_type, compute AutoScore/AutoTier, attach scoring")
    ap.add_argument("--root", default="out/visual/regions/gdino_sam2")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    root = Path(args.root)
    total = 0
    changed = 0
    if not root.exists():
        print(f"no root: {root}")
        return
    weights = load_type_weights()
    for slug_dir in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name):
        for item_dir in sorted([p for p in slug_dir.iterdir() if p.is_dir()]):
            n, u = process_item(item_dir, weights)
            total += n
            changed += u
            if args.limit and changed >= args.limit:
                break
        if args.limit and changed >= args.limit:
            break
    print(f"Processed regions: {total}; updated types: {changed}")


if __name__ == "__main__":
    main()
