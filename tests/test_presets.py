"""Auto-generated coverage: every preset in openanalog.presets gets a test."""

from __future__ import annotations

import pytest

from openanalog.config import resolve_ngspice_cmd
from openanalog.presets import PRESETS

NGSPICE = resolve_ngspice_cmd() is not None


@pytest.mark.parametrize("preset", PRESETS, ids=[p.id for p in PRESETS])
def test_preset_expectation(preset):
    """Each preset must match its documented expect_pass on ngspice."""
    if not NGSPICE:
        pytest.skip("ngspice not available")
    from openanalog.interface.designer import verify_preset

    out = verify_preset(preset.id)
    assert out["passed"], (
        f"{preset.id}: expected meets_all={preset.expect_pass}, "
        f"got meets_all={out['meets_all']}"
    )
