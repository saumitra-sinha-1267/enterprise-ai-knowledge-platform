"""Authentication and RBAC database models.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base SQLAlchemy declarative class."""
    pass


class RoleEnum(str, Enum):
    ADMIN = "admin"
    HR = "hr"
    FINANCE = "finance"
    ENGINEERING = "engineering"
    EMPLOYEE = "employee"


class DepartmentEnum(str, Enum):
    HR = "hr"
    FINANCE = "finance"
    ENGINEERING = "engineering"
    GENERAL = "general"


class AccessLevelEnum(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class User(Base):
    """User account model with department and role assignment."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Primary Role & Department
    role: Mapped[str] = mapped_column(String(50), default=RoleEnum.EMPLOYEE.value, nullable=False)
    department: Mapped[str] = mapped_column(String(50), default=DepartmentEnum.GENERAL.value, nullable=False)
    
    # Account status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}' department='{self.department}'>"
