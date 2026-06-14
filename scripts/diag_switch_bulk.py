from openanalog.forge.topologies.base import BUNDLED_MODELS, NMOS, grab_meas, run_ngspice

for wn in [2000, 5000, 10000]:
    deck = f"""* sw
{BUNDLED_MODELS}
.param WN={wn}u LENN=0.18u VDD=5
Mn out sig ctrl sig {NMOS} W={{WN}} L={{LENN}}
Rload out 0 1k
Vctrl ctrl 0 5
Vsig sig 0 2.5
.control
op
let ron = abs(v(sig)-v(out))/(abs(v(out)/1000)+1e-15)
print ron
.endc
.end
"""
    ok, out = run_ngspice(deck)
    print(f"Wn={wn}u ron={grab_meas('ron', out):.2f}")
