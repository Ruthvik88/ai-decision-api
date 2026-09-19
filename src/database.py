"""
Database configuration, SQLAlchemy engine, session factory, and ORM models.
Uses SQLite as the backing store.
"""

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./decisions.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ---------------------------------------------------------------------------
# Dependency for FastAPI
# ---------------------------------------------------------------------------

def get_db():
    """Yield a database session and ensure it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    tickets = relationship("Ticket", back_populates="owner")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    order_value_inr = Column(Float, nullable=True)
    days_since_delivery = Column(Integer, nullable=True)
    days_since_dispatch = Column(Integer, nullable=True)
    product_type = Column(String, nullable=True)
    opened_status = Column(String, nullable=True)
    order_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="tickets")
    decision = relationship("Decision", back_populates="ticket", uselist=False)


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    action = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    sources = Column(Text, nullable=False)  # stored as JSON string
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    ticket = relationship("Ticket", back_populates="decision")


# ---------------------------------------------------------------------------
# Table creation helper
# ---------------------------------------------------------------------------

def create_tables():
    """Create all tables in the database (idempotent)."""
    Base.metadata.create_all(bind=engine)
