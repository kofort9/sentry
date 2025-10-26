#!/usr/bin/env python3
"""
CAMEL Dashboard - Streamlit UI for monitoring multi-agent test fixing workflow.

This dashboard provides:
- Real-time workflow monitoring
- Error reporting and recovery
- Agent activity tracking
- Historical workflow analysis
- Manual workflow control
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from sentries.camel.coordinator import CAMELCoordinator
    from sentries.chat import is_simulation_mode
    from sentries.runner_common import MODEL_PATCH, MODEL_PLAN, get_logger
except ImportError as e:
    st.error(f"❌ Import Error: {e}")
    st.error("Make sure you're running this from the project root directory.")
    st.stop()

# Configure logging
logger = get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="🐫 CAMEL Dashboard", page_icon="🐫", layout="wide", initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-card {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .error-card {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .warning-card {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .agent-status {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 0.25rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)


class CAMELDashboard:
    """Main dashboard class for CAMEL workflow monitoring."""

    _MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"

    def __init__(self):
        # Initialize session state first
        if "workflow_history" not in st.session_state:
            st.session_state.workflow_history = []
        if "current_workflow" not in st.session_state:
            st.session_state.current_workflow = None
        if "error_log" not in st.session_state:
            st.session_state.error_log = []
        if "auto_refresh" not in st.session_state:
            st.session_state.auto_refresh = False
        if "coordinator" not in st.session_state:
            st.session_state.coordinator = None
        if "llm_session_logs" not in st.session_state:
            st.session_state.llm_session_logs = []

        # Initialize coordinator in session state for persistence across reruns
        if st.session_state.coordinator is None:
            self.initialize_coordinator()

    @property
    def coordinator(self):
        """Get coordinator from session state."""
        return st.session_state.coordinator

    @coordinator.setter
    def coordinator(self, value):
        """Set coordinator in session state."""
        st.session_state.coordinator = value

    def initialize_coordinator(self) -> bool:
        """Initialize the CAMEL coordinator with error handling."""
        try:
            if not self.coordinator:
                # Pass the LLM logger to the coordinator
                self.coordinator = CAMELCoordinator(
                    MODEL_PLAN, MODEL_PATCH, llm_logger=self.log_llm_interaction
                )
                logger.info(
                    "🐫 CAMEL coordinator initialized successfully and persisted in session state"
                )
            return True
        except Exception as e:
            error_msg = f"Failed to initialize CAMEL coordinator: {str(e)}"
            logger.error(error_msg)
            self.log_error("Initialization Error", error_msg, {"component": "coordinator"})
            return False

    def log_error(self, error_type: str, message: str, context: Dict[str, Any] = None):
        """Log an error with timestamp and context."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "context": context or {},
        }
        st.session_state.error_log.append(error_entry)
        logger.error(f"{error_type}: {message}")

    def log_llm_interaction(
        self,
        agent_type: str,
        role: str,
        content: str,
        model: str = None,
        metadata: Dict[str, Any] = None,
    ):
        """Log LLM agent interactions for debugging."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_type": agent_type,  # "planner", "patcher", "coordinator"
            "role": role,  # "system", "user", "assistant"
            "content": (
                content[:1000] + "..." if len(content) > 1000 else content
            ),  # Truncate long content
            "model": model,
            "metadata": metadata or {},
        }
        st.session_state.llm_session_logs.append(log_entry)
        logger.debug(f"LLM [{agent_type}] {role}: {content[:100]}...")

    def render_header(self):
        """Render the dashboard header with status indicators."""
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.title("🐫 CAMEL Test Fix Dashboard")
            st.caption("Multi-Agent Workflow Monitoring & Control")

        with col2:
            # Simulation mode indicator
            if is_simulation_mode():
                st.success("🎭 Simulation Mode")
            else:
                st.info("🤖 Live Mode")

        with col3:
            # Auto-refresh toggle
            st.session_state.auto_refresh = st.checkbox(
                "Auto Refresh",
                value=st.session_state.auto_refresh,
                help="Automatically refresh the dashboard every 5 seconds",
            )

    def render_agent_status(self):
        """Render the current status of CAMEL agents."""
        st.subheader("🤖 Agent Status")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📋 Planner Agent")
            if self.coordinator and hasattr(self.coordinator, "planner"):
                planner_history = len(self.coordinator.planner.conversation_history)
                st.metric("Planning Sessions", planner_history)

                if planner_history > 0:
                    latest = self.coordinator.planner.conversation_history[-1]
                    st.text(f"Last Activity: {latest.get('timestamp', 'Unknown')}")
                else:
                    st.text("No activity yet")
            else:
                st.warning("Planner not initialized")

        with col2:
            st.markdown("### 🔧 Patcher Agent")
            if self.coordinator and hasattr(self.coordinator, "patcher"):
                patcher_history = len(self.coordinator.patcher.conversation_history)
                st.metric("Patching Sessions", patcher_history)

                if patcher_history > 0:
                    latest = self.coordinator.patcher.conversation_history[-1]
                    st.text(f"Last Activity: {latest.get('timestamp', 'Unknown')}")
                else:
                    st.text("No activity yet")
            else:
                st.warning("Patcher not initialized")

    def render_workflow_control(self):
        """Render workflow control panel."""
        st.subheader("⚡ Workflow Control")

        col1, col2 = st.columns([2, 1])

        with col1:
            test_output = st.text_area(
                "Test Failure Output",
                placeholder="Paste pytest output with failing tests here...",
                height=150,
                help="Paste the output from a failing pytest run",
            )

        with col2:
            st.markdown("### Quick Examples")

            if st.button("🧪 Demo Failure"):
                test_output = """
FAILED tests/test_camel_demo.py::test_simple_assertion - AssertionError: assert 1 == 2
tests/test_camel_demo.py:8: AssertionError
>       def test_simple_assertion():
>           assert 1 == 2  # This should fail for demo
E       AssertionError: assert 1 == 2

=========================== short test summary info ============================
FAILED tests/test_camel_demo.py::test_simple_assertion - AssertionError: assert 1 == 2
"""
                st.text_area("Generated Demo", value=test_output, height=100)

            if st.button("🔄 Clear Output"):
                test_output = ""

        # Workflow execution
        if st.button("🚀 Start Workflow", type="primary", disabled=not test_output.strip()):
            if not self.initialize_coordinator():
                st.error("❌ Cannot start workflow - coordinator initialization failed")
                return

            with st.spinner("🐫 CAMEL agents are working..."):
                self.run_workflow(test_output.strip())

    def run_workflow(self, test_output: str):
        """Execute the CAMEL workflow with progress tracking."""
        try:
            workflow_start = datetime.now()

            # Create a progress container
            progress_container = st.container()

            with progress_container:
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Step 1: Initialize
                status_text.text("🔄 Initializing workflow...")
                progress_bar.progress(10)
                time.sleep(0.5)

                # Step 2: Analysis
                status_text.text("📋 Planner agent analyzing failures...")
                progress_bar.progress(30)
                time.sleep(1)

                # Step 3: Planning
                status_text.text("🧠 Generating fix plan...")
                progress_bar.progress(50)
                time.sleep(1)

                # Step 4: Patching
                status_text.text("🔧 Patcher agent generating solutions...")
                progress_bar.progress(70)
                time.sleep(1)

                # Step 5: Validation
                status_text.text("✅ Validating generated patches...")
                progress_bar.progress(90)
                time.sleep(1)

                # Execute the actual workflow with LLM logging
                self.log_llm_interaction(
                    "coordinator",
                    "user",
                    f"Processing test failures: {test_output[:200]}...",
                    metadata={"workflow_start": workflow_start.isoformat()},
                )

                result = self.coordinator.process_test_failures(test_output)

                # Log workflow result
                self.log_llm_interaction(
                    "coordinator",
                    "assistant",
                    f"Workflow result: {'Success' if result.get('success') else 'Failed'}",
                    metadata={
                        "result_summary": {
                            "success": result.get("success", False),
                            "validation_attempts": result.get("validation_attempts", 0),
                            "error_count": len(
                                result.get("error_recovery_summary", {}).get("error_history", [])
                            ),
                        }
                    },
                )

                # Step 6: Complete
                progress_bar.progress(100)

                if result.get("success"):
                    status_text.text("✅ Workflow completed successfully!")
                    self.display_success_result(result, workflow_start)
                else:
                    status_text.text("❌ Workflow failed")
                    self.display_error_result(result, workflow_start)

                # Store in history
                workflow_record = {
                    "timestamp": workflow_start.isoformat(),
                    "duration": (datetime.now() - workflow_start).total_seconds(),
                    "success": result.get("success", False),
                    "result": result,
                }
                st.session_state.workflow_history.append(workflow_record)

        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            self.log_error("Workflow Error", error_msg, {"test_output": test_output[:200]})
            st.error(f"❌ {error_msg}")

    def display_success_result(self, result: Dict[str, Any], start_time: datetime):
        """Display successful workflow results."""
        st.success("🎉 **Workflow Completed Successfully!**")

        col1, col2, col3 = st.columns(3)

        with col1:
            duration = (datetime.now() - start_time).total_seconds()
            st.metric("Duration", f"{duration:.2f}s")

        with col2:
            validation_attempts = len(result.get("validation_attempts", []))
            st.metric("Validation Attempts", validation_attempts)

        with col3:
            plan_confidence = result.get("plan", {}).get("confidence", 0)
            st.metric("Plan Confidence", f"{plan_confidence:.1%}")

        # Show plan details
        if "plan" in result:
            with st.expander("📋 Generated Plan", expanded=True):
                plan = result["plan"]
                st.write(f"**Strategy:** {plan.get('plan', 'N/A')}")
                st.write(f"**Target Files:** {', '.join(plan.get('target_files', []))}")
                st.write(f"**Fix Strategy:** {plan.get('fix_strategy', 'N/A')}")

        # Show generated patch
        if result.get("unified_diff"):
            with st.expander("🔧 Generated Patch"):
                st.code(result["unified_diff"], language="diff")

        # Show validation details
        if result.get("validation_attempts"):
            with st.expander("✅ Validation Details"):
                for i, attempt in enumerate(result["validation_attempts"], 1):
                    validation = attempt.get("validation", {})
                    if validation.get("valid"):
                        st.success(f"Attempt {i}: ✅ Valid")
                    else:
                        st.error(
                            f"Attempt {i}: ❌ Issues: {', '.join(validation.get('issues', []))}"
                        )

    def display_error_result(self, result: Dict[str, Any], start_time: datetime):
        """Display failed workflow results with debugging info."""
        error_msg = result.get("error", "Unknown error occurred")

        st.markdown(
            f"""
        <div class="error-card">
            <h4>❌ Workflow Failed</h4>
            <p><strong>Error:</strong> {error_msg}</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Show debugging information
        with st.expander("🔍 Debug Information", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Error Details:**")
                st.json({"error": error_msg, "timestamp": start_time.isoformat()})

            with col2:
                st.write("**Workflow Context:**")
                context = {
                    "plan_success": "plan" in result,
                    "analysis_success": "analysis" in result,
                    "validation_attempts": len(result.get("validation_attempts", [])),
                }
                st.json(context)

        # Show any partial results
        if "plan" in result:
            with st.expander("📋 Partial Plan Generated"):
                st.json(result["plan"])

    def render_mermaid_diagram(self, mermaid_code: str, height: int = 540):
        """Render a Mermaid diagram using a lightweight Streamlit component."""
        mermaid_html = f"""
        <div class="mermaid">
        {mermaid_code}
        </div>
        <script src="{self._MERMAID_CDN}"></script>
        <script>
            if (window.mermaid) {{
                window.mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
            }}
        </script>
        """
        components.html(mermaid_html, height=height)

    def render_architecture_overview(self):
        """Render a static GitHub Actions-style architecture diagram."""
        st.subheader("🏗️ CAMEL Workflow Architecture")
        st.caption("Static Mermaid snapshot of how failures move through the CAMEL pipeline.")

        mermaid_diagram = dedent(
            """
            flowchart LR
                classDef trigger fill:#1f6feb,stroke:#0d408b,color:#ffffff,font-size:13px
                classDef agent fill:#f9d949,stroke:#b8860b,color:#111111,font-size:13px
                classDef service fill:#7c3aed,stroke:#4c1d95,color:#ffffff,font-size:13px
                classDef data fill:#3fb950,stroke:#238636,color:#111111,font-size:13px
                classDef status fill:#1b1f24,stroke:#30363d,color:#c9d1d9,font-size:13px

                Trigger[Pytest Failure Logs]:::trigger --> Coord{{CAMEL Coordinator}}:::service
                Coord --> Planner[[Planner Agent]]:::agent
                Planner --> Context[(Context Packs\\n+ Target Files)]:::data
                Context --> Patcher[[Patcher Agent]]:::agent
                Patcher --> PatchEngine[[Patch Engine]]:::service
                PatchEngine --> RepoOps[(Git Ops + JSON patches)]:::data
                RepoOps --> Validator{{Validation Runner}}:::service
                Validator -->|pass| Success([Ready to Commit]):::status
                Validator -->|fail| Recovery[[Global Error Recovery]]:::service
                Recovery --> Coord
                Coord --> Telemetry[(LLM Logs, Metrics, History)]:::data
                Telemetry --> Dashboard[(Streamlit Dashboard)]:::service
            """
        ).strip()

        self.render_mermaid_diagram(mermaid_diagram)

        st.markdown(
            """
            - **Trigger**: Pytest failures seed the coordinator.
            - **Planner/Patcher**: Planner builds context packs, patcher turns them into diffs.
            - **Patch Engine**: Applies diffs and hands results to repo + validators.
            - **Validation Loop**: Failures route through error recovery before retrying.
            - **Observability**: Coordinator streams metrics directly into this dashboard.
            """
        )

    def render_workflow_history(self):
        """Render historical workflow data and analytics."""
        st.subheader("📊 Workflow History")

        if not st.session_state.workflow_history:
            st.info("No workflow history yet. Run a workflow to see analytics here.")
            return

        # Convert to DataFrame for analysis
        df = pd.DataFrame(st.session_state.workflow_history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        col1, col2 = st.columns(2)

        with col1:
            # Success rate metrics
            total_runs = len(df)
            success_column = df["success"].fillna(False)
            successful_runs = int(success_column.sum())
            success_rate = (successful_runs / total_runs) * 100 if total_runs > 0 else 0

            st.metric("Total Runs", total_runs)
            st.metric("Success Rate", f"{success_rate:.1f}%")
            st.metric("Average Duration", f"{df['duration'].mean():.2f}s")

        with col2:
            # Success/failure chart
            success_counts = df["success"].value_counts()
            fig = px.pie(
                values=success_counts.values,
                names=["Success" if x else "Failed" for x in success_counts.index],
                color_discrete_map={"Success": "#28a745", "Failed": "#dc3545"},
                title="Workflow Success Rate",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Timeline of workflows
        if len(df) > 1:
            fig_timeline = px.scatter(
                df,
                x="timestamp",
                y="duration",
                color="success",
                title="Workflow Performance Over Time",
                color_discrete_map={True: "#28a745", False: "#dc3545"},
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

        # Recent workflows table
        st.write("### Recent Workflows")
        display_df = df[["timestamp", "success", "duration"]].copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        display_df["success"] = display_df["success"].map({True: "✅", False: "❌"})
        display_df["duration"] = display_df["duration"].round(2).astype(str) + "s"

        st.dataframe(
            display_df.sort_values("timestamp", ascending=False).head(10),
            use_container_width=True,
            hide_index=True,
        )

    def render_error_log(self):
        """Render enhanced error log with recovery information."""
        st.subheader("🚨 Error Log & Recovery")

        # Get error recovery status from coordinator
        if self.coordinator:
            error_recovery_status = self.coordinator.get_error_recovery_status()
        else:
            error_recovery_status = {"total_errors": 0, "recovery_rate": 0.0}

        # Error recovery metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Errors", error_recovery_status.get("total_errors", 0))

        with col2:
            recovery_rate = error_recovery_status.get("recovery_rate", 0.0)
            st.metric("Recovery Rate", f"{recovery_rate:.1%}")

        with col3:
            successful_recoveries = error_recovery_status.get("successful_recoveries", 0)
            st.metric("Successful Recoveries", successful_recoveries)

        with col4:
            if st.button("🗑️ Clear Error History"):
                if self.coordinator:
                    self.coordinator.clear_error_history()
                st.session_state.error_log = []
                st.rerun()

        # Error category breakdown
        if error_recovery_status.get("by_category"):
            st.write("### Error Categories")

            col1, col2 = st.columns(2)

            with col1:
                # Category pie chart
                category_data = error_recovery_status["by_category"]
                if category_data:
                    fig_cat = px.pie(
                        values=list(category_data.values()),
                        names=list(category_data.keys()),
                        title="Errors by Category",
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)

            with col2:
                # Severity breakdown
                severity_data = error_recovery_status.get("by_severity", {})
                if severity_data:
                    fig_sev = px.bar(
                        x=list(severity_data.keys()),
                        y=list(severity_data.values()),
                        title="Errors by Severity",
                        color=list(severity_data.keys()),
                        color_discrete_map={
                            "low": "#28a745",
                            "medium": "#ffc107",
                            "high": "#fd7e14",
                            "critical": "#dc3545",
                        },
                    )
                    st.plotly_chart(fig_sev, use_container_width=True)

        # Recent errors with enhanced details
        recent_errors = error_recovery_status.get("recent_errors", [])
        if recent_errors:
            st.write("### Recent Errors")

            for error in recent_errors[-5:]:  # Show last 5 errors
                error_time = datetime.fromisoformat(error["timestamp"])
                time_ago = datetime.now() - error_time

                # Color code by severity
                severity = error.get("severity", "medium")
                if severity == "critical":
                    icon = "🔴"
                elif severity == "high":
                    icon = "🟠"
                elif severity == "medium":
                    icon = "🟡"
                else:
                    icon = "🟢"

                recovery_status = (
                    "✅ Recovered" if error.get("recovery_successful") else "❌ Not Recovered"
                )
                retry_info = (
                    f"(Retries: {error.get('retry_count', 0)})"
                    if error.get("retry_count", 0) > 0
                    else ""
                )

                minutes_ago = int(time_ago.total_seconds() // 60)
                expander_title = (
                    f"{icon} {error.get('category', 'Unknown')} - "
                    f"{minutes_ago}m ago {recovery_status} {retry_info}"
                ).strip()

                with st.expander(expander_title):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Time:** {error_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write(f"**Category:** {error.get('category', 'Unknown')}")
                        st.write(f"**Severity:** {error.get('severity', 'Unknown')}")
                        st.write(f"**Message:** {error.get('message', 'No message')}")

                    with col2:
                        attempted = "Yes" if error.get("recovery_attempted") else "No"
                        succeeded = "Yes" if error.get("recovery_successful") else "No"
                        st.write(f"**Recovery Attempted:** {attempted}")
                        st.write(f"**Recovery Successful:** {succeeded}")
                        st.write(f"**Retry Count:** {error.get('retry_count', 0)}")

                    if error.get("context"):
                        st.write("**Context:**")
                        st.json(error["context"])

                    if error.get("details"):
                        with st.expander("🔍 Technical Details"):
                            st.code(error["details"], language="text")

        elif error_recovery_status.get("total_errors", 0) == 0:
            st.success("✅ No errors logged in the recovery system")
        else:
            st.info("ℹ️ No recent errors to display")

    def render_llm_sessions(self):
        """Render LLM agent conversation logs."""
        st.subheader("💬 LLM Session Logs")

        # Controls
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🗑️ Clear Session Logs"):
                st.session_state.llm_session_logs = []
                st.rerun()

        with col2:
            agent_filter = st.selectbox(
                "Filter by Agent",
                ["All", "planner", "patcher", "coordinator"],
                key="llm_agent_filter",
            )

        with col3:
            role_filter = st.selectbox(
                "Filter by Role", ["All", "system", "user", "assistant"], key="llm_role_filter"
            )

        # Session logs
        logs = st.session_state.llm_session_logs

        # Apply filters
        if agent_filter != "All":
            logs = [log for log in logs if log.get("agent_type") == agent_filter]
        if role_filter != "All":
            logs = [log for log in logs if log.get("role") == role_filter]

        if logs:
            st.write(f"**Showing {len(logs)} interactions**")

            # Display logs in reverse chronological order (newest first)
            for i, log in enumerate(reversed(logs[-20:])):  # Show last 20 interactions
                timestamp = datetime.fromisoformat(log["timestamp"])
                time_ago = datetime.now() - timestamp

                # Color code by agent type
                agent_type = log.get("agent_type", "unknown")
                if agent_type == "planner":
                    agent_icon = "🧠"
                elif agent_type == "patcher":
                    agent_icon = "🔧"
                elif agent_type == "coordinator":
                    agent_icon = "🎯"
                else:
                    agent_icon = "🤖"

                # Role styling
                role = log.get("role", "unknown")
                if role == "system":
                    role_icon = "⚙️"
                elif role == "user":
                    role_icon = "👤"
                elif role == "assistant":
                    role_icon = "🤖"
                else:
                    role_icon = "❓"

                # Create expandable log entry
                minutes_ago = int(time_ago.total_seconds() // 60)
                header = (
                    f"{agent_icon} **{agent_type.title()}** "
                    f"{role_icon} *{role}* - {minutes_ago}m ago"
                )

                with st.expander(header, expanded=(i < 3)):  # Expand first 3 entries
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write("**Content:**")
                        if len(log["content"]) > 500:
                            st.text_area("", value=log["content"], height=150, key=f"content_{i}")
                        else:
                            st.write(log["content"])

                    with col2:
                        st.write(f"**Timestamp:** {timestamp.strftime('%H:%M:%S')}")
                        st.write(f"**Agent:** {agent_type}")
                        st.write(f"**Role:** {role}")
                        if log.get("model"):
                            st.write(f"**Model:** {log['model']}")
                        if log.get("metadata"):
                            st.write("**Metadata:**")
                            st.json(log["metadata"])
        else:
            st.info(
                "ℹ️ No LLM session logs available. "
                "Logs will appear here when agents interact with LLMs."
            )
            st.write("**Note:** LLM logging is automatically captured during workflow execution.")

    def render_sidebar(self):
        """Render the sidebar with settings and controls."""
        with st.sidebar:
            st.header("⚙️ Settings")

            # Model configuration
            st.subheader("🤖 Model Configuration")
            st.text(f"Planner: {MODEL_PLAN}")
            st.text(f"Patcher: {MODEL_PATCH}")

            if is_simulation_mode():
                st.info("🎭 Running in simulation mode")
            else:
                st.success("🤖 Connected to live models")

            st.divider()

            # Dashboard controls
            st.subheader("📊 Dashboard Controls")

            if st.button("🔄 Refresh Data"):
                st.rerun()

            if st.button("💾 Export History"):
                if st.session_state.workflow_history:
                    df = pd.DataFrame(st.session_state.workflow_history)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ Download CSV",
                        csv,
                        file_name=(
                            f"camel_workflow_history_"
                            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        ),
                        mime="text/csv",
                    )
                else:
                    st.warning("No history to export")

            st.divider()

            # System info
            st.subheader("📈 System Info")
            st.text(f"Dashboard Started: {datetime.now().strftime('%H:%M:%S')}")

            if self.coordinator:
                st.success("✅ CAMEL Coordinator Ready (Persistent)")
                # Show coordinator info
                try:
                    # Check if coordinator has error recovery status
                    if hasattr(self.coordinator, "get_error_recovery_status"):
                        error_status = self.coordinator.get_error_recovery_status()
                        total_errors = len(error_status.get("error_history", []))
                        if total_errors > 0:
                            st.info(f"📊 {total_errors} errors recorded")
                except Exception:
                    pass  # Skip if error recovery not available
            else:
                st.error("❌ Failed to Initialize Coordinator")

    def run(self):
        """Main dashboard run method."""
        # Auto-refresh logic
        if st.session_state.auto_refresh:
            time.sleep(5)
            st.rerun()

        # Render all components
        self.render_header()
        self.render_sidebar()

        # Main tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "🎛️ Control Panel",
                "🤖 Agent Status",
                "📊 Analytics",
                "🚨 Error Log",
                "💬 LLM Sessions",
                "🏗️ Architecture",
            ]
        )

        with tab1:
            self.render_workflow_control()

        with tab2:
            self.render_agent_status()

        with tab3:
            self.render_workflow_history()

        with tab4:
            self.render_error_log()

        with tab5:
            self.render_llm_sessions()

        with tab6:
            self.render_architecture_overview()


def main():
    """Main application entry point."""
    try:
        dashboard = CAMELDashboard()
        dashboard.run()
    except Exception as e:
        st.error(f"❌ Dashboard Error: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()
