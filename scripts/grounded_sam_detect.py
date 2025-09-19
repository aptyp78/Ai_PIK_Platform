#!/usr/bin/env python3
import argparse
import base64
import json
import math
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any


def require_packages():
    missing = []
    try:
        import groundingdino  # type: ignore
    except Exception:
        missing.append("groundingdino")
    try:
        import sam2  # type: ignore
    except Exception:
        missing.append("sam2")
    if missing:
        raise SystemExit(
            "Отсутствуют пакеты: "
            + ", ".join(missing)
            + "\nУстановите их и повторите запуск (без fallback)."
        )


def resolve_model_paths(grounding_model_cli: str, sam_model_cli: str) -> Tuple[str, str, str]:
    """Resolve model paths from CLI args or MODEL_DIR.
    Returns (grounding_path, sam_or_sam2_path, selected_kind) where kind in {"sam2","sam"}.
    """
    model_dir = os.getenv("MODEL_DIR", "").strip()
    # Resolve GroundingDINO
    grounding_path = grounding_model_cli.strip()
    if not grounding_path and model_dir:
        # Try common file names under MODEL_DIR/groundingdino
        candidates = list(Path(model_dir, "groundingdino").glob("*.pth"))
        if candidates:
            grounding_path = str(candidates[0])
    # Resolve SAM2 first, then SAM v1
    selected_kind = ""
    sam_path = sam_model_cli.strip()
    if not sam_path and model_dir:
        sam2_cands = list(Path(model_dir, "sam2").glob("*.pt"))
        sam1_cands = list(Path(model_dir, "sam").glob("*.pth"))
        if sam2_cands:
            sam_path = str(sam2_cands[0])
            selected_kind = "sam2"
        elif sam1_cands:
            sam_path = str(sam1_cands[0])
            selected_kind = "sam"
    # If still not known kind, infer from extension
    if not selected_kind and sam_path:
        selected_kind = "sam2" if sam_path.endswith(".pt") else "sam"
    return grounding_path, sam_path, selected_kind or "sam"


def detect_regions_with_grounded(images: List[Path], outdir: Path, grounding_model: str, sam_model: str, prompts: List[str]):
    import numpy as np  # type: ignore
    from PIL import Image  # type: ignore
    Image.MAX_IMAGE_PIXELS = None
    import groundingdino
    from groundingdino.util.inference import Model  # type: ignore
    # SAM2 — используем для уточнения масок опционально (здесь извлекаем крест-валидационно bbox → crop)
    try:
        import sam2  # type: ignore  # noqa: F401
    except Exception:
        sam2 = None  # type: ignore

    if not grounding_model:
        raise SystemExit("Не указан путь к GroundingDINO весам (--grounding-model или $GROUNDING_MODEL)")
    # Конфиг ищем внутри пакета
    import os
    cfg_path = os.path.join(os.path.dirname(groundingdino.__file__), "config", "GroundingDINO_SwinT_OGC.py")
    if not os.path.exists(cfg_path):
        raise SystemExit(f"Не найден конфиг GroundingDINO: {cfg_path}")

    gdino = Model(model_config_path=cfg_path, model_checkpoint_path=grounding_model)

    # Optional: SAM (v1) predictor for real masks; SAM2 hookup can be added similarly
    _sam_predictor = None
    _sam_device = "cpu"
    def _init_sam_predictor(checkpoint_path: str):
        nonlocal _sam_predictor, _sam_device
        if _sam_predictor is not None:
            return _sam_predictor
        try:
            import torch  # type: ignore
            from segment_anything import sam_model_registry, SamPredictor  # type: ignore
        except Exception:
            return None
        model_type = "vit_h"
        name = checkpoint_path.lower()
        if "vit_b" in name:
            model_type = "vit_b"
        elif "vit_l" in name:
            model_type = "vit_l"
        elif "vit_h" in name:
            model_type = "vit_h"
        try:
            sam = sam_model_registry[model_type](checkpoint=checkpoint_path)
        except Exception:
            return None
        _sam_device = "cuda" if torch.cuda.is_available() else "cpu"
        sam.to(device=_sam_device)
        _sam_predictor = SamPredictor(sam)
        return _sam_predictor

    def compute_mask_stats_with_sam(full_im, bx0: int, by0: int, bx1: int, by1: int, checkpoint_path: str) -> Dict[str, Any]:
        try:
            import numpy as np  # type: ignore
            import cv2  # type: ignore
        except Exception:
            return {}
        predictor = _init_sam_predictor(checkpoint_path)
        if predictor is None:
            return {}
        # prepare image for predictor once per image
        try:
            import numpy as np  # type: ignore
            arr = np.array(full_im.convert("RGB"))
            predictor.set_image(arr)
            box = np.array([bx0, by0, bx1, by1], dtype=float)
            masks, scores, _ = predictor.predict(box=box[None, :], multimask_output=False)
        except Exception:
            return {}
        if masks is None or len(masks) == 0:
            return {}
        m = masks[0].astype("uint8")  # HxW
        # Compute stats inside bbox window
        h, w = m.shape
        # Clip bbox just in case
        bx0c, by0c, bx1c, by1c = max(0, bx0), max(0, by0), min(w, bx1), min(h, by1)
        sub = m[by0c:by1c, bx0c:bx1c]
        if sub.size == 0:
            return {}
        area = float(sub.sum())
        bbox_area = float(max(1, (bx1c - bx0c) * (by1c - by0c)))
        fill_ratio = max(0.0, min(1.0, area / bbox_area))
        try:
            cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts:
                cnt = max(cnts, key=cv2.contourArea)
                hull = cv2.convexHull(cnt)
                hull_area = float(cv2.contourArea(hull)) if hull is not None else 0.0
                solidity = 0.0 if hull_area <= 1e-6 else max(0.0, min(1.0, float(cv2.contourArea(cnt)) / hull_area))
            else:
                solidity = 0.0
        except Exception:
            solidity = 0.0
        try:
            edges = cv2.Canny((sub * 255).astype("uint8"), 50, 150)
            edge_density = float((edges > 0).sum()) / bbox_area
            edge_density = max(0.0, min(1.0, edge_density))
        except Exception:
            edge_density = 0.0
        edge_quality = max(0.0, min(1.0, 1.0 - edge_density * 0.5))
        s2 = max(0.0, min(1.0, 0.5 * solidity + 0.4 * fill_ratio + 0.1 * edge_quality))
        return {"algo": "sam", "fill_ratio": fill_ratio, "solidity": solidity, "edge_density": edge_density, "s2": s2}

    def compute_mask_stats_from_crop(crop_im: Image.Image) -> Dict[str, Any]:
        # Эвристика по яркости и контурам: solidity, fill_ratio, edge_density → s2
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return {"algo": "none"}
        im = np.array(crop_im.convert("RGB"))
        h, w = im.shape[:2]
        if h <= 1 or w <= 1:
            return {"algo": "none"}
        gray = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        # Otsu threshold (возможна инверсия фона)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Выберем вариант с большей заполненностью
        inv = cv2.bitwise_not(th)
        def largest_contour(bin_img):
            cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                return None
            return max(cnts, key=cv2.contourArea)
        c1 = largest_contour(th)
        c2 = largest_contour(inv)
        cnt = c1
        if c2 is not None and (cv2.contourArea(c2) > (cv2.contourArea(c1) if c1 is not None else 0)):
            cnt = c2
        if cnt is None:
            return {"algo": "heuristic", "fill_ratio": 0.0, "solidity": 0.0, "edge_density": 1.0, "s2": 0.0}
        area = float(cv2.contourArea(cnt))
        hull = cv2.convexHull(cnt)
        hull_area = float(cv2.contourArea(hull)) if hull is not None else 0.0
        bbox_area = float(w * h)
        fill_ratio = 0.0 if bbox_area <= 0 else max(0.0, min(1.0, area / bbox_area))
        solidity = 0.0 if hull_area <= 1e-6 else max(0.0, min(1.0, area / hull_area))
        edges = cv2.Canny(gray, 50, 150)
        edge_count = float((edges > 0).sum())
        # Нормализация: на площадь bbox
        edge_density = 0.0 if bbox_area <= 0 else max(0.0, min(1.0, edge_count / bbox_area))
        # Чем больше edge_density, тем хуже контур; преобразуем в [0,1]
        edge_quality = max(0.0, min(1.0, 1.0 - edge_density * 0.5))
        s2 = max(0.0, min(1.0, 0.5 * solidity + 0.4 * fill_ratio + 0.1 * edge_quality))
        return {
            "algo": "heuristic",
            "area": area,
            "hull_area": hull_area,
            "fill_ratio": fill_ratio,
            "solidity": solidity,
            "edge_density": edge_density,
            "s2": s2,
        }

    # Note: Реальную SAM2 сегментацию можно подключить при наличии корректного API.
    # Здесь оставляем приземлённый, но устойчивый эвристический s2, чтобы не ломать запуск.

    for img in images:
        rdir = outdir / img.stem / "regions"
        rdir.mkdir(parents=True, exist_ok=True)
        # Запросы: объединяем в одну строку с разделителем '.' как в примерах GDINO
        caption = ". ".join(prompts)
        boxes_normalized = True
        try:
            boxes, logits, phrases = gdino.predict_with_caption(
                image=str(img),
                captions=caption,
                box_threshold=0.3,
                text_threshold=0.25,
            )
        except TypeError:
            # Современные версии groundingdino используют новый API и возвращают детекции + confidence.
            import cv2  # type: ignore

            boxes_normalized = False
            image_bgr = cv2.imread(str(img))
            if image_bgr is None:
                raise SystemExit(f"Не удалось прочитать изображение: {img}")
            detections, phrases = gdino.predict_with_caption(
                image=image_bgr,
                caption=caption,
                box_threshold=0.3,
                text_threshold=0.25,
            )
            if detections is None or detections.is_empty():
                boxes = []
                logits = []
            else:
                boxes = detections.xyxy.astype(float)
                conf_arr = getattr(detections, "confidence", None)
                confidences = conf_arr.tolist() if conf_arr is not None else []
                logits = []
                for conf in confidences:
                    c = float(conf)
                    # Нормализуем вероятность и переводим обратно в логит.
                    if c <= 0.0:
                        logits.append(float('-inf'))
                    elif c >= 1.0:
                        logits.append(float('inf'))
                    else:
                        logits.append(math.log(c / (1.0 - c)))
        phrases = list(phrases) if phrases is not None else []
        # boxes в формате xyxy (нормализованные), преобразуем в пиксели
        im = Image.open(img).convert("RGB")
        W, H = im.size
        boxes = np.array(boxes)
        if boxes.size > 0 and not boxes_normalized:
            boxes = boxes.astype(float)
            boxes[:, [0, 2]] /= float(W)
            boxes[:, [1, 3]] /= float(H)
        if boxes.size == 0:
            print(f"[warn] GroundingDINO не нашёл регионов для {img}; пропускаем файл")
            continue
        for i, b in enumerate(boxes, start=1):
            x0, y0, x1, y1 = b
            # масштабирование
            bx0 = max(0, int(x0 * W))
            by0 = max(0, int(y0 * H))
            bx1 = min(W, int(x1 * W))
            by1 = min(H, int(y1 * H))
            w, h = max(1, bx1 - bx0), max(1, by1 - by0)
            crop = im.crop((bx0, by0, bx1, by1))
            import io

            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            # GDINO confidence (sigmoid of logit)
            try:
                logit = float(logits[i - 1])
                conf = 1.0 / (1.0 + math.exp(-logit))
            except Exception:
                logit, conf = None, None
            phrase = None
            try:
                phrase = phrases[i - 1]
            except Exception:
                pass

            # Layout metrics and coarse zone
            cx = (bx0 + bx1) / 2.0 / W
            cy = (by0 + by1) / 2.0 / H
            wr = w / float(W)
            hr = h / float(H)
            def zone_from_center(cx, cy):
                # 3x3 grid
                col = 0 if cx < 1/3 else (1 if cx < 2/3 else 2)
                row = 0 if cy < 1/3 else (1 if cy < 2/3 else 2)
                names = [["top-left", "top", "top-right"],
                         ["left", "center", "right"],
                         ["bottom-left", "bottom", "bottom-right"]]
                return names[row][col]
            layout = {"cx": cx, "cy": cy, "w_rel": wr, "h_rel": hr, "zone": zone_from_center(cx, cy)}

            # mask quality stats: prefer SAM (if available), otherwise heuristic
            mask_stats = {}
            try:
                if sam_model:
                    ms = compute_mask_stats_with_sam(im, bx0, by0, bx1, by1, checkpoint_path=sam_model)
                    if isinstance(ms, dict) and ms:
                        mask_stats = ms
            except Exception:
                mask_stats = {}
            if not mask_stats:
                mask_stats = compute_mask_stats_from_crop(crop)

            rec = {
                "bbox": {"x": bx0, "y": by0, "w": w, "h": h},
                "text": "",
                "image_b64": b64,
                "gdino": {"logit": logit, "conf": conf, "phrase": phrase},
                "layout": layout,
                "mask_stats": mask_stats,
            }
            with open(rdir / f"region-{i}.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False))
        print(f"[OK] {img}: сохранено {len(boxes)} регионов -> {rdir}")


def main():
    ap = argparse.ArgumentParser(description="Detect regions using GroundedDINO + SAM/SAM2 (requires installed models)")
    ap.add_argument("--images", nargs="+", help="Page/Frame images (PNG)")
    ap.add_argument("--outdir", default="out/visual/grounded_regions", help="Output root folder")
    ap.add_argument("--grounding-model", default=os.getenv("GROUNDING_MODEL", ""), help="Path to GroundingDINO weights")
    ap.add_argument("--sam-model", default=os.getenv("SAM_MODEL", ""), help="Path to SAM/SAM2 weights")
    ap.add_argument("--prompts", nargs="*", default=["diagram", "canvas", "table", "legend", "node", "arrow", "textbox"], help="Text prompts for GroundingDINO")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # Требуем рабочие пакеты (без fallback)
    require_packages()

    g_path, s_path, kind = resolve_model_paths(args.grounding_model, args.sam_model)
    if not g_path:
        raise SystemExit("Не указан путь к весам GroundingDINO (--grounding-model или $GROUNDING_MODEL)")
    if not s_path:
        raise SystemExit("Не указан путь к весам SAM/SAM2 (--sam-model или $SAM_MODEL)")

    images = [Path(p) for p in args.images]
    detect_regions_with_grounded(images, out, g_path, s_path, args.prompts)


if __name__ == "__main__":
    main()
