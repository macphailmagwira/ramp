import enum


class AccountRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
