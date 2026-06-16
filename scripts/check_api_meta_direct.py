#!/usr/bin/env python3
from openanalog.web.app import api_meta

d = api_meta()
print("categories:", len(d["categories"]))
print("presets:", len(d["presets"]))
print("use_cases:", len(d["use_cases"]))
print("range_cats:", len(d["achievable_ranges"]["categories"]))
print("multiplier:", "multiplier" in d["categories"])
print("fitness1:", d["achievable_ranges"]["fitness1_count"])
