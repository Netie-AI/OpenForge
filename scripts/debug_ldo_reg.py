#!/usr/bin/env python3
from openanalog.forge.topologies.ldo import LDOParams, _build_line_reg_deck, _build_load_reg_deck, _build_dropout_deck
from openanalog.forge.topologies.base import run_ngspice, grab_meas

p = LDOParams()
for name, builder in [
    ("line", _build_line_reg_deck),
    ("load", _build_load_reg_deck),
    ("dropout", _build_dropout_deck),
]:
    ok, raw = run_ngspice(builder(p, 5.0, 3.3), timeout=30)
    print(f"=== {name} OK={ok} ===")
    print(raw[-600:])
    for k in ("line_reg_mV", "load_reg_mV", "dropout_mV"):
        v = grab_meas(k, raw)
        if v is not None:
            print(f"  GRAB {k} = {v}")
