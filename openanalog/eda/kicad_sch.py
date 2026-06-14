"""
openanalog/eda/kicad_sch.py

Emit a minimal KiCad 8 schematic (.kicad_sch) for an OpenForge design.
"""

from __future__ import annotations

import uuid
from typing import Any


def _uid() -> str:
    return str(uuid.uuid4())


def emit_kicad_sch(result: dict[str, Any]) -> str:
    eda = result.get("eda") or {}
    design_id = eda.get("design_id", "OF_design")
    sym = eda.get("kicad_symbol", "Amplifier_Operational:LM358")
    lib_id = sym.split(":")[-1] if ":" in sym else sym
    category = result.get("category", "opamp")
    part = result.get("spec", {}).get("part", "design")
    supply = result.get("supply_V", 5.0)

    return f"""(kicad_sch (version 20250114) (generator openforge)

  (uuid {_uid()})
  (paper "A4")
  (title_block
    (title "OpenForge {category}")
    (date "")
    (rev "1")
    (company "OpenForge")
    (comment 1 "{part}")
    (comment 2 "VS={supply}V")
    (comment 3 "{result.get('topology','')}")
  )

  (lib_symbols
    (symbol "Device:R" (power) (pin_names (offset 0.254)) (in_bom yes) (on_board yes)
      (property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
      (symbol "Device:R_0_1"
        (rectangle (start -1.016 2.54) (end 1.016 -2.54) (stroke (width 0.254) (type default)))
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1"))
        (pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2"))
      )
    )
    (symbol "power:+5V" (power) (pin_names (offset 0)) (in_bom yes) (on_board yes)
      (property "Reference" "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "power:+5V_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)))
        (pin power_in line (at 0 0 90) (length 0) (name "+5V" (effects (font (size 1.27 1.27)))) (number "1"))
      )
    )
    (symbol "power:GND" (power) (pin_names (offset 0)) (in_bom yes) (on_board yes)
      (property "Reference "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "power:GND_0_1"
        (polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)))
        (pin power_in line (at 0 0 270) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1"))
      )
    )
  )

  (symbol (lib_id "{sym}") (at 127 101.6 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid {_uid()})
    (property "Reference" "U1" (at 127 88.9 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{design_id}" (at 127 114.3 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{eda.get('kicad_footprint','')}" (at 127 101.6 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "~" (at 127 101.6 0) (effects (font (size 1.27 1.27)) hide))
    (instances
      (project "{design_id}"
        (path "/{_uid()}" (reference "U1") (unit 1))
      )
    )
  )

  (symbol (lib_id "power:+5V") (at 127 63.5 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid {_uid()})
    (property "Reference" "#PWR01" (at 127 67.31 0) (effects (font (size 1.27 1.27)) hide))
    (property "Value" "+5V" (at 127 59.69 0) (effects (font (size 1.27 1.27))))
    (instances (project "{design_id}" (path "/{_uid()}" (reference "#PWR01") (unit 1))))
  )

  (symbol (lib_id "power:GND") (at 127 139.7 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid {_uid()})
    (property "Reference" "#PWR02" (at 127 143.51 0) (effects (font (size 1.27 1.27)) hide))
    (property "Value" "GND" (at 127 135.89 0) (effects (font (size 1.27 1.27))))
    (instances (project "{design_id}" (path "/{_uid()}" (reference "#PWR02") (unit 1))))
  )

  (wire (pts (xy 127 63.5) (xy 127 88.9)) (stroke (width 0) (type default)) (uuid {_uid()}))
  (wire (pts (xy 127 114.3) (xy 127 139.7)) (stroke (width 0) (type default)) (uuid {_uid()}))

  (text "OpenForge netlist-backed design — {lib_id}" (at 50.8 177.8 0)
    (effects (font (size 1.27 1.27)) (justify left bottom))
    (uuid {_uid()})
  )
  (text "meets_all={result.get('meets_all', False)} score={result.get('score', 0)}" (at 50.8 182.88 0)
    (effects (font (size 1.016 1.016)) (justify left bottom))
    (uuid {_uid()})
  )
)
"""
