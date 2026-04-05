import logging
from dataclasses import dataclass
from typing import Dict, Optional

from src.domain.pricing.tariff_pricing_strategy import TariffPricingStrategy, PricingContext
from src.models.user import UserWithProjects

logger = logging.getLogger(__name__)


@dataclass
class ChargeEntry:
    user_id: int
    amount: int
    hint: str


class ChargeCalculator:

    def __init__(self, pricing: TariffPricingStrategy):
        self._pricing = pricing

    def calculate(
        self,
        user: UserWithProjects,
        users_data: Dict[str, dict],
        unique_phrases: int,
    ) -> Optional[ChargeEntry]:
        external = users_data.get(user.login, {})
        accounts = external.get("accounts", []) or []
        sales_accounts = external.get("salesAccounts", []) or []

        ctx = PricingContext(
            user_id=user.id,
            unique_phrases=unique_phrases,
            project_count=user.project_count,
            account_count=len(accounts),
            sales_account_count=len(sales_accounts),
            weekly_sales_sum=float(external.get("weeklySalesSum", 0) or 0),
            sales_month=user.salesMonth or 0,
            support_tariff=bool(external.get("supportTariff", False)),
            bidder_token_exists=bool(external.get("tokenExists", False)),
        )

        amount = self._pricing.calculate_price(ctx)
        if amount <= 0:
            logger.debug("User %d (%s): amount=0, skipping", user.id, user.login)
            return None

        actual_amount = min(amount, int(round(user.balance)))
        if actual_amount <= 0:
            return None

        hint = f"{user.id} / {unique_phrases} / {user.project_count} / {len(accounts)}"
        logger.debug(
            "User %d (%s): charge=%d (balance was %.2f)",
            user.id, user.login, actual_amount, user.balance,
        )
        return ChargeEntry(user_id=user.id, amount=actual_amount, hint=hint)
