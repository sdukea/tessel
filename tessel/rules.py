from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(frozen=True)
class Hour:
    at: datetime
    moisture: float
    rain_mm: float
    temo_c: float

