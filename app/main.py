import streamlit as st
import time
import os
import pandas as pd

# Page Configuration
st.set_page_config(
    page_title="Databricks Enterprise Knowledge Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    /* Primary brand colors */
    :root {
        --primary: #2563EB;
        --background: #0F172A;
        --secondary: #1E293B;
    }
    
    /* Global styles */
    .stApp {
        background-color: #0B0F19;
        color: #F8FAFC;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        background: linear-gradient(to right, #60A5FA, #2563EB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Document citation cards */
    .citation-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    .citation-title {
        font-weight: 600;
        color: #60A5FA;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
    }
    
    .citation-meta {
        font-size: 0.8rem;
        color: #94A3B8;
        margin-bottom: 8px;
    }
    
    .citation-content {
        font-size: 0.9rem;
        color: #E2E8F0;
        line-height: 1.4;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-hr { background-color: #BE185D; color: #FDF2F8; }
    .badge-finance { background-color: #047857; color: #ECFDF5; }
    .badge-it { background-color: #6D28D9; color: #F5F3FF; }
    .badge-ops { background-color: #D97706; color: #FEF3C7; }
    
    .badge-public { border: 1px solid #34D399; color: #34D399; }
    .badge-confidential { border: 1px solid #F59E0B; color: #F59E0B; }
    .badge-secret { border: 1px solid #EF4444; color: #EF4444; }

    /* Telemetry grid */
    .telemetry-container {
        display: flex;
        justify-content: space-between;
        background-color: #111827;
        border: 1px dashed #374151;
        padding: 10px;
        border-radius: 6px;
        margin-top: 15px;
        margin-bottom: 15px;
    }
    .telemetry-item {
        text-align: center;
        flex: 1;
        font-size: 0.85rem;
        color: #9CA3AF;
    }
    .telemetry-value {
        font-weight: 700;
        color: #3B82F6;
        font-size: 1.05rem;
    }
</style>
""", unsafe_allow_html=True)

# Imports from app modules
from app.auth import get_user_profiles, get_user_profile
from app.databricks_client import vector_search_query, initialize_db
from app.openai_client import generate_chat_completion
from app.mlflow_tracker import log_rag_run

# Initialize Session State Variables
if "config" not in st.session_state:
    st.session_state.config = {
        "simulation_mode": True,
        "databricks_host": "",
        "databricks_token": "",
        "uc_catalog": "main",
        "uc_schema": "knowledge_base",
        "uc_volume": "raw_docs",
        "uc_index": "vs_index",
        "vector_search_endpoint": "vs_endpoint",
        "azure_openai_endpoint": "",
        "azure_openai_key": "",
        "azure_openai_version": "2024-02-15-preview",
        "azure_llm_deployment": "gpt-4o",
        "azure_embeddings_deployment": "text-embedding-3-small",
        "temperature": 0.0,
        "max_tokens": 800,
        "top_k": 4
    }

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_query_telemetry" not in st.session_state:
    st.session_state.last_query_telemetry = None

# Header Banner
st.title("🤖 Databricks Enterprise Knowledge Assistant")
st.caption("Secure GenAI-powered Retrieval-Augmented Generation (RAG) agent operating on Delta Lake, Azure OpenAI, and Unity Catalog.")

# Setup Sidebar
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/6/63/Databricks_Logo.png", width=160)
st.sidebar.markdown("### 🔒 Security Governance Panel")

# User Selection (RBAC/ABAC Demonstration)
user_profiles = get_user_profiles()
selected_user_key = st.sidebar.selectbox(
    "Active Corporate User Profile:",
    list(user_profiles.keys()),
    index=0
)
current_user = get_user_profile(selected_user_key)

# User Attribute Visualizer
if current_user:
    st.sidebar.markdown(f"""
    **Email ID:** `{current_user['user_id']}`  
    **Role:** `{current_user['role']}`  
    **Clearance level:** `{current_user['clearance_level']}`  
    **Allowed Departments:** `{', '.join(current_user['allowed_departments'])}`
    """)
    st.sidebar.info(f"💡 *{current_user['description']}*")

st.sidebar.markdown("---")

# Active Engine State
sim_mode = st.session_state.config.get("simulation_mode", True)
if sim_mode:
    st.sidebar.warning("⚡ Engine: Simulation Mode Active")
    st.sidebar.caption("Running vector searches and Delta operations locally via SQLite database for frictionless demo.")
else:
    st.sidebar.success("🚀 Engine: Production Cloud Mode Active")
    st.sidebar.caption("Connecting directly to Databricks Vector Search index and Azure OpenAI services.")

# Clear History Button
if st.sidebar.button("🧹 Clear Conversation History"):
    st.session_state.chat_history = []
    st.session_state.last_query_telemetry = None
    st.rerun()

# ----------------- CHAT INTERFACE -----------------

# Display conversation messages
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display citation cards inside Expander if available (for assistant)
        if message.get("role") == "assistant" and message.get("citations"):
            with st.expander("📚 Grounded Citations & Reference Data"):
                for chunk in message["citations"]:
                    dept_badge = f'<span class="badge badge-{chunk["department"].lower()}">{chunk["department"]}</span>'
                    clearance_badge = f'<span class="badge badge-{chunk["clearance_level"].lower()}">{chunk["clearance_level"]}</span>'
                    
                    st.markdown(f"""
                    <div class="citation-card">
                        <div class="citation-title">
                            <span>📄 {chunk['doc_name']} (Section: {chunk['section']})</span>
                            <span>Score: {chunk['similarity']:.4f}</span>
                        </div>
                        <div class="citation-meta">
                            Dept: {dept_badge} | Clearance: {clearance_badge}
                        </div>
                        <div class="citation-content">{chunk['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)

# User Query Input
if query := st.chat_input("Ask a question about employee policies, Q1 finance statements, or IT standard operating procedures..."):
    # 1. Show user message
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.chat_history.append({"role": "user", "content": query})
    
    # 2. Execute RAG Retrieval Pipeline
    with st.chat_message("assistant"):
        with st.spinner("Executing Vector Search & Evaluating RBAC/ABAC filters in Unity Catalog..."):
            
            # Step A: Query vector database with active user permissions
            retrieved_chunks, search_meta = vector_search_query(
                query_text=query,
                user_profile=current_user,
                config=st.session_state.config,
                top_k=st.session_state.config.get("top_k", 4)
            )
            
            # Check if access was denied or no records retrieved
            if not retrieved_chunks:
                status_msg = "🚨 ACCESS DENIED: Row-level Unity Catalog permissions blocked access to matching security records or no documents were found."
                st.markdown(status_msg)
                
                # Log to MLflow
                log_res = {
                    "content": status_msg,
                    "confidence_score": 0.0,
                    "tokens_used": len(query.split()) * 1.3,
                    "latency_ms": search_meta.get("latency_ms", 10.0),
                    "model": "azure-openai/gpt-4o"
                }
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": status_msg,
                    "citations": []
                })
                
                st.session_state.last_query_telemetry = {
                    "run_id": log_rag_run(query, "Default System Instruction", log_res, [], current_user, st.session_state.config),
                    "latency_ms": search_meta.get("latency_ms", 10.0),
                    "tokens_used": len(query.split()) * 1.3,
                    "confidence_score": 0.0,
                    "status": "ACCESS_DENIED",
                    "model": "security-filter"
                }
                st.rerun()

            # Step B: LLM Generation grounded by context
            system_prompt = (
                "You are the Enterprise Knowledge Assistant. Answer the user's questions truthfully and "
                "accurately, using only the provided context chunks. Cite the document names and section titles. "
                "If the context does not contain enough information to answer, state that you cannot answer."
            )
            
            llm_result = generate_chat_completion(
                prompt=query,
                system_message=system_prompt,
                messages_history=st.session_state.chat_history[:-1], # pass history excluding the current query
                context_chunks=retrieved_chunks,
                config=st.session_state.config
            )
            
            # Render response
            st.markdown(llm_result["content"])
            
            # Show citations
            with st.expander("📚 Grounded Citations & Reference Data"):
                for chunk in retrieved_chunks:
                    dept_badge = f'<span class="badge badge-{chunk["department"].lower()}">{chunk["department"]}</span>'
                    clearance_badge = f'<span class="badge badge-{chunk["clearance_level"].lower()}">{chunk["clearance_level"]}</span>'
                    
                    st.markdown(f"""
                    <div class="citation-card">
                        <div class="citation-title">
                            <span>📄 {chunk['doc_name']} (Section: {chunk['section']})</span>
                            <span>Score: {chunk['similarity']:.4f}</span>
                        </div>
                        <div class="citation-meta">
                            Dept: {dept_badge} | Clearance: {clearance_badge}
                        </div>
                        <div class="citation-content">{chunk['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
            # 3. Log query audit log and MLflow tracking run
            run_id = log_rag_run(
                query_text=query,
                system_message=system_prompt,
                output_data=llm_result,
                retrieved_chunks=retrieved_chunks,
                user_profile=current_user,
                config=st.session_state.config
            )
            
            # Save history & telemetry
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": llm_result["content"],
                "citations": retrieved_chunks
            })
            
            st.session_state.last_query_telemetry = {
                "run_id": run_id,
                "latency_ms": search_meta.get("latency_ms", 0) + llm_result.get("latency_ms", 0),
                "tokens_used": llm_result.get("tokens_used", 0),
                "confidence_score": llm_result.get("confidence_score", 0.0),
                "status": search_meta.get("status", "SUCCESS"),
                "model": llm_result.get("model", "gpt-4o")
            }
            st.rerun()

# ----------------- TELEMETRY & AUDIT SUMMARY PANEL -----------------
if st.session_state.last_query_telemetry:
    telemetry = st.session_state.last_query_telemetry
    
    st.markdown("### 📊 Real-Time MLflow Run Telemetry")
    
    # Render indicators
    st.markdown(f"""
    <div class="telemetry-container">
        <div class="telemetry-item">
            <div>MLFLOW RUN ID</div>
            <div class="telemetry-value"><code>{telemetry['run_id']}</code></div>
        </div>
        <div class="telemetry-item">
            <div>TOTAL LATENCY</div>
            <div class="telemetry-value">{telemetry['latency_ms']:.1f} ms</div>
        </div>
        <div class="telemetry-item">
            <div>TOKENS CONSUMED</div>
            <div class="telemetry-value">{int(telemetry['tokens_used'])}</div>
        </div>
        <div class="telemetry-item">
            <div>GROUNDED CONFIDENCE</div>
            <div class="telemetry-value">{int(telemetry['confidence_score'] * 100)}%</div>
        </div>
        <div class="telemetry-item">
            <div>LLM MODEL</div>
            <div class="telemetry-value">{telemetry['model']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Short advice on audit trail
    st.caption("🔒 *Unity Catalog Security Audit Logs and model registry traces have been recorded to the Delta Auditing tables.* View details in the **Governance & Audit** tab.")
else:
    # Render welcome prompt and instructions
    st.markdown("---")
    st.markdown("### 💡 Interview Showcase Quickstart")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📊 **Step 1: Ingest Data**  \nGo to the **Upload Documents** page on the sidebar. Ingest the generated sample reports or upload your own.")
    with col2:
        st.info("🔐 **Step 2: Try RBAC/ABAC**  \nAsk a query (e.g. *What is the annual leave allowance?*) as the **HR Manager**, then switch user to **General Contractor** and ask again to watch security filters trigger!")
    with col3:
        st.info("📈 **Step 3: Audit & MLflow**  \nVisit **Governance & Audit** to review full Delta tables, query lineage, security access graphs, and MLflow run parameters.")
