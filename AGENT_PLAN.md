# OpenForge — Agent Execution Plan

This is the working plan for an AI agent (Cursor) operating on the OpenForge
repo. Work top to bottom. **Do not skip ahead to a later phase until the
current phase's exit criteria are green.** Later phases are deliberately
under-specified — they get refined once their gate clears, so the agent does
not sprint into premature work (especially training).

---

## 0. Operating rules (read every session)

These rules exist because the project has a specific failure mode: *tests pass
while the actual circuits fail in ngspice.* Do not reproduce it.

1. **ngspice is ground truth, not pytest.** A category is "working" only when a
   real ngspice run produces the measured spec. A passing unit test that only
   checks scoring logic is NOT evidence the circuit works.
2. **Every category must have a behavioral test** that asserts the *measured*
   value from a real (or recorded golden) ngspice run is within range — not
   just that the scorer returns a number.
3. **Only fitness=1 data is ever written to the training corpus.** No partial,
   no "close enough." This is the project's core differentiator. Never relax it.
4. **No proprietary or leaked designs, symbols, or footprints.** Open sources
   only: SKY130 PDK, open datasets (AnalogGenie, Masala-CHAI, spice-datasets),
   KiCad standard libraries, and spec numbers extracted from datasheets the user
   legally holds. Specs (GBW, Vos, Iq, RON) are facts and are fine; copied
   netlists/schematics are not.
5. **No secrets in commits.** Never commit `.env`, keys, or credentials.
6. **Report honestly.** If a category is broken, say it is broken. Do not write
   a celebratory summary that contradicts the actual run output.
7. **Small commits, one task per commit**, message format: `phaseN: <task>`.
8. **The fitness bar is the datasheet bar.** `make smoke`, `docs/STATUS.md`, and
   the training gate all use the RS-series envelopes in
   `openanalog/forge/spec_envelopes.py`. Never add a second, looser dev profile
   that lets `meets_all=True` mask weak silicon. Target-mode specs use 5% pass
   tolerance in `score_design` (not 30% dev slack). A red STATUS that is true
   beats a green one that lies.

### Session note (read first, every session)

1. Check `docs/STATUS.md`. If Phase 0 item **0.4** (ngspice reachability) isn't
   marked done, do that first — Phase 1 work is unverifiable without it (you'd be
   staring at `NOT_SIMULATED` no matter what you change in the bench code).
2. Once 0.4 is green, go straight to **Phase 1a (comparator)** per this plan.
   Work one category at a time, in order: comparator → analog_switch →
   charge_pump → opamp. Do not start Phase 2 or 3 until all four show `working`
   in `docs/STATUS.md` against `spec_envelopes.py` (not a softened dev profile).
3. Do not touch Phase 5 / LoRA / training unless explicitly asked. The
   bitsandbytes import-order fix is already applied — confirm `diag_train.py`
   ends in `DIAG OK` once, then leave that track alone.
4. Every task still follows the verify/check/improve loop: run it for real against
   ngspice, check against the RS-series envelope, update `docs/STATUS.md`
   honestly, commit as `phaseN: <task>`, and if it fails, say so — never mark
   working to close a task.

---

## Phase 0 — Repo hygiene & CI (do first, ~1 day)

**Goal:** the repo is versioned, secret-free, and has automated verification so
"green vs red silicon" can't hide again.

- [ ] Confirm `.gitignore` excludes venvs, secrets, large datasets, generated output.
- [ ] Add a `Makefile` (or `tasks.md`) with: `make test`, `make smoke` (runs one
      ngspice design per category), `make lint`.
- [ ] Add a GitHub Actions workflow that runs `pytest` on push. (ngspice smoke can
      stay local/WSL for now — note that in the workflow comments.)
- [ ] Add `docs/STATUS.md` — a living, honest table of every category and its
      real state: `working / partial / broken / not-started`, updated each phase.

### 0.4 — ngspice reachability from the running server (NEW — do before Phase 1)

**Goal:** the server process answers `GET /api/health` with
`ngspice_available: true`, and a `POST /api/design` call actually produces a
real measured value (even if it fails the datasheet bar — that's Phase 1's
problem, not this item's).

**Constraint:** keep the existing split-environment architecture
(`.venv_wsl` for simulation, `.venv_train` for the web server / GPU work).
Do not collapse them into one environment — that was a deliberate decision
from the machine migration, not an accident to undo.

Recommended approach — call into WSL2 from the Windows-hosted server:

- [ ] In the sim-invocation code path (wherever `simulator.py` currently
      shells out to `ngspice`), detect host OS. On native Windows, invoke
      ngspice via `wsl.exe` rather than a bare subprocess call:
      `wsl.exe -d Ubuntu -e ngspice -b <netlist_path>` (or equivalent for however the
      sim harness currently calls it — same flags, just routed through
      `wsl.exe`).
- [ ] Netlist files must be written somewhere both sides can see. Use the
      `/mnt/c/...` path translation (Windows `C:\Users\user\OpenForge\...`
      ↔ WSL `/mnt/c/Users/user/OpenForge/...`) rather than copying files
      back and forth — confirm the project directory is actually mountable
      from WSL2 (default distro may be docker-desktop with `/mnt/host/c/` —
      use `OPENFORGE_WSL_DISTRO=Ubuntu` explicitly).
- [ ] Update `/api/health` to actually attempt a trivial ngspice invocation
      (not just check a binary exists on PATH) and report the real result.
- [ ] One round-trip test: hit `/api/design` for any preset, confirm
      `metrics` in the response has real (non-null) values, even if they
      fail the spec gate.

**Do not, in this step:** fix any circuit so it passes its datasheet bar —
that's Phase 1. This item only proves the pipe between Windows and WSL2
carries a real ngspice run end to end.

**Exit criteria for 0.4:** `/api/health` reports `ngspice_available: true`
on this host, and one `/api/design` call returns real measured metrics
(pass or fail, doesn't matter) instead of `null`.

### 0.5 — Netlist/schematic rendering (fix before re-verifying 0.4)

**Symptom:** devices table shows real W/L values, but Netlist tab shows line
numbers with no SPICE content; Schematic tab shows a single OPAMP block with
no transistor-level connectivity.

**Fix (2026-06-17):**
- Frontend: `<pre>` + gutter spans in `openanalog/web/index.html` (table layout
  collapsed the content column); `resolveNetlist()` backfills from API when needed.
- Backend: `openanalog/eda/netlist_graph.py` + `render_svg()` prefers device
  graph over category template symbols.

**Exit criteria for 0.5:** Netlist tab shows readable SPICE deck with line
numbers; Schematic shows M1…Mn connected by wires for opamp + comparator.
Run `pytest tests/test_netlist_schematic.py`.

**Exit criteria:** repo pushes clean to GitHub, CI runs tests on push,
`docs/STATUS.md` reflects reality.

---

## Phase 1 — Make all categories actually converge (THE GATE)

Nothing downstream matters until this is done. Benches now produce real ngspice
measurements for four dev-mode categories, but **most do not pass the RS-series
datasheet bar** in `spec_envelopes.py`. Fix them one at a time; **do not move to
the next until the current one produces a real ngspice-validated fitness=1 design
on the datasheet bar and has a behavioral test.**

**vref is not Phase 1 work.** Real ~1.2 V bandgap needs SKY130 parasitic BJTs
(Phase 3). `make smoke` skips vref; do not fake a divider reference.

### 1a. comparator (start here — bench works, specs don't)
- Symptom: tp ~8 µs vs RS8901 tp<1 µs; iq ~113 µA vs iq<1 µA.
- [ ] Verify the diff pair trips and transient delay reflects real switching.
- [ ] Let the sizer push bias/sizing against the RS8901 envelope.
- [ ] Behavioral test asserts `meets_all` on the datasheet bar from a real run.

### 1b. analog_switch
- Symptom: ron ~1208 Ω vs RS2105 ron<50 Ω; ton/toff still unmeasured.
- [ ] Widen transmission-gate devices / overdrive so RON drops toward 50 Ω.
- [ ] Implement ton/toff transient measurements.
- [ ] Behavioral test asserts RON and BW on the datasheet bar.

### 1c. charge_pump
- Symptom: vout ~4.1 V vs RS2660 vout=5 V (diode drops are real).
- [ ] Fix topology or target interpretation so pumped output meets 5 V bar.
- [ ] Behavioral test asserts vout, ripple, settle on the datasheet bar.

### 1d. opamp (closest — verify on hard bar)
- Bench produces real AOL/GBP/PM/Iq; confirm sizer hits RS321 envelope
  (gbp=1.1MHz pm>60 aol>95dB iq<80uA) not a softened smoke profile.
- [ ] Behavioral test asserts `meets_all` on RS321 targets.

**Phase 1 exit criteria:** `make smoke` produces fitness=1 for all four
dev-mode categories **against `spec_envelopes.py`**, each backed by a behavioral
test. `docs/STATUS.md` shows four `working`. Do **not** start Phase 2 or Phase 3
until this gate is green on the real bar.

---

## Phase 2 — Seed parser (unlock the dead data) [gated on Phase 1]

~990 of 1,010 seeds use AnalogGenie/Masala parenthesis syntax
(`M0 (net4 VSS VSS) nmos4`) that ngspice can't parse, so 98% of the corpus is
inert.

- [x] `openanalog/ingestion/dialect.py` — `detect_dialect()` + breakdown
- [x] `openanalog/ingestion/converter.py` — paren → flat, net normalize, deck prep
- [x] Pre-simulation validation gate in `simulator.py` + `sim/ngspice.check_syntax`
- [x] `data/seeds_normalized.jsonl` with `original_dialect`, `conversion_warnings`
- [x] Corpus report in `docs/STATUS.md` — **768 / 1,010 sim_validated (76%)**

**Exit criteria:** measured fraction feeds forge — **GREEN** (>500 sim-validated).

---

## Phase 3 — Real PDK (silicon-plausible numbers) [gated on Phase 1]

The bundled level-1 models are toys. No one trusts a number that didn't come from
a real process. **Enter Phase 3 when level-1 cannot close the datasheet gap**
(e.g. switch RON still >>50 Ω after sizing) — not on schedule alone.

- [ ] Integrate SKY130 via volare with a **pinned** version (document the pin).
- [ ] Add a config switch: bundled-models (fast/dev) vs SKY130 (silicon-plausible).
- [ ] **vref:** real bandgap on SKY130 parasitic BJTs; no fake 1.2 V divider in dev.
- [ ] Re-validate every category on SKY130. Expect breakage — that's the point;
      log what was an artifact of fake models.

**Exit criteria:** every category (including vref) produces silicon-plausible
results on SKY130, re-validated and logged.

---

## Phase 4 — Evolutionary engine [gated on Phase 3]

The actual novel claim. Today the system *sizes* known topologies. This phase
makes it *generate* them.

- [ ] Implement directed mutation + fitness + pruning on top of the working benches
      (knowledge graph prunes losers, does not archive them — per design principle).
- [ ] Prove the loop can produce a non-trivial topology variant that passes fitness
      and was NOT hand-seeded.

**Exit criteria:** one genuinely novel, ngspice-validated topology the system
invented. The "it's alive" milestone.

---

## Phase 5 — Multitask training prep & finetune [gated on Phase 4 + sufficient fitness=1 data]

This is where the 96GB rig earns its place. Do not start until the forge is
reliably minting fitness=1 designs across categories **on the datasheet bar**.

- [ ] Define a single multitask data schema across ALL categories (prompt/spec →
      validated netlist + measured specs). One model, all categories — not one
      model per category.
- [ ] Build the corpus: fitness=1 designs only, deduplicated, with measured specs.
- [ ] Report corpus size per category. **Do not train until each category has a
      non-trivial count** — a tiny set just memorizes.
- [ ] Finetune Qwen2.5-Coder-7B + LoRA on the multitask corpus.
- [ ] Wire the verifier loop: model output → ngspice → reject if not fitness=1, so
      the model can never ship a broken circuit.

**Exit criteria:** "design me a low-Vos comparator under 1 µA" → a validated
netlist, verifier-gated. This is the demo to show the world.

---

## The verify / check / improve loop (every task, every phase)

For each task the agent completes:
1. **Run it for real** — `make smoke` or the specific ngspice bench, not just pytest.
2. **Check against acceptance criteria** — measured value in range from a real run
   **on the RS-series envelope in `spec_envelopes.py`**.
3. **Update `docs/STATUS.md`** honestly.
4. **Commit** with `phaseN: <task>`.
5. If it fails, **say so in the commit/PR notes** and leave the status `broken` —
   never mark it working to close the task.

Master Plan

1. Until green phase 1
2. do reserch on the repos posted by ceo zero asic
3. do reserarch on
then i press opamp descirption all no chagne still cannto no update reuslt thenchange the ui to be more friendly palatnri design aesthetic, cadence deisgn more ppl can use explore redesign, or assisted, then ca instruc tit to like a a  wire or change the configuration thee will parse thinkn otput a resutl with one more wire or change the configuration to current osoruce or source follower then resutl come out say o now it becoem somehting else like charge pump balbal exmaple, then predict drc lvs current hothen nextly OL
parasitic extraction that do like siemens callibre and cadenc e quantus and cadence 



Next thingbig is everythign is scattered around different ideas, differnt brain
Combine every data, u have in ur thought about semicon

we separate combine group to a right place, ur designs all recycle here
recycle plan.