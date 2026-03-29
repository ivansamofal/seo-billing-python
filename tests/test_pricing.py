import pytest

from tests.conftest import make_pricing_context


class TestTariffName:
    def test_free_small_usage(self, pricing):
        ctx = make_pricing_context(unique_phrases=500, account_count=1, project_count=1)
        assert pricing.get_tariff_name(ctx) == "FREE"

    def test_free_exactly_500_phrases(self, pricing):
        ctx = make_pricing_context(unique_phrases=500, account_count=1, project_count=1)
        assert pricing.get_tariff_name(ctx) == "FREE"

    def test_free_low_sales_regardless_of_accounts(self, pricing):
        # salesMonth ≤ 300k, weekly ≤ 200k, phrases ≤ 900 → FREE even with multiple accounts
        ctx = make_pricing_context(
            unique_phrases=900,
            account_count=3,
            sales_month=100_000,
            weekly_sales_sum=50_000,
        )
        assert pricing.get_tariff_name(ctx) == "FREE"

    def test_free_boundary_sales_month(self, pricing):
        ctx = make_pricing_context(
            unique_phrases=900, account_count=2,
            sales_month=300_000, weekly_sales_sum=200_000,
        )
        assert pricing.get_tariff_name(ctx) == "FREE"

    def test_help_tariff(self, pricing):
        # sales_month > 300k bypasses the "FREE if low sales" rule,
        # leaving only the HELP check to match.
        ctx = make_pricing_context(
            unique_phrases=800,
            account_count=1,
            sales_account_count=1,
            project_count=3,
            weekly_sales_sum=100_000,
            sales_month=400_000,
            support_tariff=True,
        )
        assert pricing.get_tariff_name(ctx) == "HELP"

    def test_help_requires_support_tariff_flag(self, pricing):
        ctx = make_pricing_context(
            unique_phrases=800,
            account_count=1,
            sales_account_count=1,
            project_count=3,
            weekly_sales_sum=100_000,
            support_tariff=False,  # flag off
        )
        # Falls through to PAID because sales_month=0 & phrases≤900 → actually FREE
        # Use high phrases to force PAID path
        ctx2 = make_pricing_context(
            unique_phrases=950,
            account_count=2,
            sales_account_count=1,
            project_count=3,
            weekly_sales_sum=100_000,
            support_tariff=False,
        )
        assert pricing.get_tariff_name(ctx2) == "PAID"

    def test_paid_high_phrases(self, pricing):
        ctx = make_pricing_context(unique_phrases=10_000, account_count=2, project_count=10)
        assert pricing.get_tariff_name(ctx) == "PAID"

    def test_paid_exceeds_sales_limits(self, pricing):
        ctx = make_pricing_context(
            unique_phrases=950,
            account_count=2,
            sales_month=400_000,   # over 300k
            weekly_sales_sum=250_000,
        )
        assert pricing.get_tariff_name(ctx) == "PAID"


class TestPhrasePriceTiers:
    def test_tier_boundary_500(self, pricing):
        # sales_month > 300k forces PAID (bypasses "FREE if low sales" shortcut)
        ctx = make_pricing_context(
            unique_phrases=500, account_count=2, project_count=10, sales_month=400_000
        )
        # base raised to 217 (>1 account with ≤500 phrases), +50 for extra account, +5*66 for projects
        assert pricing.calculate_price(ctx) == 217 + (1 * 50) + (5 * 66)

    def test_tier_501_to_5000(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 217

    def test_tier_5001_to_8000(self, pricing):
        ctx = make_pricing_context(unique_phrases=6000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 237

    def test_tier_8001_to_10000(self, pricing):
        ctx = make_pricing_context(unique_phrases=9000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 297

    def test_tier_10001_to_15000(self, pricing):
        ctx = make_pricing_context(unique_phrases=12000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 337

    def test_tier_15001_to_20000(self, pricing):
        ctx = make_pricing_context(unique_phrases=18000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 437

    def test_tier_20001_to_30000(self, pricing):
        ctx = make_pricing_context(unique_phrases=25000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 617

    def test_tier_30001_to_50000(self, pricing):
        ctx = make_pricing_context(unique_phrases=40000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 917

    def test_tier_50001_to_100000(self, pricing):
        ctx = make_pricing_context(unique_phrases=75000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 1683

    def test_tier_over_100000(self, pricing):
        ctx = make_pricing_context(unique_phrases=150000, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 2000


class TestAccountSurcharge:
    def test_one_account_no_surcharge(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=1)
        assert pricing.calculate_price(ctx) == 217  # base only

    def test_two_accounts_adds_50(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=2)
        assert pricing.calculate_price(ctx) == 217 + 50

    def test_three_accounts_adds_100(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=3)
        assert pricing.calculate_price(ctx) == 217 + 100

    def test_minimum_price_enforced_with_multiple_accounts(self, pricing):
        # sales_month > 300k forces PAID; then phrases=200 (base=0) + 2 accounts → min base 217
        ctx = make_pricing_context(
            unique_phrases=200, account_count=2, project_count=10, sales_month=400_000
        )
        price = pricing.calculate_price(ctx)
        assert price >= 217


class TestProjectSurcharge:
    def test_five_projects_no_surcharge(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=1, project_count=5)
        assert pricing.calculate_price(ctx) == 217

    def test_six_projects_adds_one_tier1_package(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=1, project_count=6)
        assert pricing.calculate_price(ctx) == 217 + 66

    def test_ten_projects_tier1(self, pricing):
        # 5 extra projects in tier1 (≤20): 5 * 66 = 330
        ctx = make_pricing_context(unique_phrases=1000, account_count=1, project_count=10)
        assert pricing.calculate_price(ctx) == 217 + 5 * 66

    def test_twenty_projects_full_tier1(self, pricing):
        # 15 extra in tier1: 15 * 66 = 990
        ctx = make_pricing_context(unique_phrases=1000, account_count=1, project_count=20)
        assert pricing.calculate_price(ctx) == 217 + 15 * 66

    def test_twenty_five_projects_crosses_tiers(self, pricing):
        # tier1: 15 projects * 66 = 990
        # tier2: 5 projects * 33 = 165
        ctx = make_pricing_context(unique_phrases=1000, account_count=1, project_count=25)
        assert pricing.calculate_price(ctx) == 217 + 15 * 66 + 5 * 33

    def test_combined_account_and_project_surcharge(self, pricing):
        ctx = make_pricing_context(unique_phrases=1000, account_count=3, project_count=6)
        # base=217, accounts=(2*50)=100, projects=66
        assert pricing.calculate_price(ctx) == 217 + 100 + 66


class TestFreeAndHelpReturnZero:
    def test_free_tariff_returns_zero(self, pricing):
        ctx = make_pricing_context(unique_phrases=100, account_count=1, project_count=1)
        assert pricing.calculate_price(ctx) == 0

    def test_help_tariff_returns_zero(self, pricing):
        ctx = make_pricing_context(
            unique_phrases=800,
            account_count=1,
            sales_account_count=0,
            project_count=2,
            weekly_sales_sum=50_000,
            support_tariff=True,
        )
        assert pricing.calculate_price(ctx) == 0
