"""
Declarative base for all SQLAlchemy models.

Import every model module here so Alembic autogenerate can discover them.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so they are registered on Base.metadata for Alembic autogenerate.
from app.models import economic, market, system  # noqa: E402,F401
