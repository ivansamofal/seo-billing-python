from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class User:
    id: int
    login: str
    balance: float
    confirmed: int
    regDate: Optional[datetime]
    projects: int
    queries: int
    unic_queries: int
    projects_ozon: int
    queries_ozon: int
    unic_queries_ozon: int
    salesMonth: int
    blocked: int
    unlimitedBalance: int
    tariffStatus: int
    wbKey: Optional[str]
    promocode: Optional[str]
    pass2: Optional[str]


@dataclass
class UserWithProjects:
    user: User
    project_count: int = 0

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def login(self) -> str:
        return self.user.login

    @property
    def balance(self) -> float:
        return self.user.balance

    @property
    def confirmed(self) -> int:
        return self.user.confirmed

    @property
    def regDate(self) -> Optional[datetime]:
        return self.user.regDate

    @property
    def unic_queries(self) -> int:
        return self.user.unic_queries

    @property
    def salesMonth(self) -> int:
        return self.user.salesMonth

    @property
    def tariffStatus(self) -> int:
        return self.user.tariffStatus

    @property
    def wbKey(self) -> Optional[str]:
        return self.user.wbKey

    @property
    def pass2(self) -> Optional[str]:
        return self.user.pass2
