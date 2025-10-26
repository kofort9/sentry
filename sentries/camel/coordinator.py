"""Coordinator for the CAMEL planner/patcher workflow."""

import datetime
from typing import Any, Dict

from .planner import PlannerAgent
from .patcher import PatcherAgent
from .error_recovery import global_error_recovery, with_error_recovery
from ..runner_common import get_logger

logger = get_logger(__name__)


class CAMELCoordinator:
    """
    Simple coordinator that manages the interaction between PlannerAgent and PatcherAgent.

    Implements a resource-conscious 2-agent workflow with structured logging.
    """

    def __init__(self, planner_model: str, patcher_model: str, llm_logger=None):
        self.planner = PlannerAgent(planner_model, llm_logger=llm_logger)
        self.patcher = PatcherAgent(patcher_model, llm_logger=llm_logger)
        self.workflow_history = []
        self.llm_logger = llm_logger

        logger.info("🚀 Created CAMEL coordinator with planner and patcher agents")

    def process_test_failures(self, test_output: str) -> Dict[str, Any]:
        """
        Process test failures using the 2-agent workflow with enhanced error recovery.

        Args:
            test_output: Raw pytest output with failures

        Returns:
            Complete workflow results with agent interactions and error recovery info
        """
        try:
            workflow_start = datetime.datetime.now()
            logger.info("🎯 Starting CAMEL 2-agent workflow for test failures")

            # Step 1: Planning with error recovery
            logger.info("📋 Planner agent analyzing test failures...")
            planning_result = global_error_recovery.with_recovery(
                lambda: self.planner.analyze_and_plan(test_output),
                context={"phase": "planning", "agent": "planner", "test_output_length": len(test_output)},
                custom_max_retries=2
            )

            if not planning_result.get("success"):
                return {
                    "success": False,
                    "error": planning_result.get("error"),
                    "workflow_history": self._create_workflow_summary(workflow_start),
                    "error_recovery_summary": global_error_recovery.get_error_summary(),
                }

            plan = planning_result.get("plan")
            analysis = planning_result.get("analysis")

            # Build enhanced context with explicit file paths
            context_packs = analysis.get("context_packs", []) if analysis else []
            if context_packs:
                enhanced_context_parts = []
                for pack in context_packs:
                    # Add file header for each pack
                    test_file = pack.get("test_file", "unknown_file")
                    enhanced_context_parts.append(f"=== File: {test_file} ===")
                    enhanced_context_parts.extend(pack.get("context_parts", []))
                
                context = "\n".join(enhanced_context_parts)
                
                # Log the enhanced context for debugging
                file_list = [pack.get("test_file", "unknown") for pack in context_packs]
                logger.info(f"📁 Enhanced context includes {len(context_packs)} files: {file_list}")
            else:
                # Fallback if no context packs available
                context = "No test context available"
                logger.warning("⚠️ No context packs found in planning result")

            # Step 2: Patching with error recovery
            logger.info("🔧 Patcher agent generating patch from plan...")
            patching_result = global_error_recovery.with_recovery(
                lambda: self.patcher.generate_patch(plan, context),
                context={"phase": "patching", "agent": "patcher", "plan_complexity": len(str(plan))},
                custom_max_retries=3  # Allow more retries for patching since it has iterative validation
            )

            workflow_end = datetime.datetime.now()
            workflow_duration = (workflow_end - workflow_start).total_seconds()

            result = {
                "success": patching_result.get("success", False),
                "plan": plan,
                "analysis": analysis,
                "json_operations": patching_result.get("json_operations"),
                "unified_diff": patching_result.get("unified_diff"),
                "validation": patching_result.get("validation"),
                "validation_attempts": patching_result.get("validation_attempts", []),
                "error": patching_result.get("error"),
                "workflow_history": self._create_workflow_summary(workflow_start),
                "workflow_duration": workflow_duration,
                "error_recovery_summary": global_error_recovery.get_error_summary(),
            }

            logger.info(f"✅ CAMEL workflow completed in {workflow_duration:.2f}s")
            return result

        except Exception as exc:
            # Classify and log the error through our recovery system
            global_error_recovery.classify_error(exc, {
                "component": "coordinator",
                "operation": "process_test_failures",
                "test_output_length": len(test_output)
            })
            
            logger.error(f"Error in CAMEL coordinator: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "workflow_history": self._create_workflow_summary(workflow_start),
                "error_recovery_summary": global_error_recovery.get_error_summary(),
            }

    def _create_workflow_summary(self, start_time: datetime.datetime) -> Dict[str, Any]:
        """Create a structured summary of the workflow for observability."""
        end_time = datetime.datetime.now()

        return {
            "framework": "CAMEL",
            "version": "Phase1",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "agents": [
                {
                    "name": "planner",
                    "interactions": len(self.planner.conversation_history),
                    "last_interaction": (
                        self.planner.conversation_history[-1]["timestamp"]
                        if self.planner.conversation_history
                        else None
                    ),
                },
                {
                    "name": "patcher",
                    "interactions": len(self.patcher.conversation_history),
                    "last_interaction": (
                        self.patcher.conversation_history[-1]["timestamp"]
                        if self.patcher.conversation_history
                        else None
                    ),
                },
            ],
            "total_interactions": (
                len(self.planner.conversation_history)
                + len(self.patcher.conversation_history)
            ),
        }

    def get_error_recovery_status(self) -> Dict[str, Any]:
        """
        Get the current error recovery status for dashboard monitoring.
        
        Returns:
            Dictionary with error recovery statistics and recent errors
        """
        return global_error_recovery.get_error_summary()

    def clear_error_history(self):
        """Clear the error recovery history."""
        global_error_recovery.clear_history()
        logger.info("Error recovery history cleared")
