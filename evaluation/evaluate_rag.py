"""Quantitative evaluation framework for RAG retrieval quality, answer faithfulness, and RBAC isolation.
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import sys
from typing import Dict, List, Any

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.auth.models import User, RoleEnum, DepartmentEnum
from app.generation.rag_chain import rag_chain, NOT_FOUND_MESSAGE
from app.retrieval.search import retrieve_relevant_chunks

logger = logging.getLogger("evaluate_rag")


@dataclass
class EvaluationMetrics:
    total_test_cases: int
    hit_at_k: float  # Top-k retrieval hit rate
    mrr: float  # Mean Reciprocal Rank
    groundedness_rate: float  # Answer contains expected facts
    rbac_isolation_rate: float  # 1.0 = zero cross-department data leakage
    prompt_injection_defense_rate: float
    unsupported_rejection_rate: float


class RAGEvaluator:
    """Evaluates information retrieval precision, answer groundedness, and security boundaries."""

    def __init__(self, dataset_path: Path):
        with open(dataset_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.test_cases = self.data["test_cases"]

    def run_evaluation(self, test_users_map: Dict[str, User]) -> Dict[str, Any]:
        """Execute automated benchmark test cases."""
        retrieval_hits = 0
        reciprocal_ranks = []
        grounded_count = 0
        domain_case_count = 0

        rbac_checks_total = 0
        rbac_checks_passed = 0

        injection_checks_total = 0
        injection_checks_passed = 0

        unsupported_checks_total = 0
        unsupported_checks_passed = 0

        case_results = []

        for tc in self.test_cases:
            cat = tc["category"]
            query = tc["query"]
            target_doc = tc.get("target_document")
            expected_keywords = tc.get("expected_keywords", [])

            # 1. Domain Grounding & Retrieval Precision (Authorized Persona)
            if cat == "domain_grounding":
                domain_case_count += 1
                auth_role = tc["authorized_roles"][-1]  # Department specialist
                user = test_users_map.get(auth_role)
                if not user:
                    user = test_users_map["admin"]

                # Evaluate retrieval
                retrieved = retrieve_relevant_chunks(query=query, user=user, top_k=4)
                hit = False
                rank = 0
                for idx, chunk in enumerate(retrieved, 1):
                    if target_doc and target_doc in chunk.filename:
                        hit = True
                        rank = idx
                        break

                if hit:
                    retrieval_hits += 1
                    reciprocal_ranks.append(1.0 / rank)
                else:
                    reciprocal_ranks.append(0.0)

                # Evaluate Generation & Groundedness
                response = rag_chain.answer_question(question=query, user=user)
                has_keywords = any(kw.lower() in response.answer.lower() for kw in expected_keywords)
                if response.is_grounded and has_keywords:
                    grounded_count += 1

                case_results.append({
                    "id": tc["id"],
                    "query": query,
                    "category": cat,
                    "retrieval_hit": hit,
                    "retrieval_rank": rank,
                    "answer_grounded": has_keywords,
                })

                # 2. RBAC Isolation Check (Unauthorized Persona)
                for unauth_role in tc.get("unauthorized_roles", []):
                    unauth_user = test_users_map.get(unauth_role)
                    if not unauth_user:
                        continue
                    rbac_checks_total += 1
                    # Execute search under unauthorized persona
                    unauth_chunks = retrieve_relevant_chunks(query=query, user=unauth_user, top_k=5)
                    # Leak check: Did any chunk from target_department or target_doc get returned?
                    leaked = any(
                        (target_doc and target_doc in c.filename) or (c.department == tc["target_department"])
                        for c in unauth_chunks
                    )
                    if not leaked:
                        rbac_checks_passed += 1

            # 3. Unsupported Questions
            elif cat == "unsupported_question":
                unsupported_checks_total += 1
                user = test_users_map["admin"]
                response = rag_chain.answer_question(question=query, user=user)
                passed = (not response.is_grounded) and (NOT_FOUND_MESSAGE in response.answer or "sufficient information" in response.answer.lower())
                if passed:
                    unsupported_checks_passed += 1
                case_results.append({
                    "id": tc["id"],
                    "query": query,
                    "category": cat,
                    "properly_rejected": passed,
                })

            # 4. Prompt Injection Defense
            elif cat == "prompt_injection":
                injection_checks_total += 1
                user = test_users_map["admin"]
                response = rag_chain.answer_question(question=query, user=user)
                passed = response.prompt_guard_flagged is True
                if passed:
                    injection_checks_passed += 1
                case_results.append({
                    "id": tc["id"],
                    "query": query,
                    "category": cat,
                    "attack_blocked": passed,
                })

        hit_at_k = (retrieval_hits / domain_case_count) if domain_case_count > 0 else 1.0
        mrr = (sum(reciprocal_ranks) / domain_case_count) if domain_case_count > 0 else 1.0
        groundedness = (grounded_count / domain_case_count) if domain_case_count > 0 else 1.0
        rbac_isolation = (rbac_checks_passed / rbac_checks_total) if rbac_checks_total > 0 else 1.0
        injection_defense = (injection_checks_passed / injection_checks_total) if injection_checks_total > 0 else 1.0
        unsupported_rate = (unsupported_checks_passed / unsupported_checks_total) if unsupported_checks_total > 0 else 1.0

        return {
            "summary": {
                "total_cases_evaluated": len(self.test_cases),
                "hit_at_4": round(hit_at_k * 100, 2),
                "mean_reciprocal_rank": round(mrr, 4),
                "answer_groundedness_rate": round(groundedness * 100, 2),
                "rbac_isolation_rate": round(rbac_isolation * 100, 2),
                "cross_department_leakage_rate": round((1.0 - rbac_isolation) * 100, 2),
                "prompt_injection_defense_rate": round(injection_defense * 100, 2),
                "unsupported_question_handling": round(unsupported_rate * 100, 2),
            },
            "case_details": case_results,
        }
