import logging
from typing import List, Tuple

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

    def get_unique_phrases_count(self, user_id: int) -> int:
        return (
            self._session.query(func.count(distinct(ProjectListPhraseOrm.idPhrase)))
            .join(ProjectOrm, ProjectListPhraseOrm.idProject == ProjectOrm.id)
            .filter(
                ProjectOrm.user_id == user_id,
                ProjectListPhraseOrm.tech == 0,
            )
            .scalar()
            or 0
        )

    def has_active_promocode(self, user_id: int) -> bool:
        return (
            self._session.query(UserPromocodeOrm)
            .join(PromocodeOrm, UserPromocodeOrm.promocode_id == PromocodeOrm.id)
            .filter(
                UserPromocodeOrm.user_id == user_id,
                PromocodeOrm.active == 1,
                text("DATE_ADD(promocodes.dt, INTERVAL promocode.value DAY) >= CURDATE()"),
            )
            .first()
        ) is not None

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
