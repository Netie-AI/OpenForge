"""PMOS pass LDO — error amplifier + resistor divider feedback."""

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
class LDOParams:
    Wp: float = 200.0
    Lp: float = 0.5
    W1: float = 8.0
    L1: float = 1.0
    W3: float = 8.0
    L3: float = 1.0
    W5: float = 12.0
    L5: float = 1.0
    W6: float = 30.0
    L6: float = 1.0
    W7: float = 12.0
    L7: float = 1.0
    Wb: float = 8.0
    Lb: float = 1.0
    Iref: float = 15e-6
    Cc: float = 5e-12
    R2: float = 120e3
    Iout_mA: float = 1.0

    def as_dict(self) -> dict:
        return self.__dict__.copy()

    def r1_ohm(self, vout: float, vref: float = 1.2) -> float:
        if vref <= 0:
            return self.R2
        return self.R2 * max(vout / vref - 1.0, 0.1)


def _params_block(p: LDOParams, vin: float, vout_target: float, vref: float) -> str:
    r1 = p.r1_ohm(vout_target, vref)
    return f""".param VIN={vin}
.param VOUTT={vout_target}
.param VREF={vref}
.param R1={r1}
.param R2={p.R2}
.param WP={p.Wp}u LP={p.Lp}u
.param W1={p.W1}u L1={p.L1}u W3={p.W3}u L3={p.L3}u
.param W5={p.W5}u L5={p.L5}u W6={p.W6}u L6={p.L6}u
.param W7={p.W7}u L7={p.L7}u Wb={p.Wb}u Lb={p.Lb}u
.param IREF={p.Iref}
.param CC={p.Cc}
.param ILOAD={p.Iout_mA}m
"""


def _error_amp(ms: ResolvedModels) -> str:
    lines = [
        "Iref vdd nb {IREF}",
        mos_line("8", "nb", "nb", "0", "0", "n", w="{Wb}", l="{Lb}", ms=ms),
        mos_line("5", "tail", "nb", "0", "0", "n", w="{W5}", l="{L5}", ms=ms),
        mos_line("7", "vgate", "nb", "0", "0", "n", w="{W7}", l="{L7}", ms=ms),
        mos_line("1", "n1", "vref", "tail", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("2", "nout1", "vfb", "tail", "0", "n", w="{W1}", l="{L1}", ms=ms),
        mos_line("3", "n1", "n1", "vdd", "vdd", "p", w="{W3}", l="{L3}", ms=ms),
        mos_line("4", "nout1", "n1", "vdd", "vdd", "p", w="{W3}", l="{L3}", ms=ms),
        mos_line("6", "vgate", "nout1", "vdd", "vdd", "p", w="{W6}", l="{L6}", ms=ms),
        "Cc vgate nout1 {CC}",
    ]
    return "\n" + "\n".join(lines) + "\n"


def _core(ms: ResolvedModels) -> str:
    head = """
Vin vin 0 {VIN}
Vdd vdd 0 {VIN}
Vref vref 0 {VREF}
R1 vout vfb {R1}
R2 vfb 0 {R2}
"""
    pass_dev = mos_line("p", "vout", "vgate", "vin", "vin", "p", w="{WP}", l="{LP}", ms=ms)
    tail = """
Iload vout 0 DC {ILOAD}
Cout vout 0 1u
"""
    return head + pass_dev + "\n" + tail + _error_amp(ms)


def _build_dc_deck(p: LDOParams, vin: float, vout_target: float) -> str:
    ms = resolve_models()
    harness = """
.control
set filetype=ascii
alter Iload dc 0
op
let vout_dc = v(vout)
let isupp = abs(i(vin))
print vout_dc
print isupp
.endc
.end
"""
    return (
        "* LDO DC\n"
        + ms.block
        + _params_block(p, vin, vout_target, 1.2)
        + _core(ms)
        + harness
    )


def _build_line_reg_deck(p: LDOParams, vin: float, vout_target: float) -> str:
    ms = resolve_models()
    v_lo = max(vout_target + 0.3, 3.5)
    v_hi = vin + 0.5
    harness = f"""
.control
dc Vin {v_lo} {v_hi} 0.1
meas dc line_reg_mv pp v(vout)
.endc
.end
"""
    return "* LDO line reg\n" + ms.block + _params_block(p, vin, vout_target, 1.2) + _core(ms) + harness


def _build_load_reg_deck(p: LDOParams, vin: float, vout_target: float) -> str:
    ms = resolve_models()
    iout_a = p.Iout_mA * 1e-3
    step = max(iout_a / 10.0, 0.0001)
    harness = f"""
.control
dc Iload 0 {iout_a * 2:.4f} {step:.4f}
meas dc load_reg_mv pp v(vout)
.endc
.end
"""
    return "* LDO load reg\n" + ms.block + _params_block(p, vin, vout_target, 1.2) + _core(ms) + harness


def _build_dropout_deck(p: LDOParams, vin: float, vout_target: float) -> str:
    ms = resolve_models()
    v_test = max(vout_target + 0.15, 3.5)
    harness = """
.control
op
let dropm = (v(vin)-v(vout))*1000
print dropm
.endc
.end
"""
    return (
        "* LDO dropout\n"
        + ms.block
        + _params_block(p, v_test, vout_target, 1.2)
        + _core(ms)
        + harness
    )


def _build_reg_deck(p: LDOParams, vin: float, vout_target: float) -> str:
    """Legacy alias — line reg only."""
    return _build_line_reg_deck(p, vin, vout_target)


def _build_ac_deck(p: LDOParams, vin: float, vout_target: float) -> str:
    ms = resolve_models()
    core = _core(ms).replace("Vin vin 0 {VIN}", "Vin vin 0 dc {VIN} ac 0.1")
    harness = """
.control
set filetype=ascii
op
ac dec 30 10 1Meg
meas ac psrr_db find vdb(vout) at=100
.endc
.end
"""
    return "* LDO PSRR\n" + ms.block + _params_block(p, vin, vout_target, 1.2) + core + harness


class LDOTopology(Topology):
    circuit_type = "ldo"
    topology_name = "pmos_pass_ldo"
    spec_weights = {
        "vout_V": 1.0,
        "dropout_mV": 0.8,
        "line_reg_mV": 0.6,
        "load_reg_mV": 0.6,
        "iq_uA": 0.5,
        "psrr_dB": 0.4,
    }

    def default_params(self) -> LDOParams:
        return LDOParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "Wp": (50.0, 800.0, True),
            "Lp": (0.3, 2.0, False),
            "W1": (4.0, 20.0, True),
            "L1": (0.5, 2.0, False),
            "W3": (4.0, 20.0, True),
            "L3": (0.5, 2.0, False),
            "W5": (4.0, 24.0, True),
            "L5": (0.5, 2.0, False),
            "W6": (10.0, 80.0, True),
            "L6": (0.5, 2.0, False),
            "W7": (4.0, 24.0, True),
            "L7": (0.5, 2.0, False),
            "Wb": (4.0, 16.0, True),
            "Lb": (0.5, 2.0, False),
            "Iref": (5e-6, 40e-6, True),
            "Cc": (1e-12, 20e-12, True),
            "R2": (50e3, 300e3, True),
            "Iout_mA": (0.1, 5.0, False),
        }

    def measurable_specs(self) -> set[str]:
        return {"vout_V", "dropout_mV", "line_reg_mV", "load_reg_mV", "iq_uA", "psrr_dB"}

    def measure(
        self,
        params: LDOParams,
        *,
        supply_V: float = 5.0,
        cload_F: float = 1e-6,
        with_full: bool = True,
    ) -> TopologyMetrics:
        _ = cload_F
        vout_target = 3.3
        vin = supply_V
        dc_deck = _build_dc_deck(params, vin, vout_target)
        ok, raw = run_ngspice(dc_deck, timeout=NGSPICE_TIMEOUT)
        m = TopologyMetrics(ok=ok, raw=raw)
        if not ok:
            m.error = "dc failed"
            return m

        vout = grab_meas("vout_dc", raw)
        iq = grab_meas("isupp", raw)
        if iq is not None:
            iq *= 1e6
        m.values["vout_V"] = vout
        m.values["iq_uA"] = iq

        if not with_full:
            return m

        reg_decks = (
            ("line_reg_mV", _build_line_reg_deck, "line_reg_mv"),
            ("load_reg_mV", _build_load_reg_deck, "load_reg_mv"),
            ("dropout_mV", _build_dropout_deck, "dropm"),
        )
        for key, builder, spice_name in reg_decks:
            ok2, raw2 = run_ngspice(builder(params, vin, vout_target), timeout=NGSPICE_TIMEOUT + 10)
            if ok2:
                m.raw += "\n" + raw2
                val = grab_meas(spice_name, raw2)
                if val is not None:
                    if key in ("line_reg_mV", "load_reg_mV"):
                        val = abs(val) * 1000.0
                    m.values[key] = abs(val)

        ac_deck = _build_ac_deck(params, vin, vout_target)
        ok3, raw3 = run_ngspice(ac_deck, timeout=NGSPICE_TIMEOUT)
        if ok3:
            m.raw += "\n" + raw3
            psrr = grab_meas("psrr_db", raw3)
            if psrr is not None:
                m.values["psrr_dB"] = abs(psrr)

        m.ok = ok and vout is not None
        return m

    def emit_netlist(self, params: LDOParams, *, supply_V: float = 5.0, cload_F: float = 1e-6) -> str:
        _ = cload_F
        return _build_dc_deck(params, supply_V, 3.3)

    def device_list(self, params: LDOParams) -> list[dict[str, Any]]:
        r1 = params.r1_ohm(3.3)
        return [
            {"name": "Mp", "role": "pass_pmos", "W_um": params.Wp, "L_um": params.Lp},
            {"name": "M1-M7", "role": "error_amp", "W_um": params.W1, "L_um": params.L1},
            {"name": "R1", "role": "divider_top", "value": f"{r1/1e3:.1f}k"},
            {"name": "R2", "role": "divider_bot", "value": f"{params.R2/1e3:.1f}k"},
            {"name": "Cc", "role": "comp", "value": f"{params.Cc*1e12:.1f}pF"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(LDOTopology())
