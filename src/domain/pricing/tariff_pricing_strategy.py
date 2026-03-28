import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Base daily price tiers by unique phrase count (rubles/day)
PHRASE_PRICE_TIERS = [
    (500,    0),
    (5000,   217),
    (8000,   237),
    (10000,  297),
    (15000,  337),
    (20000,  437),
    (30000,  617),
    (50000,  917),
    (100000, 1683),
    (None,   2000),  # 100000+
]

# Project surcharge tiers: (max_projects_in_tier, price_per_package)
PROJECT_PRICE_TIERS = [
    (20,  66),
    (40,  33),
    (100, 17),
    (None, 8),
]

EXTRA_ACCOUNT_PRICE = 50  # rubles/day per account beyond the first
FREE_TARIFF_MAX_PHRASES = 500
HELP_TARIFF_MAX_PHRASES = 900
HELP_TARIFF_MAX_WEEKLY_SALES = 200_000
HELP_TARIFF_MAX_SALES_MONTH = 300_000
FREE_PROJECT_ALLOWANCE = 5  # projects included in base price


@dataclass
class PricingContext:
    user_id: int
    unique_phrases: int
    project_count: int
    account_count: int          # total bidder accounts
    sales_account_count: int    # total sales accounts
    weekly_sales_sum: float
    sales_month: int
    support_tariff: bool        # whether BM Common API confirms support tariff
    bidder_token_exists: bool


class TariffPricingStrategy:
    def calculate_price(self, ctx: PricingContext) -> int:
        """Return daily charge in rubles (integer)."""
        tariff = self.get_tariff_name(ctx)
        logger.debug(
            "User %d: tariff=%s phrases=%d accounts=%d projects=%d",
            ctx.user_id, tariff, ctx.unique_phrases, ctx.account_count, ctx.project_count,
        )

        if tariff == "FREE":
            return 0

        if tariff == "HELP":
            return 0

        # PAID tariff
        base_price = self._phrase_base_price(ctx.unique_phrases)

        # If user has accounts but phrases ≤ 500, charge the minimum PAID tier
        if ctx.account_count > 1 and ctx.unique_phrases <= FREE_TARIFF_MAX_PHRASES:
            base_price = max(base_price, 217)

        account_surcharge = max(0, ctx.account_count - 1) * EXTRA_ACCOUNT_PRICE
        project_surcharge = self._project_surcharge(ctx.project_count)

        total = base_price + account_surcharge + project_surcharge
        logger.debug(
            "User %d price breakdown: base=%d accounts_surcharge=%d projects_surcharge=%d total=%d",
            ctx.user_id, base_price, account_surcharge, project_surcharge, total,
        )
        return total

    def get_tariff_name(self, ctx: PricingContext) -> str:
        # FREE: very small usage
        if (
            ctx.unique_phrases <= FREE_TARIFF_MAX_PHRASES
            and ctx.account_count <= 1
            and ctx.project_count <= 1
        ):
            return "FREE"

        # FREE: low sales & low phrases regardless of accounts
        if (
            ctx.sales_month <= HELP_TARIFF_MAX_SALES_MONTH
            and ctx.weekly_sales_sum <= HELP_TARIFF_MAX_WEEKLY_SALES
            and ctx.unique_phrases <= HELP_TARIFF_MAX_PHRASES
        ):
            return "FREE"

        # HELP (support tariff): API-confirmed, small usage
        if (
            ctx.support_tariff
            and ctx.unique_phrases < HELP_TARIFF_MAX_PHRASES
            and ctx.sales_account_count <= 1
            and ctx.account_count <= 1
            and ctx.project_count <= 3
            and ctx.weekly_sales_sum <= HELP_TARIFF_MAX_WEEKLY_SALES
        ):
            return "HELP"

        return "PAID"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _phrase_base_price(self, unique_phrases: int) -> int:
        for threshold, price in PHRASE_PRICE_TIERS:
            if threshold is None or unique_phrases <= threshold:
                return price
        return 2000

    def _project_surcharge(self, project_count: int) -> int:
        if project_count <= FREE_PROJECT_ALLOWANCE:
            return 0

        extra = project_count - FREE_PROJECT_ALLOWANCE
        surcharge = 0
        tier_start = FREE_PROJECT_ALLOWANCE

        for tier_max, price_per_package in PROJECT_PRICE_TIERS:
            if extra <= 0:
                break
            if tier_max is None:
                surcharge += extra * price_per_package
                break
            tier_capacity = tier_max - tier_start
            charged = min(extra, tier_capacity)
            surcharge += charged * price_per_package
            extra -= charged
            tier_start = tier_max

        return surcharge
