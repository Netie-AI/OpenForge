#!/usr/bin/env python3
"""Phase 3 — vref bandgap on SKY130 (requires parasitic BJT models)."""
from __future__ import annotations

import os
import sys

from openanalog.forge.spec_envelopes import VREF_PHASE3_SPEC
from openanalog.interface.designer import design
from openanalog.sim.models import resolve_models, set_active_model_set


def main() -> int:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    card = os.getenv("OPENFORGE_SKY130_CARD", "level1")
    os.environ.setdefault("OPENFORGE_SKY130_CARD", card)

    set_active_model_set("sky130")
    ms = resolve_models()

    print(f"SKY130 card={card} npn={ms.npn} mos_subckt={ms.mos_subckt}")
    print(f"spec={VREF_PHASE3_SPEC}")

    r = design(inline_spec=VREF_PHASE3_SPEC, budget=80, seed=42, record_kg=False)
    m = r["metrics"]
    ok = r["meets_all"]
    print(f"meets_all={ok} metrics={m}")
    if not ok:
        fails = [k for k, v in r["compliance"].items() if not v.get("pass")]
        print(f"misses={fails}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
