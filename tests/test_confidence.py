from openanalog.confidence import decide, should_write_kg_seed, ConfidenceAction


def test_thresholds():
    assert decide(0.95).action == ConfidenceAction.AUTO_ACCEPT
    assert decide(0.8).action == ConfidenceAction.AUTO_ACCEPT_REVIEW
    assert decide(0.6).needs_claude
    assert decide(0.3).action == ConfidenceAction.REJECT


def test_kg_write():
    assert should_write_kg_seed(0.85, True)
    assert not should_write_kg_seed(0.4, True)
    assert not should_write_kg_seed(0.9, False)
