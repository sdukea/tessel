from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tessel.rules import Hour, evaluate, is_silent, is_spike, is_stuck

T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def hours(values, rain=0.0, temp=20.0):
    return [Hour(T0 + timedelta(hours=i), v, rain, temp) for i, v in enumerate(values)]


def test_flat_soil_in_a_dry_spell_is_not_a_fault():
    assert not is_stuck(hours([0.21] * 24, rain=0.0))


def test_flat_soil_while_it_rains_is_a_stuck_probe():
    assert is_stuck(hours([0.21] * 12, rain=0.5))           # 6 mm in 12 h and the value never moved
    assert not is_stuck(hours([0.21] * 12, rain=0.5, temp=-3))   # frozen ground: water can't soak in


def test_spike_needs_a_jump_rain_cannot_explain():
    a, b = Hour(T0, 0.20, 0, 20), Hour(T0 + timedelta(hours=1), 0.34, 0.0, 20)
    assert is_spike(a, b)
    assert not is_spike(a, Hour(b.at, 0.34, 12.0, 20))


def test_silent_and_evaluate_order():
    assert is_silent(T0, T0 + timedelta(minutes=16), timedelta(minutes=5))
    assert evaluate(hours([0.2] * 11 + [0.05], rain=0.0), threshold=0.1) == ["dry", "spike"]
    assert evaluate([], 0.1) == []


@pytest.mark.skipif(not Path("data/raw/pune_in.parquet").exists(), reason="download the data first (Day 4)")
def test_false_alarm_rate_on_real_soil():
    import pandas as pd
    df = pd.read_parquet("data/raw/pune_in.parquet").dropna(subset=["soil_moisture_0_to_7cm"])
    hs = [Hour(t, m, r, c) for t, m, r, c in zip(df.index, df.soil_moisture_0_to_7cm, df.precipitation, df.temperature_2m)]
    sample = range(12, len(hs), 7)
    naive = sum(max(h.moisture for h in hs[i - 12:i]) - min(h.moisture for h in hs[i - 12:i]) < 1e-4 for i in sample)
    ours = sum(is_stuck(hs[i - 12:i]) for i in sample)
    assert naive / len(sample) > 0.05          # "flat for 12 h" fires constantly on healthy soil
    assert ours / len(sample) < 0.001          # the weather-aware rule almost never does
