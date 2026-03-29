# Set env vars before any src module is imported (settings.py reads them at class body time)
import os
os.environ.update({
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "DB_NAME": "test_db",
    "DB_USERNAME": "test_user",
    "DB_PASSWORD": "test_pass",
    "BM_COMMON_API_URL": "http://test.api",
    "BM_COMMON_API_TOKEN": "test_token",
})

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.domain.pricing.tariff_pricing_strategy import PricingContext, TariffPricingStrategy
from src.models.history import HistoryEntry
from src.models.orm import UserOrm
from src.models.user import UserWithProjects


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user_orm(
    id: int = 1,
    login: str = "user@test.com",
    balance: float = 1000.0,
    confirmed: int = 1,
    reg_date: datetime = datetime(2020, 1, 1),
    unic_queries: int = 0,
    sales_month: int = 0,
    tariff_status: int = 1,
    wb_key: str = None,
    pass2: str = None,
) -> MagicMock:
    user = MagicMock(spec=UserOrm)
    user.id = id
    user.login = login
    user.balance = balance
    user.confirmed = confirmed
    user.regDate = reg_date
    user.unic_queries = unic_queries
    user.salesMonth = sales_month
    user.tariffStatus = tariff_status
    user.wbKey = wb_key
    user.pass2 = pass2
    return user


def make_user_with_projects(
    id: int = 1,
    login: str = "user@test.com",
    balance: float = 1000.0,
    reg_date: datetime = datetime(2020, 1, 1),
    unic_queries: int = 0,
    sales_month: int = 0,
    project_count: int = 2,
    tariff_status: int = 1,
) -> UserWithProjects:
    return UserWithProjects(
        id=id,
        login=login,
        balance=balance,
        confirmed=1,
        regDate=reg_date,
        unic_queries=unic_queries,
        salesMonth=sales_month,
        tariffStatus=tariff_status,
        wbKey=None,
        pass2=None,
        project_count=project_count,
    )


def make_pricing_context(
    user_id: int = 1,
    unique_phrases: int = 1000,
    project_count: int = 2,
    account_count: int = 1,
    sales_account_count: int = 0,
    weekly_sales_sum: float = 0.0,
    sales_month: int = 0,
    support_tariff: bool = False,
    bidder_token_exists: bool = False,
) -> PricingContext:
    return PricingContext(
        user_id=user_id,
        unique_phrases=unique_phrases,
        project_count=project_count,
        account_count=account_count,
        sales_account_count=sales_account_count,
        weekly_sales_sum=weekly_sales_sum,
        sales_month=sales_month,
        support_tariff=support_tariff,
        bidder_token_exists=bidder_token_exists,
    )


def make_history_entry(
    user_id: int = 1,
    amount: float = 217.0,
    hint: str = "1 / 1000 / 2 / 1",
) -> HistoryEntry:
    return HistoryEntry(
        user_id=user_id,
        dt=datetime(2024, 1, 15),
        txt="Списание абоненсткой платы",
        amount=amount,
        hint=hint,
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pricing():
    return TariffPricingStrategy()


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def sample_user():
    return make_user_with_projects()


@pytest.fixture
def sample_user_orm():
    return make_user_orm()
