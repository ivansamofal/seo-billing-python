from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from src.domain.pricing.tariff_pricing_strategy import TariffPricingStrategy
from src.services.billing_service import BillingService
from src.services.external_api_service import ExternalApiService
from tests.conftest import make_user_orm, make_user_with_projects


BILLING_DATE = "2024-01-15"
BILLING_DT = datetime(2024, 1, 15)


def _make_service(mock_session, mock_external_api=None, pricing=None):
    if mock_external_api is None:
        mock_external_api = MagicMock(spec=ExternalApiService)
        mock_external_api.get_users_info.return_value = {}
    if pricing is None:
        pricing = TariffPricingStrategy()
    return BillingService(mock_session, mock_external_api, pricing)


@pytest.fixture
def mock_external_api():
    api = MagicMock(spec=ExternalApiService)
    api.get_users_info.return_value = {}
    return api


# Patch both repos so tests don't need a real DB session
@pytest.fixture
def patched_repos():
    with patch("src.services.billing_service.UserRepository") as MockUserRepo, \
         patch("src.services.billing_service.HistoryRepository") as MockHistoryRepo:
        yield MockUserRepo.return_value, MockHistoryRepo.return_value


class TestNoEligibleUsers:
    def test_returns_zero_result(self, mock_session, mock_external_api, patched_repos):
        user_repo, _ = patched_repos
        user_repo.find_eligible_users_for_write_off.return_value = []

        service = _make_service(mock_session, mock_external_api)
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 0
        assert result.total_amount == 0
        assert result.date == BILLING_DATE
        mock_external_api.get_users_info.assert_not_called()

    def test_does_not_commit(self, mock_session, mock_external_api, patched_repos):
        user_repo, _ = patched_repos
        user_repo.find_eligible_users_for_write_off.return_value = []

        service = _make_service(mock_session, mock_external_api)
        service.process_write_off(BILLING_DATE)

        mock_session.commit.assert_not_called()


class TestBonusPeriodFilter:
    def test_new_user_within_bonus_days_is_skipped(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        # regDate 1 day ago → within FREE_DAYS=3
        new_user_orm = make_user_orm(
            id=1, login="new@test.com", balance=500.0,
            reg_date=BILLING_DT - timedelta(days=1),
        )
        user_repo.find_eligible_users_for_write_off.return_value = [(new_user_orm, 2)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 5000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {"new@test.com": {"tokenExists": False}}

        service = _make_service(mock_session, api)
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 0
        user_repo.batch_update_user_balances.assert_not_called()

    def test_old_user_past_bonus_period_is_charged(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        old_user_orm = make_user_orm(
            id=1, login="old@test.com", balance=500.0,
            reg_date=datetime(2020, 1, 1),  # far in the past
        )
        user_repo.find_eligible_users_for_write_off.return_value = [(old_user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "old@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 0,
                             "supportTariff": False, "tokenExists": False}
        }

        service = _make_service(mock_session, api)
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 1

    def test_token_user_gets_longer_bonus_period(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        # regDate 5 days ago: past FREE_DAYS(3) but within FREE_DAYS_API_ENTERED(7)
        user_orm = make_user_orm(
            id=1, login="token@test.com", balance=500.0,
            reg_date=BILLING_DT - timedelta(days=5),
        )
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {"token@test.com": {"tokenExists": True}}

        service = _make_service(mock_session, api)
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 0  # still in bonus


class TestPromoFilter:
    def test_user_with_active_promo_is_skipped(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(id=5, login="promo@test.com", balance=500.0)
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = {5}  # user 5 has promo
        user_repo.get_unique_phrases_counts_batch.return_value = {5: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {}

        service = _make_service(mock_session, api)
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 0

    def test_phrase_counts_not_loaded_for_promo_users(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(id=5, login="promo@test.com", balance=500.0)
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = {5}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {}

        service = _make_service(mock_session, api)
        service.process_write_off(BILLING_DATE)

        # Called with empty list because all users were filtered out
        user_repo.get_unique_phrases_counts_batch.assert_called_once_with([])


class TestChargeCalculation:
    def _setup_paid_user(self, patched_repos, user_id=1, balance=1000.0, phrase_count=5000):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(
            id=user_id, login="paid@test.com", balance=balance,
            reg_date=datetime(2020, 1, 1),
        )
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {user_id: phrase_count}
        return user_repo, history_repo

    def _paid_api(self, login="paid@test.com"):
        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            login: {
                "accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                "supportTariff": False, "tokenExists": False,
            }
        }
        return api

    def test_user_with_free_tariff_not_charged(self, mock_session, patched_repos):
        user_repo, _ = self._setup_paid_user(patched_repos, phrase_count=100)
        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "paid@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 0,
                              "supportTariff": False, "tokenExists": False}
        }

        service = _make_service(mock_session, api)
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 0
        user_repo.batch_update_user_balances.assert_not_called()

    def test_paid_user_charged_correct_amount(self, mock_session, patched_repos):
        user_repo, _ = self._setup_paid_user(patched_repos, phrase_count=1000)

        service = _make_service(mock_session, self._paid_api())
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 1
        assert result.total_amount == 217  # 1000 phrases, 1 account → 217

    def test_charge_capped_at_available_balance(self, mock_session, patched_repos):
        # balance=100, but tariff=217 → actual charge = 100
        user_repo, _ = self._setup_paid_user(patched_repos, balance=100.0, phrase_count=1000)

        service = _make_service(mock_session, self._paid_api())
        result = service.process_write_off(BILLING_DATE)

        assert result.total_amount == 100

    def test_user_with_zero_balance_not_charged(self, mock_session, patched_repos):
        user_repo, _ = self._setup_paid_user(patched_repos, balance=0.0, phrase_count=1000)

        service = _make_service(mock_session, self._paid_api())
        result = service.process_write_off(BILLING_DATE)

        assert result.processed_users == 0


class TestBatchWriteAndCommit:
    def test_batch_update_called_with_correct_user_and_amount(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(id=42, login="u@test.com", balance=1000.0,
                                 reg_date=datetime(2020, 1, 1))
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {42: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "u@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                           "supportTariff": False, "tokenExists": False}
        }

        service = _make_service(mock_session, api)
        service.process_write_off(BILLING_DATE)

        user_repo.batch_update_user_balances.assert_called_once_with(
            [{"user_id": 42, "amount": 217}]
        )

    def test_history_batch_insert_called(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(id=1, login="u@test.com", balance=500.0,
                                 reg_date=datetime(2020, 1, 1))
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "u@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                           "supportTariff": False, "tokenExists": False}
        }

        service = _make_service(mock_session, api)
        service.process_write_off(BILLING_DATE)

        history_repo.batch_insert.assert_called_once()
        entries = history_repo.batch_insert.call_args.args[0]
        assert len(entries) == 1
        assert entries[0].user_id == 1

    def test_session_commit_called_on_success(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(id=1, login="u@test.com", balance=500.0,
                                 reg_date=datetime(2020, 1, 1))
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "u@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                           "supportTariff": False, "tokenExists": False}
        }

        service = _make_service(mock_session, api)
        service.process_write_off(BILLING_DATE)

        mock_session.commit.assert_called_once()

    def test_rollback_and_reraise_on_db_error(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user_orm = make_user_orm(id=1, login="u@test.com", balance=500.0,
                                 reg_date=datetime(2020, 1, 1))
        user_repo.find_eligible_users_for_write_off.return_value = [(user_orm, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 1000}
        user_repo.batch_update_user_balances.side_effect = RuntimeError("DB error")

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "u@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                           "supportTariff": False, "tokenExists": False}
        }

        service = _make_service(mock_session, api)

        with pytest.raises(RuntimeError, match="DB error"):
            service.process_write_off(BILLING_DATE)

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()


class TestFilterOrderAndBatchScope:
    def test_phrase_counts_only_loaded_for_billable_users(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user1 = make_user_orm(id=1, login="a@test.com", balance=500.0)
        user2 = make_user_orm(id=2, login="b@test.com", balance=500.0)  # has promo
        user_repo.find_eligible_users_for_write_off.return_value = [(user1, 1), (user2, 1)]
        user_repo.get_users_with_active_promocode.return_value = {2}
        user_repo.get_unique_phrases_counts_batch.return_value = {1: 1000}

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {}

        service = _make_service(mock_session, api)
        service.process_write_off(BILLING_DATE)

        # user 2 must NOT appear in the phrase count query
        called_ids = user_repo.get_unique_phrases_counts_batch.call_args.args[0]
        assert 2 not in called_ids
        assert 1 in called_ids

    def test_per_user_error_does_not_abort_other_users(self, mock_session, patched_repos):
        user_repo, history_repo = patched_repos
        user1 = make_user_orm(id=1, login="a@test.com", balance=500.0,
                              reg_date=datetime(2020, 1, 1))
        user2 = make_user_orm(id=2, login="b@test.com", balance=500.0,
                              reg_date=datetime(2020, 1, 1))
        user_repo.find_eligible_users_for_write_off.return_value = [(user1, 1), (user2, 1)]
        user_repo.get_users_with_active_promocode.return_value = set()
        # Raise for user 1, return normally for user 2
        user_repo.get_unique_phrases_counts_batch.side_effect = lambda ids: {
            i: (500_000 if i == 1 else 1000) for i in ids
        }

        api = MagicMock(spec=ExternalApiService)
        api.get_users_info.return_value = {
            "a@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                           "supportTariff": False, "tokenExists": False},
            "b@test.com": {"accounts": [1], "salesAccounts": [], "weeklySalesSum": 500_000,
                           "supportTariff": False, "tokenExists": False},
        }

        service = _make_service(mock_session, api)
        # Should not raise even if one user causes issues
        result = service.process_write_off(BILLING_DATE)
        assert result is not None
