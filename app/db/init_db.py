"""Database schema creation and initial demo user seeding.
"""

import logging
from sqlalchemy.orm import Session

from app.auth.models import Base, User, RoleEnum, DepartmentEnum
from app.auth.security import get_password_hash
from app.db.session import engine, SessionLocal
# Ensure all models are imported so Base.metadata knows about them
import app.models.document

logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@enterprise.internal",
        "full_name": "System Administrator",
        "password": "AdminPassword123!",
        "role": RoleEnum.ADMIN.value,
        "department": DepartmentEnum.GENERAL.value,
        "is_superuser": True,
    },
    {
        "username": "hr_manager",
        "email": "hr.director@enterprise.internal",
        "full_name": "Helena Ross (HR Lead)",
        "password": "HrPassword123!",
        "role": RoleEnum.HR.value,
        "department": DepartmentEnum.HR.value,
        "is_superuser": False,
    },
    {
        "username": "finance_lead",
        "email": "frank.fin@enterprise.internal",
        "full_name": "Frank Fletcher (Finance Director)",
        "password": "FinancePassword123!",
        "role": RoleEnum.FINANCE.value,
        "department": DepartmentEnum.FINANCE.value,
        "is_superuser": False,
    },
    {
        "username": "engineer_lead",
        "email": "edward.eng@enterprise.internal",
        "full_name": "Edward Miller (Staff Engineer)",
        "password": "EngineeringPassword123!",
        "role": RoleEnum.ENGINEERING.value,
        "department": DepartmentEnum.ENGINEERING.value,
        "is_superuser": False,
    },
    {
        "username": "employee_alice",
        "email": "alice.emp@enterprise.internal",
        "full_name": "Alice Standard (General Staff)",
        "password": "EmployeePassword123!",
        "role": RoleEnum.EMPLOYEE.value,
        "department": DepartmentEnum.GENERAL.value,
        "is_superuser": False,
    },
]


def init_db(db: Session = None) -> None:
    """Create all tables and seed default enterprise accounts if they do not exist."""
    Base.metadata.create_all(bind=engine)
    
    close_at_end = False
    if db is None:
        db = SessionLocal()
        close_at_end = True
        
    try:
        for user_data in DEMO_USERS:
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            if not existing:
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=get_password_hash(user_data["password"]),
                    role=user_data["role"],
                    department=user_data["department"],
                    is_active=True,
                    is_superuser=user_data.get("is_superuser", False),
                )
                db.add(user)
                logger.info(f"Seeded demo user: {user.username} (role: {user.role}, dept: {user.department})")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error during database initialization: {e}")
        raise
    finally:
        if close_at_end:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database initialized and demo users seeded successfully.")
