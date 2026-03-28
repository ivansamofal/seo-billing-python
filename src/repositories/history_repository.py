import logging
from typing import List

from sqlalchemy import insert
from sqlalchemy.orm import Session

from src.models.history import HistoryEntry
from src.models.orm import HistoryOrm

logger = logging.getLogger(__name__)


class HistoryRepository:
    def __init__(self, session: Session):
        self._session = session

    def batch_insert(self, entries: List[HistoryEntry]) -> None:
        if not entries:
            return

        self._session.execute(
            insert(HistoryOrm),
            [
                {
                    "user_id": e.user_id,
                    "dt": e.dt,
                    "txt": e.txt,
                    "amount": -abs(e.amount),
                    "hint": e.hint,
                }
                for e in entries
            ],
        )
