#!/usr/bin/env python3
"""
Sync playbooks and frames from GCS buckets to local cache on VAST.

Requires `gsutil` (or `gcloud storage rsync`), otherwise prints instructions.
Default mappings:
  gs://pik_source_bucket/playbooks -> /root/data/playbooks
  gs://pik_source_bucket/frames    -> /root/data/frames
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync GCS sources to local cache")
    ap.add_argument("--playbooks-src", default="gs://pik_source_bucket/playbooks")
    ap.add_argument("--frames-src", default="gs://pik_source_bucket/frames")
    ap.add_argument("--playbooks-dst", default="/root/data/playbooks")
    ap.add_argument("--frames-dst", default="/root/data/frames")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    use_gsutil = shutil.which("gsutil") is not None
    use_gcloud = shutil.which("gcloud") is not None

    if not use_gsutil and not use_gcloud:
        print("Neither gsutil nor gcloud found. Install Google Cloud SDK on the remote host.")
        print("curl https://sdk.cloud.google.com | bash && exec -l $SHELL")
        print("Then: gcloud init && gcloud auth application-default login && gcloud components install gsutil")
        sys.exit(1)

    ensure_dir(Path(args.playbooks_dst))
    ensure_dir(Path(args.frames_dst))

    tasks = [
        (args.playbooks_src, args.playbooks_dst),
        (args.frames_src, args.frames_dst),
    ]

    for src, dst in tasks:
        if use_gsutil:
            cmd = ["gsutil", "-m", "rsync", "-r"]
            if args.dry_run:
                cmd.append("-n")
            cmd += [src, dst]
        else:
            subcmd = ["storage", "rsync", "-r"]
            if args.dry_run:
                subcmd.append("--dry-run")
            cmd = ["gcloud", *subcmd, src, dst]
        print("Running:", " ".join(cmd))
        code = run(cmd)
        if code != 0:
            print(f"Sync failed for {src} -> {dst} (exit {code})")


if __name__ == "__main__":
    main()

