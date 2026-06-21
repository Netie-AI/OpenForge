# UI end-to-end checklist (browser — not a report)

**When:** After any change to `openanalog/web/index.html` or web JS.  
**Who:** Human in browser (agent cannot replace this gate).  
**URL:** http://127.0.0.1:8080 (or `python -m openanalog.web` / `python -m openanalog serve`)

---

## Startup

- [ ] Page loads without console errors (F12 → Console)
- [ ] Header shows **OpenForge** + **OpenForge L1** badge
- [yes ] **Product type chips** appear (not stuck on “Loading product types…”)
- [yes ] **Applications** section loads (not stuck on “Loading…”)
- [ ] **Achievable ranges** section loads
- [ ] Footer shows PDK + ngspice status + git hash

---

## Product selection

- [yes ] Click **Op-Amp** (or RS321 product chip) — chip highlights active
- [yes ] Specification textarea fills with sample text
- [ yes] Click a **use-case card** — spec/budget update

---

## Design flow

- [ yes] Click **Design Chip** with default op-amp spec
- [ yes] Status line shows progress then “Design complete” (or clear error)
- [ yes] Result pane appears (empty state hidden)
- [ ] Status banner shows category/topology (not stuck ERROR)
- [ ] **Metrics** row shows numbers or explicit “not simulated”
- [ ] **Schematic** tab shows SVG (not blank)
- [ ] Wires visible; IN+/IN−/OUT labels not overlapping device bodies
- [ ] **Netlist** tab has SPICE text
- [ ] **Copy SVG** works

---

## Regression traps (this session)

- [ ] No infinite “Loading…” — if yes, check `index.html` script for syntax/orphan blocks (`node --check` on extracted script)
- [ ] `loadMeta()` completes — `/api/meta` and `/api/health` return 200 in Network tab

---

## Optional

- [ ] Comparator product → Design Chip → schematic renders
- [ ] Planned product (if any) disables Design Chip with message

---

## Pass criteria

**Pass** = all Startup + Product selection + Design flow items checked.  
**Fail** = stop; fix UI before schematic/verifier work. Do not trust pytest alone.
