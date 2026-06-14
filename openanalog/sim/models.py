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

# Minimal SKY130-style cards (replaced by fetched cards when data/pdk/sky130/models.sp exists)
SKY130_MODELS_BUILTIN = """* openforge sky130 models (builtin minimal)
.model sky130_fd_pr__nfet_01v8 nmos (level=54 version=4.5
+ lmin=0.15u lmax=20u wmin=0.42u wmax=1000u
+ toxe=4.148e-9 vth0=0.409 u0=0.025 vfb=-0.55
+ nfactor=1.0 lint=0 wint=0 cgso=1e-11 cgdo=1e-11)
.model sky130_fd_pr__pfet_01v8 pmos (level=54 version=4.5
+ lmin=0.15u lmax=20u wmin=0.42u wmax=1000u
+ toxe=4.148e-9 vth0=-0.389 u0=0.010 vfb=0.55
+ nfactor=1.0 lint=0 wint=0 cgso=1e-11 cgdo=1e-11)
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
    if fetched.exists():
        return fetched.read_text(encoding="utf-8")
    return None


def sky130_models_block() -> str:
    fetched = _load_fetched_sky130_block()
    if fetched:
        # Corner cards pull relative .include chains — use fetched only if self-contained
        if '.include "' in fetched.lower() and not (PDK_DIR / "cells").exists():
            return SKY130_MODELS_BUILTIN
        return fetched
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


def models_available() -> dict[str, bool]:
    return {
        "bundled": True,
        "sky130": True,
        "sky130_fetched": (PDK_DIR / "models.sp").exists(),
    }
