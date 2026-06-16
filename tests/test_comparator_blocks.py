"""Regression: composed comparator blocks match legacy flat template."""

from __future__ import annotations

import re

from openanalog.forge.blocks.comparator_core import emit as emit_comparator_core
from openanalog.forge.topologies.comparator import ComparatorParams, ComparatorTopology
from openanalog.sim.models import resolve_models


def _device_lines(netlist: str) -> list[str]:
    lines = []
    for raw in netlist.splitlines():
        line = raw.strip()
        if not line or line.startswith("*") or line.startswith("."):
            continue
        if line[0] in "MRVI":
            lines.append(re.sub(r"\s+", " ", line))
    return lines


def test_comparator_core_device_lines_match_legacy_template():
    ms = resolve_models("bundled")
    core = emit_comparator_core(ms).netlist
    legacy_devices = [
        "VSUP vdd 0 {VDD}",
        "Iref vdd nb {IREF}",
        f"M8 nb nb 0 0 {ms.nmos} W={{Wb}} L={{Lb}}",
        f"M5 tail nb 0 0 {ms.nmos} W={{W5}} L={{L5}}",
        f"M7 vout nb 0 0 {ms.nmos} W={{W7}} L={{L7}}",
        f"M1 n1 vinp tail 0 {ms.nmos} W={{W1}} L={{L1}}",
        f"M2 nout1 vinn tail 0 {ms.nmos} W={{W1}} L={{L1}}",
        f"M3 n1 n1 vdd vdd {ms.pmos} W={{W3}} L={{L3}}",
        f"M4 nout1 n1 vdd vdd {ms.pmos} W={{W3}} L={{L3}}",
        f"M6 vout nout1 vdd vdd {ms.pmos} W={{W6}} L={{L6}}",
        "Rload vout 0 {RLOAD}",
    ]
    composed = _device_lines(core)
    assert composed == legacy_devices


def test_comparator_emit_netlist_unchanged_shape():
    topo = ComparatorTopology()
    params = ComparatorParams()
    nl = topo.emit_netlist(params)
    assert "M1 n1" in nl
    assert "M3 n1    n1 vdd vdd" in nl or "M3 n1 n1 vdd vdd" in nl.replace("  ", " ")
    assert nl.strip().endswith(".end")


def test_cross_coupled_mirror_gates():
    ms = resolve_models("bundled")
    std = emit_comparator_core(ms, cross_coupled=False).netlist
    xcouple = emit_comparator_core(ms, cross_coupled=True).netlist
    assert "M3 n1    nout1 vdd vdd" in xcouple or "M3 n1 nout1 vdd vdd" in xcouple.replace("  ", " ")
    assert std != xcouple
