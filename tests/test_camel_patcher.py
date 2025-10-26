#!/usr/bin/env python3
"""
Test suite for CAMEL PatcherAgent - Phase 2 iterative validation.

Tests the enhanced validation loops, learning context, and multi-attempt
validation functionality in the PatcherAgent.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from sentries.camel.patcher import PatcherAgent


class TestPatcherAgentValidation:
    """Test suite for PatcherAgent Phase 2 validation enhancements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.patcher = PatcherAgent("test-model")
        # Mock the LLM wrapper to avoid actual LLM calls
        self.patcher.llm = Mock()

    def test_single_attempt_validation_success(self):
        """Test successful validation on first attempt."""
        # Arrange
        plan = {"plan": "Fix assertion error"}
        context = "def test_example():\n    assert 1 == 2"
        
        # Mock successful validation
        valid_json = json.dumps({
            "ops": [{
                "file": "tests/test_example.py",
                "find": "assert 1 == 2", 
                "replace": "assert 1 == 1"
            }]
        })
        
        self.patcher.llm.generate.return_value = valid_json
        self.patcher.validation_tool.validate_operations = Mock(return_value={
            "valid": True,
            "issues": [],
            "suggestions": []
        })
        self.patcher.patch_tool.generate_patch = Mock(return_value={
            "success": True,
            "unified_diff": "--- a/tests/test_example.py\n+++ b/tests/test_example.py"
        })

        # Act
        result = self.patcher.generate_patch(plan, context)

        # Assert
        assert result["success"] is True
        assert len(result["validation_attempts"]) == 1
        assert result["validation_attempts"][0]["attempt"] == 1
        assert result["validation_attempts"][0]["validation"]["valid"] is True

    def test_multiple_validation_attempts_with_learning(self):
        """Test iterative validation with learning from failures."""
        # Arrange
        plan = {"plan": "Fix complex assertion"}
        context = "def test_complex():\n    assert complex_function() == expected_result"
        
        # Simulate 2 failed attempts then success
        invalid_json1 = json.dumps({"ops": [{"file": "invalid/path.py"}]})
        invalid_json2 = json.dumps({"ops": [{"missing": "required_keys"}]})  
        valid_json = json.dumps({
            "ops": [{
                "file": "tests/test_complex.py",
                "find": "assert complex_function() == expected_result",
                "replace": "assert complex_function() == actual_result"
            }]
        })
        
        # Mock LLM responses in sequence
        self.patcher.llm.generate.side_effect = [
            invalid_json1, invalid_json2, valid_json
        ]
        
        # Mock validation results
        def validation_side_effect(json_ops):
            if "invalid/path" in json_ops:
                return {"valid": False, "issues": ["Invalid file path"], "suggestions": []}
            elif "missing" in json_ops:
                return {"valid": False, "issues": ["Missing required keys"], "suggestions": []}
            else:
                return {"valid": True, "issues": [], "suggestions": []}
        
        self.patcher.validation_tool.validate_operations = Mock(side_effect=validation_side_effect)
        self.patcher.patch_tool.generate_patch = Mock(return_value={
            "success": True,
            "unified_diff": "--- a/tests/test_complex.py\n+++ b/tests/test_complex.py"
        })

        # Act
        result = self.patcher.generate_patch(plan, context)

        # Assert
        assert result["success"] is True
        assert len(result["validation_attempts"]) == 3
        
        # Verify attempt progression
        assert result["validation_attempts"][0]["validation"]["valid"] is False
        assert result["validation_attempts"][1]["validation"]["valid"] is False  
        assert result["validation_attempts"][2]["validation"]["valid"] is True
        
        # Verify learning context tracking
        assert "learning_context" in self.patcher.conversation_history[-1]
        learning_ctx = self.patcher.conversation_history[-1]["learning_context"]
        assert learning_ctx["total_attempts"] == 3
        assert learning_ctx["final_success"] is True
        assert len(learning_ctx["all_issues"]) > 0

    def test_max_attempts_reached_failure(self):
        """Test behavior when max validation attempts are reached."""
        # Arrange
        plan = {"plan": "Problematic fix"}
        context = "def test_fail():\n    assert True"
        
        # Always return invalid JSON
        invalid_json = json.dumps({"invalid": "structure"})
        self.patcher.llm.generate.return_value = invalid_json
        self.patcher.validation_tool.validate_operations = Mock(return_value={
            "valid": False,
            "issues": ["Structure is invalid"],
            "suggestions": ["Fix the structure"]
        })
        self.patcher.patch_tool.generate_patch = Mock()

        # Act
        result = self.patcher.generate_patch(plan, context)

        # Assert
        assert result["success"] is False
        assert len(result["validation_attempts"]) == 3  # Max attempts
        assert result["unified_diff"] == ""
        assert "skipping diff generation" in result["notification"]
        self.patcher.patch_tool.generate_patch.assert_not_called()
        
        # All attempts should have failed
        for attempt in result["validation_attempts"]:
            assert attempt["validation"]["valid"] is False
        
        # Conversation history should record the failed notification
        history_entry = self.patcher.conversation_history[-1]
        assert history_entry["notification"] == result["notification"]
        assert history_entry["patch_success"] is False

    def test_contextual_prompt_building(self):
        """Test that prompts improve with validation context."""
        patcher = PatcherAgent("test-model")
        
        # Test initial prompt (no previous attempts)
        prompt1 = patcher._build_contextual_prompt("Fix test", "context", [])
        assert "PREVIOUS VALIDATION FEEDBACK" not in prompt1
        
        # Test prompt with previous attempts
        previous_attempts = [
            {
                "attempt": 1,
                "validation": {
                    "valid": False,
                    "issues": ["Invalid file path"],
                    "suggestions": ["Use tests/ prefix"]
                }
            }
        ]
        
        prompt2 = patcher._build_contextual_prompt("Fix test", "context", previous_attempts)
        assert "PREVIOUS VALIDATION FEEDBACK" in prompt2
        assert "Invalid file path" in prompt2
        assert "Use tests/ prefix" in prompt2

    def test_learning_context_extraction(self):
        """Test extraction of learning patterns from validation attempts."""
        patcher = PatcherAgent("test-model")
        
        # Create validation attempts with various outcomes
        validation_attempts = [
            {
                "validation": {"valid": False, "issues": ["File path error", "Missing key error"]},
                "attempt": 1
            },
            {
                "validation": {"valid": False, "issues": ["File path error"]},
                "attempt": 2
            },
            {
                "validation": {"valid": True, "issues": []},
                "attempt": 3
            }
        ]
        
        # Test learning context extraction
        learning_ctx = patcher._extract_learning_context(validation_attempts)
        
        assert learning_ctx["total_attempts"] == 3
        assert learning_ctx["final_success"] is True
        assert "File path error" in learning_ctx["all_issues"]
        assert learning_ctx["common_issue_patterns"]["File path error"] == 2
        assert learning_ctx["improvement_trajectory"] == [False, False, True]

    @patch('sentries.camel.patcher.datetime')
    def test_conversation_history_tracking(self, mock_datetime):
        """Test that conversation history properly tracks validation sessions."""
        # Arrange
        mock_datetime.datetime.now.return_value.isoformat.return_value = "2024-01-15T10:30:00"
        
        plan = {"plan": "Track history"}
        context = "test context"
        
        # Mock successful validation
        self.patcher.llm.generate.return_value = json.dumps({
            "ops": [{"file": "tests/test.py", "find": "old", "replace": "new"}]
        })
        self.patcher.validation_tool.validate_operations = Mock(return_value={"valid": True})
        self.patcher.patch_tool.generate_patch = Mock(return_value={"success": True})

        # Act
        result = self.patcher.generate_patch(plan, context)

        # Assert
        assert len(self.patcher.conversation_history) == 1
        interaction = self.patcher.conversation_history[0]
        
        assert interaction["timestamp"] == "2024-01-15T10:30:00"
        assert interaction["input"]["plan"] == "Track history"
        assert interaction["input"]["validation_attempts_count"] == 1
        assert "learning_context" in interaction
        assert interaction["patch_success"] is True

    def test_json_extraction_from_various_formats(self):
        """Test JSON extraction from different LLM response formats."""
        patcher = PatcherAgent("test-model")
        
        # Test 1: Pure JSON
        pure_json = '{"ops": [{"file": "test.py", "find": "a", "replace": "b"}]}'
        extracted = patcher._extract_json_from_response(pure_json)
        assert json.loads(extracted)  # Should be valid JSON
        
        # Test 2: JSON in markdown code block
        markdown_json = '```json\n{"ops": [{"file": "test.py", "find": "a", "replace": "b"}]}\n```'
        extracted = patcher._extract_json_from_response(markdown_json)
        parsed = json.loads(extracted)
        assert parsed["ops"][0]["file"] == "test.py"
        
        # Test 3: Simulation fallback for specific patterns
        simulation_response = "I need to fix assert 1 == 2 in the test"
        extracted = patcher._extract_json_from_response(simulation_response)
        parsed = json.loads(extracted)
        assert "test_camel_demo.py" in parsed["ops"][0]["file"]

    def test_validation_error_recovery(self):
        """Test error recovery in validation process."""
        plan = {"plan": "Test error recovery"}
        context = "test context"
        
        # Mock LLM to return valid JSON first
        self.patcher.llm.generate.return_value = json.dumps({
            "ops": [{"file": "tests/test.py", "find": "old", "replace": "new"}]
        })
        
        # Mock validation tool to raise exception
        self.patcher.validation_tool.validate_operations = Mock(
            side_effect=Exception("Validation tool error")
        )
        
        # Act
        result = self.patcher.generate_patch(plan, context)
        
        # Assert - Should handle exception gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Validation tool error" in result["error"]


class TestPatcherAgentIntegration:
    """Integration tests for PatcherAgent validation workflow."""

    def test_realistic_validation_scenario(self):
        """Test realistic scenario with actual validation patterns."""
        patcher = PatcherAgent("test-model")
        
        # Mock the LLM wrapper properly
        patcher.llm = Mock()
        
        # Mock realistic validation progression
        plan = {"plan": "Fix failing assertion in test_calculation"}
        context = """
def test_calculation():
    result = calculate_sum(2, 3)
    assert result == 6  # This is wrong, should be 5
"""
        
        # Simulate realistic validation failures then success
        responses = [
            # Attempt 1: Wrong file path
            json.dumps({
                "ops": [{"file": "src/test_calc.py", "find": "assert result == 6", "replace": "assert result == 5"}]
            }),
            # Attempt 2: Missing required fields
            json.dumps({
                "ops": [{"file": "tests/test_calc.py", "find": "assert result == 6"}]  # Missing replace
            }),
            # Attempt 3: Success
            json.dumps({
                "ops": [{
                    "file": "tests/test_calc.py",
                    "find": "assert result == 6",
                    "replace": "assert result == 5"
                }]
            })
        ]
        
        def validation_logic(json_ops):
            ops = json.loads(json_ops)
            if not ops.get("ops"):
                return {"valid": False, "issues": ["Missing ops key"]}
            
            op = ops["ops"][0]
            if not op.get("file", "").startswith("tests/"):
                return {"valid": False, "issues": ["Invalid file path"]}
            if "replace" not in op:
                return {"valid": False, "issues": ["Missing replace key"]}
            
            return {"valid": True, "issues": []}
        
        # Set up mocks properly
        patcher.llm.generate.side_effect = responses
        patcher.validation_tool = Mock()
        patcher.validation_tool.validate_operations.side_effect = validation_logic
        patcher.patch_tool = Mock()
        patcher.patch_tool.generate_patch.return_value = {
            "success": True,
            "unified_diff": "--- a/tests/test_calc.py\n+++ b/tests/test_calc.py\n@@ -2,1 +2,1 @@\n-    assert result == 6\n+    assert result == 5"
        }
        
        # Execute
        result = patcher.generate_patch(plan, context)
        
        # Verify
        assert result["success"] is True
        assert len(result["validation_attempts"]) == 3
        
        # Check learning progression
        attempts = result["validation_attempts"]
        assert "Invalid file path" in attempts[0]["validation"]["issues"]
        assert "Missing replace key" in attempts[1]["validation"]["issues"]  
        assert attempts[2]["validation"]["valid"] is True
        
        # Verify learning context
        learning = patcher.conversation_history[-1]["learning_context"]
        assert learning["total_attempts"] == 3
        assert learning["final_success"] is True
        assert "Invalid file path" in learning["all_issues"]
