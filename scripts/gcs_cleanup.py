#!/usr/bin/env python3
import argparse
import os
from google.cloud import storage  # type: ignore


def delete_prefix(bucket: storage.Bucket, prefix: str, dry: bool = False) -> int:
    n = 0
    blobs = bucket.list_blobs(prefix=prefix)
    for b in blobs:
        if dry:
            print(f"[dry] delete gs://{bucket.name}/{b.name}")
        else:
            b.delete()
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="GCS cleanup helper (dangerous)")
    ap.add_argument("--project", default=None, help="GCP project (optional)")
    ap.add_argument("--dry", action="store_true", help="Dry run")
    args = ap.parse_args()

    client = storage.Client(project=args.project) if args.project else storage.Client()

    # 1) Remove experimental VLM outputs in pik_source_bucket/vlm_unstructured/
    b1 = client.bucket("pik_source_bucket")
    n1 = delete_prefix(b1, "vlm_unstructured/", dry=args.dry)
    print(f"pik_source_bucket: removed {n1} objects under vlm_unstructured/")

    # 2) Clean pik-artifacts-dev from past results (preserve models/)
    b2 = client.bucket("pik-artifacts-dev")
    # list all prefixes at root and delete everything except models/
    prefixes = [
        "grounded_regions/",
        "cv_regions/",
        "cv_frames/",
        "visual_review/",
        "embeddings/",
        "colab_runs/",
    ]
    total = 0
    for p in prefixes:
        total += delete_prefix(b2, p, dry=args.dry)
    print(f"pik-artifacts-dev: removed {total} objects (kept models/)")

    print("Done. Use --dry first to preview deletions.")


if __name__ == "__main__":
    # Requires GOOGLE_APPLICATION_CREDENTIALS to be set
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("[warn] GOOGLE_APPLICATION_CREDENTIALS is not set; using ADC if available")
    main()

