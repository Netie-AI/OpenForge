"""
Voltage reference — PTAT+CTAT bandgap on SKY130 parasitic BJTs (Phase 3).

Substrate PNP pair (1x / 8x) generates ΔVbe; resistor ratio sums CTAT + PTAT to ~1.2 V.
No VDD-to-vref divider — output is a bandgap stack (see scripts/diag_vref_pnp_ideal.py).

Deferred on bundled level-1 MOSFET-only models (no SKY130 BJT cards).
"""

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
from openanalog.forge.blocks.current_mirror import emit_pmos_load
from openanalog.forge.blocks.differential_pair import emit as emit_diff_pair
from openanalog.sim.models import ResolvedModels, mos_line, resolve_models

_PHASE3_MSG = (
    "vref deferred on bundled models: requires SKY130 parasitic BJTs. "
    "Set OPENFORGE_MODEL_SET=sky130 to enable bandgap reference."
)

# Structural diagnosis (2026-06-19): defaults target RS431 vref≈1.2 V on builtin BJT cards;
# line_reg remains above the 5 mV bar until bias/mirror sizing closes the loop.
_DEFAULT_RPTAT_OHM = 1000.0
_DEFAULT_RSCALE_OHM = 8400.0
_DEFAULT_MIRROR_L_UM = 3.0
# Opamp input-stage defaults (Phase 1d / BSIM-validated sizing philosophy)
_DEFAULT_AMP_W1_UM = 8.0
_DEFAULT_AMP_L1_UM = 1.0
_DEFAULT_AMP_W3_UM = 8.0
_DEFAULT_AMP_L3_UM = 1.0
_DEFAULT_AMP_W5_UM = 16.0
_DEFAULT_AMP_L5_UM = 1.0
_DEFAULT_AMP_WB_UM = 8.0
_DEFAULT_AMP_LB_UM = 1.0
_DEFAULT_IREF_AMP_UA = 15.0


@dataclass
class VRefParams:
    rptat_ohm: float = _DEFAULT_RPTAT_OHM
    rscale_ohm: float = _DEFAULT_RSCALE_OHM
    mirror_l_um: float = _DEFAULT_MIRROR_L_UM

    mirror_w_um: float = 8.0

    amp_w1_um: float = _DEFAULT_AMP_W1_UM
    amp_l1_um: float = _DEFAULT_AMP_L1_UM
    amp_w3_um: float = _DEFAULT_AMP_W3_UM
    amp_l3_um: float = _DEFAULT_AMP_L3_UM
    amp_w5_um: float = _DEFAULT_AMP_W5_UM
    amp_l5_um: float = _DEFAULT_AMP_L5_UM
    amp_wb_um: float = _DEFAULT_AMP_WB_UM
    amp_lb_um: float = _DEFAULT_AMP_LB_UM
    iref_amp_uA: float = _DEFAULT_IREF_AMP_UA

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _params_block(p: VRefParams, supply_V: float) -> str:
    return f""".param VDD={supply_V}
.param RPTAT={p.rptat_ohm}
.param RSCALE={p.rscale_ohm}
.param MIRROR_L={p.mirror_l_um}u
.param W1={p.amp_w1_um}u L1={p.amp_l1_um}u
.param W3={p.amp_w3_um}u L3={p.amp_l3_um}u
.param W5={p.amp_w5_um}u L5={p.amp_l5_um}u
.param Wb={p.amp_wb_um}u Lb={p.amp_lb_um}u
.param IREF_AMP={p.iref_amp_uA}u
"""


def _error_amp(ms: ResolvedModels) -> str:
    """Bandgap loop amp — reuse opamp NMOS diff pair + PMOS mirror load (single-ended → net2)."""
    lines = [
        "* bandgap error amp: servo V(ra1)≈V(qp1) via net2 (PMOS mirror gate)",
        "Iref_amp vdd nb_amp {IREF_AMP}",
        mos_line("ea8", "nb_amp", "nb_amp", "0", "0", "n", w="{Wb}", l="{Lb}", ms=ms),
        mos_line("ea5", "amp_tail", "nb_amp", "0", "0", "n", w="{W5}", l="{L5}", ms=ms),
    ]
    lines.extend(
        emit_diff_pair(
            ms,
            vinp="ra1",
            vinn="qp1",
            tail="amp_tail",
            out_p="amp_n1",
            out_n="net2",
            inst_p="ea1",
            inst_n="ea2",
        ).lines
    )
    lines.extend(
        emit_pmos_load(
            ms,
            drain_ref="amp_n1",
            drain_out="net2",
            inst_ref="ea3",
            inst_out="ea4",
        ).lines
    )
    return "\n".join(lines) + "\n"


def _ptat_mirror(ms: ResolvedModels, *, mirror_w: str = "8u") -> str:
    w, l = mirror_w, "{MIRROR_L}"
    return "\n".join(
        [
            mos_line("p1", "qp1", "net2", "vdd", "vdd", "p", w=w, l=l, ms=ms),
            mos_line("p2", "ra1", "net2", "vdd", "vdd", "p", w=w, l=l, ms=ms),
            mos_line("p3", "vref", "net2", "vdd", "vdd", "p", w=w, l=l, ms=ms),
        ]
    )


def _build_bandgap_deck(p: VRefParams, supply_V: float) -> str:
    """SKY130 substrate-PNP bandgap: CTAT (Q1) + PTAT (Q2 ΔVbe × Rscale/Rptat) → vref."""
    ms = resolve_models()
    body = f"""
* OpenForge SKY130 bandgap (substrate PNP PTAT + CTAT)
Vsup vdd 0 {supply_V}
{_error_amp(ms)}{_ptat_mirror(ms, mirror_w=f"{p.mirror_w_um}u")}
* Substrate PNP: C=B=0, E=signal (SKY130 sky130_fd_pr__pnp_11v0)
Q1 0 0 qp1 0 {ms.pnp} area=1
Q2 0 0 qp2 0 {ms.pnp} area=8
Q3 0 0 qp3 0 {ms.pnp} area=1
Rptat ra1 qp2 {{RPTAT}}
Rscale vref qp3 {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref) v(qp1) v(ra1) v(net2)
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.1
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
dc Vsup 5 5 1 temp -40 125 20
meas dc tempco pp v(vref)
.endc
.end
"""
    return ms.block + _params_block(p, supply_V) + body


def _comment_spice_control_block(deck: str) -> str:
    """Comment .control … .endc for schematic export (meas/print lines are not devices)."""
    out: list[str] = []
    in_control = False
    for line in deck.splitlines():
        stripped = line.strip()
        if stripped.startswith(".control"):
            in_control = True
        if in_control:
            out.append(line if stripped.startswith("*") else f"* {line}")
            if stripped.startswith(".endc"):
                in_control = False
            continue
        if stripped.startswith(".") and not stripped.startswith(".param"):
            out.append(line if stripped.startswith("*") else f"* {line}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


class VRefTopology(Topology):
    circuit_type = "vref"
    topology_name = "sky130_bandgap"
    spec_weights = {"vref_V": 2.0, "line_reg_mV": 1.5, "tempco_ppm": 1.0, "iq_uA": 1.0}

    def default_params(self) -> VRefParams:
        return VRefParams()

    def param_ranges(self) -> dict[str, tuple[float, float, bool]]:
        return {
            "rptat_ohm": (400.0, 3000.0, True),
            "rscale_ohm": (4000.0, 16000.0, True),
            "mirror_l_um": (1.0, 6.0, True),
            "mirror_w_um": (4.0, 24.0, True),
        }

    def measurable_specs(self) -> set[str]:
        return {"vref_V", "line_reg_mV", "tempco_ppm", "iq_uA"}

    def measure(
        self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12, with_full: bool = True
    ) -> TopologyMetrics:
        m = TopologyMetrics()
        ms = resolve_models()
        if ms.model_set != "sky130":
            m.warnings.append(_PHASE3_MSG)
            m.error = _PHASE3_MSG
            m.ok = False
            return m

        ok, out = run_ngspice(_build_bandgap_deck(params, supply_V), timeout=max(NGSPICE_TIMEOUT, 45))
        m.raw = out[-3000:]
        if not ok:
            m.error = out[:800]
            return m
        vref = grab_meas("vref_nom", out)
        line_reg = grab_meas("line_reg", out)
        tempco = grab_meas("tempco", out)
        iq = grab_meas("isupp", out)
        m.values["vref_V"] = vref
        m.values["line_reg_mV"] = line_reg * 1000 if line_reg else None
        m.values["iq_uA"] = abs(iq) * 1e6 if iq else None
        if tempco is not None and vref:
            m.values["tempco_ppm"] = abs(tempco / vref) * 1e6
        m.ok = vref is not None and 1.18 <= vref <= 1.22
        return m

    def emit_netlist(self, params: VRefParams, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str:
        ms = resolve_models()
        if ms.model_set != "sky130":
            return f"* {_PHASE3_MSG}\n.end\n"
        return _comment_spice_control_block(_build_bandgap_deck(params, supply_V))

    def device_list(self, params: VRefParams) -> list[dict[str, Any]]:
        ms = resolve_models()
        if ms.model_set != "sky130":
            return [{"name": "—", "role": "deferred (bundled)", "value": ""}]
        p = params.as_dict()
        return [
            {"name": "Q1/Q2/Q3", "role": "substrate PNP bandgap core", "value": "SKY130 PNP 1×/8×/1×"},
            {"name": "Rptat", "role": "PTAT ΔVbe resistor", "value": f"{p['rptat_ohm']:.0f} Ω"},
            {"name": "Rscale", "role": "CTAT+PTAT scale", "value": f"{p['rscale_ohm']:.0f} Ω"},
            {"name": "Mp1–3", "role": "PMOS bias mirror", "value": f"L={p['mirror_l_um']:.1f} µm"},
            {"name": "Ea1–4", "role": "bandgap error amp (diff pair + mirror load)", "value": f"W1={p['amp_w1_um']:.0f} µm"},
        ]

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"


register(VRefTopology())
