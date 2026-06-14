"""
Canonical RS-series datasheet spec envelopes.

These inline specs are the ONLY bar for fitness=1, make smoke, and STATUS.md.
Do not loosen them for dev convenience — a green gate on soft targets poisons
the training flywheel silently.

Sources (user-held datasheets):
  RS321/RS358  — opamp
  RS8901       — comparator
  RS2105       — analog switch
  RS2660       — charge pump
  RS431        — voltage reference (Phase 3 / SKY130)
"""

from __future__ import annotations

DATASHEET_PARTS: dict[str, str] = {
    "opamp": "RS321",
    "comparator": "RS8901",
    "switch": "RS2105",
    "charge_pump": "RS2660",
    "vref": "RS431",
}

# Dev-mode categories: achievable targets on bundled level-1 models (in principle).
DEV_MODE_SPECS: dict[str, str] = {
    "opamp": "gbp=1.1MHz pm>60 aol>95dB iq<80uA slew>0.5",
    "comparator": "type=comparator tp<1us vos<3mV iq<1uA",
    "switch": "type=switch ron<50ohm bw>10MHz ton<20ns toff<20ns",
    "charge_pump": "type=charge_pump vout=5V settle<5ms ripple<50mV",
}

# Real bandgap needs SKY130 parasitic BJTs — not level-1 MOS (see AGENT_PLAN Phase 3).
DEFERRED_CATEGORIES: list[str] = ["vref"]

VREF_PHASE3_SPEC: str = "type=vref vref=1.2V line_reg<5mV iq<100uA"
