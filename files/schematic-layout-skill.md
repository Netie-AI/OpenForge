# Schematic layout skill: avoiding wire tangling

Read this before touching `openanalog/eda/schematic_layout.py` or
`openanalog/eda/schematic_geometry.py`. It exists because the first version
of the role-based floorplan (Phase 0.6/0.7) shipped a `two_stage_miller_opamp`
render where a single wire cut diagonally across the entire schematic,
through unrelated devices — see the original bug report screenshot. This
doc captures *why* that happened and the rules that stop it from happening
again silently.

## The one-sentence version

**Tangling is a placement bug wearing a routing costume.** A wire that
crosses half the schematic isn't badly drawn — it's connecting two devices
that shouldn't have been placed that far apart. Fix where things go before
trying to fix how wires get drawn between them.

## What actually went wrong (verified, not guessed)

The op-amp's `nb` bias net ties together M8 (diode-connected bias), M5
(tail current source), and M7 (stage-2 current sink). The floorplan placed
these three devices in three different, far-apart zones (bottom-left,
middle, top-right). The router had no way to draw that net without a wire
spanning nearly the full canvas — and that wire is what sliced through the
Miller cap and the input pair in the original screenshot.

Confirmed with a synthetic reproduction before touching the real code
(see `schematic_geometry.py` checks): routing the *same* bad placement more
cleverly only moved the tangle around. Moving the device into the bias
column removed it outright. **Placement, then routing — not routing
instead of placement.**

This is not a novel idea — it's the two pillars cited in the academic
lineage behind ALIGN (the one serious open-source analog-layout project):
symmetry-based placement, and net-crossing-minimized routing. Worth
internalizing: even the schematic-capture tool already in our SKY130-aligned
flow (Xschem, via the efabless recommended flow) has **no auto-layout at
all** — every placement decision a human EDA tool ships today is manual.
There is no off-the-shelf "good schematic layout" library to import; the
realistic path is a small, scored search scoped to our own fixed topology
library, not adopting a GDSII-layout engine built for a different problem.

## Rules

1. **A crossing is only OK if it's one of three things**: same net touching
   itself, a declared junction dot (real 3+-way tie), or two rail segments
   riding alongside each other. Everything else is a bug, full stop —
   `schematic_geometry.find_bad_crossings` is the literal definition, not a
   approximation of one.

2. **A wire through a device body is worse than a wire-wire crossing.**
   `score_layout` weights `wire-through-device` 3x a plain crossing for
   exactly this reason — it reads as "this wire touches this transistor,"
   which is a stronger wrong signal than two unrelated wires overlapping.

3. **Nets with 3+ points spanning more than ~150px get a bus, not a star.**
   Centroid-star routing (every point connects to one synthetic midpoint)
   is fine for 2-3 nearby pins. For a net whose points are scattered across
   the canvas, the centroid is usually nowhere near any of the actual
   devices, and the long arms it draws to reach far points are exactly the
   tangling pattern from the original bug.

4. **A bus's spine position has to be searched, not assumed.** The median
   x of the tap points seems like the "obvious" choice and is wrong in
   practice — it tends to land the spine in the middle of the active
   circuit instead of along an edge, because the devices a shared bias net
   bridges are usually placed on either side of the signal path, not
   clustered together. Every tap's own x is a candidate; pick whichever
   crosses the least.

5. **Search jointly when more than one bus exists, never greedily.**
   Routing the widest-span net first because the canvas is "emptiest" then
   sounds reasonable and is wrong: that net sees zero conflicts (nothing's
   routed yet) and grabs the cheapest position regardless of what it then
   blocks for the next net. Verified failing in practice during this fix —
   see `route_all_nets`'s docstring for the reproduction. Enumerate
   candidate spines per wide net and score every *combination* together.

6. **Placement variants get scored, not hand-picked.** `_STAGE2_VARIANTS`
   in `schematic_layout.py` is a small, named, growable set of placement
   options for the op-amp's stage-2 devices. `build_schematic_layout` scores
   each with the real netlist's terminal positions and keeps the lowest. Log
   the winner and its score — a layout decision that isn't visible in logs
   isn't reviewable.

7. **Mirroring is a placement tool, not a default.** The existing diff-pair
   mirror (`M2`, `M4` flipped horizontally so the differential structure
   reads symmetrically) is correct and should stay. The instinct to "try
   flipping things" is right — the lesson here is to make that instinct a
   scored search instead of a single hardcoded flip, so it generalizes to
   the next topology instead of needing a new hand-tuned case each time.

## Known remaining gap (as of this patch)

`crossing_score` for `two_stage_miller_opamp` dropped from a cross-canvas
multi-net tangle to **3**, all three localized at the Miller cap: `Cc`'s two
leads sit close to both `vout` and `nout1`'s other star-routed points, and
the centroids of those two nets land close enough together that their stub
geometry briefly overlaps right where the cap is. This is a different,
smaller-scope problem than the original bug — it doesn't span the canvas,
it's two parallel wires nearly touching over a ~10px span next to the
component that's *supposed* to bridge them.

Likely real fix (not yet implemented): treat 2-terminal passives that sit
between two already-routed nets as **taps onto the existing route** (drop a
perpendicular stub from the cap lead to the nearest point on the net's
already-computed path) rather than as ordinary points that get folded into
a fresh centroid calculation alongside far-away transistor drains. That's a
genuine architecture change (routing passives in a second pass, after the
active devices' nets are fixed) — scope it as its own ticket, don't bolt it
onto this one.

## Verification

```bash
pytest tests/test_schematic_no_tangling.py -v
```

`crossing_score == 0` is the target for every floorplan-defined topology.
Until then, the regression test asserts `<=` the current measured baseline
— tighten that bound when the Miller-cap gap above gets fixed, never loosen
it to make a test pass.
