import uuid

from sqlalchemy.orm import Mapped, mapped_column, relationship, mapped_column
from sqlalchemy import Boolean, ForeignKey, String, Integer, DateTime, func, Text

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin
from datetime import datetime


class GitHubOAuthToken(BaseDbModelMixin, Base):
    __tablename__ = "github_oauth_token"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    access_token: Mapped[str] = mapped_column(String(1024), nullable=False)
    token_type: Mapped[str] = mapped_column(String(64), default="bearer")
    scope: Mapped[str | None] = mapped_column(String(512), nullable=True)
    github_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    github_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User")  # noqa: F821


class ConnectedRepository(BaseDbModelMixin, Base):
    __tablename__ = "connected_repository"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    clone_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    scan_progress: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship("User")  # noqa: F821



class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connected_repo_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("connected_repository.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    path: Mapped[str] = mapped_column(String(2048))
    name: Mapped[str] = mapped_column(String(512))
    extension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())




class FileDependency(Base):
    __tablename__ = "file_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connected_repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_repository.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), index=True
    )
    target_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), index=True
    )
    import_type: Mapped[str] = mapped_column(String(64), default="import")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_file: Mapped["RepositoryFile"] = relationship("RepositoryFile", foreign_keys=[source_file_id])
    target_file: Mapped["RepositoryFile"] = relationship("RepositoryFile", foreign_keys=[target_file_id])




class RepositoryFunction(Base):
    """
    One row per extracted symbol (function, method, or class) found in a
    source file.  Linked to RepositoryFile via file_id.
    """

    __tablename__ = "repository_functions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Ownership / location
    connected_repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_repository.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), index=True
    )

    # Identity
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    qualified_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # "function" | "method" | "class"
    symbol_type: Mapped[str] = mapped_column(String(32), default="function")

    # Signature metadata
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: [{name, type, default}]
    return_type: Mapped[str | None] = mapped_column(String(512), nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted source code (trimmed to MAX_FUNCTION_LINES)
    source_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source location
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Class membership (for methods)
    class_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    is_async: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    file: Mapped["RepositoryFile"] = relationship(  # noqa: F821
        "RepositoryFile", foreign_keys=[file_id]
    )
    outgoing_calls: Mapped[list["FunctionCall"]] = relationship(
        "FunctionCall",
        foreign_keys="FunctionCall.source_function_id",
        back_populates="source_function",
        cascade="all, delete-orphan",
    )
    incoming_calls: Mapped[list["FunctionCall"]] = relationship(
        "FunctionCall",
        foreign_keys="FunctionCall.target_function_id",
        back_populates="target_function",
        cascade="all, delete-orphan",
    )


class FunctionCall(Base):
    """
    Directed edge: source_function calls target_function.
    Both must belong to the same connected repository.
    """

    __tablename__ = "function_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    connected_repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_repository.id", ondelete="CASCADE"), index=True
    )
    source_function_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_functions.id", ondelete="CASCADE"), index=True
    )
    target_function_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_functions.id", ondelete="CASCADE"), index=True
    )

    # Line number in the *source* file where the call appears
    call_line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source_function: Mapped["RepositoryFunction"] = relationship(
        "RepositoryFunction",
        foreign_keys=[source_function_id],
        back_populates="outgoing_calls",
    )
    target_function: Mapped["RepositoryFunction"] = relationship(
        "RepositoryFunction",
        foreign_keys=[target_function_id],
        back_populates="incoming_calls",
    )