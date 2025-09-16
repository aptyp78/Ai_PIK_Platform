#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


STOP = set(
    "the a an and or for from with into on at by of in to over under against between among across as is are was were be been being it this that those these which who what when where why how your our their its".split()
)


def load_struct(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def triples_from_struct(struct: Dict[str, Any], page: int, rid: int) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    at = (struct.get("artifact_type") or "").strip()
    i = 0
    def add(subj_name: str, subj_type: str, pred: str, obj_name: str, obj_type: str, tags: List[str], conf: float):
        nonlocal i
        i += 1
        triples.append({
            "id": f"t-p{page}-r{rid}-n{i}",
            "subject": {"name": subj_name, "type": subj_type},
            "predicate": pred,
            "object": {"name": obj_name, "type": obj_type},
            "tags": tags,
            "confidence": conf,
        })

    if at == "Canvas":
        cv = struct.get("Canvas", {}) if isinstance(struct.get("Canvas"), dict) else {}
        for l in (cv.get("layers", []) or []):
            # Always tag Layer + Canvas; add canonical layer tag if matched
            tags = ["Canvas", "Layer"]
            low = str(l).strip().lower()
            canon = {
                "engagement": "Engagement",
                "intelligence": "Intelligence",
                "infrastructure": "Infrastructure",
                "ecosystem": "EcosystemConnectivity",
                "ecosystem connectivity": "EcosystemConnectivity",
            }.get(low)
            if canon:
                tags.append(canon)
            add(str(l), "Layer", "is_a", "Layer", "Class", tags, 0.80)
        for c in (cv.get("components", []) or []):
            add(str(c), "Component", "appears_in", "Canvas", "Artifact", ["Canvas", "Component"], 0.75)
    elif at == "Assessment":
        av = struct.get("Assessment", {}) if isinstance(struct.get("Assessment"), dict) else {}
        for p in (av.get("pillars", {}) or {}).keys():
            add(str(p), "Pillar", "is_a", "Pillar", "Class", ["Assessment"], 0.80)
        for cr in (av.get("criteria", []) or []):
            add(str(cr), "Criterion", "belongs_to", "Assessment", "Artifact", ["Assessment"], 0.70)
    elif at == "Diagram":
        dg = struct.get("Diagram", {}) if isinstance(struct.get("Diagram"), dict) else {}
        for e in (dg.get("entities", []) or []):
            add(str(e), "Entity", "appears_in", "Diagram", "Artifact", ["Diagram"], 0.70)
    return triples


def fallback_from_caption(caption: str, page: int, rid: int, limit: int = 6) -> List[Dict[str, Any]]:
    if not caption:
        return []
    # extract tokens (keep alnum and hyphen), length >=3, skip stopwords
    toks = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}" , caption)
    uniq = []
    seen = set()
    for t in toks:
        tt = t.strip().strip('-')
        low = tt.lower()
        if low in STOP:
            continue
        if low in seen:
            continue
        seen.add(low)
        uniq.append(tt)
        if len(uniq) >= limit:
            break
    triples = []
    for i, term in enumerate(uniq, start=1):
        triples.append({
            "id": f"t-p{page}-r{rid}-f{i}",
            "subject": {"name": term, "type": "Entity"},
            "predicate": "mentioned_in",
            "object": {"name": "Region", "type": "Artifact"},
            "tags": ["Fallback"],
            "confidence": 0.40,
        })
    return triples


def process_root(root: Path) -> int:
    total_regions = 0
    for unit in sorted([d for d in root.iterdir() if d.is_dir()]):
        try:
            page = int(unit.name)
        except Exception:
            page = -1
        rdir = unit / "regions"
        if not rdir.exists():
            continue
        for cap in sorted(rdir.glob("region-*.caption.txt")):
            stem = cap.stem  # e.g., region-1.caption
            try:
                rid = int(stem.split('-')[-1].split('.')[0])
            except Exception:
                continue
            struct_path = rdir / f"region-{rid}.struct.json"
            facts_path = rdir / f"region-{rid}.facts.jsonl"
            if facts_path.exists() and facts_path.stat().st_size > 0:
                total_regions += 1
                continue
            caption = cap.read_text(encoding='utf-8').strip()
            struct = load_struct(struct_path)
            triples = triples_from_struct(struct, page=page, rid=rid)
            if not triples:
                triples = fallback_from_caption(caption, page=page, rid=rid)
            with open(facts_path, 'w', encoding='utf-8') as f:
                for tr in triples:
                    f.write(json.dumps(tr, ensure_ascii=False) + "\n")
            total_regions += 1
    return total_regions


def main():
    ap = argparse.ArgumentParser(description="Ensure region facts exist; create fallback facts from caption if struct is unknown")
    ap.add_argument("--roots", nargs="+", default=["out/visual/cv_regions", "out/visual/cv_frames"], help="Region roots to process")
    args = ap.parse_args()

    count = 0
    for r in args.roots:
        root = Path(r)
        if root.exists():
            count += process_root(root)
    print(f"Processed regions: {count}")


if __name__ == "__main__":
    main()
