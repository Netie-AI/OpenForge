#!/usr/bin/env python3
"""Phase 3 — SKY130 parasitic BJT bandgap (structural + RS431 bar)."""
from __future__ import annotations

import os
import sys

from openanalog.forge.spec_envelopes import VREF_PHASE3_SPEC
from openanalog.forge.topologies.vref import VRefParams, VRefTopology
from openanalog.interface.designer import design
from openanalog.sim.models import resolve_models, set_active_model_set


def main() -> int:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    card = os.getenv("OPENFORGE_SKY130_CARD", "level1")
    os.environ.setdefault("OPENFORGE_SKY130_CARD", card)

    set_active_model_set("sky130")
    ms = resolve_models()

    print(f"SKY130 card={card} pnp={ms.pnp} npn={ms.npn}")
    print(f"spec={VREF_PHASE3_SPEC}")

    topo = VRefTopology()
    base = topo.measure(VRefParams())
    print(f"defaults: ok={base.ok} metrics={base.values}")

    r = design(inline_spec=VREF_PHASE3_SPEC, budget=80, seed=42, record_kg=False, model_set="sky130")
    m = r["metrics"]
    ok = r["meets_all"]
    print(f"sized meets_all={ok} metrics={m}")
    if not ok:
        fails = [k for k, v in r["compliance"].items() if not v.get("pass")]
        print(f"misses={fails}")
        print("exit=1 (honest fail — iq structural floor; see docs/semicon-log.md entry 3)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
