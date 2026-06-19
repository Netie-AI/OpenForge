"""Four-quadrant Gilbert-cell analog multiplier (experimental)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.config import NGSPICE_TIMEOUT
from openanalog.forge.topologies.base import (
    Topology,
    TopologyMetrics,
    grab_meas,
    register,
    run_ngspice,
)
from openanalog.sim.models import ResolvedModels, mos_line, resolve_models


@dataclass
class MultiplierParams:
    W1: float = 40.0
    L1: float = 1.0
    W2: float = 30.0
    L2: float = 1.0
    Wtail: float = 20.0
    Ltail: float = 1.0
    Wb: float = 10.0
    Lb: float = 1.0
    Iref: float = 30e-6
    Rload: float = 5e3

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _params_block(p: MultiplierParams, supply_V: float) -> str:
    vcm = supply_V / 2.0
    return f""".param VDD={supply_V}
.param VCM={vcm}
.param W1={p.W1}u L1={p.L1}u
.param W2={p.W2}u L2={p.L2}u
.param WTAIL={p.Wtail}u LTAIL={p.Ltail}u
.param Wb={p.Wb}u Lb={p.Lb}u
.param IREF={p.Iref}
.param RLOAD={p.Rload}
"""


def _core(ms: ResolvedModels) -> str:
    """Standard cross-coupled Gilbert quad with differential X and single-ended Y."""
    lines = [
        "VSUP vdd 0 {VDD}",
        "Ib vdd nb {IREF}",
        mos_line("b", "nb", "nb", "0", "0", "n", w="{Wb}", l="{Lb}", ms=ms),
        mos_line("tail", "tail", "nb", "0", "0", "n", w="{WTAIL}", l="{LTAIL}", ms=ms),
        mos_line("y1", "tail1", "vy", "tail", "0", "n", w="{W2}", l="{L2}", ms=ms),
        mos_line("y2", "tail2", "vyn", "tail", "0", "n", w="{W2}", l="{L2}", ms=ms),
        mos_line("x1", "outp", "vxp", "tail1", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("x2", "outn", "vxp", "tail2", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("x3", "outp", "vxn", "tail2", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("x4", "outn", "vxn", "tail1", "0", "n", w="{W1}", l="{L1}", ms=ms),
        "Rlp outp vdd {RLOAD}",
        "Rln outn vdd {RLOAD}",
    ]
    return "\n" + "\n".join(lines) + "\n"


def _input_harness(*, vxp: str, vxn: str, vy: str, vyn: str) -> str:
    return f"""
Vxp vxp 0 {vxp}
Vxn vxn 0 {vxn}
Vy vy 0 {vy}
Vyn vyn 0 {vyn}
"""


def _build_op_deck(p: MultiplierParams, supply_V: float) -> str:
    vcm = supply_V / 2.0
    harness = _input_harness(vxp=str(vcm), vxn=str(vcm), vy=str(vcm), vyn=str(vcm)) + """
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
.endc
.end
"""
    ms = resolve_models()
    return "* Multiplier OP\n" + ms.block + _params_block(p, supply_V) + _core(ms) + harness


def _build_dc_deck(p: MultiplierParams, supply_V: float) -> str:
    """Sweep differential X (vxp) at fixed Y offset."""
    vcm = supply_V / 2.0
    vy_fix = vcm + 0.4
    lo, hi = vcm - 0.4, vcm + 0.4
    harness = _input_harness(
        vxp=f"dc {vcm}", vxn=str(vcm), vy=str(vy_fix), vyn=str(vcm)
    ) + f"""
.control
set filetype=ascii
dc Vxp {lo} {hi} 0.01
let vdiff = v(outp)-v(outn)
meas dc vout_min min vdiff
meas dc vout_max max vdiff
meas dc vout_pp pp vdiff
.endc
.end
"""
    ms = resolve_models()
    return "* Multiplier DC\n" + ms.block + _params_block(p, supply_V) + _core(ms) + harness


def _build_ac_deck(p: MultiplierParams, supply_V: float) -> str:
    vcm = supply_V / 2.0
    harness = _input_harness(
        vxp=f"dc {vcm} ac 1", vxn=str(vcm), vy=str(vcm + 0.3), vyn=str(vcm)
    ) + """
.control
set filetype=ascii
ac dec 30 1 100Meg
let vdiff = v(outp)-v(outn)
meas ac dbdc find vdb(vdiff) at=1
meas ac bw_hz when vdb(vdiff)=dbdc-3 cross=1
.endc
.end
"""
    ms = resolve_models()
    return "* Multiplier AC\n" + ms.block + _params_block(p, supply_V) + _core(ms) + harness


class MultiplierTopology(Topology):
    circuit_type = "multiplier"
    topology_name = "gilbert_cell"
    spec_weights = {
        "gain_err_pct": 2.0,
        "bw_MHz": 1.5,
        "iq_uA": 1.0,
        "output_swing_V": 1.0,
    }

    def default_params(self) -> MultiplierParams:
        return MultiplierParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "W1": (8.0, 60.0, True),
            "L1": (0.5, 2.0, True),
            "W2": (8.0, 40.0, True),
            "L2": (0.5, 2.0, True),
            "Wtail": (6.0, 30.0, True),
            "Ltail": (0.5, 2.0, True),
            "Wb": (4.0, 20.0, True),
            "Lb": (0.5, 2.0, True),
            "Iref": (5e-6, 40e-6, True),
            "Rload": (2e3, 50e3, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"gain_err_pct", "bw_MHz", "iq_uA", "output_swing_V"}

    def measure(
        self,
        params: MultiplierParams,
        *,
        supply_V: float = 5.0,
        cload_F: float = 10e-12,
        with_full: bool = True,
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ok_op, out_op = run_ngspice(_build_op_deck(params, supply_V), timeout=NGSPICE_TIMEOUT)
        if not ok_op:
            m.error = out_op[:800]
            return m
        isupp = grab_meas("isupp", out_op)
        m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None

        ok_dc, out_dc = run_ngspice(_build_dc_deck(params, supply_V), timeout=NGSPICE_TIMEOUT)
        if ok_dc:
            v_min = grab_meas("vout_min", out_dc)
            v_max = grab_meas("vout_max", out_dc)
            v_pp = grab_meas("vout_pp", out_dc)
            swing = v_pp if v_pp is not None else (
                abs(v_max - v_min) if v_min is not None and v_max is not None else None
            )
            m.values["output_swing_V"] = swing
            if swing is not None and swing > 1e-6:
                asym = abs((v_max or 0) + (v_min or 0)) / max(swing, 1e-6) * 100
                m.values["gain_err_pct"] = min(max(asym, 0.0), 99.9)
            else:
                m.values["gain_err_pct"] = 100.0
            m.raw = out_dc[-2000:]

        if with_full:
            ok_ac, out_ac = run_ngspice(_build_ac_deck(params, supply_V), timeout=NGSPICE_TIMEOUT)
            if ok_ac:
                bw = grab_meas("bw_hz", out_ac)
                m.values["bw_MHz"] = bw / 1e6 if bw else None

        m.ok = m.values.get("output_swing_V") is not None and (m.values.get("output_swing_V") or 0) > 1e-5
        return m

    def emit_netlist(
        self, params: MultiplierParams, *, supply_V: float = 5.0, cload_F: float = 10e-12
    ) -> str:
        deck = _build_op_deck(params, supply_V)
        return deck.replace(".control", "* .control").replace(".endc", "* .endc")

    def device_list(self, params: MultiplierParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "Mx", "role": "Gilbert quad", "value": f"W={p['W1']:.1f}µm"},
            {"name": "My", "role": "Y steering", "value": f"W={p['W2']:.1f}µm"},
            {"name": "Iref", "role": "bias", "value": f"{p['Iref']*1e6:.1f} µA"},
            {"name": "Rload", "role": "output load", "value": f"{p['Rload']/1e3:.1f} kΩ"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOIC-8"


register(MultiplierTopology())
