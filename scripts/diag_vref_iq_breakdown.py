#!/usr/bin/env python3
"""Quick iq diagnosis: is the gap closable by amp bias / mirror sizing?"""
from __future__ import annotations

import os

from openanalog.forge.spec_envelopes import VREF_PHASE3_SPEC
from openanalog.forge.sizer import size
from openanalog.forge.topologies.vref import VRefParams, VRefTopology
from openanalog.interface.datasheet import parse_inline_spec
from openanalog.sim.models import set_active_model_set


def main() -> int:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    topo = VRefTopology()
    cases = [
        ("defaults", VRefParams()),
        ("iref_amp_3u", VRefParams(iref_amp_uA=3.0)),
        ("iref_amp_1u", VRefParams(iref_amp_uA=1.0)),
        ("mirror_w_4", VRefParams(mirror_w_um=4.0)),
    ]
    print(f"spec={VREF_PHASE3_SPEC}")
    for label, p in cases:
        m = topo.measure(p)
        iq = m.values.get("iq_uA")
        vref = m.values.get("vref_V")
        lr = m.values.get("line_reg_mV")
        print(f"{label}: iq={iq:.1f} uA vref={vref:.4f} V line_reg={lr:.2f} mV ok={m.ok}")

    spec = parse_inline_spec(VREF_PHASE3_SPEC, category="vref")
    c = size(topo, spec, budget=80, seed=42)
    print(f"sized: meets_all={c.meets_all} metrics={c.metrics.as_dict()}")
    if not c.meets_all:
        fails = [k for k, v in c.per_spec.items() if not v.get("pass")]
        print(f"sized misses={fails}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
