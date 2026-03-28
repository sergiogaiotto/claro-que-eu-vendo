"""Modelos de banco de dados e setup SQLAlchemy."""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # root, admin, user
    display_name = Column(String(200), nullable=False, default="")
    profile_description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    pitches = relationship("Pitch", back_populates="user", cascade="all, delete-orphan")


class Pitch(Base):
    __tablename__ = "pitches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_name = Column(String(300), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="pitches")
    interactions = relationship(
        "PitchInteraction", back_populates="pitch",
        cascade="all, delete-orphan", order_by="PitchInteraction.created_at",
    )


class PitchInteraction(Base):
    __tablename__ = "pitch_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pitch_id = Column(Integer, ForeignKey("pitches.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    liked = Column(Boolean, nullable=True, default=None)  # None=sem avaliação, True=gostei, False=não gostei
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    pitch = relationship("Pitch", back_populates="interactions")


class CatalogProduct(Base):
    __tablename__ = "catalog_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Text, nullable=False, default="{}")  # JSON com campos dinâmicos
    created_at = Column(DateTime, default=datetime.utcnow)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        cfg = get_settings()
        db_dir = os.path.dirname(cfg.database_url.replace("sqlite:///", ""))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        _engine = create_engine(cfg.database_url, connect_args={"check_same_thread": False})
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_db():
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
