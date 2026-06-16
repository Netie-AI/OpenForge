"""Offline tests for netlist LLM harness (no API calls)."""

from openanalog.netlist_llm import _extract_netlist, _ensure_models


def test_extract_netlist_strips_markdown():
    raw = """Here is the netlist:
```spice
* OpenForge opamp
.model nmos_ana nmos (level=1)
M1 d g s 0 nmos_ana W=1u L=0.5u
.end
```
"""
    nl = _extract_netlist(raw)
    assert "* OpenForge opamp" in nl
    assert ".end" in nl
    assert "```" not in nl


def test_ensure_models_prepends_bundled():
    nl = "M1 d g s 0 nmos_ana W=1u L=0.5u\n.end\n"
    out = _ensure_models(nl)
    assert ".model nmos_ana" in out
    assert out.index(".model") < out.index("M1")
