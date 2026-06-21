"""Standalone sanity checks for schematic_geometry.py — run with `python check.py`.

Not pytest (no repo to integrate with here) — this is the evidence that the
detector itself is correct before it ships into schematic_layout.py.
"""

from schematic_geometry import Segment, find_bad_crossings, score_layout


def check_basic_intersections() -> None:
    h = Segment(0, 10, 20, 10, net="a")
    v = Segment(10, 0, 10, 20, net="b")
    crossings = find_bad_crossings([h, v], junctions=set())
    assert len(crossings) == 1, crossings
    assert crossings[0].point == (10.0, 10.0)

    # same crossing, but declared as a junction dot -> not bad
    crossings = find_bad_crossings([h, v], junctions={(10, 10)})
    assert crossings == [], crossings

    # same net never flags, even with no junction
    h2 = Segment(0, 10, 20, 10, net="a")
    v2 = Segment(10, 0, 10, 20, net="a")
    assert find_bad_crossings([h2, v2], junctions=set()) == []

    print("check_basic_intersections: OK")


def check_parallel_rails_excused() -> None:
    rail = Segment(0, 0, 500, 0, net="vdd", kind="rail")
    drop = Segment(100, 0, 100, 50, net="vdd", kind="rail")
    assert find_bad_crossings([rail, drop], junctions=set()) == []
    print("check_parallel_rails_excused: OK")


def _centroid_star(points: list[tuple[int, int]], net: str) -> list[Segment]:
    """Reproduce schematic_layout._route_net's current behavior: every point
    in a multi-point net connects to one synthetic centroid via an L-route.
    """
    jx = round(sum(p[0] for p in points) / len(points))
    jy = round(sum(p[1] for p in points) / len(points))
    segs: list[Segment] = []
    for (x, y) in points:
        if x == jx or y == jy:
            segs.append(Segment(x, y, jx, jy, net=net))
        else:
            segs.append(Segment(x, y, jx, y, net=net))
            segs.append(Segment(jx, y, jx, jy, net=net))
    return segs


def _spine_bus(points: list[tuple[int, int]], net: str) -> list[Segment]:
    """Proposed replacement for wide-spanning nets: one vertical bus at the
    median x, each point taps in with a short horizontal stub.
    """
    xs = sorted(p[0] for p in points)
    spine_x = xs[len(xs) // 2]
    ys = [p[1] for p in points]
    segs = [Segment(spine_x, min(ys), spine_x, max(ys), net=net, kind="stub")]
    for (x, y) in points:
        if x != spine_x:
            segs.append(Segment(x, y, spine_x, y, net=net, kind="stub"))
    return segs


def check_bias_net_reproduction() -> None:
    """Reproduces the actual bug: nb net ties M8 (bottom-left), M5
    (mid-center), M7 (top-right) across the whole canvas. An unrelated net
    (M6-drain -> Cc, a vertical riser around x=420) sits in between.

    Three variants, same unrelated riser held fixed:
      1. original placement (M7 far right) + centroid-star routing -> current code
      2. original placement (M7 far right) + spine-bus routing       -> "just reroute it"
      3. moved placement (M7 pulled into the bias column) + spine    -> placement fix
    """
    unrelated = Segment(420, 150, 420, 350, net="vout")

    original_placement = [(170, 420), (250, 330), (480, 210)]  # M8, M5, M7 (far right)
    moved_placement = [(170, 420), (250, 330), (260, 210)]      # M7 pulled into the bias column

    star_score = score_layout(_centroid_star(original_placement, "nb") + [unrelated], junctions=set())
    reroute_only_score = score_layout(_spine_bus(original_placement, "nb") + [unrelated], junctions=set())
    placement_fix_score = score_layout(_spine_bus(moved_placement, "nb") + [unrelated], junctions=set())

    print(f"1. original placement, centroid-star routing (current code): {star_score}")
    print(f"2. original placement, spine-bus routing only:                {reroute_only_score}")
    print(f"3. moved placement (M7 into bias column) + spine-bus:         {placement_fix_score}")

    assert star_score > 0, "expected the star-routed bias net to tangle with the vout run"
    assert reroute_only_score > 0, (
        "rerouting alone, with M7 left in its original far-away column, should NOT "
        "fully fix this — the long arm to M7 still has to cross the vout riser no "
        "matter how it's drawn. This is the point: it's a placement bug, not a "
        "routing-algorithm bug."
    )
    assert placement_fix_score == 0, "moving M7 into the bias column should eliminate the crossing entirely"
    print("check_bias_net_reproduction: OK — confirms placement, not routing, is the actual fix")


def check_wire_through_device() -> None:
    from schematic_geometry import DeviceBox

    box = DeviceBox(name="M7", x=460, y=200, w=36, h=40, terminal_nets=frozenset({"vout", "nb", "0"}))
    foreign = Segment(400, 220, 500, 220, net="cc_route")  # cuts through M7's body
    owned = Segment(400, 220, 500, 220, net="vout")  # same net as a terminal -> fine

    bad = find_bad_crossings([foreign], junctions=set(), device_boxes=[box])
    assert len(bad) == 1 and bad[0].reason.startswith("wire-through-device"), bad

    ok = find_bad_crossings([owned], junctions=set(), device_boxes=[box])
    assert ok == [], ok
    print("check_wire_through_device: OK")


if __name__ == "__main__":
    check_basic_intersections()
    check_parallel_rails_excused()
    check_bias_net_reproduction()
    check_wire_through_device()
    print("\nAll checks passed.")
