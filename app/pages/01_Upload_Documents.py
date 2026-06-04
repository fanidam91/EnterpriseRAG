import streamlit as st
import pandas as pd
from datetime import datetime
from app.databricks_client import upload_document_to_volume, get_document_lineage, get_db_connection

# Page Configuration
st.set_page_config(page_title="Upload Documents - Databricks RAG", page_icon="📤", layout="wide")

# Custom Styling (Shared/Extended)
st.markdown("""
<style>
    .stApp { background-color: #0B0F19; color: #F8FAFC; }
    h1, h2, h3 {
        background: linear-gradient(to right, #60A5FA, #2563EB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .flowchart {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        margin-bottom: 25px;
    }
    .flow-node {
        display: inline-block;
        padding: 8px 16px;
        background-color: #0F172A;
        border: 1.5px solid #3B82F6;
        border-radius: 6px;
        color: #F8FAFC;
        font-family: monospace;
        font-size: 0.85rem;
    }
    .flow-arrow {
        display: inline-block;
        margin: 0 10px;
        color: #60A5FA;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("📤 Document Ingestion & Volume Ingestion")
st.caption("Upload and chunk source documentation into Delta tables and Unity Catalog Volumes.")

# Columns: Left for Upload, Right for Lineage & Database Inventory
col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.markdown("### 📥 Ingest New Documents")
    
    # Ingestion Form
    with st.form("upload_form"):
        uploaded_files = st.file_uploader(
            "Select corporate files (PDF, DOCX, XLSX, PPTX):",
            type=["pdf", "docx", "xlsx", "pptx"],
            accept_multiple_files=True
        )
        
        # Meta-tags for RBAC/ABAC
        col_dept, col_clear = st.columns(2)
        with col_dept:
            department = st.selectbox("Department Owner (ABAC Attribute):", ["HR", "Finance", "IT", "Operations"])
        with col_clear:
            clearance_level = st.selectbox("Security Clearance Required:", ["Public", "Confidential", "Secret"])
            
        submit_btn = st.form_submit_button("🚀 Start Ingestion Pipeline")

    # Ingestion execution
    if submit_btn:
        if not uploaded_files:
            st.error("⚠️ Please select at least one document to ingest.")
        else:
            current_user = {"user_id": "sjenkins@company.com", "role": "HR_Manager"} # Default Uploader Profile
            progress_bar = st.progress(0)
            
            for idx, file in enumerate(uploaded_files):
                st.write(f"⚙️ Processing `{file.name}`...")
                
                # Read bytes
                file_bytes = file.read()
                
                # Upload and ingest
                result = upload_document_to_volume(
                    doc_name=file.name,
                    file_content_bytes=file_bytes,
                    department=department,
                    clearance_level=clearance_level,
                    uploader_profile=current_user,
                    config=st.session_state.config
                )
                
                if result["status"] == "success":
                    st.success(f"✅ Ingested `{file.name}`. Generated **{result['chunks_count']}** vector chunks in Delta Lake in {result['latency_ms']:.1f}ms.")
                else:
                    st.error(f"❌ Failed to ingest `{file.name}`: {result.get('message', 'Unknown Error')}")
                    
                progress_bar.progress((idx + 1) / len(uploaded_files))
                
            st.toast("🎉 Documents successfully ingested!")
            st.rerun()

with col_right:
    st.markdown("### ⛓️ Delta Lake Document Lineage")
    st.caption("How documents transition through the data platform:")
    
    # Graphic flowchart representing Lineage
    st.markdown("""
    <div class="flowchart">
        <div class="flow-node" title="User uploaded file stream">File Upload</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node" title="Unity Catalog External Volume Storage">UC Volume</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node" title="Spark Autoloader Stream Ingestion">Spark Autoloader</div>
        <br/><br/>
        <div class="flow-arrow">▼</div>
        <br/>
        <div class="flow-node" title="Delta Lake Structured bronze/silver table">Delta Silver Table</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node" title="Databricks Vector Search Sync Trigger">Vector Index</div>
        <div class="flow-arrow">➔</div>
        <div class="flow-node" title="Grounded context model serving endpoint">RAG Endpoint</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🗄️ Unity Catalog Catalog Inventory")
    
    # Load Lineage/catalog info from SQLite (representing delta tables)
    lineage_df = get_document_lineage()
    
    if lineage_df.empty:
        st.info("No documents currently registered in the database catalog. Load sample data from System Settings or upload documents above.")
    else:
        # Display table with styled formatting
        st.markdown(f"Total documents: **{len(lineage_df)}**")
        
        display_df = lineage_df.copy()
        display_df = display_df.rename(columns={
            "doc_name": "Document Name",
            "department": "Department Owner",
            "clearance_level": "Clearance Level",
            "file_size": "Size (Bytes)",
            "upload_timestamp": "Ingested Date"
        })
        
        st.dataframe(
            display_df[["Document Name", "Department Owner", "Clearance Level", "Size (Bytes)", "Ingested Date"]],
            use_container_width=True,
            hide_index=True
        )
        
        # In case the user wants to clear the tables
        if st.button("🚨 Wipe Data Catalog"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM delta_document_chunks")
            cursor.execute("DELETE FROM delta_documents")
            cursor.execute("DELETE FROM audit_query_logs")
            conn.commit()
            conn.close()
            st.success("Database catalog purged.")
            st.rerun()
