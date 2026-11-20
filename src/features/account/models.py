from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin


class Account(BaseDbModelMixin, Base):
    __tablename__ = "account"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
