# Software design learnings (OpenForge)

**Purpose:** Capture *how we thought*, not just *what shipped* — so the next session does not re-litigate the same geometry, gate, or agent-handoff traps.

**Sibling folders:**

| Path | Focus |
|------|--------|
| `docs/research/testbench_learnings/` | ngspice benches, PVT metrics, fixture equivalence |
| `docs/research/softwaredesign_learnings/` | Schematic/EDA routing, verification gates, agent orchestration, UI evidence |
| `docs/research/*.md` | Surveys and roadmaps (long-lived references) |

**When to append:** After any session where (1) a visual/geometry claim was disputed and resolved with coordinates, (2) tests and eye disagreed, (3) router vs placement boundary moved, or (4) Claude/Cursor split produced a reusable pattern.

**Format:** One file per incident or theme: `<topic>_<YYYY-MM-DD>.md`. Lead with facts and coordinates; end with verify commands and “do not repeat.”
