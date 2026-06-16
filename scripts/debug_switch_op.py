#!/usr/bin/env python3
from openanalog.forge.topologies.analog_switch import SwitchParams, _params_block, _core
from openanalog.forge.topologies.base import run_ngspice
from openanalog.sim.models import resolve_models, set_active_model_set

set_active_model_set("bundled")
p = SwitchParams(Wn=4000.0, len_n=0.18, Wp=1105.0, len_p=0.228)
ms = resolve_models()
deck = "* dbg\n" + ms.block + _params_block(p, 5.0) + _core(ms) + """
Vctrl ctrl 0 5
Vsig sig 0 dc 2.5
.control
op
print v(sig) v(out) v(ctrl) v(ctrl_n)
print i(vsup)
.endc
.end
"""
ok, raw = run_ngspice(deck, timeout=15)
print(raw)
