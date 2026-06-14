"""Dickson charge pump topology."""

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


@dataclass
class ChargePumpParams:
    stages: int = 3
    cap_F: float = 100e-9
    freq_Hz: float = 500e3
    rload_ohm: float = 10e3
    diode_drop: float = 0.35

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _build_tran_deck(p: ChargePumpParams, supply_V: float) -> str:
    stages = max(1, min(int(p.stages), 6))
    caps = "\n".join(f"C{i} n{i} n{i+1} {p.cap_F}" for i in range(stages))
    diodes = "\n".join(
        f"D{i} n{i+1} clk{i%2+1} Dmod" for i in range(stages)
    )
    period = 1.0 / p.freq_Hz
    half = period / 2.0
    harness = f"""
Vsup vdd 0 {supply_V}
Vclk1 clk1 0 pulse(0 {supply_V} 0 1n 1n {half} {period})
Vclk2 clk2 0 pulse(0 {supply_V} {half} 1n 1n {half} {period})
Rload n{stages} 0 {p.rload_ohm}
Cout n{stages} 0 {p.cap_F * 2}
.model Dmod D (IS=1e-14 N=1.2 RS=5)
{diodes}
{caps}
C0 n0 vdd {p.cap_F}
.control
set filetype=ascii
tran {period/200} {period*200}
meas tran vout_avg avg v(n{stages})
meas tran ripple_pp pp v(n{stages})
meas tran settle when v(n{stages})={supply_V * stages * 0.5} rise=1
let isupp = avg(abs(i(vsup)))
print isupp
print vout_avg
print ripple_pp
.endc
.end
"""
    return "* OpenForge Dickson charge pump\n" + harness


class ChargePumpTopology(Topology):
    circuit_type = "charge_pump"
    topology_name = "dickson_charge_pump"
    spec_weights = {"vout_V": 2.0, "ripple_mV": 1.5, "settle_ms": 1.0, "iout_mA": 1.0, "iq_uA": 0.5}

    def default_params(self) -> ChargePumpParams:
        return ChargePumpParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "stages": (2.0, 5.0, False),
            "cap_F": (10e-9, 500e-9, True),
            "freq_Hz": (50e3, 2e6, True),
            "rload_ohm": (1e3, 50e3, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"vout_V", "ripple_mV", "settle_ms", "iout_mA", "iq_uA"}

    def measure(
        self, params: ChargePumpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ok, out = run_ngspice(_build_tran_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 30))
        m.raw = out[-3000:]
        if not ok:
            m.error = out[:500]
            return m
        vout = grab_meas("vout_avg", out)
        ripple = grab_meas("ripple_pp", out)
        settle = grab_meas("settle", out)
        isupp = grab_meas("isupp", out)
        m.values["vout_V"] = vout
        m.values["ripple_mV"] = ripple * 1000 if ripple else None
        m.values["settle_ms"] = settle * 1000 if settle else None
        m.values["iq_uA"] = abs(isupp) * 1e6 if isupp else None
        if vout and params.rload_ohm > 0:
            m.values["iout_mA"] = (vout / params.rload_ohm) * 1000
        m.ok = vout is not None
        return m

    def emit_netlist(self, params: ChargePumpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        return _build_tran_deck(params, supply_V).replace(".control", "* .control").replace(".endc", "* .endc")

    def device_list(self, params: ChargePumpParams) -> list[dict[str, Any]]:
        p = params.as_dict()
        return [
            {"name": "stages", "role": "Dickson stages", "value": int(p["stages"])},
            {"name": "Cpump", "role": "pump cap", "value": f"{p['cap_F']*1e9:.1f} nF"},
            {"name": "fclk", "role": "clock", "value": f"{p['freq_Hz']/1e3:.1f} kHz"},
            {"name": "Rload", "role": "load", "value": f"{p['rload_ohm']/1e3:.1f} kOhm"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOIC-8"


register(ChargePumpTopology())
