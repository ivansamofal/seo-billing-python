import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.domain.pricing.tariff_pricing_strategy import TariffPricingStrategy
from src.models.history import HistoryEntry
from src.models.orm import UserOrm
from src.models.user import UserWithProjects
from src.repositories.history_repository import HistoryRepository
from src.repositories.user_repository import UserRepository
from src.services.charge_calculator import ChargeCalculator, ChargeEntry
from src.services.external_api_service import ExternalApiService
from src.services.user_eligibility_filter import UserEligibilityFilter

logger = logging.getLogger(__name__)


@dataclass
class BillingResult:
    processed_users: int
    total_amount: int
    date: str


class BillingService:
    def __init__(
        self,
        session: Session,
        external_api: ExternalApiService,
        pricing: TariffPricingStrategy,
    ):
        self._session = session
        self._user_repo = UserRepository(session)
        self._history_repo = HistoryRepository(session)
        self._external_api = external_api
        self._eligibility_filter = UserEligibilityFilter()
        self._charge_calculator = ChargeCalculator(pricing)

    def process_write_off(self, date: Optional[str] = None) -> BillingResult:
        billing_date, billing_dt = _parse_billing_date(date)
        logger.info("Starting billing write-off for date: %s", billing_date)

        rows = self._user_repo.find_eligible_users_for_write_off()
        logger.info("Eligible users found: %d", len(rows))
        if not rows:
            return BillingResult(processed_users=0, total_amount=0, date=billing_date)

        users = _map_to_domain(rows)
        users_data = self._external_api.get_users_info([u.login for u in users])
        logger.info("External API returned data for %d users", len(users_data))

        users = self._eligibility_filter.filter_bonus_period(users, users_data, billing_dt)
        logger.info("Users after bonus period filter: %d", len(users))

        promo_ids = self._user_repo.get_users_with_active_promocode([u.id for u in users])
        users = self._eligibility_filter.filter_promo(users, promo_ids)
        logger.info("Users after promo filter: %d", len(users))

        phrase_counts = self._user_repo.get_unique_phrases_counts_batch([u.id for u in users])

        charges = self._calculate_charges(users, users_data, phrase_counts)
        total_amount = sum(c.amount for c in charges)
        logger.info("Billing summary: %d users charged, total=%d rubles", len(charges), total_amount)

        if charges:
            self._persist_charges(charges, billing_dt)

        return BillingResult(
            processed_users=len(charges),
            total_amount=total_amount,
            date=billing_date,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculate_charges(
        self,
        users: List[UserWithProjects],
        users_data: Dict[str, dict],
        phrase_counts: Dict[int, int],
    ) -> List[ChargeEntry]:
        charges = []
        for user in users:
            try:
                entry = self._charge_calculator.calculate(
                    user, users_data, phrase_counts.get(user.id, 0)
                )
                if entry:
                    charges.append(entry)
            except Exception as exc:
                logger.error("Error processing user %d (%s): %s", user.id, user.login, exc, exc_info=True)
        return charges

    def _persist_charges(self, charges: List[ChargeEntry], billing_dt: datetime) -> None:
        balance_updates = [{"user_id": c.user_id, "amount": c.amount} for c in charges]
        history_entries = [
            HistoryEntry(
                user_id=c.user_id,
                dt=billing_dt,
                txt=settings.HISTORY_TXT,
                amount=c.amount,
                hint=c.hint,
            )
            for c in charges
        ]
        try:
            self._user_repo.batch_update_user_balances(balance_updates)
            self._history_repo.batch_insert(history_entries)
            self._session.commit()
            logger.info("Batch billing transaction committed successfully")
        except Exception as exc:
            self._session.rollback()
            logger.error("Billing transaction rolled back: %s", exc, exc_info=True)
            raise


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _parse_billing_date(date: Optional[str]) -> Tuple[str, datetime]:
    billing_date = date or datetime.now().strftime("%Y-%m-%d")
    billing_dt = datetime.strptime(billing_date, "%Y-%m-%d")
    return billing_date, billing_dt


def _map_to_domain(rows: List[Tuple[UserOrm, int]]) -> List[UserWithProjects]:
    return [
        UserWithProjects(
            id=orm_user.id,
            login=orm_user.login,
            balance=float(orm_user.balance or 0),
            confirmed=orm_user.confirmed or 0,
            regDate=orm_user.regDate,
            unic_queries=orm_user.unic_queries or 0,
            salesMonth=orm_user.salesMonth or 0,
            tariffStatus=orm_user.tariffStatus or 0,
            wbKey=orm_user.wbKey,
            pass2=orm_user.pass2,
            project_count=project_count or 0,
        )
        for orm_user, project_count in rows
    ]
