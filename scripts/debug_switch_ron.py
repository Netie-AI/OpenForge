#!/usr/bin/env python3
from openanalog.forge.topologies.analog_switch import SwitchParams, _build_dc_deck
from openanalog.forge.topologies.base import run_ngspice, grab_meas
from openanalog.sim.models import set_active_model_set

set_active_model_set("bundled")
p = SwitchParams(Wn=4000.0, len_n=0.18, Wp=1105.0, len_p=0.228, Wdrv=127.8, len_drv=0.5)
ok, raw = run_ngspice(_build_dc_deck(p, 5.0), timeout=15)
print("RON (4000um):", grab_meas("ron", raw))

p2 = SwitchParams(Wn=200.0, len_n=0.5, Wp=400.0, len_p=0.5)
ok2, raw2 = run_ngspice(_build_dc_deck(p2, 5.0), timeout=15)
print("RON (200um):", grab_meas("ron", raw2))
