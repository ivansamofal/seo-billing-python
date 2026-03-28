import logging
from typing import List, Tuple, Dict, Set

from sqlalchemy import func, distinct, text, or_
from sqlalchemy.orm import Session

from src.models.orm import UserOrm, ProjectOrm, ProjectListPhraseOrm, UserPromocodeOrm, PromocodeOrm

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: Session):
        self._session = session

    def find_eligible_users_for_write_off(self) -> List[Tuple[UserOrm, int]]:
        return (
            self._session.query(UserOrm, func.count(ProjectOrm.id).label("project_count"))
            .outerjoin(ProjectOrm, ProjectOrm.user_id == UserOrm.id)
            .filter(
                UserOrm.confirmed == 1,
                UserOrm.tariffStatus > 0,
                UserOrm.balance > 0,
                or_(UserOrm.blocked == 0, UserOrm.blocked.is_(None)),
            )
            .group_by(UserOrm.id)
            .all()
        )

    def get_unique_phrases_counts_batch(self, user_ids: List[int]) -> Dict[int, int]:
        if not user_ids:
            return {}
        rows = (
            self._session.query(
                ProjectOrm.user_id,
                func.count(distinct(ProjectListPhraseOrm.idPhrase)).label("cnt"),
            )
            .join(ProjectListPhraseOrm, ProjectListPhraseOrm.idProject == ProjectOrm.id)
            .filter(
                ProjectOrm.user_id.in_(user_ids),
                ProjectListPhraseOrm.tech == 0,
            )
            .group_by(ProjectOrm.user_id)
            .all()
        )
        result = {uid: 0 for uid in user_ids}
        for user_id, cnt in rows:
            result[user_id] = cnt
        return result

    def get_users_with_active_promocode(self, user_ids: List[int]) -> Set[int]:
        if not user_ids:
            return set()
        rows = (
            self._session.query(UserPromocodeOrm.user_id)
            .join(PromocodeOrm, UserPromocodeOrm.promocode_id == PromocodeOrm.id)
            .filter(
                UserPromocodeOrm.user_id.in_(user_ids),
                PromocodeOrm.active == 1,
                text("DATE_ADD(promocodes.dt, INTERVAL promocode.value DAY) >= CURDATE()"),
            )
            .distinct()
            .all()
        )
        return {row.user_id for row in rows}

    def batch_update_user_balances(self, updates: List[dict]) -> None:
        if not updates:
            return

        self._session.execute(text(
            "CREATE TEMPORARY TABLE IF NOT EXISTS temp_user_balance_updates "
            "(user_id INT NOT NULL, amount INT NOT NULL, PRIMARY KEY (user_id))"
        ))
        self._session.execute(text("DELETE FROM temp_user_balance_updates"))

        values = ", ".join(f"({u['user_id']}, {u['amount']})" for u in updates)
        self._session.execute(text(
            f"INSERT INTO temp_user_balance_updates (user_id, amount) VALUES {values}"
        ))

        self._session.execute(text(
            "UPDATE users u "
            "INNER JOIN temp_user_balance_updates tmp ON u.id = tmp.user_id "
            "SET u.balance = GREATEST(0, CAST(ROUND(u.balance) AS SIGNED) - tmp.amount)"
        ))

        self._session.execute(text("DROP TEMPORARY TABLE temp_user_balance_updates"))
