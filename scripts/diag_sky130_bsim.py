#!/usr/bin/env python3
"""Diagnose opamp/comparator on SKY130 level-1 vs fetched BSIM cards."""
from __future__ import annotations

import os

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design


def _run(label: str, card: str) -> None:
    os.environ["OPENFORGE_SKY130_CARD"] = card
    for cat in ("opamp", "comparator"):
        spec = DEV_MODE_SPECS[cat]
        seed = 42 if cat == "opamp" else 7
        r = design(
            inline_spec=spec,
            budget=200,
            record_kg=False,
            seed=seed,
            model_set="sky130",
        )
        print(f"{label} {cat}: meets_all={r['meets_all']} metrics={r['metrics']}")


def main() -> int:
    from openanalog.sim.models import _load_fetched_sky130_block

    fetched = _load_fetched_sky130_block()
    print(f"fetched BSIM block: {'OK' if fetched else 'MISSING'} ({len(fetched or '')} chars)")
    _run("L1", "level1")
    if fetched:
        _run("BSIM", "bsim")
    else:
        print("BSIM: skipped (models.sp includes missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
