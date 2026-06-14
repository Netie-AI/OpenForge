from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openanalog.config import TRAINING_DIR, ensure_dirs


class DatasetWriter:
    def __init__(self) -> None:
        ensure_dirs()
        self.winners = TRAINING_DIR / "winners.jsonl"
        self.losers = TRAINING_DIR / "losers.jsonl"

    def write(
        self,
        *,
        fitness: int,
        topology: str,
        netlist: str,
        sim_result: dict[str, Any],
        generation: int,
        topology_id: str,
        pass_margins: dict[str, float],
        instruction: str | None = None,
    ) -> None:
        if fitness == 1:
            path = self.winners
            inst = instruction or (
                f"Design a {topology} in sky130 130nm meeting validated simulation specs."
            )
            record = {
                "instruction": inst,
                "input": "",
                "output": netlist,
                "netlist": netlist,
                "topology": topology,
                "measured_specs": sim_result,
                "sim_result": sim_result,
                "fitness": 1,
                "topology_id": topology_id,
                "generation": generation,
                "pass_margins": pass_margins,
            }
        else:
            path = self.losers
            record = {
                "netlist": netlist,
                "sim_result": sim_result,
                "fitness": 0,
                "topology_id": topology_id,
                "generation": generation,
                "failed": pass_margins,
            }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
