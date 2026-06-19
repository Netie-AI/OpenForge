#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

os.environ["OPENFORGE_MODEL_SET"] = "sky130"
os.environ["OPENFORGE_SKY130_CARD"] = "bsim"

from openanalog.forge.topologies import opamp as opmod
from openanalog.forge.topologies.opamp import OpAmpTopology
from openanalog.forge.topologies.base import run_ngspice
from openanalog.sim.models import set_active_model_set

set_active_model_set("sky130")
op = OpAmpTopology()
p = op.default_params()
deck = opmod._build_ac_deck(p, 3.3, 1e-12)
out_path = sys.argv[1] if len(sys.argv) > 1 else "bsim_netlist_sample.sp"
log_path = sys.argv[2] if len(sys.argv) > 2 else "bsim_pfet_failure_raw.log"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(deck)
ok, out = run_ngspice(deck, timeout=120)
with open(log_path, "w", encoding="utf-8") as f:
    f.write(out if out else "")
    f.write(f"\n--- run_ngspice returned ok={ok} ---\n")
print(f"wrote {out_path} ({len(deck)} bytes)")
print(f"wrote {log_path} ({len(out or '')} bytes) ok={ok}")
