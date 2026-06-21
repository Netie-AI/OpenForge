"""Separate DUT schematic view from simulation testbench elements.

Ngspice netlists include bench loads, stimulus sources, and measurement decks.
The schematic renderer shows the design-under-test only — same connectivity rules
apply on the filtered device set for LVS-precursor checks.
"""

from __future__ import annotations

from openanalog.eda.netlist_graph import SpiceDevice

# Resistors/caps used only as bench fixtures (not on-chip DUT).
_TESTBENCH_PASSIVE_NAMES = frozenset({"RLOAD", "CLOAD", "ILOAD"})

# Topologies where Cout is on-chip output filter (keep in DUT view).
_COUT_IS_DUT = frozenset({"dickson_charge_pump"})


def is_schematic_testbench(dev: SpiceDevice, *, topology: str = "") -> bool:
    """True if this parsed device is simulation harness, not DUT artwork."""
    name = dev.name.upper()
    if dev.kind == "V":
        return True
    if dev.kind == "R" and name in _TESTBENCH_PASSIVE_NAMES:
        return True
    if dev.kind == "C" and name == "CLOAD":
        return True
    if dev.kind == "C" and name == "COUT" and topo not in _COUT_IS_DUT:
        return True
    if dev.kind == "I" and name in {"ILOAD"}:
        return True
    return False


def dut_devices_for_schematic(
    devices: list[SpiceDevice],
    *,
    topology: str = "",
) -> list[SpiceDevice]:
    """Devices to place/route in the schematic SVG (DUT only)."""
    topo = (topology or "").lower()
    out: list[SpiceDevice] = []
    for dev in devices:
        if is_schematic_testbench(dev, topology=topo):
            continue
        out.append(dev)
    return out


def _sky130_vref_devices() -> list[SpiceDevice]:
    """Bandgap netlist for schematic when bundled models defer vref emit."""
    import os

    from openanalog.eda.netlist_graph import parse_spice_devices
    from openanalog.forge.topologies.vref import VRefParams, VRefTopology

    prev = os.environ.get("OPENFORGE_MODEL_SET")
    os.environ["OPENFORGE_MODEL_SET"] = "sky130"
    try:
        netlist = VRefTopology().emit_netlist(VRefParams())
        return parse_spice_devices(netlist)
    finally:
        if prev is None:
            os.environ.pop("OPENFORGE_MODEL_SET", None)
        else:
            os.environ["OPENFORGE_MODEL_SET"] = prev


def schematic_devices(
    devices: list[SpiceDevice],
    result: dict | None = None,
) -> list[SpiceDevice]:
    """DUT-only device list for schematic layout, connectivity, and SVG."""
    result = result or {}
    topo = str(result.get("topology") or result.get("category") or "")
    dut = dut_devices_for_schematic(devices, topology=topo)
    if len(dut) < 2 and topo.lower() == "sky130_bandgap":
        dut = dut_devices_for_schematic(_sky130_vref_devices(), topology=topo)
    return dut
