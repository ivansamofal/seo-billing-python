import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set

from src.config.settings import settings
from src.models.user import UserWithProjects

logger = logging.getLogger(__name__)


class UserEligibilityFilter:
    """Filters users that should be excluded from a billing run."""

    def filter_bonus_period(
        self,
        users: List[UserWithProjects],
        users_data: Dict[str, dict],
        billing_dt: datetime,
    ) -> List[UserWithProjects]:
        result = []
        for user in users:
            if not user.regDate:
                result.append(user)
                continue
            token_exists = bool(users_data.get(user.login, {}).get("tokenExists", False))
            bonus_days = settings.FREE_DAYS_API_ENTERED if token_exists else settings.FREE_DAYS
            if billing_dt < user.regDate + timedelta(days=bonus_days):
                logger.debug("User %d is in bonus period, skipping", user.id)
            else:
                result.append(user)
        return result

    def filter_promo(
        self,
        users: List[UserWithProjects],
        promo_user_ids: Set[int],
    ) -> List[UserWithProjects]:
        result = []
        for user in users:
            if user.id in promo_user_ids:
                logger.debug("User %d has active promocode, skipping", user.id)
            else:
                result.append(user)
        return result
