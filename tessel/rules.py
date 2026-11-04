from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(frozen=True)
class Hour:
    at: datetime
    moisture: float
    rain_mm: float
    temo_c: float

def is_dry(h: Hour, threshold: float) -> bool:
    """Below the crop's stress threshold: the argonomic alert"""
    