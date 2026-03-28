import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.domain.pricing.tariff_pricing_strategy import TariffPricingStrategy, PricingContext
from src.models.history import HistoryEntry
from src.models.orm import UserOrm
from src.models.user import UserWithProjects
from src.repositories.history_repository import HistoryRepository
from src.repositories.user_repository import UserRepository
from src.services.external_api_service import ExternalApiService

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
        self._pricing = pricing

    def process_write_off(self, date: Optional[str] = None) -> BillingResult:
        billing_date = date or datetime.now().strftime("%Y-%m-%d")
        billing_dt = datetime.strptime(billing_date, "%Y-%m-%d")
        logger.info("Starting billing write-off for date: %s", billing_date)

        rows: List[Tuple[UserOrm, int]] = self._user_repo.find_eligible_users_for_write_off()
        logger.info("Eligible users found: %d", len(rows))

        if not rows:
            return BillingResult(processed_users=0, total_amount=0, date=billing_date)

        users = self._map_to_domain(rows)

        emails = [u.login for u in users]
        users_data = self._external_api.get_users_info(emails)
        logger.info("External API returned data for %d users", len(users_data))

        users = self._filter_users_by_promo_codes(users)
        logger.info("Users after promo filter: %d", len(users))

        balance_updates: List[dict] = []
        history_entries: List[HistoryEntry] = []

        for user in users:
            try:
                amount = self._calculate_charge(user, users_data, billing_dt)
                if amount <= 0:
                    logger.debug("User %d (%s): amount=0, skipping", user.id, user.login)
                    continue

                actual_amount = min(amount, int(round(user.balance)))
                if actual_amount <= 0:
                    continue

                unique_phrases = self._user_repo.get_unique_phrases_count(user.id)
                account_count = self._get_account_count(user, users_data)
                hint = f"{user.id} / {unique_phrases} / {user.project_count} / {account_count}"

                balance_updates.append({"user_id": user.id, "amount": actual_amount})
                history_entries.append(HistoryEntry(
                    user_id=user.id,
                    dt=billing_dt,
                    txt=settings.HISTORY_TXT,
                    amount=actual_amount,
                    hint=hint,
                ))
                logger.debug(
                    "User %d (%s): charge=%d (balance was %.2f)",
                    user.id, user.login, actual_amount, user.balance,
                )
            except Exception as exc:
                logger.error("Error processing user %d (%s): %s", user.id, user.login, exc, exc_info=True)

        total_amount = sum(u["amount"] for u in balance_updates)
        logger.info(
            "Billing summary: %d users charged, total=%d rubles",
            len(balance_updates), total_amount,
        )

        if balance_updates:
            try:
                self._user_repo.batch_update_user_balances(balance_updates)
                self._history_repo.batch_insert(history_entries)
                self._session.commit()
                logger.info("Batch billing transaction committed successfully")
            except Exception as exc:
                self._session.rollback()
                logger.error("Billing transaction rolled back: %s", exc, exc_info=True)
                raise

        return BillingResult(
            processed_users=len(balance_updates),
            total_amount=total_amount,
            date=billing_date,
        )

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _map_to_domain(self, rows: List[Tuple[UserOrm, int]]) -> List[UserWithProjects]:
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

    # ------------------------------------------------------------------
    # Business logic helpers
    # ------------------------------------------------------------------

    def _calculate_charge(
        self,
        user: UserWithProjects,
        users_data: Dict[str, dict],
        billing_dt: datetime,
    ) -> int:
        if self._is_in_bonus_period(user, users_data, billing_dt):
            logger.debug("User %d is in bonus period, skipping", user.id)
            return 0

        external = users_data.get(user.login, {})
        accounts = external.get("accounts", []) or []
        sales_accounts = external.get("salesAccounts", []) or []
        weekly_sales_sum = float(external.get("weeklySalesSum", 0) or 0)
        support_tariff = bool(external.get("supportTariff", False))
        bidder_token_exists = bool(external.get("tokenExists", False))

        unique_phrases = self._user_repo.get_unique_phrases_count(user.id)

        ctx = PricingContext(
            user_id=user.id,
            unique_phrases=unique_phrases,
            project_count=user.project_count,
            account_count=len(accounts),
            sales_account_count=len(sales_accounts),
            weekly_sales_sum=weekly_sales_sum,
            sales_month=user.salesMonth or 0,
            support_tariff=support_tariff,
            bidder_token_exists=bidder_token_exists,
        )

        return self._pricing.calculate_price(ctx)

    def _is_in_bonus_period(
        self,
        user: UserWithProjects,
        users_data: Dict[str, dict],
        billing_dt: datetime,
    ) -> bool:
        """
        - FREE_DAYS (3) days free after registration for all users
        - FREE_DAYS_API_ENTERED (7) days free if bidder token is valid
        """
        if not user.regDate:
            return False

        external = users_data.get(user.login, {})
        token_exists = bool(external.get("tokenExists", False))

        bonus_days = settings.FREE_DAYS_API_ENTERED if token_exists else settings.FREE_DAYS
        return billing_dt < user.regDate + timedelta(days=bonus_days)

    def _filter_users_by_promo_codes(
        self, users: List[UserWithProjects]
    ) -> List[UserWithProjects]:
        result = []
        for user in users:
            try:
                if self._user_repo.has_active_promocode(user.id):
                    logger.debug("User %d has active promocode, skipping", user.id)
                    continue
                result.append(user)
            except Exception as exc:
                logger.warning("Error checking promo for user %d: %s", user.id, exc)
                result.append(user)
        return result

    def _get_account_count(self, user: UserWithProjects, users_data: Dict[str, dict]) -> int:
        return len(users_data.get(user.login, {}).get("accounts", []) or [])
