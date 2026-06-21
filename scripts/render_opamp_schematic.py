"""Render the canonical two-stage Miller op-amp schematic via the browser render path.

No ngspice needed: render_schematic_svg() only consumes device topology, not sized
values, so this faithfully reproduces the schematic the web UI draws for the op-amp.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_layout import render_schematic_svg


def _opamp_devices() -> list[SpiceDevice]:
    return [
        SpiceDevice("Iref", "I", ["vdd", "nb"]),
        SpiceDevice("M8", "M", ["nb", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M5", "M", ["tail", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M7", "M", ["vout", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M1", "M", ["n1", "vinp", "tail", "0"], model="nmos"),
        SpiceDevice("M2", "M", ["nout1", "vinn", "tail", "0"], model="nmos"),
        SpiceDevice("M3", "M", ["n1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M4", "M", ["nout1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M6", "M", ["vout", "nout1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("Cc", "C", ["vout", "nout1"]),
    ]


def main() -> int:
    out = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "logs/schematic_opamp_m4_fix.svg")
    svg = render_schematic_svg(_opamp_devices(), {"topology": "two_stage_miller_opamp"})
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
