"""
openanalog/use_cases.py

Application use-case cards for the OpenForge web UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UseCase:
    id: str
    title: str
    summary: str
    tags: tuple[str, ...]
    product_ids: tuple[str, ...]
    preset_ids: tuple[str, ...]
    highlight_metrics: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "tags": list(self.tags),
            "product_ids": list(self.product_ids),
            "preset_ids": list(self.preset_ids),
            "highlight_metrics": list(self.highlight_metrics),
        }


USE_CASES: list[UseCase] = [
    UseCase(
        id="battery_low_iq",
        title="Battery / Low Quiescent Current",
        summary=(
            "Design blocks with sub-µA to tens-of-µA Iq for always-on sensor nodes, "
            "wearables, and coin-cell products. Forge winners show comparators down to "
            "~0.4 µA and LDOs under 15 µA — no digital sleep controller required."
        ),
        tags=("battery", "low-power", "quiescent", "wearable", "IoT"),
        product_ids=("comparator", "ldo", "opamp"),
        preset_ids=("rs8901_comparator", "low_iq_opamp", "rs3001_ldo"),
        highlight_metrics=("iq_uA",),
    ),
    UseCase(
        id="sensor_frontend",
        title="Low-Power Sensor Front-End",
        summary=(
            "Precision op-amp + low-Iq LDO + analog switch for multiplexed sensor "
            "channels. Analog signal path stays in the continuous domain — fewer "
            "ADC conversions and less digital filtering overhead."
        ),
        tags=("sensor", "front-end", "multiplex", "precision"),
        product_ids=("precision_opamp", "ldo", "analog_switch"),
        preset_ids=("rs321_opamp", "rs3001_ldo", "rs2105_switch"),
        highlight_metrics=("iq_uA", "vos_mV", "ron_ohm"),
    ),
    UseCase(
        id="analog_multiply",
        title="Analog Multiplication (Gilbert Cell)",
        summary=(
            "Four-quadrant analog multiplier computes Vout ∝ Vx·Vy in one transistor "
            "stage — replacing a chain of digital MAC operations for small vector "
            "products, mixers, and control loops."
        ),
        tags=("multiply", "gilbert", "mixer", "analog-compute"),
        product_ids=("analog_multiplier",),
        preset_ids=("rs7001_multiplier",),
        highlight_metrics=("gain_err_pct", "bw_MHz", "iq_uA"),
    ),
    UseCase(
        id="vector_mac",
        title="Vector–Matrix Multiply (Analog MAC)",
        summary=(
            "Tile Gilbert cells into a crossbar: each junction computes one product "
            "directly in silicon. Summation happens on the output bus — the final "
            "dot-product emerges without intermediate digital multiplies. Planned for "
            "Phase 4+ compute tiles."
        ),
        tags=("matrix", "mac", "crossbar", "analog-ai", "in-memory"),
        product_ids=("analog_mac", "analog_compute_tile"),
        preset_ids=(),
        highlight_metrics=("gain_err_pct", "bw_MHz"),
    ),
    UseCase(
        id="analog_replaces_digital",
        title="Analog Replaces Digital Chains",
        summary=(
            "Where precision requirements are moderate and speed/power dominate, "
            "analog blocks (multiply, integrate, compare) can replace digital "
            "pipelines — fewer clock cycles, lower switching energy, direct final "
            "product instead of repeated multiply-accumulate steps."
        ),
        tags=("analog-digital", "energy", "direct-product", "edge-ai"),
        product_ids=("analog_multiplier", "comparator", "opamp"),
        preset_ids=("rs7001_multiplier", "fast_comparator"),
        highlight_metrics=("iq_uA", "tp_us", "gain_err_pct"),
    ),
]


def use_cases_payload() -> dict[str, Any]:
    return {"use_cases": [u.to_dict() for u in USE_CASES]}
