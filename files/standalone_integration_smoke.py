import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_layout import build_schematic_layout, render_schematic_svg

# Transcribed directly from the user's pasted two_stage_miller_opamp deck.
devices = [
    SpiceDevice("M8", "M", ["nb", "nb", "0", "0"]),
    SpiceDevice("M5", "M", ["tail", "nb", "0", "0"]),
    SpiceDevice("M7", "M", ["vout", "nb", "0", "0"]),
    SpiceDevice("M1", "M", ["n1", "vinp", "tail", "0"]),
    SpiceDevice("M2", "M", ["nout1", "vinn", "tail", "0"]),
    SpiceDevice("M3", "M", ["n1", "n1", "vdd", "vdd"]),
    SpiceDevice("M4", "M", ["nout1", "n1", "vdd", "vdd"]),
    SpiceDevice("M6", "M", ["vout", "nout1", "vdd", "vdd"]),
    SpiceDevice("Cc", "C", ["vout", "nout1"]),
]

result = {"topology": "two_stage_miller_opamp"}

layout = build_schematic_layout(devices, result)
print()
print(f"chosen variant:   {layout.variant}")
print(f"crossing_score:   {layout.crossing_score}")
print(f"placed devices:   {sorted(pd.dev.name for pd in layout.placed)}")
print(f"canvas size:      {layout.width}x{layout.height}")

# The fix verified here: the cross-canvas `nb` bias-net tangle (the one
# visible in the original screenshot, where a single wire cut across the
# whole schematic) is gone. What's left is a much smaller, LOCAL issue
# right at the Miller cap (Cc's two leads sit close to both vout and
# nout1's other star-routed points, and the centroids briefly touch).
# That's a different, smaller, separately-scoped problem — see
# docs/schematic-layout-skill.md "Known remaining gap".
assert layout.variant == "isolated", f"unexpected variant winner: {layout.variant}"
assert layout.crossing_score <= 3, (
    f"regression: crossing_score={layout.crossing_score}, expected <=3 "
    "(the Miller-cap-local residual, not the cross-canvas bias tangle)"
)
assert {pd.dev.name for pd in layout.placed} == {d.name for d in devices}, "every device should be placed"

svg = render_schematic_svg(devices, result)
assert svg.startswith("<svg")
assert "two_stage_miller_opamp" in svg
print(f"SVG rendered:     {len(svg)} chars, well-formed start tag OK")
print("\nIntegration smoke test PASSED")
