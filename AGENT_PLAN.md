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

**Exit criteria:** repo pushes clean to GitHub, CI runs tests on push,
`docs/STATUS.md` reflects reality (op-amp = working; the other four = broken).

---

## Phase 1 — Make all categories actually converge (THE GATE)

Nothing downstream matters until this is done. Today only the op-amp produces
real fitness=1. The other four report `n/a` or garbage. Fix them one at a time;
**do not move to the next until the current one produces a real ngspice-validated
fitness=1 design and has a behavioral test.**

### 1a. vref (start here — cleanest failure)
- Symptom: outputs **0.701 V** (≈ one Vto) instead of 1.2 V; line_reg 2031 mV.
- Diagnosis: the beta-multiplier reference never starts up; the node sits at one
  threshold. This is a startup/operating-point problem.
- [ ] Dump the DC operating point (`.op`) and inspect every node voltage.
- [ ] Identify why the reference branch is degenerate (likely no startup path, or
      the mirror/PTAT branch isn't biased).
- [ ] Fix the topology/bench so a real 1.2 V appears in ngspice.
- [ ] Behavioral test asserts measured vref ∈ [1.15, 1.25] V from a real run.

### 1b. comparator
- Symptom: Vos measured **2498 mV** vs 3 mV target — the bench is measuring a
  degenerate point; the comparator isn't switching.
- [ ] Verify the diff pair actually trips: sweep vinp around vinn, confirm output
      swings rail-to-rail.
- [ ] Fix the offset measurement so it measures real input-referred offset, not a
      stuck node.
- [ ] Behavioral test asserts the output switches and Vos is in the mV range.

### 1c. charge_pump
- Symptom: returns `n/a` for vout/ripple. **Known concrete bug:** the generated
  netlist defines `C0` twice —
  `C0 n0 n1 ...` and `C0 n0 vdd ...`. Duplicate instance name. ngspice will error
  or silently clobber one. The second pumping cap must have a unique name.
- [ ] Fix duplicate device names in the Dickson netlist generator.
- [ ] Verify the clock-coupled pumping actually charges the output node.
- [ ] Behavioral test asserts vout ≈ target and ripple is measured (not n/a).

### 1d. analog_switch
- Symptom: ron/bw return `n/a` — the bench isn't producing measurements.
- [ ] Implement the RON measurement (DC: drive sig, measure V/I across the gate).
- [ ] Implement the −3dB bandwidth measurement (AC sweep through the on-gate).
- [ ] Behavioral test asserts RON and BW are real numbers in range.

**Phase 1 exit criteria:** `make smoke` produces a real fitness=1 design for ALL
five categories, each backed by a behavioral test. `docs/STATUS.md` shows five
`working`. This is the milestone that's been blocked for weeks — clear it before
touching anything below.

---

## Phase 2 — Seed parser (unlock the dead data)

~990 of 1,010 seeds use AnalogGenie/Masala parenthesis syntax
(`M0 (net4 VSS VSS) nmos4`) that ngspice can't parse, so 98% of the corpus is
inert.

- [ ] Build a converter from the parenthesis dialect to ngspice-flat syntax, OR an
      alternate parser path. Pick whichever is more robust; document the choice.
- [ ] Add a pre-simulation validation gate: detect incompatible syntax and skip
      with a warning rather than failing silently and wasting compute.
- [ ] Report: how many of the 1,010 seeds now parse and simulate.

**Exit criteria:** a measured, reported fraction of the seed corpus now feeds the
forge instead of dying on parse.

---

## Phase 3 — Real PDK (silicon-plausible numbers) [gated on Phase 1]

The bundled level-1 models are toys. No one trusts a number that didn't come from
a real process.

- [ ] Integrate SKY130 via volare with a **pinned** version (document the pin).
- [ ] Add a config switch: bundled-models (fast/dev) vs SKY130 (silicon-plausible).
- [ ] Re-validate every category on SKY130. Expect breakage — that's the point;
      log what was an artifact of fake models.

**Exit criteria:** every category produces silicon-plausible results on SKY130,
re-validated and logged.

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
reliably minting fitness=1 designs across categories.

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
2. **Check against acceptance criteria** — measured value in range from a real run.
3. **Update `docs/STATUS.md`** honestly.
4. **Commit** with `phaseN: <task>`.
5. If it fails, **say so in the commit/PR notes** and leave the status `broken` —
   never mark it working to close the task.
