from __future__ import annotations

from openanalog.forge.generator import MutationMode, mutate_netlist


def directed_mutate(
    parent_netlist: str,
    failed_checks: list[str],
    margins: dict[str, float],
    *,
    stagnant_gens: int = 0,
) -> str:
    mode = MutationMode.DIRECTED
    if stagnant_gens >= 10:
        mode = MutationMode.RANDOM
    return mutate_netlist(
        parent_netlist,
        mode,
        failed_checks=failed_checks,
    )
