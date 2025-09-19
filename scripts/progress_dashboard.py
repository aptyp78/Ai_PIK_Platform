#!/usr/bin/env python3
import argparse
import os
import time
from pathlib import Path
from typing import Tuple


def count_sources(playbooks: Path, frames: Path) -> Tuple[int, int]:
    def pdfs(p: Path) -> int:
        return sum(1 for _ in p.rglob("*.pdf")) if p.exists() else 0
    return pdfs(playbooks), pdfs(frames)


def count_render(out_pages: Path) -> Tuple[int, int]:
    if not out_pages.exists():
        return 0, 0
    doc_dirs = [d for d in out_pages.iterdir() if d.is_dir()]
    pages = sum(1 for _ in out_pages.rglob("page-*.png"))
    return len(doc_dirs), pages


def count_detection(regions_root: Path) -> Tuple[int, int]:
    if not regions_root.exists():
        return 0, 0
    units = [d for d in regions_root.iterdir() if d.is_dir()]
    rjson = sum(1 for _ in regions_root.rglob("region-*.json"))
    return len(units), rjson


def count_analysis(regions_root: Path) -> int:
    if not regions_root.exists():
        return 0
    return sum(1 for _ in regions_root.rglob("region-*.struct.json"))


def read_index_lines(index_path: Path) -> int:
    if not index_path.exists():
        return 0
    try:
        with index_path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def eta(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def main():
    ap = argparse.ArgumentParser(description="Generate a progress dashboard for the IPMK visual pipeline")
    ap.add_argument("--playbooks", default="/root/data/playbooks")
    ap.add_argument("--frames", default="/root/data/frames")
    ap.add_argument("--pages-dir", default="out/page_images")
    ap.add_argument("--regions-dir", default="out/visual/grounded_regions")
    ap.add_argument("--index", default="out/openai_embeddings.ndjson")
    ap.add_argument("--out", default="eval/progress.html")
    ap.add_argument("--auto-refresh", type=int, default=0, help="Add meta refresh tag (seconds) for live updates")
    # Simple per-step throughput estimates (tune to your GPU/LLM limits)
    ap.add_argument("--t-render", type=float, default=0.3, help="sec/page for render")
    ap.add_argument("--t-detect", type=float, default=1.0, help="sec/page for detection")
    ap.add_argument("--t-analyze", type=float, default=1.5, help="sec/region for LLM analysis")
    args = ap.parse_args()

    playbooks = Path(args.playbooks)
    frames = Path(args.frames)
    pages_dir = Path(args.pages_dir)
    regions_dir = Path(args.regions_dir)
    index_path = Path(args.index)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    src_pb, src_fr = count_sources(playbooks, frames)
    docs, pages = count_render(pages_dir)
    units, regions = count_detection(regions_dir)
    analyzed = count_analysis(regions_dir)
    indexed = read_index_lines(index_path)

    # Rough ETAs (only if not completed)
    eta_render = pages * args.t_render if pages else 0
    eta_detect = pages * args.t_detect if pages else 0
    remaining_regions = max(0, regions - analyzed)
    eta_analyze = remaining_regions * args.t_analyze

    now = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    refresh = f"<meta http-equiv=\"refresh\" content=\"{int(args.auto_refresh)}\">" if args.auto_refresh and args.auto_refresh > 0 else ""
    html = f"""
<!doctype html>
<meta charset="utf-8" />{refresh}
<title>IPMK Progress</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 940px; margin: 24px auto; }}
.sec {{ margin: 16px 0; padding: 12px 16px; border: 1px solid #e5e7eb; border-radius: 8px; }}
.h {{ font-weight: 600; margin-bottom: 8px; }}
.kv {{ color: #374151; }}
.small {{ color: #6b7280; font-size: 12px; }}
.bar {{ background: #f3f4f6; height: 10px; border-radius: 6px; overflow: hidden; }}
.bar > div {{ height: 10px; background: #3b82f6; }}
</style>
<h1>IPMK — Прогресс пайплайна</h1>
<div class="small">Обновлено: {now}</div>

<div class="sec">
  <div class="h">Источники</div>
  <div class="kv">Playbooks (PDF): <b>{src_pb}</b>; Frames (PDF): <b>{src_fr}</b></div>
</div>

<div class="sec">
  <div class="h">Рендер страниц</div>
  <div class="kv">Документов: <b>{docs}</b>; Страниц (PNG): <b>{pages}</b></div>
  <div class="small">ETA при {args.t_render}s/страницу: {eta(eta_render)}</div>
</div>

<div class="sec">
  <div class="h">Детекции (GroundedDINO+SAM)</div>
  <div class="kv">Юнитов: <b>{units}</b>; Регионов (json): <b>{regions}</b></div>
  <div class="small">ETA при {args.t_detect}s/страницу: {eta(eta_detect)}</div>
</div>

<div class="sec">
  <div class="h">Анализ (LLM + PVStack)</div>
  <div class="kv">Проанализировано регионов: <b>{analyzed}</b> из <b>{regions}</b></div>
  <div class="bar"><div style="width:{(100*analyzed/max(1,regions)):.1f}%"></div></div>
  <div class="small">Осталось ≈ {remaining_regions}; ETA при {args.t_analyze}s/регион: {eta(eta_analyze)}</div>
</div>

<div class="sec">
  <div class="h">Индекс эмбеддингов</div>
  <div class="kv">Строк в индексe: <b>{indexed}</b>; Файл: <code>{index_path}</code></div>
</div>

"""
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
