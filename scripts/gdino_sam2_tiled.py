#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


def require_packages() -> None:
    missing = []
    try:
        import groundingdino  # type: ignore  # noqa: F401
    except Exception:
        missing.append("groundingdino")
    if missing:
        raise SystemExit("Отсутствуют пакеты: " + ", ".join(missing))


def resolve_model_paths(grounding_model_cli: str, sam_model_cli: str) -> Tuple[str, str, str]:
    import os
    from pathlib import Path

    model_dir = os.getenv("MODEL_DIR", "").strip()
    grounding_path = grounding_model_cli.strip()
    if not grounding_path and model_dir:
        cands = list(Path(model_dir, "groundingdino").glob("*.pth"))
        if cands:
            grounding_path = str(cands[0])
    selected_kind = ""
    sam_path = sam_model_cli.strip()
    if not sam_path and model_dir:
        c2 = list(Path(model_dir, "sam2").glob("*.pt"))
        c1 = list(Path(model_dir, "sam").glob("*.pth"))
        if c2:
            sam_path = str(c2[0]); selected_kind = "sam2"
        elif c1:
            sam_path = str(c1[0]); selected_kind = "sam"
    if not selected_kind and sam_path:
        selected_kind = "sam2" if sam_path.endswith(".pt") else "sam"
    return grounding_path, sam_path, selected_kind or "sam"


@dataclass
class Tile:
    x0: int
    y0: int
    x1: int
    y1: int


def make_tiles(W: int, H: int, n: int, overlap: float) -> List[Tile]:
    tiles: List[Tile] = []
    if n <= 1:
        return [Tile(0, 0, W, H)]
    dx = W / float(n)
    dy = H / float(n)
    ox = int(overlap * dx)
    oy = int(overlap * dy)
    for r in range(n):
        for c in range(n):
            x0 = max(0, int(c * dx) - (ox if c > 0 else 0))
            y0 = max(0, int(r * dy) - (oy if r > 0 else 0))
            x1 = min(W, int((c + 1) * dx) + (ox if c < n - 1 else 0))
            y1 = min(H, int((r + 1) * dy) + (oy if r < n - 1 else 0))
            tiles.append(Tile(x0, y0, x1, y1))
    return tiles


def iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0: return 0.0
    area_a = max(1, (ax1 - ax0) * (ay1 - ay0))
    area_b = max(1, (bx1 - bx0) * (by1 - by0))
    return inter / float(area_a + area_b - inter)


def nms(boxes: List[Tuple[int,int,int,int]], scores: List[float], thr: float) -> List[int]:
    idxs = list(range(len(boxes)))
    idxs.sort(key=lambda i: scores[i], reverse=True)
    keep: List[int] = []
    while idxs:
        i = idxs.pop(0)
        keep.append(i)
        rem = []
        for j in idxs:
            if iou(boxes[i], boxes[j]) <= thr:
                rem.append(j)
        idxs = rem
    return keep


def detect_on_image(full_img: Path, outdir: Path, gdino_model, prompts: List[str],
                    grids: List[int], scales: List[float], box_thr: float, text_thr: float, nms_thr: float) -> int:
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore
    Image.MAX_IMAGE_PIXELS = None

    caption = ". ".join(prompts)
    im = Image.open(full_img).convert("RGB")
    W, H = im.size
    boxes_all: List[Tuple[int,int,int,int]] = []
    scores_all: List[float] = []
    phrases_all: List[str] = []

    # attempt both API variants by duck-typing
    def predict_tile(img_arr_or_path):
        try:
            boxes, logits, phrases = gdino_model.predict_with_caption(
                image=img_arr_or_path, captions=caption, box_threshold=box_thr, text_threshold=text_thr)
            # boxes normalized xyxy, logits list
            confs = []
            for lg in logits:
                try:
                    c = 1.0 / (1.0 + math.exp(-float(lg)))
                except Exception:
                    c = 0.5
                confs.append(c)
            return np.array(boxes, dtype=float), confs, list(phrases) if phrases is not None else [] , True
        except TypeError:
            # new API path (OpenCV BGR image expected)
            import cv2  # type: ignore
            if isinstance(img_arr_or_path, str):
                img_bgr = cv2.imread(img_arr_or_path)
            else:
                img_bgr = img_arr_or_path
            det, phr = gdino_model.predict_with_caption(
                image=img_bgr, caption=caption, box_threshold=box_thr, text_threshold=text_thr)
            if det is None or det.is_empty():
                return np.zeros((0,4), dtype=float), [], [], True
            boxes = det.xyxy.astype(float)
            confs = []
            ca = getattr(det, 'confidence', None)
            if ca is not None:
                confs = ca.tolist()
            return boxes, confs, list(phr) if phr is not None else [], False

    # Use original scale first
    import numpy as np  # type: ignore
    b, confs, phr, norm = predict_tile(str(full_img))
    if b.size:
        if norm:
            # normalized → px
            bpx = b.copy()
            bpx[:,[0,2]] *= W
            bpx[:,[1,3]] *= H
        else:
            bpx = b
        for (x0,y0,x1,y1), c, p in zip(bpx, confs or [0.5]*len(bpx), phr or [""]*len(bpx)):
            boxes_all.append((int(x0),int(y0),int(x1),int(y1)))
            scores_all.append(float(c))
            phrases_all.append(p)

    # Tiled detections with multi-scale
    import numpy as np  # type: ignore
    import cv2  # type: ignore
    img_bgr_full = cv2.imread(str(full_img))
    for scale in scales:
        if scale <= 0: continue
        if abs(scale - 1.0) < 1e-6:
            img_bgr_scaled = img_bgr_full
            Ws, Hs = W, H
        else:
            Ws = int(W * scale); Hs = int(H * scale)
            img_bgr_scaled = cv2.resize(img_bgr_full, (Ws, Hs), interpolation=cv2.INTER_LINEAR)
        for n in grids:
            tiles = make_tiles(Ws, Hs, n=n, overlap=0.15)
            for t in tiles:
                crop = img_bgr_scaled[t.y0:t.y1, t.x0:t.x1]
                if crop is None or crop.size == 0:
                    continue
                b, confs, phr, norm = predict_tile(crop)
                if b.size == 0:
                    continue
                # map to full px
                bpx = b.copy()
                if norm:
                    h = float(t.y1 - t.y0); w = float(t.x1 - t.x0)
                    bpx[:,[0,2]] *= w; bpx[:,[1,3]] *= h
                # add tile offset in scaled space
                bpx[:,[0,2]] += t.x0; bpx[:,[1,3]] += t.y0
                # if scaled, map back to original
                if abs(scale - 1.0) > 1e-6:
                    bpx[:,[0,2]] = bpx[:,[0,2]] / scale
                    bpx[:,[1,3]] = bpx[:,[1,3]] / scale
                for (x0,y0,x1,y1), c, p in zip(bpx, confs or [0.5]*len(bpx), phr or [""]*len(bpx)):
                    boxes_all.append((int(x0),int(y0),int(x1),int(y1)))
                    scores_all.append(float(c))
                    phrases_all.append(p)

    # NMS merge
    if boxes_all:
        keep = nms(boxes_all, scores_all, thr=nms_thr)
        boxes_all = [boxes_all[i] for i in keep]
        scores_all = [scores_all[i] for i in keep]
        phrases_all = [phrases_all[i] for i in keep]

    # Write out raw regions
    rdir = outdir / full_img.stem / 'regions'
    rdir.mkdir(parents=True, exist_ok=True)
    from PIL import Image  # type: ignore
    im = Image.open(full_img).convert('RGB')
    cnt = 0
    for i, (bx, sc, ph) in enumerate(zip(boxes_all, scores_all, phrases_all), start=1):
        x0,y0,x1,y1 = bx
        w = max(1, x1-x0); h=max(1, y1-y0)
        crop = im.crop((x0,y0,x1,y1))
        import io
        buf = io.BytesIO(); crop.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        rec = {
            'bbox': {'x': x0, 'y': y0, 'w': w, 'h': h},
            'text': '',
            'image_b64': b64,
            'gdino': {'conf': sc, 'phrase': ph},
        }
        (rdir / f'region-{i}.json').write_text(json.dumps(rec, ensure_ascii=False), encoding='utf-8')
        cnt += 1
    return cnt


def main():
    parser = argparse.ArgumentParser(description='Tiled GroundedDINO detection with NMS merge')
    parser.add_argument('--images', nargs='+', help='Images (PNG)')
    parser.add_argument('--pages-dir', default='', help='Directory with page-*.png (optional)')
    parser.add_argument('--outdir', default='out/visual/grounded_regions')
    parser.add_argument('--grounding-model', default='')
    parser.add_argument('--sam-model', default='')
    parser.add_argument('--prompts', nargs='*', default=['diagram','canvas','table','legend','node','arrow','textbox','block','title','subtitle','caption','icon','axis','label','cell','header','footer','chart','graph','map','matrix','card','badge','marker'])
    parser.add_argument('--grids', default='2,3,4', help='Comma-separated tile grids (e.g., 2,3,4)')
    parser.add_argument('--scales', default='1.0,1.5', help='Comma-separated scales (e.g., 1.0,1.5)')
    parser.add_argument('--box-threshold', type=float, default=0.20)
    parser.add_argument('--text-threshold', type=float, default=0.18)
    parser.add_argument('--nms-threshold', type=float, default=0.55)
    args = parser.parse_args()

    require_packages()
    g_path, s_path, _ = resolve_model_paths(args.grounding_model, args.sam_model)
    if not g_path:
        raise SystemExit('Не указан путь к весам GroundingDINO (MODEL_DIR/groundingdino/*.pth)')

    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)

    # Init model once
    import groundingdino
    import os
    from groundingdino.util.inference import Model  # type: ignore
    cfg_path = os.path.join(os.path.dirname(groundingdino.__file__), 'config', 'GroundingDINO_SwinT_OGC.py')
    gdino_model = Model(model_config_path=cfg_path, model_checkpoint_path=g_path)

    images: List[Path] = []
    if args.images:
        images += [Path(p) for p in args.images]
    if args.pages_dir:
        images += sorted([p for p in Path(args.pages_dir).glob('page-*.png')])
    if not images:
        raise SystemExit('Не указаны входные изображения')

    total = 0
    grids = [int(x) for x in str(args.grids).split(',') if x.strip()]
    scales = [float(x) for x in str(args.scales).split(',') if x.strip()]
    for img in images:
        n = detect_on_image(img, out, gdino_model, args.prompts, grids, scales, args.box_threshold, args.text_threshold, args.nms_threshold)
        print(f'[TILED] {img}: {n} regions after NMS')
        total += n
    print(f'Total regions: {total} (images={len(images)})')


if __name__ == '__main__':
    main()
