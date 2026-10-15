"""Pytest fixtures for Enterprise AI Knowledge Platform test suite.
"""

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.auth.models import Base, User, RoleEnum, DepartmentEnum
from app.auth.security import get_password_hash, create_access_token
from app.api.deps import get_db
from app.main import app

# In-memory SQLite database for test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all database tables for test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a transactional database session per test function."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_users(db_session):
    """Create test users representing all core enterprise roles and departments."""
    users = {}
    personas = [
        ("admin", "admin@enterprise.internal", RoleEnum.ADMIN.value, DepartmentEnum.GENERAL.value, True),
        ("hr_user", "hr@enterprise.internal", RoleEnum.HR.value, DepartmentEnum.HR.value, False),
        ("finance_user", "finance@enterprise.internal", RoleEnum.FINANCE.value, DepartmentEnum.FINANCE.value, False),
        ("eng_user", "eng@enterprise.internal", RoleEnum.ENGINEERING.value, DepartmentEnum.ENGINEERING.value, False),
        ("employee_user", "employee@enterprise.internal", RoleEnum.EMPLOYEE.value, DepartmentEnum.GENERAL.value, False),
    ]

    for username, email, role, dept, is_super in personas:
        user = User(
            username=username,
            email=email,
            full_name=f"Test {username.capitalize()}",
            hashed_password=get_password_hash("TestPassword123!"),
            role=role,
            department=dept,
            is_active=True,
            is_superuser=is_super,
        )
        db_session.add(user)
        db_session.flush()
        users[username] = user

    db_session.commit()
    return users


@pytest.fixture
def auth_headers(test_users):
    """Provide valid Authorization bearer headers for each test persona."""
    headers = {}
    for username, user in test_users.items():
        token = create_access_token(
            subject=user.username,
            user_id=user.id,
            role=user.role,
            department=user.department,
        )
        headers[username] = {"Authorization": f"Bearer {token}"}
    return headers
