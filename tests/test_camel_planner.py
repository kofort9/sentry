#!/usr/bin/env python3
"""
Test suite for CAMEL PlannerAgent - Phase 2 historical learning.

Tests the enhanced planning features including confidence scoring,
risk assessment, and historical context integration.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from sentries.camel.planner import PlannerAgent


class TestPlannerAgentLearning:
    """Test suite for PlannerAgent Phase 2 learning enhancements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.planner = PlannerAgent("test-model")
        # Mock the LLM wrapper and analysis tool
        self.planner.llm = Mock()
        self.planner.analysis_tool = Mock()

    def test_basic_planning_without_history(self):
        """Test basic planning functionality without historical context."""
        # Arrange
        test_output = "FAILED tests/test_example.py::test_function - AssertionError: assert 1 == 2"
        
        # Mock analysis tool response
        self.planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [{
                "test_function": "test_function",
                "test_file": "tests/test_example.py", 
                "failure_type": "ASSERT_MISMATCH",
                "error_message": "AssertionError: assert 1 == 2",
                "context_parts": ["def test_function():", "    assert 1 == 2"]
            }]
        }
        
        # Mock LLM response
        plan_json = json.dumps({
            "plan": "Fix assertion by changing 1 == 2 to 1 == 1",
            "target_files": ["tests/test_example.py"],
            "fix_strategy": "assertion_correction",
            "reasoning": "Simple assertion mismatch fix"
        })
        self.planner.llm.generate.return_value = plan_json

        # Act
        result = self.planner.analyze_and_plan(test_output)

        # Assert
        assert result["success"] is True
        assert result["plan"]["plan"] == "Fix assertion by changing 1 == 2 to 1 == 1"
        assert "planning_insights" in result
        insights = result["planning_insights"]
        assert insights["failure_type"] == "ASSERT_MISMATCH"
        assert insights["complexity_assessment"] == "low"  # Should be low for assertions

    def test_confidence_scoring_with_history(self):
        """Test confidence scoring based on historical success."""
        # Arrange - Add historical successful interactions
        self.planner.conversation_history = [
            {
                "input": {"failure_type": "ASSERT_MISMATCH"},
                "learning_context": {"plan_success": True}
            },
            {
                "input": {"failure_type": "ASSERT_MISMATCH"}, 
                "learning_context": {"plan_success": True}
            },
            {
                "input": {"failure_type": "IMPORT_ERROR"},
                "learning_context": {"plan_success": False}
            }
        ]

        failure = {"failure_type": "ASSERT_MISMATCH", "error_message": "assert 1 == 2"}
        
        # Act
        confidence = self.planner._calculate_historical_success_rate(failure)
        
        # Assert - Should have high confidence (2/2 successful for ASSERT_MISMATCH)
        assert confidence == 0.9  # Should be clamped to max 0.9

    def test_confidence_scoring_without_history(self):
        """Test default confidence when no history exists."""
        failure = {"failure_type": "NEW_ERROR", "error_message": "Unknown error"}
        
        # Act
        confidence = self.planner._calculate_historical_success_rate(failure)
        
        # Assert - Should return default confidence
        assert confidence == 0.5

    def test_historical_context_integration(self):
        """Test integration of historical context into planning prompts."""
        # Arrange - Add relevant history
        self.planner.conversation_history = [
            {
                "input": {
                    "failure_type": "ASSERT_MISMATCH",
                    "test_file": "tests/test_math.py"
                },
                "learning_context": {
                    "successful_strategies": ["assertion_correction", "value_adjustment"]
                }
            }
        ]
        
        failure = {
            "failure_type": "ASSERT_MISMATCH",
            "test_file": "tests/test_math.py",
            "test_function": "test_addition",
            "error_message": "assert 2+2 == 5",
            "context_parts": ["def test_addition():", "    assert 2+2 == 5"]
        }
        
        # Act
        historical_context = self.planner._get_relevant_historical_context(failure)
        
        # Assert
        assert "assertion_correction" in historical_context
        assert "value_adjustment" in historical_context
        assert "Similar failures were successfully handled using" in historical_context

    def test_enhanced_planning_with_historical_insights(self):
        """Test full planning process with historical insights integration."""
        # Arrange
        test_output = "FAILED tests/test_calc.py::test_multiply - AssertionError: assert 4*5 == 21"
        
        # Add historical context
        self.planner.conversation_history = [
            {
                "input": {"failure_type": "ASSERT_MISMATCH"},
                "learning_context": {"plan_success": True, "successful_strategies": ["assertion_fix"]}
            }
        ]
        
        # Mock analysis
        self.planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [{
                "test_function": "test_multiply",
                "test_file": "tests/test_calc.py",
                "failure_type": "ASSERT_MISMATCH", 
                "error_message": "AssertionError: assert 4*5 == 21",
                "context_parts": ["def test_multiply():", "    assert 4*5 == 21"]
            }]
        }
        
        # Mock enhanced plan with confidence
        enhanced_plan = {
            "plan": "Fix multiplication assertion from 21 to 20",
            "target_files": ["tests/test_calc.py"],
            "fix_strategy": "assertion_correction",
            "reasoning": "Mathematical error in expected value"
        }
        self.planner.llm.generate.return_value = json.dumps(enhanced_plan)

        # Act  
        result = self.planner.analyze_and_plan(test_output)

        # Assert
        assert result["success"] is True
        
        # Check enhanced plan has confidence scoring
        plan = result["plan"]
        assert "confidence" in plan
        assert plan["confidence"] > 0.5  # Should have some confidence based on history
        
        # Check planning insights
        insights = result["planning_insights"]
        assert insights["failure_type"] == "ASSERT_MISMATCH"
        assert insights["recommended_approach"] == "assertion_correction"

    def test_complexity_assessment(self):
        """Test failure complexity assessment logic."""
        planner = PlannerAgent("test-model")
        
        # Test cases for different complexity levels
        test_cases = [
            {"error_message": "AssertionError: assert 1 == 2", "expected": "low"},
            {"error_message": "ImportError: No module named 'missing'", "expected": "medium"}, 
            {"error_message": "SyntaxError: invalid syntax", "expected": "medium"},
            {"error_message": "ComplexBusinessLogicError: workflow failed", "expected": "high"}
        ]
        
        for case in test_cases:
            failure = {"error_message": case["error_message"]}
            complexity = planner._assess_failure_complexity(failure)
            assert complexity == case["expected"], f"Failed for {case['error_message']}"

    def test_risk_assessment(self):
        """Test automatic risk factor identification."""
        planner = PlannerAgent("test-model")
        
        # Test cases for different risk levels
        test_cases = [
            {
                "error_message": "Database connection failed in production",
                "expected_risks": ["may_affect_production", "database_related"]
            },
            {
                "error_message": "Network timeout in API call",
                "expected_risks": ["external_dependency"]
            },
            {
                "error_message": "Simple assertion failed",
                "expected_risks": []
            }
        ]
        
        for case in test_cases:
            failure = {"error_message": case["error_message"]}
            risks = planner._identify_risk_factors(failure)
            for expected_risk in case["expected_risks"]:
                assert expected_risk in risks

    def test_learning_pattern_extraction(self):
        """Test extraction of learning patterns from conversation history."""
        planner = PlannerAgent("test-model")
        
        # Add varied conversation history
        planner.conversation_history = [
            {
                "input": {"failure_type": "ASSERT_MISMATCH"},
                "learning_context": {"plan_success": True}
            },
            {
                "input": {"failure_type": "IMPORT_ERROR"},
                "learning_context": {"plan_success": False}
            },
            {
                "input": {"failure_type": "ASSERT_MISMATCH"},
                "learning_context": {"plan_success": True}
            }
        ]
        
        # Act
        patterns = planner._extract_planning_patterns()
        
        # Assert
        assert patterns["total_planning_sessions"] == 3
        assert "ASSERT_MISMATCH" in patterns["common_failure_types"]
        assert "IMPORT_ERROR" in patterns["common_failure_types"]
        assert len(patterns["successful_strategies"]) == 2  # 2 successful plans

    @patch('sentries.camel.planner.datetime')
    def test_conversation_history_enhancement(self, mock_datetime):
        """Test enhanced conversation history with learning context."""
        # Arrange
        mock_datetime.datetime.now.return_value.isoformat.return_value = "2024-01-15T15:30:00"
        
        test_output = "FAILED tests/test_example.py::test_func"
        
        # Mock analysis and LLM
        self.planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [{
                "test_function": "test_func",
                "test_file": "tests/test_example.py",
                "failure_type": "SYNTAX_ERROR",
                "error_message": "SyntaxError: invalid syntax",
                "context_parts": ["invalid code"]
            }]
        }
        
        self.planner.llm.generate.return_value = json.dumps({
            "plan": "Fix syntax error",
            "target_files": ["tests/test_example.py"]
        })

        # Act
        result = self.planner.analyze_and_plan(test_output)

        # Assert
        assert len(self.planner.conversation_history) == 1
        interaction = self.planner.conversation_history[0]
        
        # Check enhanced interaction structure
        assert interaction["timestamp"] == "2024-01-15T15:30:00"
        assert interaction["input"]["failure_type"] == "SYNTAX_ERROR"
        assert interaction["input"]["test_file"] == "tests/test_example.py"
        assert interaction["input"]["test_function"] == "test_func"
        assert "learning_context" in interaction

    def test_plan_enhancement_with_insights(self):
        """Test plan enhancement with historical insights."""
        planner = PlannerAgent("test-model")
        
        # Add successful history for confidence
        planner.conversation_history = [
            {"input": {"failure_type": "ASSERT_MISMATCH"}, "learning_context": {"plan_success": True}}
        ]
        
        original_plan = {
            "plan": "Fix assertion",
            "target_files": ["tests/test.py"]
        }
        
        failure = {
            "failure_type": "ASSERT_MISMATCH",
            "error_message": "assert 1 == 2"
        }
        
        # Act
        enhanced_plan = planner._enhance_plan_with_insights(original_plan, failure)
        
        # Assert
        assert "confidence" in enhanced_plan
        assert enhanced_plan["confidence"] > 0.5  # Should have confidence from history
        assert "historical_context" in enhanced_plan
        assert enhanced_plan["plan"] == "Fix assertion"  # Original plan preserved
        assert enhanced_plan["target_files"] == ["tests/test.py"]  # Original data preserved

    def test_recommended_approach_mapping(self):
        """Test mapping of failure types to recommended approaches."""
        planner = PlannerAgent("test-model")
        
        # Test approach mapping for different failure types
        test_cases = [
            {"failure_type": "ASSERT_MISMATCH", "expected": "assertion_correction"},
            {"failure_type": "IMPORT_ERROR", "expected": "import_fix"},
            {"failure_type": "SYNTAX_ERROR", "expected": "syntax_correction"},
            {"failure_type": "ATTRIBUTE_ERROR", "expected": "attribute_fix"},
            {"failure_type": "UNKNOWN_ERROR", "expected": "general_debugging"}
        ]
        
        for case in test_cases:
            failure = {"failure_type": case["failure_type"]}
            approach = planner._get_recommended_approach(failure)
            assert approach == case["expected"]


class TestPlannerAgentIntegration:
    """Integration tests for PlannerAgent learning workflow."""

    def test_learning_across_multiple_sessions(self):
        """Test learning accumulation across multiple planning sessions."""
        planner = PlannerAgent("test-model")
        planner.llm = Mock()
        planner.analysis_tool = Mock()

        # Simulate multiple planning sessions
        sessions = [
            {
                "failure_type": "ASSERT_MISMATCH",
                "success": True,
                "test_file": "tests/test_math.py"
            },
            {
                "failure_type": "ASSERT_MISMATCH", 
                "success": True,
                "test_file": "tests/test_calc.py"
            },
            {
                "failure_type": "IMPORT_ERROR",
                "success": False,
                "test_file": "tests/test_imports.py"
            }
        ]
        
        for i, session in enumerate(sessions):
            # Manually add successful history for previous sessions to test confidence building
            if i > 0:
                # Add explicit success record for previous sessions
                for j in range(i):
                    prev_session = sessions[j]
                    planner.conversation_history.append({
                        "input": {
                            "failure_type": prev_session["failure_type"],
                            "test_file": prev_session["test_file"]
                        },
                        "learning_context": {
                            "plan_success": prev_session["success"],
                            "successful_strategies": ["successful_plan"] if prev_session["success"] else []
                        }
                    })
            
            # Mock analysis for this session
            planner.analysis_tool.analyze_failures.return_value = {
                "success": True,
                "context_packs": [{
                    "test_function": f"test_func_{i}",
                    "test_file": session["test_file"],
                    "failure_type": session["failure_type"],
                    "error_message": f"Error {i}",
                    "context_parts": [f"context {i}"]
                }]
            }
            
            # Mock LLM response
            planner.llm.generate.return_value = json.dumps({
                "plan": f"Fix session {i}",
                "target_files": [session["test_file"]]
            })
            
            # Execute planning
            result = planner.analyze_and_plan(f"test output {i}")
            
            # Verify each session builds on previous learning
            if i > 0:
                # For ASSERT_MISMATCH with previous success, should have high confidence
                if session["failure_type"] == "ASSERT_MISMATCH" and i > 0:
                    confidence = result["plan"]["confidence"]
                    assert confidence > 0.7  # Should be confident based on previous success

        # Final verification - learning patterns should be comprehensive
        final_patterns = planner._extract_planning_patterns()
        # Total sessions will include all the manually added history + the actual analyze_and_plan calls
        assert final_patterns["total_planning_sessions"] >= 3  # At least 3 sessions
        assert "ASSERT_MISMATCH" in final_patterns["common_failure_types"]
        assert "IMPORT_ERROR" in final_patterns["common_failure_types"]

    def test_realistic_planning_scenario_with_learning(self):
        """Test realistic planning scenario with full learning integration."""
        planner = PlannerAgent("test-model")
        planner.llm = Mock()
        planner.analysis_tool = Mock()
        
        # Set up realistic historical context
        planner.conversation_history = [
            {
                "input": {
                    "failure_type": "ASSERT_MISMATCH",
                    "test_file": "tests/test_calculations.py"
                },
                "learning_context": {
                    "plan_success": True,
                    "successful_strategies": ["assertion_correction"]
                }
            }
        ]
        
        # Current failure scenario
        test_output = """
FAILED tests/test_calculations.py::test_division - AssertionError: assert divide(10, 2) == 4
>       assert divide(10, 2) == 4
E       AssertionError: assert 5 == 4
"""
        
        # Mock analysis
        planner.analysis_tool.analyze_failures.return_value = {
            "success": True,
            "context_packs": [{
                "test_function": "test_division",
                "test_file": "tests/test_calculations.py",
                "failure_type": "ASSERT_MISMATCH",
                "error_message": "AssertionError: assert 5 == 4",
                "context_parts": [
                    "def test_division():",
                    "    result = divide(10, 2)", 
                    "    assert result == 4  # Should be 5"
                ]
            }]
        }
        
        # Mock enhanced plan response
        plan_response = {
            "plan": "Fix division test assertion from == 4 to == 5",
            "target_files": ["tests/test_calculations.py"],
            "fix_strategy": "assertion_correction",
            "reasoning": "Mathematical error in expected result"
        }
        planner.llm.generate.return_value = json.dumps(plan_response)
        
        # Execute
        result = planner.analyze_and_plan(test_output)
        
        # Verify comprehensive result
        assert result["success"] is True
        
        # Check plan enhancement with confidence
        plan = result["plan"]
        assert plan["confidence"] > 0.8  # High confidence due to similar past success
        assert "historical_context" in plan
        
        # Check insights
        insights = result["planning_insights"]
        assert insights["complexity_assessment"] == "low"
        assert insights["recommended_approach"] == "assertion_correction"
        assert len(insights["risk_factors"]) == 0  # No risks for simple assertion fix
        
        # Verify conversation history enhancement
        latest_interaction = planner.conversation_history[-1]
        assert latest_interaction["input"]["failure_type"] == "ASSERT_MISMATCH"
        # The learning_context counts the history at the time it was created, which includes the initial history + the new session
        assert latest_interaction["learning_context"]["total_planning_sessions"] >= 1
