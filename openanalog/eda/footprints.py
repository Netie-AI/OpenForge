"""
openanalog/eda/footprints.py

Map OpenForge designs to open KiCad standard library symbol/footprint names
and emit a minimal .kicad_sym stub for schematic drop-in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Open KiCad standard library references (names only — libraries are free/open)
_SYMBOL_MAP: dict[str, dict[str, str]] = {
    "opamp": {
        "default": "Amplifier_Operational:LM358",
        "SOT23-5": "Amplifier_Operational:LMV321",
        "SOIC-8": "Amplifier_Operational:LM358",
    },
    "comparator": {
        "default": "Comparator:LM393",
        "SOT23-5": "Comparator:LMV331",
        "SOIC-8": "Comparator:LM393",
    },
    "switch": {
        "default": "Switch:ADG714",
        "SOT23-6": "Switch:TS5A3159",
        "SOIC-8": "Switch:ADG714",
    },
    "charge_pump": {
        "default": "Power_Management:LM2664",
        "SOIC-8": "Power_Management:LM2664",
        "SOT23-6": "Power_Management:TPS60400",
    },
    "vref": {
        "default": "Reference_Voltage:REF3030",
        "SOT23-5": "Reference_Voltage:REF3030",
        "SOIC-8": "Reference_Voltage:REF3030",
    },
}

_FOOTPRINT_MAP: dict[str, dict[str, str]] = {
    "SOT23-5": "Package_TO_SOT_SMD:SOT-23-5",
    "SOT23-6": "Package_TO_SOT_SMD:SOT-23-6",
    "SOIC-8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "default": "Package_TO_SOT_SMD:SOT-23-5",
}


def kicad_symbol_name(circuit_type: str, package: str) -> str:
    m = _SYMBOL_MAP.get(circuit_type, _SYMBOL_MAP["opamp"])
    return m.get(package, m["default"])


def kicad_footprint_name(package: str) -> str:
    return _FOOTPRINT_MAP.get(package, _FOOTPRINT_MAP["default"])


def emit_kicad_sym_stub(
    *,
    design_id: str,
    circuit_type: str,
    symbol_lib_id: str,
    pins: list[str] | None = None,
) -> str:
    """Minimal KiCad v6+ symbol stub referencing open library naming."""
    pins = pins or ["IN+", "IN-", "OUT", "VCC", "GND"]
    pin_lines = "\n".join(
        f'    (pin passive line (at 0 {-10 - i * 2.54} 0) (length 2.54)\n'
        f'      (name "{name}" (effects (font (size 1.27 1.27))))\n'
        f'      (number "{i + 1}" (effects (font (size 1.27 1.27)))))\n'
        for i, name in enumerate(pins)
    )
    return f"""(kicad_symbol_lib (version 20211014) (generator openforge)
  (symbol "{design_id}" (in_bom yes) (on_board yes)
    (property "Reference" "U" (at 0 0 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{design_id}" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "ki_keywords" "openforge {circuit_type}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "ki_fp_filters" "{symbol_lib_id}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "{design_id}_0_1"
      (rectangle (start -5.08 5.08) (end 5.08 -5.08) (stroke (width 0.254) (type default)))
{pin_lines}
    )
  )
)
"""


def attach_eda_metadata(result: dict[str, Any], *, out_dir: Path | None = None) -> dict[str, Any]:
    """Add KiCad symbol/footprint association to a design result dict."""
    circuit_type = result.get("category") or result["spec"].get("circuit_type", "opamp")
    package = result.get("package", "SOT23-5")
    design_id = f"OF_{circuit_type}_{result['spec'].get('part', 'design').replace('/', '_')}"
    sym = kicad_symbol_name(circuit_type, package)
    fp = kicad_footprint_name(package)
    eda = {
        "design_id": design_id,
        "kicad_symbol": sym,
        "kicad_footprint": fp,
        "package": package,
        "library": "KiCad standard (open)",
    }
    result["eda"] = eda
    stub = emit_kicad_sym_stub(design_id=design_id, circuit_type=circuit_type, symbol_lib_id=sym)
    result["kicad_sym_stub"] = stub
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{design_id}_symbol.json").write_text(json.dumps(eda, indent=2), encoding="utf-8")
        (out_dir / f"{design_id}.kicad_sym").write_text(stub, encoding="utf-8")
    return result
