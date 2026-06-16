# Clone audit — read-only pass (2026-06-16)

Investigation only. No code copied, no `.gitignore` changes, no extraction performed.
Review this before any EXTRACT verdict is acted on.

**OpenForge assumption:** repo stays private/local; corpus and weights are not pushed via git.

---

## AnalogSAGE

**License:** No LICENSE file in clone. Treat as all-rights-reserved.

**What it actually does:** LLM + RAG-style knowledge retrieval (Pinecone) for iterative analog sizing suggestions; topology vector DB for similarity search. PySpice/ngspice-oriented, not OpenForge's forge loop.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `sizing.py` (`askLLM`, `getMySizing`) | Pattern for LLM sizing loops — overlaps Phase 5 API path, not blocks |
| `knowledge.py` (`getKnowledge`) | RAG query decomposition |
| `tolology.py` (`TopologyDatabase`) | Topology embedding retrieval |
| `evalTask.py` | Eval harness pattern |

**Verdict:** REFERENCE-ONLY

---

## Anvil

**License:** GPL-3.0 (`LICENSE.md` — "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007").

**What it actually does:** FreeCAD → STL + OpenFOAM CFD automation (single-run, data gen, Bayesian optimization). Not circuit/SPICE.

**Relevant to OpenForge:** None (wrong domain).

**Verdict:** SKIP

---

## RoSE

**License:** GPL-3.0 (`LICENSE` — GPLv3 header).

**What it actually does:** Bayesian optimization + RL around a Cadence-oriented simulator environment (`gym_tso/envs/RL_env.py`). Parameter search, not netlist emission.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `gym_tso/envs/RL_env.py` | RL env structure — design-loop ideas only |
| `main_train_BORL.py`, `DE_tso_BORL.py` | Training orchestration |

**Verdict:** REFERENCE-ONLY (GPL — do not copy code)

---

## ZeroSim

**License:** No LICENSE file in clone. Treat as all-rights-reserved.

**What it actually does:** Netlist → graph preprocessing + `CircuitTransformer` training for zero-shot analog performance prediction (ICCAD 2025 paper). Dataset on HuggingFace (`Xun49/Amplifer60`).

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `scripts/preprocess_topology.py` (`process_netlist`, pin-node graph) | KG / topology fingerprint schema |
| `model/circuitformer.py` (`CircuitTransformer`) | Graph embedding ideas |
| `circuit_ga/AMP.py` (`AMPEnv`) | Simulation dataset generation pattern |

**Verdict:** REFERENCE-ONLY

---

## spice-completion

**License:** No LICENSE file (only `setup.py` metadata claiming MIT — insufficient). Treat as all-rights-reserved until upstream LICENSE is confirmed.

**What it actually does:** SPICE → graph via PySpice parser; trains KNN/GAT models to predict omitted components ("node actions") for netlist completion.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `spice_completion/datasets/helpers.py` | SPICE→graph encoding (`SpiceParser`, component types) |
| `spice_completion/datasets/omitted.py` (`OmittedDataset`) | Completion task dataset |
| `spice_completion/datasets/graphdata.py` | gSpan graph serialization |
| `train_node_actions.py` | Training entrypoint |

**Verdict:** REFERENCE-ONLY

---

## SymCAD

**License:** GPL-3.0 (`LICENSE` — GPLv3 header).

**What it actually does:** Symbolic CAD/geometry library with FreeCAD integration. Mechanical/parametric parts, not SPICE netlists.

**Relevant to OpenForge:** None (naming overlap with "CAD" only).

**Verdict:** SKIP

---

## GraphGYM

**License:** MIT (`LICENSE` — "Permission is hereby granted, free of charge…").

**What it actually does:** Configurable GNN experiment framework. This fork adds netlist loaders that pipe `spice-completion` graphs into DeepSNAP for classification/link tasks.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `graphgym/contrib/loader/netlists.py` (`load_dataset`, `NetlistOmitted`) | Netlist→training-graph bridge |
| `graphgym/contrib/loader/netlist_proto_links.py` (`NetlistProtoLinks`) | Link-prediction dataset format |
| `run/configs/omitted_classification/*.yaml` | Dataset format config examples |

**Verdict:** EXTRACT (MIT) — but depends on `spice-completion` (no LICENSE in clone); extract loader patterns, not a blind copy of the dependency chain.

---

## symbench-athens-client

**License:** Apache-2.0 (`LICENSE` — "Apache License Version 2.0, January 2004").

**What it actually does:** Python client for Symbench UAV workflows (Jenkins + Gremlin graph DB). Design cloning and component swap operations.

**Relevant to OpenForge:** None (UAV domain, not analog IC).

**Verdict:** SKIP

---

## symbench-studio

**License:** No LICENSE file at repo root. Submodules (`constraint-prog`, `symbench-dataset`, `cp-problems-generator`) declared in `.gitmodules` but uninitialized in this clone — submodule licenses unknown.

**What it actually does:** Streamlit UI running optimization solvers over benchmark problems; stores run history/configs.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `spa.py` | Streamlit orchestration pattern only |

**Verdict:** SKIP

---

## spice-datasets

**License:** GPL-3.0 (`LICENSE.txt` — GPLv3 header).

**What it actually does:** Curated directory tree of LTspice + KiCad-scraped SPICE netlists (`kicad_github/`, `ltspice_demos/`, `ltspice_examples/`). Data corpus, not tooling.

**Relevant to OpenForge:** External seed source for `data/seeds_normalized.jsonl` ingestion — already used indirectly. Do not vendor into git.

**Verdict:** REFERENCE-ONLY (GPL dataset + third-party circuit copyrights in README)

---

## AnalogGenie

**License:** MIT (`LICENSE` — "MIT License, Copyright (c) 2025 XZ Group").

**What it actually does:** SPICE netlist → adjacency/pin-token graphs; decoder-only transformer predicts next device-pin token for topology generation.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `SPICE2GRAPH_full.py` (`read_netlist`, `build_connection_matrix`) | KG topology representation |
| `SPICE2GRAPH_compress.py` | Compressed graph variant |
| `Augmentation.py`, `Stack.py`, `Pretrain.py`, `Inference.py` | Topology generation pipeline |

**Verdict:** EXTRACT (MIT) — graph extraction logic is the highest-value, lowest-risk lift for `openanalog/kg/`.

---

## electric-circuits

**License:** Apache-2.0 (`LICENSE` — Apache-2.0 header).

**What it actually does:** WebGME web app: SPICE import → internal circuit model → export; ML plugins for next-component recommendation.

**Relevant to OpenForge:**

| Path | Relevance |
|------|-----------|
| `src/plugins/ConvertNetlistToCircuit/.../__init__.py` | PySpice-based netlist→structured model |
| `src/plugins/ConvertCircuitToNetlist/.../__init__.py` | Model→netlist export |
| `src/plugins/RecommendNextComponents/.../__init__.py` | Completion-style recommendation |

**Verdict:** EXTRACT (Apache-2.0) — parsing/reference patterns for `netlist_llm.py` repair harness; keep NOTICE if substantial portions copied.

---

## Summary table

| Repo | License | Verdict |
|------|---------|---------|
| AnalogSAGE | None | REFERENCE-ONLY |
| Anvil | GPL-3.0 | SKIP |
| RoSE | GPL-3.0 | REFERENCE-ONLY |
| ZeroSim | None | REFERENCE-ONLY |
| spice-completion | None (claims MIT in setup) | REFERENCE-ONLY |
| SymCAD | GPL-3.0 | SKIP |
| GraphGYM | MIT | EXTRACT |
| symbench-athens-client | Apache-2.0 | SKIP |
| symbench-studio | None | SKIP |
| spice-datasets | GPL-3.0 | REFERENCE-ONLY |
| AnalogGenie | MIT | EXTRACT |
| electric-circuits | Apache-2.0 | EXTRACT |

## Recommended review order (if extraction proceeds)

1. **AnalogGenie** `SPICE2GRAPH_full.py` → `openanalog/kg/` (MIT, clearest win)
2. **electric-circuits** netlist parser patterns → `netlist_llm.py` repair (Apache-2.0)
3. **GraphGYM** netlist loader interface → KG training hooks (MIT, but verify spice-completion dependency chain first)

Do **not** copy from GPL repos (Anvil, RoSE, SymCAD, spice-datasets) into OpenForge without a deliberate license strategy.
