"""Auto-generated coverage: every preset in openanalog.presets gets a test."""

from __future__ import annotations

import pytest

from openanalog.config import resolve_ngspice_cmd
from openanalog.forge.topologies.base import run_ngspice
from openanalog.presets import PRESETS


def _ngspice_ready() -> bool:
    """True when ngspice is installed and can run a minimal deck."""
    if resolve_ngspice_cmd() is None:
        return False
    ok, _ = run_ngspice("* smoke\nV1 a 0 1\nR1 a 0 1k\n.op\n.end\n", timeout=5)
    return ok


pytestmark = pytest.mark.skipif(
    not _ngspice_ready(),
    reason="ngspice not available or not functional",
)


@pytest.mark.parametrize("preset", PRESETS, ids=[p.id for p in PRESETS])
def test_preset_expectation(preset):
    """Each preset must match its documented expect_pass on ngspice."""
    from openanalog.interface.designer import verify_preset

    out = verify_preset(preset.id)
    assert out["passed"], (
        f"{preset.id}: expected meets_all={preset.expect_pass}, "
        f"got meets_all={out['meets_all']}"
    )
