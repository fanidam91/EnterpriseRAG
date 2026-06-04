import streamlit as st
import pandas as pd
import json
import plotly.express as px
from app.databricks_client import get_audit_trail
from app.mlflow_tracker import get_mlflow_runs, get_mlflow_run_details

# Page Configuration
st.set_page_config(page_title="Governance & Audit - Databricks RAG", page_icon="🛡️", layout="wide")

# Custom Styling
st.markdown("""
<style>
    .stApp { background-color: #0B0F19; color: #F8FAFC; }
    h1, h2, h3 {
        background: linear-gradient(to right, #60A5FA, #2563EB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 15px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #60A5FA;
    }
    .trace-card {
        background-color: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 15px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Unity Catalog Governance & Compliance Dashboard")
st.caption("Review data lineage, compliance access audits, and MLflow model tracking telemetry.")

# Tabs: Audit Logs & Security Metrics, MLflow Experiments Board
tab_audit, tab_mlflow = st.tabs(["🔒 Unity Catalog Access Audit Logs", "🧪 MLflow Experiment Tracking"])

# ----------------- TAB: AUDIT LOGS -----------------
with tab_audit:
    st.markdown("### 🔍 Query Access Audit Trail (`system.audit.query_logs`)")
    st.caption("Logs all queries, active security policies, row-level evaluations, and user roles.")
    
    # Load Logs
    audit_df = get_audit_trail()
    
    if audit_df.empty:
        st.info("No queries have been executed yet. Return to the Chat interface to generate audit data.")
    else:
        # Display aggregate KPI metrics
        total_queries = len(audit_df)
        denied_queries = len(audit_df[audit_df["status"].str.contains("DENIED|VIOLATION")])
        avg_latency = audit_df["latency_ms"].mean()
        total_tokens = audit_df["tokens_used"].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="metric-card"><div>Total Queries Audit Log</div><div class="metric-value">{total_queries}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><div>Security Violations Blocks</div><div class="metric-value" style="color: #EF4444;">{denied_queries}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><div>Avg Endpoint Latency</div><div class="metric-value" style="color: #10B981;">{avg_latency:.1f} ms</div></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="metric-card"><div>Accumulated Tokens</div><div class="metric-value" style="color: #F59E0B;">{int(total_tokens)}</div></div>', unsafe_allow_html=True)
            
        st.write("")
        
        # Plotly Charts
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("##### Security Access Outcome Distribution")
            status_counts = audit_df["status"].value_value_counts() if hasattr(audit_df["status"], "value_value_counts") else audit_df["status"].value_counts()
            fig_status = px.bar(
                x=status_counts.index,
                y=status_counts.values,
                labels={"x": "Security Outcome", "y": "Audit Logs Count"},
                color=status_counts.index,
                color_discrete_map={
                    "ACCESS_GRANTED": "#10B981", 
                    "ACCESS_DENIED_VIOLATION": "#EF4444",
                    "NO_RESULTS_OR_ACCESS_DENIED": "#6B7280"
                },
                height=300
            )
            fig_status.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_status, use_container_width=True)
            
        with col_chart2:
            st.markdown("##### RAG Ingestion & Endpoint Latency Trends")
            fig_lat = px.line(
                audit_df.sort_values("timestamp"),
                x="timestamp",
                y="latency_ms",
                labels={"timestamp": "Query Time", "latency_ms": "Latency (ms)"},
                markers=True,
                height=300
            )
            fig_lat.update_layout(margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig_lat.update_traces(line_color="#3B82F6")
            st.plotly_chart(fig_lat, use_container_width=True)
            
        st.markdown("##### Audit Records Catalog Table")
        
        # Format table for readability
        table_df = audit_df.copy()
        table_df = table_df.rename(columns={
            "timestamp": "Timestamp",
            "user_id": "User Email",
            "user_role": "Active Role",
            "query_text": "User Query",
            "status": "Security Status",
            "latency_ms": "Latency (ms)",
            "tokens_used": "Tokens"
        })
        
        st.dataframe(
            table_df[["Timestamp", "User Email", "Active Role", "User Query", "Security Status", "Latency (ms)", "Tokens"]],
            use_container_width=True,
            hide_index=True
        )

# ----------------- TAB: MLFLOW EXPERIMENTS -----------------
with tab_mlflow:
    st.markdown("### 🧪 MLflow Model Serving Registry & Run Telemetry")
    st.caption("Aggregates hyperparameter logs, evaluation metrics, and RAG execution paths.")
    
    # Load MLflow runs
    runs_df = get_mlflow_runs()
    
    if runs_df.empty:
        st.info("No tracked model serving runs located in local registry. Generate RAG answers to record experiment details.")
    else:
        # Display Run Registry Table
        st.markdown("##### Registered Run Logs")
        
        display_runs = runs_df.copy()
        display_runs = display_runs.rename(columns={
            "run_id": "Run ID",
            "run_name": "Run Name",
            "start_time": "Time Logged",
            "user_id": "Uploader / User",
            "model_name": "Target Model",
            "latency_ms": "Latency (ms)",
            "tokens_used": "Token Count",
            "confidence_score": "Confidence"
        })
        
        st.dataframe(
            display_runs[["Run ID", "Run Name", "Time Logged", "Target Model", "Latency (ms)", "Token Count", "Confidence"]],
            use_container_width=True,
            hide_index=True
        )
        
        st.write("")
        st.markdown("---")
        
        # Run Selector for Detailed Trace Drill-down
        st.markdown("### 🔍 Model Execution Trace & Run Drill-down")
        selected_run_id = st.selectbox("Select MLflow Run ID to investigate execution paths:", runs_df["run_id"].tolist())
        
        if selected_run_id:
            run_data = get_mlflow_run_details(selected_run_id)
            
            col_params, col_metrics = st.columns(2)
            
            with col_params:
                st.markdown("**Logged Model Parameters**")
                param_table = [{"Parameter": k, "Logged Value": v} for k, v in run_data["params"].items()]
                st.table(pd.DataFrame(param_table))
                
            with col_metrics:
                st.markdown("**Logged Serving Metrics**")
                metric_table = [{"Evaluation Metric": k, "Value": f"{v:.2f}" if k == "confidence_score" else f"{v:.1f}"} for k, v in run_data["metrics"].items()]
                st.table(pd.DataFrame(metric_table))
                
            # Render trace logs
            trace = run_data["trace"]
            if trace:
                st.markdown("**Model Execution Trace Paths (Inputs/Outputs Table)**")
                
                # Container layout representing prompt -> retrieve -> respond pipeline
                st.markdown(f"""
                <div class="trace-card">
                    <div style="color: #60A5FA; font-weight: bold; font-size: 0.8rem; margin-bottom: 5px;">[INPUT: USER QUERY]</div>
                    <div style="font-size: 1rem; color: #F1F5F9; font-family: monospace;">{trace.get('input_query')}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Context retrieved list
                retrieved_meta = json.loads(trace.get('retrieved_context_json', '[]'))
                st.markdown("**[PROCESS: CONTEXT RETRIEVAL]** Chunks loaded from Unity Catalog Vector Search index:")
                if retrieved_meta:
                    for chunk in retrieved_meta:
                        st.markdown(f"- 📄 `{chunk['doc_name']}` | Section: *{chunk['section']}* | Vector Similarity Score: **{chunk['similarity']:.4f}**")
                else:
                    st.markdown("*None (Blocked by security policies or no matches)*")
                    
                st.markdown("")
                st.markdown(f"""
                <div class="trace-card" style="border-left: 3px solid #10B981;">
                    <div style="color: #10B981; font-weight: bold; font-size: 0.8rem; margin-bottom: 5px;">[OUTPUT: GROUNDED LLM GENERATION]</div>
                    <div style="font-size: 0.95rem; color: #E2E8F0; line-height: 1.5;">{trace.get('output_response')}</div>
                </div>
                """, unsafe_allow_html=True)
