#!/usr/bin/env python3
from openanalog.interface.designer import design

r = design(inline_spec="gbp=1.1MHz pm>60 aol>95dB iq<80uA", budget=100, seed=42, record_kg=False)
svg = r.get("schematic_svg", "")
kicad = r.get("kicad_sch", "")
print("meets_all", r["meets_all"])
print("schematic_svg_len", len(svg))
print("kicad_sch_len", len(kicad))
print("svg_starts_with", svg[:80] if svg else "EMPTY")
