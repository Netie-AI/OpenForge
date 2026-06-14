"""Comparator topology — diff pair + output stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.config import NGSPICE_TIMEOUT
from openanalog.forge.topologies.base import (
    BUNDLED_MODELS,
    NMOS,
    PMOS,
    Topology,
    TopologyMetrics,
    grab_meas,
    register,
    run_ngspice,
)


@dataclass
class ComparatorParams:
    W1: float = 4.0
    L1: float = 0.8
    W3: float = 6.0
    L3: float = 0.8
    W5: float = 4.0
    L5: float = 0.8
    W6: float = 12.0
    L6: float = 0.8
    W7: float = 8.0
    L7: float = 0.8
    Wb: float = 4.0
    Lb: float = 0.8
    Iref: float = 500e-9
    Rload: float = 50e3

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _params_block(p: ComparatorParams, supply_V: float) -> str:
    vcm = supply_V / 2.0
    return f""".param VDD={supply_V}
.param VCM={vcm}
.param W1={p.W1}u L1={p.L1}u W3={p.W3}u L3={p.L3}u
.param W5={p.W5}u L5={p.L5}u W6={p.W6}u L6={p.L6}u
.param W7={p.W7}u L7={p.L7}u Wb={p.Wb}u Lb={p.Lb}u
.param IREF={p.Iref}
.param RLOAD={p.Rload}
"""

_CORE = f"""
VSUP vdd 0 {{VDD}}
Iref vdd nb {{IREF}}
M8 nb nb 0 0 {NMOS} W={{Wb}} L={{Lb}}
M5 tail nb 0 0 {NMOS} W={{W5}} L={{L5}}
M7 vout nb 0 0 {NMOS} W={{W7}} L={{L7}}
M1 n1    vinp tail 0 {NMOS} W={{W1}} L={{L1}}
M2 nout1 vinn tail 0 {NMOS} W={{W1}} L={{L1}}
M3 n1    n1 vdd vdd {PMOS} W={{W3}} L={{L3}}
M4 nout1 n1 vdd vdd {PMOS} W={{W3}} L={{L3}}
M6 vout nout1 vdd vdd {PMOS} W={{W6}} L={{L6}}
Rload vout 0 {{RLOAD}}
"""


def _build_op_deck(p: ComparatorParams, supply_V: float) -> str:
    harness = """
Vinp vinp 0 {VCM}
Vinn vinn 0 {VCM}
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
.endc
.end
"""
    return "* Comparator OP\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


def _build_vos_deck(p: ComparatorParams, supply_V: float) -> str:
    """Sweep vinp around vinn; input-referred offset = vinp at output mid-crossing - VCM."""
    vcm = supply_V / 2.0
    lo, hi = vcm - 0.05, vcm + 0.05
    mid = supply_V * 0.5
    harness = f"""
Vinn vinn 0 {vcm}
Vinp vinp 0 {vcm}
.control
set filetype=ascii
dc Vinp {lo} {hi} 0.0005
meas dc vos find v(vinp) when v(vout)={mid} cross=1
.endc
.end
"""
    return "* Comparator Vos\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


def _build_tran_deck(p: ComparatorParams, supply_V: float) -> str:
    vcm = supply_V / 2.0
    vin_lo = vcm - 0.15
    vin_hi = vcm + 0.15
    thresh = vcm + 0.02
    vout_trip = supply_V * 0.5
    harness = f"""
Vinn vinn 0 {vcm}
Vinp vinp 0 pulse({vin_lo} {vin_hi} 200n 50p 50p 4u 20u)
.control
set filetype=ascii
tran 5n 3u
meas tran t_plh trig v(vinp) val={thresh} rise=1 targ v(vout) val={vout_trip} fall=1
meas tran trise trig v(vout) val={supply_V * 0.8} fall=1 targ v(vout) val={supply_V * 0.2} fall=1
meas tran tfall trig v(vout) val={supply_V * 0.2} rise=1 targ v(vout) val={supply_V * 0.8} rise=1
.endc
.end
"""
    return "* Comparator tran\n" + BUNDLED_MODELS + _params_block(p, supply_V) + _CORE + harness


class ComparatorTopology(Topology):
    circuit_type = "comparator"
    topology_name = "diff_pair_comparator"
    spec_weights = {"tp_us": 2.0, "iq_uA": 1.0, "vos_mV": 1.5, "trise_ns": 1.0, "tfall_ns": 1.0}

    def default_params(self) -> ComparatorParams:
        return ComparatorParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "W1": (2.0, 60.0, True), "W3": (2.0, 60.0, True), "W5": (2.0, 80.0, True),
            "W6": (4.0, 120.0, True), "W7": (2.0, 80.0, True), "Wb": (2.0, 30.0, True),
            "Iref": (50e-9, 20e-6, True),
            "Rload": (5e3, 100e3, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"tp_us", "iq_uA", "vos_mV", "trise_ns", "tfall_ns"}

    def measure(
        self, params: ComparatorParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ok, out = run_ngspice(_build_op_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 10))
        if ok:
            isupp = grab_meas("isupp", out)
            m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        vok, vout = run_ngspice(_build_vos_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 15))
        if vok:
            vos = grab_meas("vos", vout)
            vcm = supply_V / 2.0
            if vos is not None:
                m.values["vos_mV"] = abs(vos - vcm) * 1000
        if with_full:
            tok, tout = run_ngspice(_build_tran_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 25))
            m.raw = tout[-3000:]
            if tok:
                t_plh = grab_meas("t_plh", tout)
                if t_plh and t_plh > 0:
                    m.values["tp_us"] = t_plh * 1e6
                tr = grab_meas("trise", tout)
                tf = grab_meas("tfall", tout)
                m.values["trise_ns"] = tr * 1e9 if tr else None
                m.values["tfall_ns"] = tf * 1e9 if tf else None
        m.ok = m.values.get("tp_us") is not None and m.values.get("vos_mV") is not None
        return m

    def emit_netlist(self, params: ComparatorParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        return "* OpenForge comparator\n" + BUNDLED_MODELS + _params_block(params, supply_V) + _CORE + "\n.end\n"

    def device_list(self, params: ComparatorParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "M1/M2", "role": "diff pair", "W_um": round(p["W1"], 3), "L_um": round(p["L1"], 3)},
            {"name": "M6", "role": "output stage", "W_um": round(p["W6"], 3), "L_um": round(p["L6"], 3)},
            {"name": "Iref", "role": "bias", "value": f"{p['Iref']*1e6:.2f} uA"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(ComparatorTopology())
