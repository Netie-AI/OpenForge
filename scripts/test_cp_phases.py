#!/usr/bin/env python3
from openanalog.forge.topologies.charge_pump import ChargePumpParams, ChargePumpTopology

t = ChargePumpTopology()
for n in (2, 4):
    p = ChargePumpParams(stages=2, n_phases=n, cap_F=100e-9, freq_Hz=500e3, rload_ohm=100e3, w_switch=80.0)
    m = t.measure(p)
    print(f"n_phases={n} vout={m.values.get('vout_V'):.3f} ripple_mV={m.values.get('ripple_mV')}")
