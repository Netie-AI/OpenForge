from openanalog.interface.datasheet import (
    detect_category,
    extract_comparator_specs_regex,
    extract_opamp_specs_regex,
    parse_inline_spec,
)

RS321 = """1.1MHz Rail-to-Rail CMOS Op-Amp
GBP Gain-Bandwidth Product 1.1 MHz
SR Slew Rate 0.5 V/us
PM Phase Margin 64 deg
AOL Open-Loop Voltage Gain RL=10K 95 100 dB
IQ Quiescent Current Per Amplifier 60 80 uA
CMRR Common-Mode Rejection Ratio 80 dB
"""

COMPARATOR = """RS8901 Comparator
Propagation Delay 0.8 us
Input Offset Voltage 2.5 mV
Quiescent Current 0.5 uA
"""


def test_extract_rs321():
    spec = extract_opamp_specs_regex(RS321)
    t = spec["targets"]
    assert spec["circuit_type"] == "opamp"
    assert abs(t["gbp_MHz"]["value"] - 1.1) < 1e-6
    assert t["gbp_MHz"]["mode"] == "target"
    assert t["slew_Vus"]["value"] == 0.5
    assert t["iq_uA"]["mode"] == "max"
    assert t["iq_uA"]["value"] == 80.0
    assert t["aol_dB"]["mode"] == "min"
    assert t["aol_dB"]["value"] == 95.0


def test_parse_inline_opamp():
    spec = parse_inline_spec("gbp=1.1MHz pm>60 aol>95dB iq<80uA slew>0.5")
    t = spec["targets"]
    assert spec["circuit_type"] == "opamp"
    assert t["gbp_MHz"]["value"] == 1.1
    assert t["pm_deg"]["mode"] == "min"
    assert t["iq_uA"]["mode"] == "max"
    assert t["aol_dB"]["value"] == 95.0


def test_detect_category_comparator():
    assert detect_category(COMPARATOR) == "comparator"
    assert detect_category("type=charge_pump vout=5V") == "charge_pump"


def test_parse_inline_comparator():
    spec = parse_inline_spec("type=comparator tp<1us vos<3mV iq<1uA")
    assert spec["circuit_type"] == "comparator"
    assert spec["targets"]["tp_us"]["mode"] == "max"
    assert spec["targets"]["vos_mV"]["value"] == 3.0


def test_extract_comparator():
    spec = extract_comparator_specs_regex(COMPARATOR)
    assert spec["circuit_type"] == "comparator"
    assert "tp_us" in spec["targets"]
