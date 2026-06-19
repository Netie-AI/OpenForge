"""Two-stage Miller op-amp topology."""

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
class OpAmpParams:
    W1: float = 8.0
    L1: float = 1.0
    W3: float = 8.0
    L3: float = 1.0
    W5: float = 16.0
    L5: float = 1.0
    W6: float = 40.0
    L6: float = 1.0
    W7: float = 16.0
    L7: float = 1.0
    Wb: float = 8.0
    Lb: float = 1.0
    Iref: float = 20e-6
    Cc: float = 2e-12

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _core(ms: ResolvedModels) -> str:
    lines = [
        "VSUP vdd 0 {VDD}",
        "Iref vdd nb {IREF}",
        mos_line("8", "nb", "nb", "0", "0", "n", w="{Wb}", l="{Lb}", ms=ms),
        mos_line("5", "tail", "nb", "0", "0", "n", w="{W5}", l="{L5}", ms=ms),
        mos_line("7", "vout", "nb", "0", "0", "n", w="{W7}", l="{L7}", ms=ms),
        mos_line("1", "n1", "vinp", "tail", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("2", "nout1", "vinn", "tail", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("3", "n1", "n1", "vdd", "vdd", "p", w="{W3}", l="{L3}", ms=ms),
        mos_line("4", "nout1", "n1", "vdd", "vdd", "p", w="{W3}", l="{L3}", ms=ms),
        mos_line("6", "vout", "nout1", "vdd", "vdd", "p", w="{W6}", l="{L6}", ms=ms),
        "Cc vout nout1 {CC}",
        "CL vout 0 {CLOAD}",
    ]
    return "\n" + "\n".join(lines) + "\n"


def _params_block(p: OpAmpParams, supply_V: float, cload_F: float) -> str:
    vcm = supply_V / 2.0
    return f""".param VDD={supply_V}
.param VCM={vcm}
.param CLOAD={cload_F}
.param W1={p.W1}u L1={p.L1}u
.param W3={p.W3}u L3={p.L3}u
.param W5={p.W5}u L5={p.L5}u
.param W6={p.W6}u L6={p.L6}u
.param W7={p.W7}u L7={p.L7}u
.param Wb={p.Wb}u Lb={p.Lb}u
.param IREF={p.Iref}
.param CC={p.Cc}
"""


def _build_ac_deck(p: OpAmpParams, supply_V: float, cload_F: float) -> str:
    harness = """
Vcm  vinn 0 {VCM}
Vac  sigin 0 dc {VCM} ac 1
Lfb  vout vinp 1T
Cin  vinp sigin 1T
.control
set filetype=ascii
set units=degrees
op
let isupp = abs(i(vsup))
print isupp
ac dec 25 0.1 1G
meas ac aol_db   find vdb(vout) at=0.1
meas ac ph_dc    find vp(vout) at=0.1
meas ac gbw_hz   when vdb(vout)=0
meas ac ph_ugf   find vp(vout) when vdb(vout)=0
.endc
.end
"""
    ms = resolve_models()
    return "* OpenForge op-amp AC\n" + ms.block + _params_block(p, supply_V, cload_F) + _core(ms) + harness


def _build_tran_deck(p: OpAmpParams, supply_V: float, cload_F: float) -> str:
    vcm = supply_V / 2.0
    lo, hi = max(0.1, vcm - 0.25), min(supply_V - 0.1, vcm + 0.25)
    harness = f"""
Vstep vinn 0 pulse({lo} {hi} 1u 1n 1n 10u 20u)
Rfb vout vinp 1
Cfb vout vinp 1f
.control
set filetype=ascii
tran 5n 12u
meas tran tr_rise trig v(vout) val={lo + 0.1 * (hi - lo)} rise=1 targ v(vout) val={lo + 0.9 * (hi - lo)} rise=1
.endc
.end
"""
    ms = resolve_models()
    return "* OpenForge op-amp tran\n" + ms.block + _params_block(p, supply_V, cload_F) + _core(ms) + harness


class OpAmpTopology(Topology):
    circuit_type = "opamp"
    topology_name = "two_stage_miller_opamp"
    spec_weights = {"pm_deg": 2.0, "gbp_MHz": 1.5, "aol_dB": 1.5, "slew_Vus": 2.0, "iq_uA": 1.0}

    def default_params(self) -> OpAmpParams:
        return OpAmpParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "W1": (1.0, 60.0, True), "W3": (1.0, 60.0, True), "W5": (2.0, 120.0, True),
            "W6": (4.0, 200.0, True), "W7": (2.0, 120.0, True), "Wb": (2.0, 40.0, True),
            "L1": (0.5, 4.0, False), "L6": (0.5, 4.0, False),
            "Iref": (2e-6, 200e-6, True), "Cc": (0.2e-12, 12e-12, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"aol_dB", "gbp_MHz", "pm_deg", "iq_uA", "slew_Vus"}

    def estimate_extra(self, params: OpAmpParams, *, cload_F: float = 10e-12) -> dict[str, float]:
        i_tail = params.Iref * (params.W5 / params.Wb) * (params.Lb / params.L5)
        i_out = params.Iref * (params.W7 / params.Wb) * (params.Lb / params.L7)
        sr_in = (i_tail / params.Cc) / 1e6 if params.Cc > 0 else 0.0
        sr_out = (i_out / cload_F) / 1e6 if cload_F > 0 else 0.0
        return {"slew_Vus": max(0.0, min(sr_in, sr_out))}

    def measure(
        self, params: OpAmpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ok, out = run_ngspice(_build_ac_deck(params, supply_V, cload_F), timeout=max(NGSPICE_TIMEOUT, 15))
        m.raw = out[-4000:]
        if not ok:
            m.error = out[:600]
            return m
        isupp = grab_meas("isupp", out)
        m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        m.values["aol_dB"] = grab_meas("aol_db", out)
        gbw = grab_meas("gbw_hz", out)
        m.values["gbp_MHz"] = gbw / 1e6 if gbw else None
        ph_ugf, ph_dc = grab_meas("ph_ugf", out), grab_meas("ph_dc", out)
        if ph_ugf is not None and ph_dc is not None:
            pm = 180.0 + (ph_ugf - ph_dc)
            while pm > 180:
                pm -= 360
            while pm < -180:
                pm += 360
            m.values["pm_deg"] = pm
        if with_full:
            tok, tout = run_ngspice(_build_tran_deck(params, supply_V, cload_F), timeout=max(NGSPICE_TIMEOUT, 20))
            tr = grab_meas("tr_rise", tout)
            if tok and tr and tr > 0:
                m.values["slew_Vus"] = (0.8 * 0.5) / (tr * 1e6)
        m.ok = all(m.values.get(k) is not None for k in ("aol_dB", "gbp_MHz", "pm_deg"))
        return m

    def emit_netlist(self, params: OpAmpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        ms = resolve_models()
        tb = "\nVcm vinn 0 {VCM}\nVac sigin 0 dc {VCM} ac 1\nLfb vout vinp 1T\nCin vinp sigin 1T\n.end\n"
        return "* OpenForge two-stage Miller op-amp\n" + ms.block + _params_block(params, supply_V, cload_F) + _core(ms) + tb

    def device_list(self, params: OpAmpParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "M1/M2", "role": "NMOS input pair", "W_um": round(p["W1"], 3), "L_um": round(p["L1"], 3)},
            {"name": "M3/M4", "role": "PMOS mirror load", "W_um": round(p["W3"], 3), "L_um": round(p["L3"], 3)},
            {"name": "M5", "role": "NMOS tail", "W_um": round(p["W5"], 3), "L_um": round(p["L5"], 3)},
            {"name": "M6", "role": "PMOS 2nd stage", "W_um": round(p["W6"], 3), "L_um": round(p["L6"], 3)},
            {"name": "M7", "role": "NMOS sink", "W_um": round(p["W7"], 3), "L_um": round(p["L7"], 3)},
            {"name": "M8", "role": "bias diode", "W_um": round(p["Wb"], 3), "L_um": round(p["Lb"], 3)},
            {"name": "Iref", "role": "bias", "value": f"{p['Iref']*1e6:.2f} uA"},
            {"name": "Cc", "role": "Miller cap", "value": f"{p['Cc']*1e12:.2f} pF"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(OpAmpTopology())
