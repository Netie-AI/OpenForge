"""
openanalog/forge/topologies/base.py

Pluggable topology protocol for the multi-category analog generator.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openanalog.config import NGSPICE_TIMEOUT, ngspice_path_arg, resolve_ngspice_cmd

from openanalog.sim.models import ResolvedModels, resolve_models, set_active_model_set


@dataclass
class TopologyMetrics:
    ok: bool = False
    values: dict[str, float | None] = field(default_factory=dict)
    raw: str = ""
    error: str = ""
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, float | None]:
        return dict(self.values)

    def get(self, key: str, default: float | None = None) -> float | None:
        return self.values.get(key, default)


def run_ngspice(deck: str, *, timeout: int | None = None) -> tuple[bool, str]:
    cmd = resolve_ngspice_cmd()
    if not cmd:
        return False, "ngspice not found"
    with tempfile.NamedTemporaryFile("w", suffix=".sp", delete=False, prefix="oftopo_") as tmp:
        tmp.write(deck)
        path = Path(tmp.name)
    try:
        r = subprocess.run(
            [*cmd, "-b", ngspice_path_arg(path, cmd)],
            capture_output=True,
            text=True,
            timeout=timeout or NGSPICE_TIMEOUT,
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return False, "ngspice not found"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        path.unlink(missing_ok=True)


def grab_meas(name: str, text: str) -> float | None:
    m = re.search(rf"{name}\s*=\s*([-\d.eE+]+)", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


class Topology(ABC):
    circuit_type: str
    topology_name: str
    spec_weights: dict[str, float]

    @abstractmethod
    def default_params(self) -> Any: ...

    @abstractmethod
    def param_ranges(self) -> dict[str, tuple[float, float, bool]]: ...

    @abstractmethod
    def measurable_specs(self) -> set[str]: ...

    @abstractmethod
    def measure(
        self,
        params: Any,
        *,
        supply_V: float = 5.0,
        cload_F: float = 10e-12,
        with_full: bool = True,
    ) -> TopologyMetrics: ...

    @abstractmethod
    def emit_netlist(self, params: Any, *, supply_V: float = 5.0, cload_F: float = 10e-12) -> str: ...

    @abstractmethod
    def device_list(self, params: Any) -> list[dict[str, Any]]: ...

    def package_hint(self, spec: dict[str, Any] | None = None) -> str:
        return "SOT23-5"

    def estimate_extra(self, params: Any, *, cload_F: float = 10e-12) -> dict[str, float]:
        """Optional cheap analytic estimates during search (before full sim)."""
        return {}

    def params_from_dict(self, d: dict[str, float]) -> Any:
        cls = type(self.default_params())
        return cls(**{k: v for k, v in d.items() if hasattr(cls, k)})


REGISTRY: dict[str, Topology] = {}


def get_topology(circuit_type: str) -> Topology:
    key = circuit_type.lower().replace("-", "_")
    aliases = {
        "op_amp": "opamp",
        "operational_amplifier": "opamp",
        "analog_switch": "switch",
        "voltage_reference": "vref",
        "reference": "vref",
        "bandgap": "vref",
        "ldo": "ldo",
        "linear_regulator": "ldo",
        "multiplier": "multiplier",
        "analog_multiplier": "multiplier",
        "gilbert": "multiplier",
    }
    key = aliases.get(key, key)
    if key not in REGISTRY:
        raise ValueError(f"Unknown circuit type '{circuit_type}'. Available: {list(REGISTRY)}")
    return REGISTRY[key]


def register(topology: Topology) -> None:
    REGISTRY[topology.circuit_type] = topology
