"""
openanalog/presets.py

Versioned design presets — each preset is also a test case.
Adding a preset automatically adds coverage via tests/test_presets.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.forge.spec_envelopes import (
    DATASHEET_PARTS,
    DEV_MODE_SPECS,
    VREF_PHASE3_SPEC,
)

PRESET_VERSION = "1.0.0"


@dataclass(frozen=True)
class DesignPreset:
    id: str
    name: str
    category: str
    spec: str
    expect_pass: bool
    budget: int = 200
    seed: int = 42
    part: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "spec": self.spec,
            "expect_pass": self.expect_pass,
            "budget": self.budget,
            "seed": self.seed,
            "part": self.part or DATASHEET_PARTS.get(self.category, ""),
            "notes": self.notes,
            "version": PRESET_VERSION,
        }


# RS-series canonical presets (datasheet bar)
PRESETS: list[DesignPreset] = [
    DesignPreset(
        id="rs321_opamp",
        name="RS321 Op-Amp",
        category="opamp",
        spec=DEV_MODE_SPECS["opamp"],
        expect_pass=True,
        budget=200,
        seed=42,
        part="RS321",
        notes="1.1 MHz GBP, PM>60, AOL>95 dB, Iq<80 µA",
    ),
    DesignPreset(
        id="rs8901_comparator",
        name="RS8901 Comparator",
        category="comparator",
        spec=DEV_MODE_SPECS["comparator"],
        expect_pass=True,
        budget=200,
        seed=1,
        part="RS8901",
        notes="tp<1 µs, Vos<3 mV, Iq<1 µA",
    ),
    DesignPreset(
        id="rs2105_switch",
        name="RS2105 Analog Switch",
        category="switch",
        spec=DEV_MODE_SPECS["switch"],
        expect_pass=False,
        budget=200,
        seed=1,
        part="RS2105",
        notes="blocked-phase3 on level-1; expect fail until SKY130",
    ),
    DesignPreset(
        id="rs2660_charge_pump",
        name="RS2660 Charge Pump",
        category="charge_pump",
        spec=DEV_MODE_SPECS["charge_pump"],
        expect_pass=False,
        budget=200,
        seed=1,
        part="RS2660",
        notes="blocked-phase3 on level-1; expect fail until SKY130",
    ),
    DesignPreset(
        id="rs431_vref",
        name="RS431 Voltage Reference",
        category="vref",
        spec=VREF_PHASE3_SPEC,
        expect_pass=False,
        budget=200,
        seed=1,
        part="RS431",
        notes="deferred to Phase 3 SKY130 bandgap",
    ),
    # Extra presets for regression growth
    DesignPreset(
        id="fast_comparator",
        name="Fast Comparator (500 ns)",
        category="comparator",
        spec="type=comparator tp<0.5us vos<5mV iq<2uA",
        expect_pass=True,
        budget=150,
        seed=7,
        part="custom",
        notes="Aggressive delay target on bundled models",
    ),
    DesignPreset(
        id="low_iq_opamp",
        name="Low-Iq Op-Amp",
        category="opamp",
        spec="gbp=0.8MHz pm>55 aol>90dB iq<60uA",
        expect_pass=True,
        budget=180,
        seed=11,
        part="custom",
        notes="Relaxed GBP, tighter Iq",
    ),
]


def list_presets(*, category: str | None = None) -> list[DesignPreset]:
    if category:
        return [p for p in PRESETS if p.category == category]
    return list(PRESETS)


def get_preset(preset_id: str) -> DesignPreset | None:
    for p in PRESETS:
        if p.id == preset_id:
            return p
    return None


def presets_payload() -> dict[str, Any]:
    return {
        "version": PRESET_VERSION,
        "presets": [p.to_dict() for p in PRESETS],
    }
