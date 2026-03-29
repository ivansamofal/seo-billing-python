from unittest.mock import MagicMock, call, patch

import pytest

from tests.conftest import make_user_orm
from src.repositories.user_repository import UserRepository


class TestFindEligibleUsers:
    def test_returns_list_of_tuples(self, mock_session):
        orm_user = make_user_orm(id=1, login="a@test.com")
        mock_session.query.return_value \
            .outerjoin.return_value \
            .filter.return_value \
            .group_by.return_value \
            .all.return_value = [(orm_user, 3)]

        repo = UserRepository(mock_session)
        result = repo.find_eligible_users_for_write_off()

        assert len(result) == 1
        user, count = result[0]
        assert user.id == 1
        assert count == 3

    def test_returns_empty_list_when_no_users(self, mock_session):
        mock_session.query.return_value \
            .outerjoin.return_value \
            .filter.return_value \
            .group_by.return_value \
            .all.return_value = []

        repo = UserRepository(mock_session)
        result = repo.find_eligible_users_for_write_off()

        assert result == []


class TestGetUniquePhrasesCountsBatch:
    def test_returns_dict_with_counts(self, mock_session):
        mock_session.query.return_value \
            .join.return_value \
            .filter.return_value \
            .group_by.return_value \
            .all.return_value = [(1, 500), (2, 1200)]

        repo = UserRepository(mock_session)
        result = repo.get_unique_phrases_counts_batch([1, 2, 3])

        assert result[1] == 500
        assert result[2] == 1200
        assert result[3] == 0  # user with no phrases defaults to 0

    def test_empty_input_returns_empty_dict(self, mock_session):
        repo = UserRepository(mock_session)
        result = repo.get_unique_phrases_counts_batch([])

        assert result == {}
        mock_session.query.assert_not_called()

    def test_all_users_default_to_zero_when_no_phrases(self, mock_session):
        mock_session.query.return_value \
            .join.return_value \
            .filter.return_value \
            .group_by.return_value \
            .all.return_value = []  # no phrases at all

        repo = UserRepository(mock_session)
        result = repo.get_unique_phrases_counts_batch([1, 2])

        assert result == {1: 0, 2: 0}


class TestGetUsersWithActivePromocode:
    def test_returns_set_of_user_ids(self, mock_session):
        row1, row2 = MagicMock(user_id=10), MagicMock(user_id=20)
        mock_session.query.return_value \
            .join.return_value \
            .filter.return_value \
            .distinct.return_value \
            .all.return_value = [row1, row2]

        repo = UserRepository(mock_session)
        result = repo.get_users_with_active_promocode([10, 20, 30])

        assert result == {10, 20}

    def test_empty_input_returns_empty_set(self, mock_session):
        repo = UserRepository(mock_session)
        result = repo.get_users_with_active_promocode([])

        assert result == set()
        mock_session.query.assert_not_called()

    def test_no_active_promos_returns_empty_set(self, mock_session):
        mock_session.query.return_value \
            .join.return_value \
            .filter.return_value \
            .distinct.return_value \
            .all.return_value = []

        repo = UserRepository(mock_session)
        result = repo.get_users_with_active_promocode([1, 2, 3])

        assert result == set()


class TestBatchUpdateUserBalances:
    def test_executes_four_sql_statements(self, mock_session):
        repo = UserRepository(mock_session)
        repo.batch_update_user_balances([{"user_id": 1, "amount": 217}])

        # CREATE, DELETE, INSERT, UPDATE, DROP = 5 execute calls
        assert mock_session.execute.call_count == 5

    def test_empty_updates_skips_all_sql(self, mock_session):
        repo = UserRepository(mock_session)
        repo.batch_update_user_balances([])

        mock_session.execute.assert_not_called()

    def test_insert_contains_user_id_and_amount(self, mock_session):
        repo = UserRepository(mock_session)
        repo.batch_update_user_balances([
            {"user_id": 42, "amount": 500},
            {"user_id": 99, "amount": 217},
        ])

        all_sql = " ".join(
            str(c.args[0]) for c in mock_session.execute.call_args_list
        )
        assert "42" in all_sql
        assert "500" in all_sql
        assert "99" in all_sql
        assert "217" in all_sql

    def test_update_uses_greatest_to_prevent_negative_balance(self, mock_session):
        repo = UserRepository(mock_session)
        repo.batch_update_user_balances([{"user_id": 1, "amount": 100}])

        update_call = mock_session.execute.call_args_list[3]  # 4th call is UPDATE
        assert "GREATEST" in str(update_call.args[0])
