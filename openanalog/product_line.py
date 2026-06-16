"""
openanalog/product_line.py

Runic RS-series product catalog for the chat-to-chip UI.

Each product maps to a forge topology backend where simulation exists.
Products without a backend are marked ``planned`` — the UI shows them but
blocks design until Phase 4+ topologies land.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS, VREF_PHASE3_SPEC, MULTIPLIER_EXPERIMENTAL_SPEC


@dataclass(frozen=True)
class ProductType:
    id: str
    label: str
    family: str
    topology: str | None  # forge REGISTRY key; None = not yet implemented
    status: str  # available | partial | planned
    part: str
    sample: str
    inline_spec: str
    keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "topology": self.topology,
            "status": self.status,
            "part": self.part,
            "sample": self.sample,
            "inline_spec": self.inline_spec,
            "keywords": list(self.keywords),
            "designable": self.topology is not None and self.status != "planned",
        }


def _sample_opamp(part: str, *, precision: bool = False) -> str:
    vos = "0.5 mV" if precision else "2.5 mV"
    aol = "110 120 dB" if precision else "95 100 dB"
    return f"""{part} Rail-to-Rail CMOS Operational Amplifier
SUPPLY RANGE: +2.2V to +5.5V  (test VS=5V)
GAIN-BANDWIDTH PRODUCT: 1.1 MHz
SLEW RATE: 0.5 V/us
PHASE MARGIN: 64 deg
AOL Open-Loop Voltage Gain: {aol} (RL=10k)
Input Offset Voltage: {vos}
IQ Quiescent Current Per Amplifier: 60 80 uA
"""


PRODUCT_LINE: list[ProductType] = [
    ProductType(
        id="opamp",
        label="Op-Amp",
        family="Amplifiers",
        topology="opamp",
        status="available",
        part="RS321",
        sample=_sample_opamp("RS321/RS358 1.1MHz"),
        inline_spec=DEV_MODE_SPECS["opamp"],
        keywords=("op-amp", "op amp", "opamp", "operational amplifier", "ota", "rs321", "rs358"),
    ),
    ProductType(
        id="precision_opamp",
        label="High-Precision Op-Amp",
        family="Amplifiers",
        topology="opamp",
        status="available",
        part="RS722",
        sample=_sample_opamp("RS722 Precision", precision=True),
        inline_spec="gbp=1.0MHz pm>60 aol>110dB iq<100uA vos<1mV",
        keywords=("precision op", "high precision", "low offset", "rs722", "auto-zero"),
    ),
    ProductType(
        id="comparator",
        label="Comparator",
        family="Amplifiers",
        topology="comparator",
        status="available",
        part="RS8901",
        sample="""RS8901 Low-Power Comparator
SUPPLY VS=5V
Propagation Delay: 0.8 us
Input Offset Voltage: 2.5 mV
Quiescent Current: 0.5 uA
""",
        inline_spec=DEV_MODE_SPECS["comparator"],
        keywords=("comparator", "compare", "rs8901", "lm2903", "lm393"),
    ),
    ProductType(
        id="analog_switch",
        label="Analog Switch",
        family="Switches",
        topology="switch",
        status="partial",
        part="RS2105",
        sample="""RS2105 Analog Switch
SUPPLY VS=5V
On-Resistance: 25 ohm
Bandwidth -3dB: 15 MHz
Turn-On Time: 12 ns  Turn-Off Time: 10 ns
""",
        inline_spec=DEV_MODE_SPECS["switch"],
        keywords=("analog switch", "transmission gate", "rs2105", "analog mux"),
    ),
    ProductType(
        id="hs_switch",
        label="High-Speed Switch",
        family="Switches",
        topology="switch",
        status="partial",
        part="RS2227",
        sample="""RS2227 High-Speed Analog Switch
SUPPLY VS=5V
On-Resistance: 15 ohm
Bandwidth -3dB: 300 MHz
Turn-On Time: 5 ns  Turn-Off Time: 4 ns
""",
        inline_spec="type=switch ron<30ohm bw>200MHz ton<10ns toff<10ns",
        keywords=("high speed switch", "hs switch", "rs2227", "video switch"),
    ),
    ProductType(
        id="logic_switch",
        label="Logic Switch / Mux",
        family="Switches",
        topology="switch",
        status="partial",
        part="RS2251",
        sample="""RS2251 4-Channel Logic-Level Analog Switch
SUPPLY VS=5V
On-Resistance: 40 ohm
Bandwidth: 50 MHz
Logic-compatible control inputs
""",
        inline_spec="type=switch ron<60ohm bw>40MHz ton<30ns toff<30ns",
        keywords=("logic switch", "analog mux", "multiplexer", "rs2251", "4051"),
    ),
    ProductType(
        id="charge_pump",
        label="Charge Pump",
        family="Power",
        topology="charge_pump",
        status="partial",
        part="RS2660",
        sample="""RS2660 Charge Pump
SUPPLY VS=5V
Output Voltage: 5.0 V
Ripple: 30 mV
Settling Time: 3 ms
""",
        inline_spec=DEV_MODE_SPECS["charge_pump"],
        keywords=("charge pump", "dickson", "voltage doubler", "rs2660"),
    ),
    ProductType(
        id="vref",
        label="Voltage Reference",
        family="Power",
        topology="vref",
        status="partial",
        part="RS431",
        sample="""RS431 Voltage Reference
SUPPLY VS=5V
Reference Voltage: 1.225 V
Line Regulation: 2 mV
Temperature Coefficient: 50 ppm/°C
""",
        inline_spec=VREF_PHASE3_SPEC,
        keywords=("voltage reference", "bandgap", "vref", "shunt reference", "rs431"),
    ),
    ProductType(
        id="ldo",
        label="LDO Regulator",
        family="Power",
        topology="ldo",
        status="partial",
        part="RS3001",
        sample="""RS3001 300mA Low-Dropout Regulator
Input: 2.5V to 6.0V
Output: 3.3V fixed
Dropout: 150 mV @ 300mA
Line Regulation: 5 mV
Load Regulation: 15 mV
Quiescent Current: 25 uA
""",
        inline_spec=DEV_MODE_SPECS["ldo"],
        keywords=("ldo", "low dropout", "linear regulator", "voltage regulator", "rs3001"),
    ),
    ProductType(
        id="level_translator",
        label="Level Translator",
        family="Interface",
        topology=None,
        status="planned",
        part="RS0102",
        sample="""RS0102 Dual-Channel Level Shifter
VCCA: 1.2V to 3.6V
VCCB: 1.8V to 5.5V
Propagation Delay: 5 ns
""",
        inline_spec="type=level_translator delay<10ns",
        keywords=("level translator", "level shifter", "voltage translator", "rs0102"),
    ),
    ProductType(
        id="logic_ic",
        label="Logic IC",
        family="Digital",
        topology=None,
        status="planned",
        part="RS74HC",
        sample="""RS74HC00 Quad 2-Input NAND Gate
SUPPLY: 2.0V to 6.0V
Propagation Delay: 8 ns @ 5V
Input Leakage: 1 uA
""",
        inline_spec="type=logic_ic delay<15ns",
        keywords=("logic gate", "nand", "nor", "74hc", "cmos logic", "logic ic"),
    ),
    ProductType(
        id="adc",
        label="ADC",
        family="Data Converters",
        topology=None,
        status="planned",
        part="RS1100",
        sample="""RS1100 12-bit SAR ADC
SUPPLY: 2.7V to 5.5V
Sample Rate: 1 MSPS
INL: ±1 LSB
""",
        inline_spec="type=adc bits=12 inl<2lsb",
        keywords=("adc", "sar adc", "analog to digital", "rs1100"),
    ),
    ProductType(
        id="dac",
        label="DAC",
        family="Data Converters",
        topology=None,
        status="planned",
        part="RS2200",
        sample="""RS2200 12-bit Voltage-Output DAC
SUPPLY: 2.7V to 5.5V
Settling Time: 4 us
INL: ±1 LSB
""",
        inline_spec="type=dac bits=12 inl<2lsb",
        keywords=("dac", "digital to analog", "voltage output dac", "rs2200"),
    ),
    ProductType(
        id="controller",
        label="Controller / PMIC",
        family="System",
        topology=None,
        status="planned",
        part="RS5000",
        sample="""RS5000 Power Management Controller
Input: 3.0V to 5.5V
Buck + LDO rails, I2C config
Quiescent: 12 uA
""",
        inline_spec="type=controller iq<20uA",
        keywords=("pmic", "power management", "controller", "buck controller", "rs5000"),
    ),
    ProductType(
        id="lcd_controller",
        label="LCD Controller",
        family="System",
        topology=None,
        status="planned",
        part="RS8800",
        sample="""RS8800 Segment LCD Driver
SUPPLY: 2.5V to 5.5V
COM/SEG mux, 4x40 segments
Bias: 1/3
""",
        inline_spec="type=lcd_controller segments=160",
        keywords=("lcd controller", "lcd driver", "segment driver", "rs8800"),
    ),
    ProductType(
        id="analog_multiplier",
        label="Analog Multiplier",
        family="Compute",
        topology="multiplier",
        status="partial",
        part="RS7001",
        sample="""RS7001 Four-Quadrant Analog Multiplier (Gilbert Cell)
SUPPLY VS=5V
Transfer Function: Vout proportional to Vx * Vy
Gain Error: < 15 %
Bandwidth: 1 MHz
Quiescent Current: 150 uA
Output Swing: 0.5 V differential
Use: mixers, analog MAC tiles, control loops — direct product without digital multiply chain
""",
        inline_spec=MULTIPLIER_EXPERIMENTAL_SPEC,
        keywords=("multiplier", "gilbert", "analog multiply", "four quadrant", "rs7001", "mixer"),
    ),
    ProductType(
        id="analog_mac",
        label="Vector-Matrix MAC",
        family="Compute",
        topology=None,
        status="planned",
        part="RS7100",
        sample="""RS7100 Analog MAC Crossbar Tile
SUPPLY VS=5V
8x8 Gilbert-cell crossbar
Direct dot-product on output bus — no intermediate digital multiplies
Target: edge inference, sensor fusion, analog AI accelerator
""",
        inline_spec="type=multiplier gain_err<10% bw>5MHz",
        keywords=("mac", "matrix multiply", "crossbar", "analog ai", "rs7100", "dot product"),
    ),
    ProductType(
        id="analog_compute_tile",
        label="Analog Compute Tile",
        family="Compute",
        topology=None,
        status="planned",
        part="RS7200",
        sample="""RS7200 Analog Compute Tile
SUPPLY VS=5V
16x16 multiply-accumulate array
In-memory analog compute — final product emerges on shared output line
Replaces digital MAC pipeline for moderate-precision workloads
""",
        inline_spec="type=multiplier gain_err<8% bw>10MHz iq<500uA",
        keywords=("analog compute", "in-memory", "mac array", "rs7200", "analog digital"),
    ),
]

_BY_ID: dict[str, ProductType] = {p.id: p for p in PRODUCT_LINE}


def list_products(*, family: str | None = None) -> list[ProductType]:
    if family:
        return [p for p in PRODUCT_LINE if p.family == family]
    return list(PRODUCT_LINE)


def get_product(product_id: str) -> ProductType | None:
    return _BY_ID.get(product_id)


def resolve_product(
    *,
    product_id: str | None = None,
    category: str | None = None,
    text: str | None = None,
) -> ProductType | None:
    """Pick the best product type from explicit id, topology category, or text."""
    if product_id:
        p = get_product(product_id)
        if p:
            return p
    if category:
        cat = category.lower().replace("-", "_")
        for p in PRODUCT_LINE:
            if p.id == cat or p.topology == cat:
                return p
    if text:
        lower = text.lower()
        best: ProductType | None = None
        best_score = 0
        for p in PRODUCT_LINE:
            score = sum(len(kw) for kw in p.keywords if kw in lower)
            if score > best_score:
                best_score = score
                best = p
        if best_score > 0:
            return best
    return None


def product_line_payload() -> dict[str, Any]:
    families: dict[str, list[dict[str, Any]]] = {}
    for p in PRODUCT_LINE:
        families.setdefault(p.family, []).append(p.to_dict())
    return {
        "products": [p.to_dict() for p in PRODUCT_LINE],
        "families": families,
        "designable_count": sum(1 for p in PRODUCT_LINE if p.topology and p.status != "planned"),
        "planned_count": sum(1 for p in PRODUCT_LINE if p.status == "planned"),
    }
