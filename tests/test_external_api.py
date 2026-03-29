from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.services.external_api_service import ExternalApiService


@pytest.fixture
def api():
    return ExternalApiService()


class TestGetUsersInfo:
    def test_returns_dict_keyed_by_email(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"email": "a@test.com", "accounts": [], "weeklySalesSum": 0},
            {"email": "b@test.com", "accounts": [1, 2], "weeklySalesSum": 50000},
        ]

        with patch("httpx.post", return_value=mock_response):
            result = api.get_users_info(["a@test.com", "b@test.com"])

        assert "a@test.com" in result
        assert "b@test.com" in result
        assert result["b@test.com"]["accounts"] == [1, 2]

    def test_empty_emails_returns_empty_dict_without_http_call(self, api):
        with patch("httpx.post") as mock_post:
            result = api.get_users_info([])

        assert result == {}
        mock_post.assert_not_called()

    def test_non_list_response_returns_empty_dict(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "object"}

        with patch("httpx.post", return_value=mock_response):
            result = api.get_users_info(["a@test.com"])

        assert result == {}

    def test_items_without_email_key_are_skipped(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"email": "a@test.com", "accounts": []},
            {"no_email_field": True},
        ]

        with patch("httpx.post", return_value=mock_response):
            result = api.get_users_info(["a@test.com"])

        assert list(result.keys()) == ["a@test.com"]

    def test_http_error_returns_empty_dict(self, api):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.post", return_value=mock_response):
            result = api.get_users_info(["a@test.com"])

        assert result == {}

    def test_network_error_returns_empty_dict(self, api):
        with patch("httpx.post", side_effect=httpx.ConnectError("connection refused")):
            result = api.get_users_info(["a@test.com"])

        assert result == {}

    def test_sends_correct_payload(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = []

        with patch("httpx.post", return_value=mock_response) as mock_post:
            api.get_users_info(["x@test.com", "y@test.com"])

        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"emails": ["x@test.com", "y@test.com"]}

    def test_uses_basic_auth_with_token(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = []

        with patch("httpx.post", return_value=mock_response) as mock_post:
            api.get_users_info(["x@test.com"])

        _, kwargs = mock_post.call_args
        token, password = kwargs["auth"]
        assert token == "test_token"
        assert password == ""


class TestCheckTokenExists:
    def test_returns_true_when_token_exists(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {"tokenExists": True}

        with patch("httpx.post", return_value=mock_response):
            result = api.check_token_exists("user@test.com")

        assert result is True

    def test_returns_false_when_token_absent(self, api):
        mock_response = MagicMock()
        mock_response.json.return_value = {"tokenExists": False}

        with patch("httpx.post", return_value=mock_response):
            result = api.check_token_exists("user@test.com")

        assert result is False

    def test_returns_false_on_http_error(self, api):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.post", return_value=mock_response):
            result = api.check_token_exists("user@test.com")

        assert result is False

    def test_returns_false_on_network_error(self, api):
        with patch("httpx.post", side_effect=Exception("timeout")):
            result = api.check_token_exists("user@test.com")

        assert result is False
