import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin
from src.features.account.enums import AccountRole


class User(BaseDbModelMixin, Base):
    __tablename__ = "user"

    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), index=True, nullable=True
    )
    account_role: Mapped[AccountRole] = mapped_column(
        SAEnum(
            AccountRole,
            name="account_role",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=AccountRole.MEMBER,
        server_default=text("'member'"),
        nullable=False,
    )
