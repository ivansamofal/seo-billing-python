import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.user import User, UserWithProjects
from src.models.history import HistoryEntry

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: Session):
        self._session = session

    def find_eligible_users_for_write_off(self) -> List[UserWithProjects]:
        """
        Find users eligible for daily billing:
        - confirmed account
        - tariff selected (tariffStatus > 0)
        - positive balance
        - not blocked
        """
        query = text("""
            SELECT
                u.id,
                u.login,
                u.balance,
                u.confirmed,
                u.regDate,
                u.projects,
                u.queries,
                u.unic_queries,
                u.projects_ozon,
                u.queries_ozon,
                u.unic_queries_ozon,
                u.salesMonth,
                u.blocked,
                u.unlimitedBalance,
                u.tariffStatus,
                u.wbKey,
                u.promocode,
                u.pass2,
                COUNT(p.id) AS project_count
            FROM users u
            LEFT JOIN projects p ON p.user_id = u.id
            WHERE u.confirmed = 1
              AND u.tariffStatus > 0
              AND u.balance > 0
              AND (u.blocked = 0 OR u.blocked IS NULL)
            GROUP BY u.id
        """)

        rows = self._session.execute(query).mappings().all()
        result: List[UserWithProjects] = []

        for row in rows:
            user = User(
                id=row["id"],
                login=row["login"],
                balance=float(row["balance"] or 0),
                confirmed=row["confirmed"],
                regDate=row["regDate"],
                projects=row["projects"] or 0,
                queries=row["queries"] or 0,
                unic_queries=row["unic_queries"] or 0,
                projects_ozon=row["projects_ozon"] or 0,
                queries_ozon=row["queries_ozon"] or 0,
                unic_queries_ozon=row["unic_queries_ozon"] or 0,
                salesMonth=row["salesMonth"] or 0,
                blocked=row["blocked"] or 0,
                unlimitedBalance=row["unlimitedBalance"] or 0,
                tariffStatus=row["tariffStatus"] or 0,
                wbKey=row["wbKey"],
                promocode=row["promocode"],
                pass2=row["pass2"],
            )
            result.append(UserWithProjects(user=user, project_count=row["project_count"] or 0))

        return result

    def get_unique_phrases_count(self, user_id: int) -> int:
        """Count distinct phrases across all user's projects."""
        query = text("""
            SELECT COUNT(DISTINCT plp.idPhrase) AS cnt
            FROM project_list_phrase plp
            JOIN projects p ON plp.idProject = p.id
            WHERE p.user_id = :user_id
              AND plp.tech = 0
        """)
        row = self._session.execute(query, {"user_id": user_id}).mappings().first()
        return int(row["cnt"]) if row else 0

    def has_active_promocode(self, user_id: int) -> bool:
        """Check if user has a currently active discount promocode."""
        query = text("""
            SELECT 1
            FROM promocodes pc
            JOIN promocode p ON pc.promocode_id = p.id
            WHERE pc.user_id = :user_id
              AND p.active = 1
              AND DATE_ADD(pc.dt, INTERVAL p.value DAY) >= CURDATE()
            LIMIT 1
        """)
        row = self._session.execute(query, {"user_id": user_id}).first()
        return row is not None

    def batch_update_user_balances(
        self,
        updates: List[dict],  # [{"user_id": int, "amount": int}, ...]
    ) -> None:
        """
        Atomically deduct balances for all users using a temporary table + INNER JOIN UPDATE.
        This is significantly faster than N individual UPDATE statements.
        """
        if not updates:
            return

        self._session.execute(text("""
            CREATE TEMPORARY TABLE IF NOT EXISTS temp_user_balance_updates (
                user_id INT NOT NULL,
                amount INT NOT NULL,
                PRIMARY KEY (user_id)
            )
        """))

        self._session.execute(text("DELETE FROM temp_user_balance_updates"))

        values_sql = ", ".join(
            f"({u['user_id']}, {u['amount']})" for u in updates
        )
        self._session.execute(text(
            f"INSERT INTO temp_user_balance_updates (user_id, amount) VALUES {values_sql}"
        ))

        self._session.execute(text("""
            UPDATE users u
            INNER JOIN temp_user_balance_updates tmp ON u.id = tmp.user_id
            SET u.balance = GREATEST(0, CAST(ROUND(u.balance) AS SIGNED) - tmp.amount)
        """))

        self._session.execute(text("DROP TEMPORARY TABLE temp_user_balance_updates"))

    def batch_insert_history(self, entries: List[HistoryEntry]) -> None:
        """Batch insert all billing history records in one query."""
        if not entries:
            return

        rows = ", ".join(
            f"({e.user_id}, '{e.dt.strftime('%Y-%m-%d %H:%M:%S')}', "
            f"'{e.txt}', {-abs(e.amount)}, '{e.hint}')"
            for e in entries
        )
        self._session.execute(text(
            f"INSERT INTO history (user_id, dt, txt, amount, hint) VALUES {rows}"
        ))
