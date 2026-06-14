#!/usr/bin/env python3
from openanalog.sim.models import set_active_model_set
from openanalog.forge.topologies.analog_switch import SwitchParams, AnalogSwitchTopology

set_active_model_set("sky130")
t = AnalogSwitchTopology()
for w in [100, 200, 400, 800]:
    p = SwitchParams(Wn=w, len_n=0.15, Wp=w * 2, len_p=0.15)
    m = t.measure(p, supply_V=5.0)
    print(f"W={w}: ron={m.values.get('ron_ohm')} bw={m.values.get('bw_MHz')}")
