"""Integration tests for RAG pipeline, factual grounding, and citation generation.
"""

import pytest
from app.generation.rag_chain import rag_chain, NOT_FOUND_MESSAGE


def test_grounded_hr_answer_with_citations(test_users):
    """Verify factual grounding and citation generation for HR question."""
    hr_user = test_users["hr_user"]
    question = "How many weeks of paid parental leave are offered to caregivers?"

    response = rag_chain.answer_question(question=question, user=hr_user)

    assert response.is_grounded is True
    assert "16 weeks" in response.answer or "parental leave" in response.answer
    assert len(response.citations) > 0

    top_citation = response.citations[0]
    assert "hr_leave_and_benefits_policy.txt" in top_citation.filename
    assert top_citation.department == "hr"
    assert top_citation.similarity_score > 0.0
    assert len(top_citation.snippet) > 10


def test_grounded_finance_answer_with_citations(test_users):
    """Verify factual grounding for Finance operational budget query."""
    finance_user = test_users["finance_user"]
    question = "What is the Q3 budget allocation for Cloud Infrastructure and Data Centers?"

    response = rag_chain.answer_question(question=question, user=finance_user)

    assert response.is_grounded is True
    assert "$4,200,000" in response.answer or "4.2" in response.answer or "cloud" in response.answer.lower()
    assert len(response.citations) > 0
    assert "finance_q3_budget_and_procurement.txt" in response.citations[0].filename


def test_unsupported_out_of_scope_question(test_users):
    """Verify that questions not answered in documents trigger explicit fallback without hallucinations."""
    admin_user = test_users["admin"]
    question = "What is the average flight speed of an African swallow carrying a coconut?"

    response = rag_chain.answer_question(question=question, user=admin_user)

    # Must explicitly state sufficient information was not found
    assert NOT_FOUND_MESSAGE in response.answer or "sufficient information was not found" in response.answer.lower()
    assert response.is_grounded is False


def test_empty_query_handling(test_users):
    """Verify system handles whitespace or empty query strings gracefully."""
    admin_user = test_users["admin"]
    response = rag_chain.answer_question(question="   ", user=admin_user)
    assert NOT_FOUND_MESSAGE in response.answer
