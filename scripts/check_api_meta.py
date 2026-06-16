#!/usr/bin/env python3
import json
import sys
import urllib.request

port = sys.argv[1] if len(sys.argv) > 1 else "8081"
url = f"http://127.0.0.1:{port}/api/meta"
with urllib.request.urlopen(url, timeout=5) as r:
    d = json.load(r)
print("categories:", len(d.get("categories", [])))
print("presets:", len(d.get("presets", [])))
print("use_cases:", len(d.get("use_cases", [])))
ar = d.get("achievable_ranges", {})
print("range_cats:", len(ar.get("categories", {})))
print("fitness1:", ar.get("fitness1_count"))
print("multiplier in categories:", "multiplier" in d.get("categories", []))
