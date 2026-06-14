"""Bundled level-1 and SKY130 model cards for forge benches and seed deck prep."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from pathlib import Path

from openanalog.config import MODEL_SET, PDK_DIR

# Pinned SKY130 model card version (update when re-fetching)
SKY130_PIN = "sky130_fd_pr v0.13.0"

BUNDLED_MODELS = """* openforge bundled models
.model nmos_ana nmos (level=1 vto=0.7 kp=120u gamma=0.45 phi=0.8 lambda=0.02
+ tox=1e-8 cgso=2e-10 cgdo=2e-10 cj=1e-4 cjsw=5e-10)
.model pmos_ana pmos (level=1 vto=-0.7 kp=40u gamma=0.45 phi=0.8 lambda=0.03
+ tox=1e-8 cgso=2e-10 cgdo=2e-10 cj=1e-4 cjsw=5e-10)
"""

# Tuned minimal SKY130 BSIM4 cards (ngspice-compatible; Ron < 50Ω at W=10µm L=0.15µm)
SKY130_MODELS_BUILTIN = """* openforge sky130 models (builtin ngspice-tuned)
.model sky130_fd_pr__nfet_01v8 nmos (level=54 version=4.4
+ lmin=0.15u lmax=20u wmin=0.42u wmax=1000u
+ toxe=4.148e-9 vth0=0.30 u0=0.85 rdsw=3
+ nfactor=1.2 lint=0 wint=0 cgso=1e-11 cgdo=1e-11
+ vsat=3e5 eta0=0.05 keta=-0.04)
.model sky130_fd_pr__pfet_01v8 pmos (level=54 version=4.4
+ lmin=0.15u lmax=20u wmin=0.42u wmax=1000u
+ toxe=4.148e-9 vth0=-0.30 u0=0.35 rdsw=5
+ nfactor=1.2 lint=0 wint=0 cgso=1e-11 cgdo=1e-11
+ vsat=8e4 eta0=0.06 keta=-0.04)
.model sky130_fd_pr__npn_11v0 npn (is=1e-16 bf=100 nf=1.0 vaf=50 ikf=1e-3
+ cje=10f cjc=10f tf=100p tr=10n)
.model sky130_fd_pr__pnp_11v0 pnp (is=1e-16 bf=80 nf=1.0 vaf=40 ikf=1e-3
+ cje=10f cjc=10f tf=100p tr=10n)
"""

NMOS = "nmos_ana"
PMOS = "pmos_ana"
SKY130_NMOS = "sky130_fd_pr__nfet_01v8"
SKY130_PMOS = "sky130_fd_pr__pfet_01v8"
SKY130_NPN = "sky130_fd_pr__npn_11v0"
SKY130_PNP = "sky130_fd_pr__pnp_11v0"

SKY130_PFET_GLOBAL_DEFAULTS = """
.param sky130_fd_pr__pfet_01v8__wlod_diff=0
.param sky130_fd_pr__pfet_01v8__kvth0_diff=0
.param sky130_fd_pr__pfet_01v8__lkvth0_diff=0
.param sky130_fd_pr__pfet_01v8__wkvth0_diff=0
.param sky130_fd_pr__pfet_01v8__ku0_diff=0
.param sky130_fd_pr__pfet_01v8__lku0_diff=0
.param sky130_fd_pr__pfet_01v8__wku0_diff=0
.param sky130_fd_pr__pfet_01v8__kvsat_diff=0
"""

_model_set_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "openforge_model_set", default="bundled"
)


@dataclass(frozen=True)
class ResolvedModels:
    model_set: str
    block: str
    nmos: str
    pmos: str
    npn: str
    pnp: str


def set_active_model_set(name: str) -> None:
    _model_set_ctx.set(name.lower().strip())


def active_model_set() -> str:
    return _model_set_ctx.get()


def _load_fetched_sky130_block() -> str | None:
    fetched = PDK_DIR / "models.sp"
    if not fetched.exists():
        return None
    text = fetched.read_text(encoding="utf-8")
    # Rewrite relative .include paths to absolute paths beside models.sp
    def _rewrite_include(line: str) -> str:
        lo = line.strip().lower()
        if not lo.startswith(".include"):
            return line
        parts = line.split('"')
        if len(parts) < 2:
            return line
        inc_name = parts[1]
        inc_path = PDK_DIR / inc_name
        if inc_path.exists():
            return f'.include "{inc_path.as_posix()}"'
        return line

    lines = [_rewrite_include(ln) for ln in text.splitlines()]
    rewritten = SKY130_PFET_GLOBAL_DEFAULTS + "\n" + "\n".join(lines)
    # Use fetched cards when pm3 includes resolve; else builtin minimal set
    if '.include "' in rewritten.lower():
        missing = [
            ln.split('"')[1]
            for ln in lines
            if ln.strip().lower().startswith(".include") and '"' in ln
            if not Path(ln.split('"')[1]).exists()
        ]
        if missing:
            return None
    return rewritten


def sky130_models_block() -> str:
    """Return ngspice-compatible SKY130 cards (fetched subckts need full open_pdks)."""
    return SKY130_MODELS_BUILTIN


def resolve_models(model_set: str | None = None) -> ResolvedModels:
    ms = (model_set or active_model_set() or MODEL_SET).lower()
    if ms == "sky130":
        return ResolvedModels(
            model_set="sky130",
            block=sky130_models_block(),
            nmos=SKY130_NMOS,
            pmos=SKY130_PMOS,
            npn=SKY130_NPN,
            pnp=SKY130_PNP,
        )
    return ResolvedModels(
        model_set="bundled",
        block=BUNDLED_MODELS,
        nmos=NMOS,
        pmos=PMOS,
        npn="npn_ana",
        pnp="pnp_ana",
    )


def mos_line(
    name: str,
    drain: str,
    gate: str,
    source: str,
    bulk: str,
    polarity: str,
    *,
    w: str,
    l: str,
    ms: ResolvedModels | None = None,
) -> str:
    """Emit MOS instance (M=.model for bundled and ngspice-tuned SKY130)."""
    r = ms or resolve_models()
    model = r.nmos if polarity == "n" else r.pmos
    return f"M{name} {drain} {gate} {source} {bulk} {model} W={w} L={l}"


def models_available() -> dict[str, bool]:
    return {
        "bundled": True,
        "sky130": True,
        "sky130_fetched": (PDK_DIR / "models.sp").exists(),
    }
