from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from openanalog.forge.simulator import SimResult


@dataclass
class FitnessSpec:
    topology: str
    checks: dict[str, Callable[[SimResult], bool]]


def _specs() -> dict[str, FitnessSpec]:
    return {
        "tia": FitnessSpec(
            "tia",
            {
                "bw": lambda s: s.bw_3db_MHz > 1,
                "gain": lambda s: s.gain_dB > 55,
                "PM": lambda s: s.phase_margin > 45,
                "power": lambda s: s.power_mW < 3,
            },
        ),
        "ota": FitnessSpec(
            "ota",
            {
                "GBW": lambda s: s.bw_3db_MHz > 10,
                "PM": lambda s: s.phase_margin > 60,
                "gain": lambda s: s.gain_dB > 70,
                "power": lambda s: s.power_mW < 2,
            },
        ),
        "charge_pump": FitnessSpec(
            "charge_pump",
            {
                "vout": lambda s: s.output_voltage > 2.0,
                "ripple": lambda s: s.ripple_mV < 50,
            },
        ),
        "filter_lp": FitnessSpec(
            "filter_lp",
            {
                "fc": lambda s: s.bw_3db_MHz > 0.01,
                "power": lambda s: s.power_mW < 1,
            },
        ),
        "filter": FitnessSpec(
            "filter",
            {
                "fc": lambda s: s.bw_3db_MHz > 0.01,
                "power": lambda s: s.power_mW < 1,
            },
        ),
        "mirror": FitnessSpec(
            "mirror",
            {
                "swing": lambda s: s.output_voltage > 0.8,
                "power": lambda s: s.power_mW < 0.5,
            },
        ),
        "crossbar_tia": FitnessSpec(
            "crossbar_tia",
            {
                "bw": lambda s: s.bw_3db_MHz > 1,
                "power": lambda s: s.power_mW < 5,
            },
        ),
        "crossbar": FitnessSpec(
            "crossbar",
            {
                "bw": lambda s: s.bw_3db_MHz > 1,
                "power": lambda s: s.power_mW < 5,
            },
        ),
        "opamp": FitnessSpec(
            "opamp",
            {
                "gain": lambda s: s.gain_dB >= 90,
                "GBW": lambda s: s.bw_3db_MHz >= 1.0,
                "PM": lambda s: s.phase_margin >= 60,
                "power": lambda s: s.power_mW < 1.0,
            },
        ),
        "comparator": FitnessSpec(
            "comparator",
            {
                "tp": lambda s: s.ok,
                "vos": lambda s: s.ok,
                "iq": lambda s: s.power_mW < 0.5,
            },
        ),
        "switch": FitnessSpec(
            "switch",
            {
                "ron": lambda s: s.ok,
                "bw": lambda s: s.bw_3db_MHz > 1,
                "power": lambda s: s.power_mW < 0.5,
            },
        ),
        "vref": FitnessSpec(
            "vref",
            {
                "vref": lambda s: s.output_voltage > 0.5,
                "line_reg": lambda s: s.ok,
                "iq": lambda s: s.power_mW < 0.5,
            },
        ),
        "unknown": FitnessSpec("unknown", {"sim_ok": lambda s: s.ok}),
    }


def score_fitness(topology: str, sim: SimResult) -> dict:
    spec = _specs().get(topology, _specs()["unknown"])
    failed: list[str] = []
    margins: dict[str, float] = {}
    for name, fn in spec.checks.items():
        passed = fn(sim)
        if not passed:
            failed.append(name)
        margins[name] = _margin(name, sim)
    score = 1 if not failed and sim.ok else 0
    return {"score": score, "failed_checks": failed, "margin_per_check": margins}


def _margin(name: str, s: SimResult) -> float:
    table = {
        "bw": s.bw_3db_MHz - 1,
        "gain": s.gain_dB - 55,
        "PM": s.phase_margin - 45,
        "power": 3 - s.power_mW,
        "GBW": s.bw_3db_MHz - 10,
        "ripple": 50 - s.ripple_mV,
        "vout": s.output_voltage - 2,
    }
    return table.get(name, 0.0)
