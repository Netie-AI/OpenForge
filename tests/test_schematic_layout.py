"""Layout-level placement/orientation checks."""

from __future__ import annotations

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_layout import (
    _two_terminal_orientation_cost,
    build_schematic_layout,
)


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


def test_two_terminal_device_lead_orientation() -> None:
    layout = build_schematic_layout(_opamp_devices(), {"topology": "two_stage_miller_opamp"})
    idx = next(i for i, pd in enumerate(layout.placed) if pd.dev.name.upper() == "CC")
    chosen = _two_terminal_orientation_cost(layout.placed, idx, mirror=layout.placed[idx].mirror)
    flipped = _two_terminal_orientation_cost(layout.placed, idx, mirror=not layout.placed[idx].mirror)
    assert chosen <= flipped + 2.0, (
        f"two-terminal orientation inflated wiring cost: chosen={chosen}, flipped={flipped}"
    )
