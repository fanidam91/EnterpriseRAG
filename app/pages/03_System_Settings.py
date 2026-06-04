import streamlit as st
import os
from app.databricks_client import upload_document_to_volume, delete_all_data

# Page Configuration
st.set_page_config(page_title="System Settings - Databricks RAG", page_icon="⚙️", layout="wide")

# Custom Styling
st.markdown("""
<style>
    .stApp { background-color: #0B0F19; color: #F8FAFC; }
    h1, h2, h3 {
        background: linear-gradient(to right, #60A5FA, #2563EB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .settings-group {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ System Configuration & Credentials")
st.caption("Manage environment modes, API keys, Databricks endpoint details, and sandbox databases.")

# Form to manage configurations
with st.form("settings_form"):
    
    # Environment Mode Toggle
    st.markdown("### 🔌 Application Operations Engine")
    sim_mode = st.toggle(
        "Enable High-Fidelity Simulation Mode",
        value=st.session_state.config.get("simulation_mode", True),
        help="If enabled, calculations, Vector Searches, and LLM reasoning are mocked locally. No cloud resources or keys required."
    )
    
    col_cloud, col_hyper = st.columns(2)
    
    with col_cloud:
        st.markdown("### 🧱 Azure OpenAI Services")
        azure_endpoint = st.text_input(
            "Azure OpenAI Endpoint URL:",
            value=st.session_state.config.get("azure_openai_endpoint", ""),
            placeholder="https://YOUR_RESOURCE.openai.azure.com/"
        )
        azure_key = st.text_input(
            "Azure OpenAI API Key:",
            value=st.session_state.config.get("azure_openai_key", ""),
            type="password",
            placeholder="Paste your Azure OpenAI API secret key here..."
        )
        
        col_depl1, col_depl2 = st.columns(2)
        with col_depl1:
            azure_llm = st.text_input("LLM Model Deployment:", value=st.session_state.config.get("azure_llm_deployment", "gpt-4o"))
        with col_depl2:
            azure_embed = st.text_input("Embeddings Model Deployment:", value=st.session_state.config.get("azure_embeddings_deployment", "text-embedding-3-small"))
            
        st.markdown("### 🏛️ Databricks & Delta Lake Configuration")
        db_host = st.text_input(
            "Databricks Workspace URL (Host):",
            value=st.session_state.config.get("databricks_host", ""),
            placeholder="https://adb-xxxxxxxxxxxx.x.azuredatabricks.net"
        )
        db_token = st.text_input(
            "Databricks Personal Access Token (PAT):",
            value=st.session_state.config.get("databricks_token", ""),
            type="password",
            placeholder="dapi..."
        )
        
    with col_hyper:
        st.markdown("### 🗃️ Unity Catalog & Vector Index Mapping")
        
        col_cat, col_sch = st.columns(2)
        with col_cat:
            uc_cat = st.text_input("UC Catalog:", value=st.session_state.config.get("uc_catalog", "main"))
        with col_sch:
            uc_sch = st.text_input("UC Schema:", value=st.session_state.config.get("uc_schema", "knowledge_base"))
            
        col_vol, col_idx = st.columns(2)
        with col_vol:
            uc_vol = st.text_input("UC Target Volume Name:", value=st.session_state.config.get("uc_volume", "raw_docs"))
        with col_idx:
            uc_idx = st.text_input("UC Vector Index Name:", value=st.session_state.config.get("uc_index", "vs_index"))
            
        vs_endpoint = st.text_input("Databricks Vector Search Endpoint:", value=st.session_state.config.get("vector_search_endpoint", "vs_endpoint"))
        
        st.markdown("### 🎛️ RAG Model Inference Hyperparameters")
        temperature = st.slider("Temperature:", min_value=0.0, max_value=1.0, value=float(st.session_state.config.get("temperature", 0.0)), step=0.1)
        max_tokens = st.slider("Max Completion Tokens:", min_value=100, max_value=2000, value=int(st.session_state.config.get("max_tokens", 800)), step=100)
        top_k = st.slider("Retrieval top-K chunks:", min_value=1, max_value=10, value=int(st.session_state.config.get("top_k", 4)), step=1)
        
    # Save settings
    save_settings = st.form_submit_button("💾 Save System Configuration")

if save_settings:
    st.session_state.config.update({
        "simulation_mode": sim_mode,
        "databricks_host": db_host,
        "databricks_token": db_token,
        "uc_catalog": uc_cat,
        "uc_schema": uc_sch,
        "uc_volume": uc_vol,
        "uc_index": uc_idx,
        "vector_search_endpoint": vs_endpoint,
        "azure_openai_endpoint": azure_endpoint,
        "azure_openai_key": azure_key,
        "azure_llm_deployment": azure_llm,
        "azure_embeddings_deployment": azure_embed,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_k": top_k
    })
    st.success("✅ System configurations successfully saved and reloaded!")
    st.rerun()

# ----------------- SANDBOX INITIALIZATION -----------------
st.markdown("---")
st.markdown("### 🛝 Simulated Sandbox Manager")
st.caption("Generate mock records inside the SQLite simulation Delta tables using the pre-created PDF, DOCX, XLSX, and PPTX reports.")

col_btn1, col_btn2 = st.columns([1, 1])

# Preload files trigger
if col_btn1.button("📂 Pre-populate Sandbox Database", type="primary", use_container_width=True):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(project_root, "data")
    
    mock_docs = [
        {"name": "HR_Employee_Handbook_2026.pdf", "dept": "HR", "clearance": "Confidential"},
        {"name": "Finance_Q1_Performance_Statement.xlsx", "dept": "Finance", "clearance": "Confidential"},
        {"name": "IT_Security_Incident_Response_Plan.docx", "dept": "IT", "clearance": "Confidential"},
        {"name": "Company_Operations_Playbook.pptx", "dept": "Operations", "clearance": "Public"}
    ]
    
    success_count = 0
    uploader_profile = {"user_id": "system_sandbox@company.com", "role": "Administrator"}
    
    with st.spinner("Parsing and indexing corporate reports in Delta tables..."):
        for doc in mock_docs:
            file_path = os.path.join(data_dir, doc["name"])
            
            if os.path.exists(file_path):
                # Read bytes
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                    
                # Upload
                res = upload_document_to_volume(
                    doc_name=doc["name"],
                    file_content_bytes=file_bytes,
                    department=doc["dept"],
                    clearance_level=doc["clearance"],
                    uploader_profile=uploader_profile,
                    config=st.session_state.config
                )
                
                if res["status"] == "success":
                    success_count += 1
            else:
                st.error(f"Missing file: {doc['name']} at {file_path}")
                
    if success_count > 0:
        st.success(f"🎉 Successfully pre-populated sandbox with **{success_count}** major corporate policy documents.")
        st.info("💡 Switch to the **Chat** interface now and query employee leave policies, IT incident response plans, or corporate finance variances.")
    else:
        st.error("Could not find generated documents. Run scripts/generate_sample_docs.py first.")

# Purge button
if col_btn2.button("🧹 Purge Sandbox Data", use_container_width=True):
    delete_all_data()
    st.warning("⚠️ All Delta tables and vector databases have been wiped.")
    st.rerun()
