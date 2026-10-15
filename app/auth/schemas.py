"""Pydantic schemas for authentication and user accounts.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from app.auth.models import RoleEnum, DepartmentEnum, AccessLevelEnum


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user_id: int
    username: str
    role: str
    department: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    department: Optional[str] = None
    exp: Optional[int] = None


class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)


class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    role: RoleEnum = RoleEnum.EMPLOYEE
    department: DepartmentEnum = DepartmentEnum.GENERAL


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: str
    department: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
