"""Coordinator for the CAMEL planner/patcher workflow."""

import datetime
from typing import Any, Dict

from .planner import PlannerAgent
from .patcher import PatcherAgent
from ..runner_common import get_logger

logger = get_logger(__name__)


class CAMELCoordinator:
    """
    Simple coordinator that manages the interaction between PlannerAgent and PatcherAgent.

    Implements a resource-conscious 2-agent workflow with structured logging.
    """

    def __init__(self, planner_model: str, patcher_model: str):
        self.planner = PlannerAgent(planner_model)
        self.patcher = PatcherAgent(patcher_model)
        self.workflow_history = []

        logger.info("🚀 Created CAMEL coordinator with planner and patcher agents")

    def process_test_failures(self, test_output: str) -> Dict[str, Any]:
        """
        Process test failures using the 2-agent workflow.

        Args:
            test_output: Raw pytest output with failures

        Returns:
            Complete workflow results with agent interactions
        """
        try:
            workflow_start = datetime.datetime.now()
            logger.info("🎯 Starting CAMEL 2-agent workflow for test failures")

            logger.info("📋 Planner agent analyzing test failures...")
            planning_result = self.planner.analyze_and_plan(test_output)

            if not planning_result.get("success"):
                return {
                    "success": False,
                    "error": planning_result.get("error"),
                    "workflow_history": self._create_workflow_summary(workflow_start),
                }

            plan = planning_result.get("plan")
            analysis = planning_result.get("analysis")

            context_parts = []
            if analysis and "context_packs" in analysis:
                for pack in analysis["context_packs"]:
                    context_parts.extend(pack.get("context_parts", []))

            context = "\n".join(context_parts)

            logger.info("🔧 Patcher agent generating patch from plan...")
            patching_result = self.patcher.generate_patch(plan, context)

            workflow_end = datetime.datetime.now()
            workflow_duration = (workflow_end - workflow_start).total_seconds()

            result = {
                "success": patching_result.get("success", False),
                "plan": plan,
                "analysis": analysis,
                "json_operations": patching_result.get("json_operations"),
                "unified_diff": patching_result.get("unified_diff"),
                "validation": patching_result.get("validation"),
                "error": patching_result.get("error"),
                "workflow_history": self._create_workflow_summary(workflow_start),
                "workflow_duration": workflow_duration,
            }

            logger.info(f"✅ CAMEL workflow completed in {workflow_duration:.2f}s")
            return result

        except Exception as exc:
            logger.error(f"Error in CAMEL coordinator: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "workflow_history": self._create_workflow_summary(workflow_start),
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
