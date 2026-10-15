"""Enterprise AI Knowledge Platform — Streamlit Dashboard.

Interactive, role-aware knowledge assistant with strict RBAC enforcement,
document management, grounded question answering, and provenance citations.
"""

import os
import sys
from pathlib import Path
import time
from typing import Dict, Any, List

import requests
import streamlit as st

# Configure page metadata
st.set_page_config(
    page_title="Enterprise AI Knowledge Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Backend API Configuration
API_BASE_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")

# Custom CSS for styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .badge-role {
        background-color: #DBEAFE;
        color: #1D4ED8;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-dept {
        background-color: #FEF3C7;
        color: #D97706;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .citation-card {
        border-left: 4px solid #3B82F6;
        background-color: #F8FAFC;
        padding: 0.75rem 1rem;
        margin-top: 0.5rem;
        border-radius: 0 6px 6px 0;
    }
    .security-alert {
        border-left: 4px solid #EF4444;
        background-color: #FEF2F2;
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_login(username: str, password: str) -> Dict[str, Any]:
    """Authenticate against FastAPI backend and return token data."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        else:
            err_msg = resp.json().get("detail", "Authentication failed.")
            return {"success": False, "error": err_msg}
    except Exception as e:
        return {"success": False, "error": f"Backend API unavailable: {str(e)}"}


def api_get_profile(token: str) -> Dict[str, Any]:
    """Fetch current user profile and RBAC permissions."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception:
        return {}


def api_list_documents(token: str) -> List[Dict[str, Any]]:
    """Fetch documents accessible to the current user."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/documents/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def api_query_rag(token: str, query: str, top_k: int = 4) -> Dict[str, Any]:
    """Execute RBAC-filtered RAG query."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}/rag/query",
            json={"query": query, "top_k": top_k},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        return {
            "query": query,
            "answer": f"Error {resp.status_code}: {resp.json().get('detail', 'Query failed.')}",
            "citations": [],
            "is_grounded": False,
        }
    except Exception as e:
        return {
            "query": query,
            "answer": f"Failed to contact backend API: {str(e)}",
            "citations": [],
            "is_grounded": False,
        }


def api_upload_document(token: str, file, department: str, access_level: str) -> Dict[str, Any]:
    """Upload a document file to the backend."""
    try:
        files = {"file": (file.name, file.getvalue(), file.type)}
        data = {"department": department, "access_level": access_level}
        resp = requests.post(
            f"{API_BASE_URL}/documents/upload",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=40,
        )
        if resp.status_code in [200, 201]:
            return {"success": True, "data": resp.json()}
        else:
            return {"success": False, "error": resp.json().get("detail", "Upload failed.")}
    except Exception as e:
        return {"success": False, "error": f"Upload failed: {str(e)}"}


def api_delete_document(token: str, doc_id: str) -> Dict[str, Any]:
    """Delete an ingested document."""
    try:
        resp = requests.delete(
            f"{API_BASE_URL}/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return {"success": True}
        return {"success": False, "error": resp.json().get("detail", "Deletion failed.")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Initialize session state variables
if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = None
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []


# ==============================================================================
# SIDEBAR: Authentication & Persona Switcher
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=64)
    st.title("Enterprise Identity")

    if st.session_state["auth_token"]:
        user = st.session_state["current_user"]
        st.success(f"Signed in as **{user.get('full_name', 'Employee')}**")

        st.markdown(
            f"""
            - **Username:** `{user.get('username')}`
            - **Role:** <span class="badge-role">{user.get('role', '').upper()}</span>
            - **Department:** <span class="badge-dept">{user.get('department', '').upper()}</span>
            """,
            unsafe_allow_html=True,
        )

        scopes = user.get("authorized_scopes", {})
        depts = scopes.get("departments", [])
        st.markdown(f"**Authorized Scopes:** {', '.join([d.upper() for d in depts])}")

        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state["auth_token"] = None
            st.session_state["current_user"] = None
            st.session_state["messages"] = []
            st.rerun()

    else:
        st.subheader("Sign In")
        st.markdown("Select a pre-configured persona or enter credentials:")

        demo_persona = st.selectbox(
            "Quick Demo Personas:",
            [
                "Select persona...",
                "Administrator (admin)",
                "HR Lead (hr_manager)",
                "Finance Lead (finance_lead)",
                "Staff Engineer (engineer_lead)",
                "General Staff (employee_alice)",
            ],
        )

        credentials_map = {
            "Administrator (admin)": ("admin", "AdminPassword123!"),
            "HR Lead (hr_manager)": ("hr_manager", "HrPassword123!"),
            "Finance Lead (finance_lead)": ("finance_lead", "FinancePassword123!"),
            "Staff Engineer (engineer_lead)": ("engineer_lead", "EngineeringPassword123!"),
            "General Staff (employee_alice)": ("employee_alice", "EmployeePassword123!"),
        }

        default_user = ""
        default_pwd = ""
        if demo_persona in credentials_map:
            default_user, default_pwd = credentials_map[demo_persona]

        with st.form("login_form"):
            username = st.text_input("Username", value=default_user)
            password = st.text_input("Password", type="password", value=default_pwd)
            submit = st.form_submit_button("Authenticate", use_container_width=True)

            if submit:
                with st.spinner("Verifying credentials with server..."):
                    res = api_login(username, password)
                    if res["success"]:
                        token = res["data"]["access_token"]
                        st.session_state["auth_token"] = token
                        st.session_state["current_user"] = api_get_profile(token)
                        st.success("Authentication successful!")
                        st.rerun()
                    else:
                        st.error(f"Login failed: {res.get('error')}")


# ==============================================================================
# MAIN VIEW
# ==============================================================================
st.markdown('<div class="main-header">🛡️ Enterprise AI Knowledge Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Secure, Grounded RAG with Document-Level Role-Based Access Control</div>', unsafe_allow_html=True)

if not st.session_state["auth_token"]:
    st.info("👈 Please sign in using the sidebar to access the knowledge base according to your enterprise role.")
    st.markdown(
        """
        ### System Architecture & Security Principles
        1. **Strict Server-Side RBAC Filtering:** Document chunks belonging to unauthorized departments are pre-filtered at the vector database layer and never enter the LLM context.
        2. **Adversarial Prompt Guardrails:** System prompts and user inputs are strictly delimited (`<untrusted_documents>`), screening out injection attempts and preventing secret exfiltration.
        3. **Factual Grounding & Citations:** Every answer cites its source file, page/chunk index, and relevance score. If facts are absent, the system explicitly refuses to invent answers.
        """
    )
    st.stop()

# Authenticated Tabs
tab_chat, tab_docs, tab_security = st.tabs([
    "💬 Knowledge Assistant",
    "📁 Document Repository & Ingestion",
    "🔐 Access Control & Security Inspector",
])


# ------------------------------------------------------------------------------
# TAB 1: Chat Assistant
# ------------------------------------------------------------------------------
with tab_chat:
    col_chat, col_tools = st.columns([3, 1])

    with col_tools:
        st.subheader("Suggested Queries")
        role = st.session_state["current_user"].get("role", "employee")

        suggestions = {
            "hr": [
                "How many weeks of paid parental leave are offered?",
                "What is the annual HSA contribution for families?",
                "What is the home office allowance stipend?",
            ],
            "finance": [
                "What is the Q3 Cloud Infrastructure budget allocation?",
                "What are the procurement limits requiring CFO approval?",
                "What are the standard vendor payment terms?",
            ],
            "engineering": [
                "What is the Kafka replication factor and retention period?",
                "How does Kong API gateway handle rate limiting?",
                "What is the SLA and MTTR target for Tier-1 services?",
            ],
            "employee": [
                "What are the rules regarding generative AI chatbots?",
                "What are the whistleblower reporting channels?",
                "What are the mandatory MFA security requirements?",
            ],
            "admin": [
                "What is the Q3 AWS cloud budget?",
                "What is the parental leave duration?",
                "What is the Kafka replication factor?",
            ],
        }

        user_suggestions = suggestions.get(role, suggestions["employee"])
        for q in user_suggestions:
            if st.button(q, key=f"sug_{q}", use_container_width=True):
                st.session_state["messages"].append({"role": "user", "content": q})
                with st.spinner("Searching authorized knowledge base..."):
                    rag_res = api_query_rag(st.session_state["auth_token"], q)
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": rag_res.get("answer", ""),
                        "citations": rag_res.get("citations", []),
                        "is_grounded": rag_res.get("is_grounded", True),
                        "flagged": rag_res.get("prompt_guard_flagged", False),
                    })
                st.rerun()

        st.divider()
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()

    with col_chat:
        # Display conversation history
        for msg in st.session_state["messages"]:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    if msg.get("flagged"):
                        st.markdown(f'<div class="security-alert">⚠️ {msg["content"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(msg["content"])

                    citations = msg.get("citations", [])
                    if citations:
                        with st.expander(f"📚 Provenance & Citations ({len(citations)} sources)"):
                            for cit in citations:
                                page_str = f"Page {cit['page_number']}" if cit.get("page_number") else f"Chunk {cit.get('chunk_index', 0)}"
                                st.markdown(
                                    f"""
                                    <div class="citation-card">
                                        <b>Source:</b> <code>{cit['filename']}</code> ({page_str}) &nbsp;|&nbsp; 
                                        <b>Department:</b> <code>{cit['department'].upper()}</code> &nbsp;|&nbsp; 
                                        <b>Relevance Score:</b> <code>{cit['similarity_score']:.4f}</code>
                                        <p style="margin-top: 0.4rem; font-size: 0.92rem; color: #374151;">
                                            <i>"{cit['snippet']}"</i>
                                        </p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

        # User input box
        if prompt := st.chat_input("Ask a question about enterprise policies, budgets, or architectures..."):
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing query, verifying permissions, and retrieving context..."):
                    rag_res = api_query_rag(st.session_state["auth_token"], prompt)
                    
                    if rag_res.get("prompt_guard_flagged"):
                        st.markdown(f'<div class="security-alert">⚠️ {rag_res["answer"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(rag_res["answer"])

                    citations = rag_res.get("citations", [])
                    if citations:
                        with st.expander(f"📚 Provenance & Citations ({len(citations)} sources)"):
                            for cit in citations:
                                page_str = f"Page {cit['page_number']}" if cit.get("page_number") else f"Chunk {cit.get('chunk_index', 0)}"
                                st.markdown(
                                    f"""
                                    <div class="citation-card">
                                        <b>Source:</b> <code>{cit['filename']}</code> ({page_str}) &nbsp;|&nbsp; 
                                        <b>Department:</b> <code>{cit['department'].upper()}</code> &nbsp;|&nbsp; 
                                        <b>Relevance Score:</b> <code>{cit['similarity_score']:.4f}</code>
                                        <p style="margin-top: 0.4rem; font-size: 0.92rem; color: #374151;">
                                            <i>"{cit['snippet']}"</i>
                                        </p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

            st.session_state["messages"].append({
                "role": "assistant",
                "content": rag_res.get("answer", ""),
                "citations": citations,
                "is_grounded": rag_res.get("is_grounded", True),
                "flagged": rag_res.get("prompt_guard_flagged", False),
            })


# ------------------------------------------------------------------------------
# TAB 2: Document Repository & Ingestion
# ------------------------------------------------------------------------------
with tab_docs:
    st.subheader("Enterprise Document Management")

    col_up, col_list = st.columns([1, 2])

    with col_up:
        st.markdown("### 📤 Ingest New Document")
        uploaded_file = st.file_uploader(
            "Select Document (PDF, DOCX, TXT):",
            type=["pdf", "docx", "txt"],
        )

        user_dept = st.session_state["current_user"].get("department", "general")
        user_role = st.session_state["current_user"].get("role", "employee")
        allowed_depts = st.session_state["current_user"].get("authorized_scopes", {}).get("departments", ["general"])

        target_dept = st.selectbox(
            "Assign Department:",
            options=allowed_depts,
            index=0,
        )

        target_access = st.selectbox(
            "Access Classification:",
            options=["public", "internal", "confidential", "restricted"] if user_role == "admin" else ["internal", "public"],
            index=0,
        )

        if st.button("🚀 Ingest & Index Document", use_container_width=True):
            if uploaded_file is not None:
                with st.spinner("Extracting text, chunking, computing embeddings, and indexing..."):
                    res = api_upload_document(
                        st.session_state["auth_token"],
                        uploaded_file,
                        target_dept,
                        target_access,
                    )
                    if res["success"]:
                        st.success(f"Ingested '{uploaded_file.name}' with {res['data'].get('chunk_count')} chunks!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Ingestion rejected: {res.get('error')}")
            else:
                st.warning("Please choose a file to upload.")

    with col_list:
        st.markdown("### 📑 Accessible Enterprise Documents")
        docs = api_list_documents(st.session_state["auth_token"])

        if docs:
            for d in docs:
                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    c1.markdown(f"**{d['filename']}** (`{d['file_type']}`)")
                    c2.markdown(f"<span class=\"badge-dept\">{d['department'].upper()}</span>", unsafe_allow_html=True)
                    c3.markdown(f"*{d['chunk_count']} chunks*")
                    if user_role == "admin":
                        if c4.button("Delete", key=f"del_{d['doc_id']}"):
                            del_res = api_delete_document(st.session_state["auth_token"], d["doc_id"])
                            if del_res["success"]:
                                st.success("Deleted!")
                                st.rerun()
                            else:
                                st.error(del_res.get("error"))
                    st.divider()
        else:
            st.info("No documents currently accessible under your credentials.")


# ------------------------------------------------------------------------------
# TAB 3: Security & RBAC Inspector
# ------------------------------------------------------------------------------
with tab_security:
    st.subheader("Security & Access Control Architecture")

    st.markdown(
        """
        ### Role-Based Access Control (RBAC) Isolation Matrix
        The table below reflects the **server-enforced authorization policy**. 
        Frontend choices are never trusted; the API validates token claims on every retrieval call.
        """
    )

    rbac_matrix = [
        {"Role": "Administrator", "Permitted Departments": "HR, Finance, Engineering, General", "Access Levels": "Public, Internal, Confidential, Restricted", "Upload Scope": "Universal"},
        {"Role": "HR Lead", "Permitted Departments": "HR, General", "Access Levels": "Public, Internal, Confidential", "Upload Scope": "HR & General"},
        {"Role": "Finance Lead", "Permitted Departments": "Finance, General", "Access Levels": "Public, Internal, Confidential", "Upload Scope": "Finance & General"},
        {"Role": "Staff Engineer", "Permitted Departments": "Engineering, General", "Access Levels": "Public, Internal, Confidential", "Upload Scope": "Engineering & General"},
        {"Role": "General Employee", "Permitted Departments": "General", "Access Levels": "Public, Internal", "Upload Scope": "General Only"},
    ]
    st.table(rbac_matrix)

    st.markdown("### Prompt Injection Defense Strategy")
    st.markdown(
        """
        - **Structural Untrusted Delimiters:** Documents are encapsulated inside `<untrusted_documents>` tags to prevent the LLM from executing adversarial instructions embedded in documents.
        - **Instruction Boundary Isolation:** Explicit system instructions dictate that context is untrusted data, not directives.
        - **Pre-Execution Heuristic Filtering:** Known jailbreak keywords, persona hijacking ('You are now DAN'), and secret exfiltration queries are flagged and rejected with audit logging.
        - **Output Scrubbing:** All responses pass through credential pattern matchers to prevent accidental API key or secret leakage.
        - **Documented Limitations:** Heuristic filters are not a silver bullet against novel token obfuscation. The true security perimeter is the **server-side RBAC pre-filter**, ensuring unauthorized data never reaches the LLM context.
        """
    )
