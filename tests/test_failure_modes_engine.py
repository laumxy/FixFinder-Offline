from __future__ import annotations

from ai_engine.failure_modes_engine import FailureModesEngine


def test_no_power():
    eng = FailureModesEngine()
    modes = eng.identify_failure_modes("outlet dead no power")
    assert modes, "expected at least one failure mode"
    assert modes[0]["code"] == "NO_POWER"


def test_overheating():
    eng = FailureModesEngine()
    modes = eng.identify_failure_modes("laptop overheating shuts down, fan loud")
    assert modes
    assert modes[0]["code"] in ("OVERHEATING",)


def test_leak():
    eng = FailureModesEngine()
    modes = eng.identify_failure_modes("rv water pump leaking and dripping")
    assert modes
    assert any(m["code"] == "LEAK" for m in modes)


def test_short_circuit():
    eng = FailureModesEngine()
    modes = eng.identify_failure_modes("sparks and tripping breaker")
    assert modes
    assert any(m["code"] == "SHORT_CIRCUIT" for m in modes)


def test_top_k_ordering():
    eng = FailureModesEngine()
    modes = eng.identify_failure_modes(
        "device dead and won't turn on; also no cooling; sometimes it cuts out"
        , top_k=3,
    )
    assert len(modes) <= 3
    codes = [m["code"] for m in modes]
    assert "NO_POWER" in codes

