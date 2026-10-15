"""Authentication and Identity endpoints.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.auth.models import User, RoleEnum, DepartmentEnum
from app.auth.schemas import Token, UserLogin, UserCreate, UserResponse
from app.auth.security import verify_password, get_password_hash, create_access_token
from app.auth.rbac import get_allowed_departments_for_user, get_allowed_access_levels_for_user
from app.config import settings
from app.db.init_db import DEMO_USERS
from app.security.audit_log import AuditLogger, EVENT_AUTH_SUCCESS, EVENT_AUTH_FAILURE

router = APIRouter()


@router.post("/login", response_model=Token, summary="User login and JWT token issuance")
def login(
    login_data: Optional[UserLogin] = None,
    form_data: Optional[OAuth2PasswordRequestForm] = Depends(lambda: None),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate user with username and password, returning signed JWT."""
    username = None
    password = None

    if form_data is not None and form_data.username:
        username = form_data.username
        password = form_data.password
    elif login_data is not None:
        username = login_data.username
        password = login_data.password

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password must be provided.",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        AuditLogger.log_event(
            event_type=EVENT_AUTH_FAILURE,
            username=username,
            details={"reason": "Invalid credentials provided"},
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Contact system administrator.",
        )

    access_token = create_access_token(
        subject=user.username,
        user_id=user.id,
        role=user.role,
        department=user.department,
    )

    AuditLogger.log_event(
        event_type=EVENT_AUTH_SUCCESS,
        user_id=user.id,
        username=user.username,
        role=user.role,
        department=user.department,
        success=True,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user_id=user.id,
        username=user.username,
        role=user.role,
        department=user.department,
    )


@router.get("/me", summary="Get current user profile and RBAC permissions")
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the profile, role, and authorized document scopes of the current user."""
    allowed_depts = get_allowed_departments_for_user(current_user)
    allowed_levels = get_allowed_access_levels_for_user(current_user)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department": current_user.department,
        "is_superuser": current_user.is_superuser,
        "authorized_scopes": {
            "departments": allowed_depts,
            "access_levels": allowed_levels,
        },
    }


@router.get("/demo-users", summary="List available demo user personas")
def list_demo_users() -> List[Dict[str, Any]]:
    """Return pre-seeded personas for quick testing and UI role switching."""
    personas = []
    for u in DEMO_USERS:
        personas.append({
            "username": u["username"],
            "password": u["password"],
            "full_name": u["full_name"],
            "role": u["role"],
            "department": u["department"],
            "description": f"Role: {u['role'].capitalize()} | Department: {u['department'].capitalize()}",
        })
    return personas


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Register user")
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Create a new enterprise user."""
    existing_user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username or email already exists.",
        )

    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role.value,
        department=user_in.department.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
