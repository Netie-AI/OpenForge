"""Trace the real op-amp schematic route path and report device-body crossings.

Read-only diagnostic. Uses the same placement+route code path as
render_schematic_svg(). Reports, per signal net, the routed segments and any
segment that passes through a device body box (INCLUDING same-net crossings,
which schematic_geometry.find_bad_crossings currently exempts).
"""

from __future__ import annotations

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_layout import (
    _device_boxes,
    build_schematic_layout,
)
from openanalog.eda.schematic_router import route_nets
from openanalog.eda.symbols import symbol_for_device, terminal_refs


def _opamp_devices() -> list[SpiceDevice]:
    return [
        SpiceDevice("Iref", "I", ["vdd", "nb"]),
        SpiceDevice("M8", "M", ["nb", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M5", "M", ["tail", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M7", "M", ["vout", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M1", "M", ["n1", "vinp", "tail", "0"], model="nmos"),
        SpiceDevice("M2", "M", ["nout1", "vinn", "tail", "0"], model="nmos"),
        SpiceDevice("M3", "M", ["n1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M4", "M", ["nout1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M6", "M", ["vout", "nout1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("Cc", "C", ["vout", "nout1"]),
    ]


def _seg_crosses_body(seg, box, inset: int = 3) -> bool:
    rx0, ry0 = box.x + inset, box.y + inset
    rx1, ry1 = box.x + box.w - inset, box.y + box.h - inset
    if seg.y1 == seg.y2:  # horizontal
        y = seg.y1
        xlo, xhi = sorted((seg.x1, seg.x2))
        return ry0 <= y <= ry1 and max(xlo, rx0) < min(xhi, rx1)
    if seg.x1 == seg.x2:  # vertical
        x = seg.x1
        ylo, yhi = sorted((seg.y1, seg.y2))
        return rx0 <= x <= rx1 and max(ylo, ry0) < min(yhi, ry1)
    return False


def main() -> None:
    devices = _opamp_devices()
    layout = build_schematic_layout(devices, {"topology": "two_stage_miller_opamp"})
    print(f"variant={layout.variant} crossing_score={layout.crossing_score}")
    print("\n== placed devices ==")
    for pd in layout.placed:
        sym = symbol_for_device(pd.dev)
        box_x1 = pd.origin.x + sym.width
        box_y1 = pd.origin.y + sym.height
        print(
            f"  {pd.dev.name:5s} kind={pd.dev.kind} mirror={pd.mirror!s:5s} "
            f"origin=({pd.origin.x},{pd.origin.y}) body=[{pd.origin.x},{box_x1}]x[{pd.origin.y},{box_y1}]"
        )

    routed = route_nets(layout.placed)
    boxes = _device_boxes(layout.placed)

    print("\n== routed segments by net ==")
    by_net: dict[str, list] = {}
    for s in routed.segments:
        by_net.setdefault(s.net, []).append(s)
    for net, segs in sorted(by_net.items()):
        print(f"  net {net}:")
        for s in segs:
            print(f"    ({s.x1},{s.y1})->({s.x2},{s.y2}) kind={s.kind}")

    print("\n== ALL wire/stub segments crossing a device body (incl. same-net) ==")
    found = False
    for s in routed.segments:
        if s.kind not in ("wire", "stub"):
            continue
        for box in boxes:
            if _seg_crosses_body(s, box):
                same = s.net in box.terminal_nets
                tag = "SAME-NET(exempted by scorer)" if same else "FOREIGN(counted)"
                print(
                    f"  seg net={s.net} ({s.x1},{s.y1})->({s.x2},{s.y2}) "
                    f"crosses {box.name} body  [{tag}]"
                )
                found = True
    if not found:
        print("  none")


if __name__ == "__main__":
    main()
