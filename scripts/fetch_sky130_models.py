#!/usr/bin/env python3
"""
Fetch pinned SKY130 ngspice model cards into data/pdk/sky130/models.sp

Lightweight alternative to full volare PDK install.
Pinned version documented in openanalog/sim/models.py (SKY130_PIN).
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "pdk" / "sky130"
OUT_FILE = OUT_DIR / "models.sp"
PIN_FILE = OUT_DIR / "PIN.txt"

# Pinned release of sky130 ngspice model includes (update deliberately)
SKY130_REPO = "https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr"
SKY130_TAG = "v0.13.0"
SKY130_COMMIT = "2997061e461c71e6e5c85153e3403ca74c62f69c"  # tag v0.13.0
SKY130_COMMIT_REF = SKY130_TAG  # raw.githubusercontent.com accepts tag or hash
MODEL_PATHS = [
    "cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.corner.spice",
    "cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.corner.spice",
]

# pm3 model cards referenced by corner files (must live beside models.sp)
PM3_PATHS = [
    "cells/nfet_01v8/sky130_fd_pr__nfet_01v8__tt.pm3.spice",
    "cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.pm3.spice",
]

# Optional rf npn corner (404 on some pins — bandgap falls back to builtin npn)
NPN_PATHS = [
    "cells/rf_npn_05v5_W1p00L1p00/sky130_fd_pr__rf_npn_05v5_W1p00L1p00__tt.corner.spice",
]

# Fallback: write bundled minimal cards if fetch fails
FALLBACK = """* openforge sky130 fallback models (fetch failed — using builtin)
.model sky130_fd_pr__nfet_01v8 nmos (level=54 version=4.5 lmin=0.15u wmin=0.42u vth0=0.409 u0=0.025)
.model sky130_fd_pr__pfet_01v8 pmos (level=54 version=4.5 lmin=0.15u wmin=0.42u vth0=-0.389 u0=0.010)
.model sky130_fd_pr__npn_11v0 npn (is=1e-16 bf=100 nf=1.0 vaf=50)
.model sky130_fd_pr__pnp_11v0 pnp (is=1e-16 bf=80 nf=1.0 vaf=40)
"""


def fetch_url(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  skip {url}: {e}")
        return None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    parts = [
        f"* OpenForge SKY130 models — pin {SKY130_TAG} ({SKY130_COMMIT})",
        "",
    ]

    for rel in MODEL_PATHS:
        url = f"{SKY130_REPO}/{SKY130_COMMIT_REF}/{rel}"
        print(f"fetching {url}")
        text = fetch_url(url)
        if text:
            parts.append(f"* --- {rel} ---")
            parts.append(text.strip())
            parts.append("")

    for rel in PM3_PATHS:
        url = f"{SKY130_REPO}/{SKY130_COMMIT_REF}/{rel}"
        print(f"fetching {url}")
        text = fetch_url(url)
        if text:
            name = Path(rel).name
            (OUT_DIR / name).write_text(text.strip() + "\n", encoding="utf-8")
            print(f"  wrote {OUT_DIR / name}")

    for rel in NPN_PATHS:
        url = f"{SKY130_REPO}/{SKY130_COMMIT_REF}/{rel}"
        print(f"fetching {url}")
        text = fetch_url(url)
        if text:
            parts.append(f"* --- {rel} ---")
            parts.append(text.strip())
            parts.append("")

    # Parasitic BJT models (builtin — not always in separate spice files)
    parts.append("* --- parasitic BJT (builtin) ---")
    parts.append(".model sky130_fd_pr__npn_11v0 npn (is=1e-16 bf=100 nf=1.0 vaf=50 ikf=1e-3)")
    parts.append(".model sky130_fd_pr__pnp_11v0 pnp (is=1e-16 bf=80 nf=1.0 vaf=40 ikf=1e-3)")
    parts.append("")

    if len(parts) <= 3:
        print("fetch failed — writing fallback models")
        OUT_FILE.write_text(FALLBACK, encoding="utf-8")
    else:
        OUT_FILE.write_text("\n".join(parts) + "\n", encoding="utf-8")

    PIN_FILE.write_text(
        f"repo={SKY130_REPO}\ntag={SKY130_TAG}\ncommit={SKY130_COMMIT}\n"
        f"output={OUT_FILE.name}\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_FILE} ({OUT_FILE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
