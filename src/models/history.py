from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class HistoryEntry:
    user_id: int
    dt: datetime
    txt: str
    amount: float
    hint: str
