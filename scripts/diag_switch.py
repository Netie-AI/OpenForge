#!/usr/bin/env python3
from openanalog.forge.topologies.analog_switch import AnalogSwitchTopology, SwitchParams, _build_dc_deck
from openanalog.forge.topologies.base import run_ngspice

t = AnalogSwitchTopology()
p = SwitchParams()
deck = _build_dc_deck(p, 5.0)
print("=== DECK ===")
print(deck[-800:])
ok, out = run_ngspice(deck, timeout=20)
print("ok=", ok)
print(out[-2000:])
