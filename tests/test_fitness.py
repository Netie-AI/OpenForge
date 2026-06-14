from openanalog.forge.fitness import score_fitness
from openanalog.forge.simulator import SimResult


def test_tia_winner():
    sim = SimResult(ok=True, bw_3db_MHz=2, gain_dB=60, phase_margin=50, power_mW=2)
    r = score_fitness("tia", sim)
    assert r["score"] == 1
    assert not r["failed_checks"]


def test_tia_loser():
    sim = SimResult(ok=True, bw_3db_MHz=0.1, gain_dB=30, phase_margin=10, power_mW=10)
    r = score_fitness("tia", sim)
    assert r["score"] == 0
    assert r["failed_checks"]
