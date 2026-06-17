#!/usr/bin/env python3
"""Show HuggingFace download progress for a model (bytes + log tail)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
MODEL = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen2.5-Coder-7B-Instruct"
repo_slug = MODEL.replace("/", "--")
cache = Path.home() / ".cache" / "huggingface" / "hub"
blobs = cache / f"models--{repo_slug}" / "blobs"
log_file = _ROOT / "logs" / f"download_{MODEL.replace('/', '_')}.log"

# Expected total ~15 GB for 7B (4 shards)
EXPECTED_GB = 15.0

print(f"Model: {MODEL}")
print(f"Cache: {blobs}")

if not blobs.exists():
    print("No cache yet — run: python scripts/download_model.py")
    sys.exit(0)

complete = [f for f in blobs.iterdir() if f.is_file() and ".incomplete" not in f.name]
incomplete = list(blobs.glob("*.incomplete"))
total_bytes = sum(f.stat().st_size for f in complete)
inc_bytes = sum(f.stat().st_size for f in incomplete)

print(f"\nComplete blobs: {len(complete)}  ({total_bytes/1e9:.2f} GB)")
print(f"Incomplete:     {len(incomplete)}  ({inc_bytes/1e9:.2f} GB partial)")
print(f"Progress est:   {min(100, 100*total_bytes/(EXPECTED_GB*1e9)):.0f}% of ~{EXPECTED_GB:.0f} GB")

if incomplete:
    print("\nActive/partial downloads:")
    for f in sorted(incomplete, key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        print(f"  {f.name[:20]}... {f.stat().st_size/1e6:.1f} MB")

locks = cache / ".locks" / f"models--{repo_slug}"
if locks.exists():
    n = sum(1 for _ in locks.rglob("*.lock"))
    print(f"\nWARN: {n} lock files present — may block download")

if log_file.exists():
    print(f"\n--- log tail ({log_file}) ---")
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-12:]:
        print(line)
else:
    print(f"\nNo log yet. Log will appear at: {log_file}")
