import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin


class User(BaseDbModelMixin, Base):
    __tablename__ = "user"

    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
