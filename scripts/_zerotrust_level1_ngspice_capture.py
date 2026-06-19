#!/usr/bin/env python3
"""Capture full ngspice stdout for one SKY130 level-1 placeholder smoke category."""
from __future__ import annotations

import os
import sys

os.environ["OPENFORGE_MODEL_SET"] = "sky130"
os.environ["OPENFORGE_SKY130_CARD"] = "level1"

from openanalog.forge.topologies import opamp as opmod
from openanalog.forge.topologies.opamp import OpAmpTopology
from openanalog.forge.topologies.base import run_ngspice
from openanalog.sim.models import set_active_model_set

set_active_model_set("sky130")
op = OpAmpTopology()
p = op.default_params()
supply_V, cload_F = 5.0, 10e-12

ac_deck = opmod._build_ac_deck(p, supply_V, cload_F)
tran_deck = opmod._build_tran_deck(p, supply_V, cload_F)

out_path = sys.argv[1] if len(sys.argv) > 1 else "sky130_level1_ngspice_stdout.txt"

sections: list[str] = []
for label, deck in [("AC analysis deck", ac_deck), ("TRAN analysis deck", tran_deck)]:
    ok, out = run_ngspice(deck, timeout=120)
    sections.append(f"{'=' * 72}\n{label}\n{'=' * 72}\n")
    sections.append(out if out else "(empty ngspice output)\n")
    sections.append(f"\n--- run_ngspice returned ok={ok} ---\n\n")

text = "".join(sections)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(text)

print(f"wrote {out_path} ({len(text)} bytes)")
print("opamp default params, SKY130 level-1 placeholder card — full AC+TRAN ngspice stdout saved")
