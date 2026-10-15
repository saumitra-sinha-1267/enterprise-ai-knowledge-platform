"""Security and RBAC tests proving strict server-side document isolation.

Validates that unauthorized chunks NEVER enter retrieval results or LLM contexts.
"""

import pytest
from app.auth.models import RoleEnum, DepartmentEnum, AccessLevelEnum, User
from app.auth.rbac import (
    get_allowed_departments_for_user,
    get_allowed_access_levels_for_user,
    can_user_access_document,
    can_user_upload_to_department,
)
from app.generation.rag_chain import rag_chain
from app.retrieval.search import retrieve_relevant_chunks


def test_rbac_permission_mappings(test_users):
    """Verify department and access level boundaries for all roles."""
    hr_user = test_users["hr_user"]
    finance_user = test_users["finance_user"]
    eng_user = test_users["eng_user"]
    emp_user = test_users["employee_user"]
    admin = test_users["admin"]

    # HR role
    assert set(get_allowed_departments_for_user(hr_user)) == {"hr", "general"}
    assert "finance" not in get_allowed_departments_for_user(hr_user)
    assert "engineering" not in get_allowed_departments_for_user(hr_user)

    # Finance role
    assert set(get_allowed_departments_for_user(finance_user)) == {"finance", "general"}
    assert "hr" not in get_allowed_departments_for_user(finance_user)
    assert "engineering" not in get_allowed_departments_for_user(finance_user)

    # Engineering role
    assert set(get_allowed_departments_for_user(eng_user)) == {"engineering", "general"}
    assert "hr" not in get_allowed_departments_for_user(eng_user)
    assert "finance" not in get_allowed_departments_for_user(eng_user)

    # General Employee role
    assert set(get_allowed_departments_for_user(emp_user)) == {"general"}
    assert "hr" not in get_allowed_departments_for_user(emp_user)
    assert "finance" not in get_allowed_departments_for_user(emp_user)

    # Admin role
    assert set(get_allowed_departments_for_user(admin)) == {"hr", "finance", "engineering", "general"}


def test_document_access_evaluation(test_users):
    """Verify boolean can_user_access_document predicate."""
    hr_user = test_users["hr_user"]
    finance_user = test_users["finance_user"]

    # HR user checks
    assert can_user_access_document(hr_user, "hr", "internal") is True
    assert can_user_access_document(hr_user, "general", "public") is True
    assert can_user_access_document(hr_user, "finance", "confidential") is False
    assert can_user_access_document(hr_user, "engineering", "internal") is False

    # Finance user checks
    assert can_user_access_document(finance_user, "finance", "confidential") is True
    assert can_user_access_document(finance_user, "hr", "internal") is False


def test_hr_user_cannot_retrieve_finance_budget(test_users):
    """PROVE that an HR user CANNOT retrieve Finance documents via semantic search."""
    hr_user = test_users["hr_user"]
    query = "What is the Q3 cloud infrastructure operational expenditure budget allocation?"

    # Execute search under HR user's credentials
    chunks = retrieve_relevant_chunks(query=query, user=hr_user, top_k=5)

    # Assert no chunks from Finance department are returned
    for c in chunks:
        assert c.department != "finance", f"Security violation: HR retrieved Finance chunk: {c.filename}"


def test_finance_user_cannot_retrieve_engineering_architecture(test_users):
    """PROVE that a Finance user CANNOT retrieve Engineering microservices architecture docs."""
    finance_user = test_users["finance_user"]
    query = "How does Kong API gateway handle rate limiting and gRPC communication?"

    chunks = retrieve_relevant_chunks(query=query, user=finance_user, top_k=5)

    for c in chunks:
        assert c.department != "engineering", f"Security violation: Finance retrieved Engineering chunk: {c.filename}"


def test_employee_cannot_retrieve_hr_or_finance_confidential(test_users):
    """PROVE that a general employee CANNOT retrieve HR policies or Finance budgets."""
    emp_user = test_users["employee_user"]

    # Query HR
    hr_chunks = retrieve_relevant_chunks(query="How many weeks of paid parental leave are offered?", user=emp_user)
    for c in hr_chunks:
        assert c.department != "hr"

    # Query Finance
    fin_chunks = retrieve_relevant_chunks(query="What are the Coupa procurement thresholds for VP sign-off?", user=emp_user)
    for c in fin_chunks:
        assert c.department != "finance"


def test_admin_can_retrieve_all_departments(test_users):
    """PROVE that Admin can retrieve documents across all departments."""
    admin_user = test_users["admin"]

    hr_chunks = retrieve_relevant_chunks(query="parental leave policy", user=admin_user)
    assert any(c.department == "hr" for c in hr_chunks)

    fin_chunks = retrieve_relevant_chunks(query="Q3 cloud infrastructure budget", user=admin_user)
    assert any(c.department == "finance" for c in fin_chunks)


def test_unauthorized_upload_rejected_at_server(client, auth_headers):
    """PROVE that an employee attempting to upload to HR or Finance is rejected with 403."""
    sample_file_content = b"This is an unauthorized document payload."

    # Employee tries to upload to HR
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("unauthorized_hr.txt", sample_file_content, "text/plain")},
        data={"department": "hr", "access_level": "confidential"},
        headers=auth_headers["employee_user"],
    )
    assert response.status_code == 403
    assert "not authorized to upload documents" in response.json()["detail"]


def test_rag_end_to_end_context_isolation(test_users):
    """PROVE that when HR asks about Finance secrets, the LLM context has ZERO finance facts."""
    hr_user = test_users["hr_user"]
    finance_question = "What is the exact Q3 AWS and GCP cloud infrastructure budget?"

    rag_response = rag_chain.answer_question(question=finance_question, user=hr_user)

    # Must NOT have any finance citations
    for cit in rag_response.citations:
        assert cit.department != "finance"

    # Because no matching documents exist in HR's scope, system must return insufficient info
    assert "sufficient information was not found" in rag_response.answer.lower()
