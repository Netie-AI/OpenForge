import json

from openanalog.ingestion.seed_loader import _parse_masala_jsonl, _classify_from_description


def test_parse_masala_jsonl():
    line = json.dumps(
        {
            "messages": [
                {"role": "user", "content": "A transimpedance amplifier for photodiodes."},
                {"role": "assistant", "content": "M0 (out in VSS VSS) nmos4\nR1 (in 0) resistor"},
            ]
        }
    )
    parsed = _parse_masala_jsonl(line)
    assert parsed is not None
    desc, netlist = parsed
    assert "transimpedance" in desc.lower()
    assert "nmos4" in netlist


def test_classify_from_description():
    assert _classify_from_description("fully differential operational amplifier") == "diff_amp"
    assert _classify_from_description("transimpedance amplifier TIA") == "tia"
