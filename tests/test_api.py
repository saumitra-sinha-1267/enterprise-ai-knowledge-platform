"""Integration tests for FastAPI endpoints and OpenAPI routing.
"""

import pytest


def test_root_endpoint(client):
    """Verify service root returns operational banner."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "Enterprise AI Knowledge Platform" in data["service"]


def test_health_check_endpoint(client):
    """Verify health probe checks database and vector store."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "healthy"
    assert data["vector_store"]["status"] == "healthy"


def test_demo_users_endpoint(client):
    """Verify demo user personas list is accessible."""
    response = client.get("/api/v1/auth/demo-users")
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 5
    usernames = [u["username"] for u in users]
    assert "admin" in usernames
    assert "hr_manager" in usernames
    assert "finance_lead" in usernames


def test_rag_query_api_endpoint(client, auth_headers):
    """Verify end-to-end question answering endpoint via HTTP client."""
    response = client.post(
        "/api/v1/rag/query",
        json={"query": "What is the policy regarding paid time off and carryover days?"},
        headers=auth_headers["hr_user"],
    )
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "answer" in data
    assert "citations" in data
    assert len(data["citations"]) > 0
    assert "hr_leave_and_benefits_policy.txt" in data["citations"][0]["filename"]


def test_search_preview_api_endpoint(client, auth_headers):
    """Verify search preview endpoint returns chunks without generation."""
    response = client.post(
        "/api/v1/rag/search-preview",
        json={"query": "Kubernetes and Istio service mesh mTLS", "top_k": 3},
        headers=auth_headers["eng_user"],
    )
    assert response.status_code == 200
    chunks = response.json()
    assert len(chunks) > 0
    assert all(c["department"] in ["engineering", "general"] for c in chunks)


def test_document_listing_filtered_by_user_department(client, auth_headers):
    """Verify /documents/ listing returns only documents allowed for current user."""
    # HR user listing
    hr_resp = client.get("/api/v1/documents/", headers=auth_headers["hr_user"])
    assert hr_resp.status_code == 200
    hr_docs = hr_resp.json()
    assert all(d["department"] in ["hr", "general"] for d in hr_docs)
    assert not any(d["department"] == "finance" for d in hr_docs)

    # General Employee listing
    emp_resp = client.get("/api/v1/documents/", headers=auth_headers["employee_user"])
    assert emp_resp.status_code == 200
    emp_docs = emp_resp.json()
    assert all(d["department"] == "general" for d in emp_docs)
