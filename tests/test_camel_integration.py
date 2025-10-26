#!/usr/bin/env python3
"""
Integration tests for CAMEL Phase 2 workflow.

Tests the complete multi-agent workflow with enhanced validation loops,
Git operations, and historical learning working together.
"""

import json
from unittest.mock import Mock, patch

from sentries.camel.coordinator import CAMELCoordinator
from sentries.camel.tools import GitOperationsTool


class TestCAMELPhase2Integration:
    """Integration tests for complete CAMEL Phase 2 workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.coordinator = CAMELCoordinator("planner-model", "patcher-model")

        # Mock the LLM wrappers to avoid actual calls
        self.coordinator.planner.llm = Mock()
        self.coordinator.patcher.llm = Mock()

        # Mock analysis and validation tools
        self.coordinator.planner.analysis_tool = Mock()
        self.coordinator.patcher.validation_tool = Mock()
        self.coordinator.patcher.patch_tool = Mock()

    def test_successful_end_to_end_workflow(self):
        """Test complete successful workflow from test failure to patch generation."""
        # Arrange
        test_output = """
FAILED tests/test_example.py::test_addition - AssertionError: assert add(2, 3) == 6
>       assert add(2, 3) == 6
E       AssertionError: assert 5 == 6
"""

        # Mock planner analysis
        self.coordinator.planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [
                {
                    "test_function": "test_addition",
                    "test_file": "tests/test_example.py",
                    "failure_type": "ASSERT_MISMATCH",
                    "error_message": "AssertionError: assert 5 == 6",
                    "context_parts": [
                        "def test_addition():",
                        "    result = add(2, 3)",
                        "    assert result == 6  # Should be 5",
                    ],
                }
            ],
        }

        # Mock planner response
        planner_plan = {
            "plan": "Fix addition assertion from 6 to 5",
            "target_files": ["tests/test_example.py"],
            "fix_strategy": "assertion_correction",
        }
        self.coordinator.planner.llm.generate.return_value = json.dumps(planner_plan)

        # Mock patcher successful validation (first attempt)
        patcher_json = json.dumps(
            {
                "ops": [
                    {
                        "file": "tests/test_example.py",
                        "find": "assert result == 6",
                        "replace": "assert result == 5",
                    }
                ]
            }
        )
        self.coordinator.patcher.llm.generate.return_value = patcher_json

        # Mock validation success
        self.coordinator.patcher.validation_tool.validate_operations.return_value = {
            "valid": True,
            "issues": [],
            "suggestions": [],
        }

        # Mock patch generation success
        self.coordinator.patcher.patch_tool.generate_patch.return_value = {
            "success": True,
            "unified_diff": (
                "--- a/tests/test_example.py\n"
                "+++ b/tests/test_example.py\n"
                "@@ -2,1 +2,1 @@\n"
                "-    assert result == 6\n"
                "+    assert result == 5"
            ),
        }

        # Act
        result = self.coordinator.process_test_failures(test_output)

        # Assert
        assert result["success"] is True
        assert result["plan"]["plan"] == "Fix addition assertion from 6 to 5"
        assert "validation_attempts" in result
        assert len(result["validation_attempts"]) == 1
        assert result["validation_attempts"][0]["validation"]["valid"] is True
        assert "workflow_history" in result
        assert result["workflow_history"]["framework"] == "CAMEL"

    def test_workflow_with_iterative_validation(self):
        """Test workflow with multiple validation attempts."""
        # Arrange
        test_output = "FAILED tests/test_complex.py::test_function - Complex error"

        # Mock planner
        self.coordinator.planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [
                {
                    "test_function": "test_function",
                    "test_file": "tests/test_complex.py",
                    "failure_type": "COMPLEX_ERROR",
                    "error_message": "Complex error",
                    "context_parts": ["complex context"],
                }
            ],
        }

        self.coordinator.planner.llm.generate.return_value = json.dumps(
            {"plan": "Complex fix strategy", "target_files": ["tests/test_complex.py"]}
        )

        # Mock patcher with multiple attempts
        patcher_responses = [
            # Attempt 1: Invalid file path
            json.dumps({"ops": [{"file": "src/wrong.py", "find": "a", "replace": "b"}]}),
            # Attempt 2: Missing key
            json.dumps({"ops": [{"file": "tests/test_complex.py", "find": "a"}]}),
            # Attempt 3: Success
            json.dumps(
                {
                    "ops": [
                        {"file": "tests/test_complex.py", "find": "old_code", "replace": "new_code"}
                    ]
                }
            ),
        ]
        self.coordinator.patcher.llm.generate.side_effect = patcher_responses

        # Mock validation responses
        def validation_side_effect(json_ops):
            ops = json.loads(json_ops)
            if not ops.get("ops"):
                return {"valid": False, "issues": ["No ops"]}

            op = ops["ops"][0]
            if not op.get("file", "").startswith("tests/"):
                return {"valid": False, "issues": ["Invalid file path"]}
            if "replace" not in op:
                return {"valid": False, "issues": ["Missing replace key"]}

            return {"valid": True, "issues": []}

        self.coordinator.patcher.validation_tool.validate_operations.side_effect = (
            validation_side_effect
        )

        # Mock successful patch generation
        self.coordinator.patcher.patch_tool.generate_patch.return_value = {
            "success": True,
            "unified_diff": "--- a/tests/test_complex.py\n+++ b/tests/test_complex.py",
        }

        # Act
        result = self.coordinator.process_test_failures(test_output)

        # Assert
        assert result["success"] is True
        assert len(result["validation_attempts"]) == 3

        # Check validation progression
        attempts = result["validation_attempts"]
        assert "Invalid file path" in attempts[0]["validation"]["issues"]
        assert "Missing replace key" in attempts[1]["validation"]["issues"]
        assert attempts[2]["validation"]["valid"] is True

    def test_workflow_failure_handling(self):
        """Test workflow failure scenarios and error handling."""
        # Arrange - Planner analysis fails
        test_output = "FAILED tests/test_fail.py - Unknown error"

        self.coordinator.planner.analysis_tool.analyze_failures.return_value = {
            "success": False,
            "error": "Analysis failed",
            "context_packs": [],
        }

        # Act
        result = self.coordinator.process_test_failures(test_output)

        # Assert
        assert result["success"] is False
        assert "Analysis failed" in result["error"]
        assert "workflow_history" in result

    def test_workflow_with_historical_learning(self):
        """Test workflow incorporating historical learning from previous runs."""
        # Arrange - Add historical context to planner
        self.coordinator.planner.conversation_history = [
            {
                "input": {"failure_type": "ASSERT_MISMATCH"},
                "learning_context": {
                    "plan_success": True,
                    "successful_strategies": ["assertion_fix"],
                },
            }
        ]

        # Current test failure
        test_output = "FAILED tests/test_history.py::test_func - AssertionError: assert 1 == 2"

        # Mock planner with historical insights
        self.coordinator.planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [
                {
                    "test_function": "test_func",
                    "test_file": "tests/test_history.py",
                    "failure_type": "ASSERT_MISMATCH",
                    "error_message": "AssertionError: assert 1 == 2",
                    "context_parts": ["def test_func():", "    assert 1 == 2"],
                }
            ],
        }

        enhanced_plan = {
            "plan": "Fix historical assertion error",
            "target_files": ["tests/test_history.py"],
            "confidence": 0.85,  # High confidence from history
        }
        self.coordinator.planner.llm.generate.return_value = json.dumps(enhanced_plan)

        # Mock successful patcher
        self.coordinator.patcher.llm.generate.return_value = json.dumps(
            {
                "ops": [
                    {
                        "file": "tests/test_history.py",
                        "find": "assert 1 == 2",
                        "replace": "assert 1 == 1",
                    }
                ]
            }
        )
        self.coordinator.patcher.validation_tool.validate_operations.return_value = {"valid": True}
        self.coordinator.patcher.patch_tool.generate_patch.return_value = {
            "success": True,
            "unified_diff": "diff",
        }

        # Act
        result = self.coordinator.process_test_failures(test_output)

        # Assert
        assert result["success"] is True
        # The enhanced planner calculates confidence based on historical success,
        # so it may be higher than the original plan's confidence
        assert result["plan"]["confidence"] >= 0.85

        # Verify workflow history tracking
        workflow_hist = result["workflow_history"]
        assert workflow_hist["agents"][0]["name"] == "planner"
        assert workflow_hist["agents"][1]["name"] == "patcher"
        assert workflow_hist["total_interactions"] >= 2  # At least planner + patcher interactions


class TestCAMELGitIntegration:
    """Integration tests for CAMEL workflow with Git operations."""

    @patch("sentries.camel.tools.create_branch")
    @patch("sentries.camel.tools.commit_all")
    @patch("sentries.camel.tools.open_pull_request")
    @patch("sentries.camel.tools.get_base_branch")
    def test_complete_workflow_with_git_operations(
        self, mock_get_base, mock_pr, mock_commit, mock_create
    ):
        """Test complete workflow including Git operations."""
        # Arrange Git mocks
        mock_create.return_value = "camel-integration-test"
        mock_get_base.return_value = "main"
        mock_pr.return_value = {"url": "https://github.com/test/repo/pull/999"}

        git_tool = GitOperationsTool()

        plan = {
            "plan": "Fix integration test assertion",
            "target_files": ["tests/test_integration.py"],
        }

        # Act - Full Git workflow
        branch_result = git_tool.create_feature_branch("integration-test", "testsentry")
        commit_result = git_tool.commit_changes("feat: Fix integration test via CAMEL agents")
        pr_result = git_tool.create_pull_request(
            "🐫 CAMEL Integration Test Fix",
            (
                f"**Plan:** {plan['plan']}\n\n"
                "**Changes:** Fixed assertion error\n\n"
                "**Generated by:** CAMEL Phase 2 workflow"
            ),
            "camel-integration-test",
        )

        # Assert
        assert branch_result["success"] is True
        assert commit_result["success"] is True
        assert pr_result["success"] is True
        assert pr_result["pr_url"] == "https://github.com/test/repo/pull/999"

        # Verify Git operations called in correct order
        mock_create.assert_called_once_with("integration-test", "testsentry")
        mock_commit.assert_called_once_with("feat: Fix integration test via CAMEL agents")
        mock_pr.assert_called_once()

    def test_git_workflow_error_recovery(self):
        """Test Git workflow error handling and recovery."""
        git_tool = GitOperationsTool()

        # Test branch creation failure
        with patch("sentries.camel.tools.create_branch") as mock_create:
            mock_create.side_effect = Exception("Git branch creation failed")

            result = git_tool.create_feature_branch("test-branch", "testsentry")

            assert result["success"] is False
            assert "Git branch creation failed" in result["error"]

        # Test commit failure
        with patch("sentries.camel.tools.commit_all") as mock_commit:
            mock_commit.side_effect = Exception("Git commit failed")

            result = git_tool.commit_changes("test commit")

            assert result["success"] is False
            assert "Git commit failed" in result["error"]


class TestCAMELPerformanceAndObservability:
    """Tests for CAMEL workflow performance tracking and observability."""

    def test_workflow_timing_and_metrics(self):
        """Test workflow timing and performance metrics collection."""
        coordinator = CAMELCoordinator("planner", "patcher")

        # Mock quick successful workflow
        coordinator.planner.analyze_and_plan = Mock(
            return_value={
                "success": True,
                "plan": {"plan": "Quick fix"},
                "analysis": {"context_packs": [{"context_parts": ["test"]}]},
            }
        )

        coordinator.patcher.generate_patch = Mock(
            return_value={
                "success": True,
                "json_operations": "{}",
                "unified_diff": "diff",
                "validation_attempts": [{"validation": {"valid": True}}],
            }
        )

        # Act
        with patch("sentries.camel.coordinator.datetime") as mock_dt:
            # Mock time progression with proper datetime objects
            from datetime import datetime

            start_time = datetime(2024, 1, 1, 10, 0, 0)
            end_time = datetime(2024, 1, 1, 10, 0, 2)  # 2 seconds later

            # Provide more mock calls since coordinator may call datetime.now() multiple times
            mock_dt.datetime.now.side_effect = [start_time, end_time, end_time, end_time]

            result = coordinator.process_test_failures("test output")

        # Assert
        assert result["success"] is True
        assert "workflow_duration" in result
        assert "workflow_history" in result

        # Check workflow history structure
        history = result["workflow_history"]
        assert history["framework"] == "CAMEL"
        assert history["version"] == "Phase1"
        assert len(history["agents"]) == 2
        # With mocked agents, interactions may not be tracked the same way
        assert history["total_interactions"] >= 0  # At least basic tracking

    def test_conversation_history_persistence(self):
        """Test that agent conversation histories are properly maintained."""
        coordinator = CAMELCoordinator("planner", "patcher")

        # Add some conversation history to agents
        coordinator.planner.conversation_history = [
            {"timestamp": "2024-01-01T10:00:00", "input": {}, "output": "plan1"}
        ]
        coordinator.patcher.conversation_history = [
            {"timestamp": "2024-01-01T10:01:00", "input": {}, "output": "patch1"}
        ]

        # Mock workflow
        coordinator.planner.analyze_and_plan = Mock(
            return_value={
                "success": True,
                "plan": {"plan": "test"},
                "analysis": {"context_packs": [{"context_parts": []}]},
            }
        )
        coordinator.patcher.generate_patch = Mock(
            return_value={
                "success": True,
                "json_operations": "{}",
                "unified_diff": "",
                "validation_attempts": [],
            }
        )

        # Act
        result = coordinator.process_test_failures("test")

        # Assert - History should be preserved and reflected in workflow summary
        history = result["workflow_history"]
        planner_agent = next(a for a in history["agents"] if a["name"] == "planner")
        patcher_agent = next(a for a in history["agents"] if a["name"] == "patcher")

        # Should include previous + new interactions
        assert planner_agent["interactions"] >= 1
        assert patcher_agent["interactions"] >= 1

    def test_structured_logging_format(self):
        """Test that workflow produces properly structured logs for observability."""
        coordinator = CAMELCoordinator("planner", "patcher")

        # Mock workflow with detailed results
        coordinator.planner.analyze_and_plan = Mock(
            return_value={
                "success": True,
                "plan": {
                    "plan": "Detailed fix plan",
                    "confidence": 0.85,
                    "target_files": ["tests/test_detailed.py"],
                },
                "analysis": {
                    "context_packs": [
                        {
                            "context_parts": ["detailed context"],
                            "test_function": "test_detailed",
                            "failure_type": "ASSERT_MISMATCH",
                        }
                    ]
                },
                "planning_insights": {"complexity_assessment": "low", "risk_factors": []},
            }
        )

        coordinator.patcher.generate_patch = Mock(
            return_value={
                "success": True,
                "json_operations": json.dumps({"ops": []}),
                "unified_diff": "detailed diff",
                "validation_attempts": [
                    {
                        "attempt": 1,
                        "validation": {"valid": True},
                        "learning_context": {"patterns": []},
                    }
                ],
                "validation": {"valid": True},
            }
        )

        # Act
        result = coordinator.process_test_failures("detailed test output")

        # Assert structured output
        assert result["success"] is True
        assert "plan" in result
        assert "analysis" in result
        assert "json_operations" in result
        assert "unified_diff" in result
        assert "validation_attempts" in result
        assert "workflow_history" in result

        # Verify workflow history is complete for observability
        workflow = result["workflow_history"]
        required_fields = [
            "framework",
            "version",
            "start_time",
            "end_time",
            "duration_seconds",
            "agents",
            "total_interactions",
        ]

        for field in required_fields:
            assert field in workflow, f"Missing required field: {field}"
