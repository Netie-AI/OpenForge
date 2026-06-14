"""
openanalog/forge/opamp.py

Backward-compatible re-exports. Implementation lives in forge/topologies/opamp.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openanalog.forge.topologies.base import BUNDLED_MODELS, NMOS, PMOS
from openanalog.forge.topologies.opamp import (
    OpAmpParams,
    OpAmpTopology,
    _build_ac_deck,
    _build_tran_deck,
)

_TOPO = OpAmpTopology()
PARAM_RANGES = _TOPO.param_ranges()


@dataclass
class OpAmpMetrics:
    ok: bool = False
    aol_dB: float | None = None
    gbp_MHz: float | None = None
    pm_deg: float | None = None
    iq_uA: float | None = None
    slew_Vus: float | None = None
    vos_mV: float | None = None
    raw: str = ""
    error: str = ""
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "aol_dB": self.aol_dB,
            "gbp_MHz": self.gbp_MHz,
            "pm_deg": self.pm_deg,
            "iq_uA": self.iq_uA,
            "slew_Vus": self.slew_Vus,
            "vos_mV": self.vos_mV,
        }


def _to_metrics(tm) -> OpAmpMetrics:
    return OpAmpMetrics(
        ok=tm.ok,
        aol_dB=tm.values.get("aol_dB"),
        gbp_MHz=tm.values.get("gbp_MHz"),
        pm_deg=tm.values.get("pm_deg"),
        iq_uA=tm.values.get("iq_uA"),
        slew_Vus=tm.values.get("slew_Vus"),
        vos_mV=tm.values.get("vos_mV"),
        raw=tm.raw,
        error=tm.error,
        warnings=list(tm.warnings),
    )


def measure(
    p: OpAmpParams,
    *,
    supply_V: float = 5.0,
    cload_F: float = 10e-12,
    with_slew: bool = True,
    vcm_V: float | None = None,
) -> OpAmpMetrics:
    del vcm_V  # topology uses supply_V/2
    return _to_metrics(_TOPO.measure(p, supply_V=supply_V, cload_F=cload_F, with_full=with_slew))


def estimate_slew_Vus(p: OpAmpParams, *, cload_F: float = 10e-12) -> float:
    return _TOPO.estimate_extra(p, cload_F=cload_F).get("slew_Vus", 0.0)


def emit_netlist(p: OpAmpParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
    return _TOPO.emit_netlist(p, supply_V=supply_V, cload_F=cload_F)


__all__ = [
    "BUNDLED_MODELS",
    "NMOS",
    "PMOS",
    "OpAmpParams",
    "OpAmpMetrics",
    "PARAM_RANGES",
    "measure",
    "estimate_slew_Vus",
    "emit_netlist",
]
