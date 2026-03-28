from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UserWithProjects:
    """Domain model: user fields relevant to billing, plus aggregated project count."""
    id: int
    login: str
    balance: float
    confirmed: int
    regDate: Optional[datetime]
    unic_queries: int
    salesMonth: int
    tariffStatus: int
    wbKey: Optional[str]
    pass2: Optional[str]
    project_count: int
