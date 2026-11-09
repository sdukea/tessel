from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(frozen=True)
class Hour:
    at: datetime
    moisture: float
    rain_mm: float
    temp_c: float

def is_dry(h: Hour, threshold: float) -> bool:
    """Below the crop's stress threshold: the argonomic alert"""
    return h.moisture < threshold

def is_stuck(window: list[Hour], hours: int = 12, flat: float = 1e-4, min_rain_mm: float = 2.0) -> bool:
    if len(window) < hours:
        return False

    # get moisture values
    w = window[-hours:]
    values = [h.moisture for h in w]

    # named conditions – all boolean
    flat_line = max(values) - min(values) < flat
    rained = sum(h.rain_mm for h in w) <= min_rain_mm
    thawed = all(h.temp_c > 0 for h in w)

    return flat_line and rained and thawed

def is_spike(prev: Hour, cur: Hour, max_jump: float = 0.10, dry_mm: float = 0.1) -> bool:
    return abs(cur.moisture - prev.moisture) > max_jump and cur.rain_mm < dry_mm
    # asks 'did the moisture jump a lot' and 'was it dry (no rain)'

def is_silent(last_seen: datetime, now: datetime, interval: timedelta, missed: int = 3) -> bool:
    return now - last_seen > missed * interval

def evaluate(window: list[Hour], threshold: float) -> list[str]:
    # runs every rule on the newest hour and returns the kind of alerts that fired
    if not window:
        return []
    