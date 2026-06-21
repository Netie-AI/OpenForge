#!/usr/bin/env python3
"""OP convergence check for vref bandgap (structural gate evidence)."""
from __future__ import annotations

import os

from openanalog.forge.topologies.vref import VRefParams, VRefTopology
from openanalog.sim.models import set_active_model_set


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    m = VRefTopology().measure(VRefParams())
    print(f"ok={m.ok} values={m.values}")
    if m.error:
        print(f"ERROR: {m.error[:600]}")
    for line in (m.raw or "").splitlines():
        low = line.lower()
        if "v(vref)" in low or "v(qp1)" in low or "v(ra1)" in low or "v(net2)" in low:
            print(line.strip())
        if "isupp" in low and "=" in low:
            print(line.strip())
        if "convergence" in low or "fatal" in low:
            print(line.strip())


if __name__ == "__main__":
    main()
