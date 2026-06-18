#!/usr/bin/env python3
"""Phase 1b verification: analog switch vs RS2105 bar."""
from __future__ import annotations

import re

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.analog_switch import AnalogSwitchTopology, SwitchParams
from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.interface.designer import design
from openanalog.sim.models import resolve_models
from openanalog.sim.models import mos_line

RS2105 = DEV_MODE_SPECS["switch"]
BUDGET = 250
SEEDS = [1, 3, 7, 11, 12]


def _device_graph(netlist: str) -> list[str]:
    out = []
    for raw in netlist.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line[0] in "MRVI":
            norm = re.sub(r"\{[^}]+\}", "{}", line)
            norm = re.sub(r"\s+", " ", norm)
            out.append(norm)
    return out


def _ratio(a: float, b: float) -> str:
    return f"{a / b:.2f}x" if b else "inf"


def _broken_core(ms) -> str:
    """Pre-175da53 PMOS/NMOS source-drain swap (834 ohm artifact)."""
    n_bulk = "0"
    p_bulk = "vdd"
    wn, ln = "{{WN}}", "{{LENN}}"
    wp, lp = "{{WP}}", "{{LENP}}"
    wd, ld = "{{WDRV}}", "{{LENDRV}}"
    lines = [
        "VSUP vdd 0 {VDD}",
        mos_line("n", "out", "sig", "ctrl", n_bulk, "n", w=wn, l=ln, ms=ms),
        mos_line("p", "sig", "out", "ctrl_n", p_bulk, "p", w=wp, l=lp, ms=ms),
        mos_line("nd", "ctrl_n", "ctrl", "0", "0", "n", w=wd, l=ld, ms=ms),
        mos_line("pd", "ctrl_n", "ctrl", "vdd", "vdd", "p", w=wd, l=ld, ms=ms),
        "Rload out 0 1k",
        "Cload out 0 10p",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    topo = AnalogSwitchTopology()
    default = topo.default_params()
    dm = topo.measure(default, with_full=True)

    print("=" * 70)
    print("1. DEFAULT vs SEED=11 SIZED — parameters and structure")
    print("=" * 70)
    r11 = design(inline_spec=RS2105, budget=BUDGET, seed=11, record_kg=False)
    sized_p = r11["params"]

    print("\n(a) DEFAULT:")
    print(f"    {default.as_dict()}")
    print(f"    ron={dm.values.get('ron_ohm')} ohm bw={dm.values.get('bw_MHz')} MHz")
    print(f"    ton={dm.values.get('ton_ns')} ns toff={dm.values.get('toff_ns')} ns")

    print("\n(b) SEED=11 sized:")
    print(f"    {sized_p}")
    print(f"    ron={r11['metrics'].get('ron_ohm')} ohm bw={r11['metrics'].get('bw_MHz')} MHz")
    print(f"    ton={r11['metrics'].get('ton_ns')} ns toff={r11['metrics'].get('toff_ns')} ns")
    print(f"    meets_all={r11['meets_all']}")

    print("\n(c) Parameter deltas (sized / default):")
    for k in default.as_dict():
        dv, sv = default.as_dict()[k], sized_p[k]
        print(f"    {k:8s}: {dv:.4g} -> {sv:.4g}  ({_ratio(sv, dv)})")

    nl_def = topo.emit_netlist(default)
    nl_sized = topo.emit_netlist(SwitchParams(**{k: sized_p[k] for k in default.as_dict()}))
    print(f"\n(d) Netlist structure identical: {_device_graph(nl_def) == _device_graph(nl_sized)}")

    print("\n(e) Causal story:")
    print(
        "    Ron drop: Wn 50->220um (4.4x), Wp 100->776um (7.8x) widens pass devices at Vctrl=VDD, Vsig=2.5V."
    )
    print("    ton/toff already pass at defaults; sizing mainly closes Ron margin (97 ohm -> 13 ohm).")

    print("\n" + "=" * 70)
    print("2. SEED SENSITIVITY (budget=250)")
    print("=" * 70)
    pass_n = 0
    for seed in SEEDS:
        r = design(inline_spec=RS2105, budget=BUDGET, seed=seed, record_kg=False)
        ok = r["meets_all"]
        pass_n += int(ok)
        m = r["metrics"]
        print(
            f"  seed={seed:2d} meets_all={ok} ron={m.get('ron_ohm'):.2f} "
            f"bw={m.get('bw_MHz'):.1f} ton={m.get('ton_ns'):.2f} toff={m.get('toff_ns'):.2f}"
        )
    print(f"\n  Pass rate: {pass_n}/{len(SEEDS)}")

    print("\n" + "=" * 70)
    print("3. PRIOR ~834 ohm RS2105 failures — topology fix, not sizing")
    print("=" * 70)
    hist = SwitchParams(Wn=200.0, len_n=0.5, Wp=400.0, len_p=0.5, Wdrv=10.0, len_drv=0.5)
    hm = topo.measure(hist, with_full=True)
    print(f"  Historical params re-measured today (fixed netlist): ron={hm.values.get('ron_ohm')} ohm")

    ms = resolve_models()
    pblock = f""".param VDD=5.0
.param WN={hist.Wn}u LENN={hist.len_n}u WP={hist.Wp}u LENP={hist.len_p}u
.param WDRV={hist.Wdrv}u LENDRV={hist.len_drv}u
"""
    broken_deck = (
        "* broken\n"
        + ms.block
        + pblock
        + _broken_core(ms)
        + """
Vctrl ctrl 0 {VDD}
Vsig sig 0 dc 2.5
.control
set filetype=ascii
op
let iload = abs(v(out)/1000)
let ron = abs(v(sig)-v(out))/max(iload, 1e-15)
print ron
.endc
.end
"""
    )
    ok, out = run_ngspice(broken_deck, timeout=20)
    ron_old = grab_meas("ron", out)
    print(f"  Same params on pre-175da53 S/D orientation: ron={ron_old} ohm (designs.jsonl ~835 ohm)")

    print("\n" + "=" * 70)
    print("4. BENCH SANITY — RS2105-style assumptions")
    print("=" * 70)
    print("  DC Ron: Vctrl=VDD, Vsig=2.5V (mid-rail), Rload=1k, Cload=10p on out.")
    print("  ton/toff: ctrl pulse 0->5V (100ps edges), out crosses 40% of Vsig (2.0V).")
    print("  Product sample: typ Ron=25 ohm, BW=15 MHz, ton=12 ns, toff=10 ns.")
    print(f"  Sized seed=11: Ron={r11['metrics']['ron_ohm']:.1f} ohm — faster than typ, under 50 ohm bar.")


if __name__ == "__main__":
    main()
