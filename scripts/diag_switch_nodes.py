#!/usr/bin/env python3
from openanalog.forge.topologies.base import run_ngspice, BUNDLED_MODELS, NMOS, PMOS

deck = f"""
{BUNDLED_MODELS}
.param VDD=5.0
.param WN=50u LENN=0.5u WP=100u LENP=0.5u WDRV=10u LENDRV=0.5u
VSUP vdd 0 {{VDD}}
Mn out sig ctrl 0 {NMOS} W={{WN}} L={{LENN}}
Mp out sig ctrl_n vdd {PMOS} W={{WP}} L={{LENP}}
Mnd ctrl_n ctrl 0 0 {NMOS} W={{WDRV}} L={{LENDRV}}
Mpd ctrl_n ctrl vdd vdd {PMOS} W={{WDRV}} L={{LENDRV}}
Rload out 0 10k
Vctrl ctrl 0 {{VDD}}
Vsig sig 0 2.5
.control
op
print v(ctrl) v(ctrl_n) v(sig) v(out) i(vsig) i(vsup)
.endc
.end
"""
ok, out = run_ngspice(deck, timeout=20)
print("ok", ok)
print(out[-1500:])
