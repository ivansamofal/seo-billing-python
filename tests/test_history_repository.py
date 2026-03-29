from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.history import HistoryEntry
from src.repositories.history_repository import HistoryRepository
from tests.conftest import make_history_entry


class TestBatchInsert:
    def test_calls_session_execute(self, mock_session):
        repo = HistoryRepository(mock_session)
        entries = [make_history_entry(user_id=1, amount=217)]

        repo.batch_insert(entries)

        mock_session.execute.assert_called_once()

    def test_empty_list_skips_execute(self, mock_session):
        repo = HistoryRepository(mock_session)
        repo.batch_insert([])

        mock_session.execute.assert_not_called()

    def test_amount_is_stored_as_negative(self, mock_session):
        repo = HistoryRepository(mock_session)
        entries = [make_history_entry(user_id=1, amount=500)]

        repo.batch_insert(entries)

        _, kwargs = mock_session.execute.call_args
        # Second arg to execute() is the list of row dicts
        row_dicts = mock_session.execute.call_args.args[1]
        assert row_dicts[0]["amount"] == -500

    def test_multiple_entries_passed_as_list(self, mock_session):
        repo = HistoryRepository(mock_session)
        entries = [
            make_history_entry(user_id=1, amount=217),
            make_history_entry(user_id=2, amount=437),
            make_history_entry(user_id=3, amount=917),
        ]

        repo.batch_insert(entries)

        row_dicts = mock_session.execute.call_args.args[1]
        assert len(row_dicts) == 3
        assert {r["user_id"] for r in row_dicts} == {1, 2, 3}

    def test_row_fields_are_correct(self, mock_session):
        dt = datetime(2024, 3, 15)
        entry = HistoryEntry(
            user_id=7,
            dt=dt,
            txt="Списание абоненсткой платы",
            amount=300,
            hint="7 / 1000 / 3 / 2",
        )
        repo = HistoryRepository(mock_session)
        repo.batch_insert([entry])

        row = mock_session.execute.call_args.args[1][0]
        assert row["user_id"] == 7
        assert row["dt"] == dt
        assert row["txt"] == "Списание абоненсткой платы"
        assert row["amount"] == -300
        assert row["hint"] == "7 / 1000 / 3 / 2"
