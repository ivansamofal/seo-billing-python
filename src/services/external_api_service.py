import logging
from typing import Dict, List, Optional

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10


class ExternalApiService:
    def __init__(self):
        self._base_url = settings.BM_COMMON_API_URL.rstrip("/")
        self._token = settings.BM_COMMON_API_TOKEN
        self._auth = (self._token, "")  # Basic auth: token as username, empty password

    def get_users_info(self, emails: List[str]) -> Dict[str, dict]:
        if not emails:
            return {}

        url = f"{self._base_url}/auth/auth/seo/infos"
        try:
            response = httpx.post(
                url,
                json={"emails": emails},
                auth=self._auth,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            # Expected: list of user objects with an "email" key
            if isinstance(data, list):
                return {item["email"]: item for item in data if "email" in item}
            return {}
        except Exception as exc:
            logger.warning("Failed to fetch users info from BM Common API: %s", exc)
            return {}

    def check_token_exists(self, email: str) -> bool:
        url = f"{self._base_url}/user/users/seo_token_exists"
        try:
            response = httpx.post(
                url,
                json={"email": email},
                auth=self._auth,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            return bool(data.get("tokenExists", False))
        except Exception as exc:
            logger.warning("Failed to check token for %s: %s", email, exc)
            return False
