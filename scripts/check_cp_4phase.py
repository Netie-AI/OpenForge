#!/usr/bin/env python3
from openanalog.forge.topologies.charge_pump import ChargePumpParams, ChargePumpTopology

cp = ChargePumpTopology()
for n_ph in [2, 4]:
    p = ChargePumpParams(n_phases=n_ph, cap_F=364e-9, cap_boot_F=118e-9, freq_Hz=644187, rload_ohm=100e3, w_switch=200)
    m = cp.measure(p)
    print(f"n_phases={n_ph} vout={m.values.get('vout_V'):.3f} ripple_mV={m.values.get('ripple_mV')}")
