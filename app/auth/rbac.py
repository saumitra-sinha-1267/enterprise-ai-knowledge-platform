"""Role-Based Access Control (RBAC) engine.

Enforces strict server-side document isolation and permission resolution.
All department and access level boundaries are validated strictly against
the authenticated user's verified token claims, never from client requests.
"""

from typing import Dict, List, Set, Any
from app.auth.models import RoleEnum, DepartmentEnum, AccessLevelEnum, User


# Mapping of Roles to the Departments they are authorized to access.
# Admin has universal access.
# Department-specific users can access their own department plus general documents.
# General employees can only access general documents.
ROLE_DEPARTMENT_PERMISSIONS: Dict[str, Set[str]] = {
    RoleEnum.ADMIN.value: {
        DepartmentEnum.HR.value,
        DepartmentEnum.FINANCE.value,
        DepartmentEnum.ENGINEERING.value,
        DepartmentEnum.GENERAL.value,
    },
    RoleEnum.HR.value: {
        DepartmentEnum.HR.value,
        DepartmentEnum.GENERAL.value,
    },
    RoleEnum.FINANCE.value: {
        DepartmentEnum.FINANCE.value,
        DepartmentEnum.GENERAL.value,
    },
    RoleEnum.ENGINEERING.value: {
        DepartmentEnum.ENGINEERING.value,
        DepartmentEnum.GENERAL.value,
    },
    RoleEnum.EMPLOYEE.value: {
        DepartmentEnum.GENERAL.value,
    },
}

# Mapping of Roles to permitted Access Levels.
# Restricted is reserved for Admin and specialized leads.
ROLE_ACCESS_LEVEL_PERMISSIONS: Dict[str, Set[str]] = {
    RoleEnum.ADMIN.value: {
        AccessLevelEnum.PUBLIC.value,
        AccessLevelEnum.INTERNAL.value,
        AccessLevelEnum.CONFIDENTIAL.value,
        AccessLevelEnum.RESTRICTED.value,
    },
    RoleEnum.HR.value: {
        AccessLevelEnum.PUBLIC.value,
        AccessLevelEnum.INTERNAL.value,
        AccessLevelEnum.CONFIDENTIAL.value,
    },
    RoleEnum.FINANCE.value: {
        AccessLevelEnum.PUBLIC.value,
        AccessLevelEnum.INTERNAL.value,
        AccessLevelEnum.CONFIDENTIAL.value,
    },
    RoleEnum.ENGINEERING.value: {
        AccessLevelEnum.PUBLIC.value,
        AccessLevelEnum.INTERNAL.value,
        AccessLevelEnum.CONFIDENTIAL.value,
    },
    RoleEnum.EMPLOYEE.value: {
        AccessLevelEnum.PUBLIC.value,
        AccessLevelEnum.INTERNAL.value,
    },
}


def get_allowed_departments_for_user(user: User) -> List[str]:
    """Retrieve the list of departments an authenticated user is authorized to query.
    
    Derived strictly from the user's role and assigned department.
    """
    if user.is_superuser or user.role == RoleEnum.ADMIN.value:
        return list(ROLE_DEPARTMENT_PERMISSIONS[RoleEnum.ADMIN.value])
    
    allowed = set(ROLE_DEPARTMENT_PERMISSIONS.get(user.role, {DepartmentEnum.GENERAL.value}))
    # Ensure user's own department is included if valid
    if user.department:
        allowed.add(user.department)
    return sorted(list(allowed))


def get_allowed_access_levels_for_user(user: User) -> List[str]:
    """Retrieve the maximum classification levels permitted for the user."""
    if user.is_superuser or user.role == RoleEnum.ADMIN.value:
        return list(ROLE_ACCESS_LEVEL_PERMISSIONS[RoleEnum.ADMIN.value])
    
    return sorted(list(ROLE_ACCESS_LEVEL_PERMISSIONS.get(user.role, {AccessLevelEnum.PUBLIC.value})))


def can_user_access_document(
    user: User,
    doc_department: str,
    doc_access_level: str,
) -> bool:
    """Validate whether an authenticated user is permitted to read a specific document.
    
    Returns True only if both department and access level are within authorized scopes.
    """
    if user.is_superuser or user.role == RoleEnum.ADMIN.value:
        return True

    allowed_depts = get_allowed_departments_for_user(user)
    if doc_department not in allowed_depts:
        return False

    allowed_levels = get_allowed_access_levels_for_user(user)
    if doc_access_level not in allowed_levels:
        return False

    return True


def can_user_upload_to_department(user: User, target_department: str) -> bool:
    """Validate whether a user is authorized to upload a document to a target department.
    
    Admins can upload to any department.
    Department members can upload to their own department or general.
    Employees cannot upload restricted or department-specific documents.
    """
    if user.is_superuser or user.role == RoleEnum.ADMIN.value:
        return True
    
    if user.role in {RoleEnum.HR.value, RoleEnum.FINANCE.value, RoleEnum.ENGINEERING.value}:
        return target_department in {user.department, DepartmentEnum.GENERAL.value}
    
    # Regular employees can only upload to General
    return target_department == DepartmentEnum.GENERAL.value


def can_user_delete_document(user: User, doc_uploader_id: int, doc_department: str) -> bool:
    """Validate whether a user can delete a document."""
    if user.is_superuser or user.role == RoleEnum.ADMIN.value:
        return True
    
    # Department heads/leads can delete documents in their department if uploaded by them
    if user.role in {RoleEnum.HR.value, RoleEnum.FINANCE.value, RoleEnum.ENGINEERING.value}:
        if doc_department == user.department and user.id == doc_uploader_id:
            return True
            
    return False
