"""
SQLAlchemy ORM-mapped classes — one per database table.
These are the only place that knows about column names and types.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, DateTime, Float, ForeignKey,
    Integer, SmallInteger, String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.database import Base


class UserOrm(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0)
    confirmed: Mapped[int] = mapped_column(Integer, default=0)
    regDate: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    projects: Mapped[int] = mapped_column(Integer, default=0)
    queries: Mapped[int] = mapped_column(Integer, default=0)
    unic_queries: Mapped[int] = mapped_column(Integer, default=0)
    projects_ozon: Mapped[int] = mapped_column(Integer, default=0)
    queries_ozon: Mapped[int] = mapped_column(Integer, default=0)
    unic_queries_ozon: Mapped[int] = mapped_column(Integer, default=0)
    salesMonth: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unlimitedBalance: Mapped[int] = mapped_column(SmallInteger, default=0)
    tariffStatus: Mapped[int] = mapped_column(Integer, default=0)
    wbKey: Mapped[Optional[str]] = mapped_column(String(1500), nullable=True)
    promocode: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pass2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    projects_rel: Mapped[list["ProjectOrm"]] = relationship(
        "ProjectOrm", back_populates="user", lazy="noload"
    )
    user_promocodes: Mapped[list["UserPromocodeOrm"]] = relationship(
        "UserPromocodeOrm", back_populates="user", lazy="noload"
    )


class ProjectOrm(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dt2: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["UserOrm"] = relationship("UserOrm", back_populates="projects_rel")
    phrases: Mapped[list["ProjectListPhraseOrm"]] = relationship(
        "ProjectListPhraseOrm", back_populates="project", lazy="noload"
    )


class ProjectListPhraseOrm(Base):
    __tablename__ = "project_list_phrase"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idProject: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    idPhrase: Mapped[int] = mapped_column(Integer, nullable=False)
    tech: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["ProjectOrm"] = relationship("ProjectOrm", back_populates="phrases")


class PromocodeOrm(Base):
    """Master promocode definitions (table: promocode)."""
    __tablename__ = "promocode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(132), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)  # duration in days
    active: Mapped[int] = mapped_column(Integer, default=0)
    createAt: Mapped[int] = mapped_column(BigInteger, default=0)
    modifyAt: Mapped[int] = mapped_column(BigInteger, default=0)

    user_promocodes: Mapped[list["UserPromocodeOrm"]] = relationship(
        "UserPromocodeOrm", back_populates="promocode_def"
    )


class UserPromocodeOrm(Base):
    """Per-user promocode assignments (table: promocodes)."""
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=False)
    dt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    promocode_id: Mapped[int] = mapped_column(Integer, ForeignKey("promocode.id"), nullable=False)

    user: Mapped["UserOrm"] = relationship("UserOrm", back_populates="user_promocodes")
    promocode_def: Mapped["PromocodeOrm"] = relationship(
        "PromocodeOrm", back_populates="user_promocodes"
    )


class HistoryOrm(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    dt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    txt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
