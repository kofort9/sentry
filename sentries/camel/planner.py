"""Planner agent for CAMEL workflow."""

import datetime
import json
from typing import Any, Dict

from .llm import SentryLLMWrapper
from .tools import TestAnalysisTool
from ..runner_common import get_logger

logger = get_logger(__name__)


class PlannerAgent:
    """
    CAMEL agent responsible for analyzing test failures and creating plans.

    Uses intelligent analysis tools to understand failures and generates
    structured plans for fixing them.
    """

    def __init__(self, model_name: str, llm_logger=None):
        self.model_name = model_name
        self.llm = SentryLLMWrapper(model_name, "planner")
        self.analysis_tool = TestAnalysisTool()
        self.llm_logger = llm_logger

        self.conversation_history = []
        self.system_message = """You are TestSentry's planner agent.
Your job is to analyze test failures and create structured plans for fixing them.

SCOPE (hard rule):
- You may ONLY suggest modifications to files under tests/** (and equivalent test paths).
- If a correct fix requires changing any non-test code or configuration, you MUST abort.

OUTPUT FORMAT:
When creating plans, use this JSON structure:
{
  "plan": "1–3 sentence summary of the intended test-side fix",
  "target_files": ["relative test paths ONLY"],
  "fix_strategy": "minimal approach (assertions, fixtures, mocks, imports)",
  "reasoning": "brief explanation of the approach"
}

If you cannot proceed within scope, output:
{"abort": "out_of_scope"} or {"abort": "cannot_comply"}

DECISION RULES:
1. Focus on ONE failing test at a time (the smallest first)
2. Prefer minimal edits: assertions → fixtures → mocks → imports
3. Never suggest edits to non-test paths
4. Use the analysis results to understand failure context
"""

        logger.info(f"✅ Created PlannerAgent with model: {model_name}")

    def analyze_and_plan(self, test_output: str) -> Dict[str, Any]:
        """
        Analyze test failures and create a plan for fixing them with Phase 2 enhancements.

        Args:
            test_output: Raw pytest output with failures

        Returns:
            Planning results with enhanced memory and learning context
        """
        try:
            # Phase 2: Enhanced analysis with historical context
            analysis_result = self.analysis_tool.analyze_failures(test_output)

            if not analysis_result.get("success"):
                return {
                    "success": False,
                    "error": analysis_result.get("error", "Analysis failed"),
                    "plan": None,
                }

            context_packs = analysis_result.get("context_packs", [])
            if not context_packs:
                return {
                    "success": False,
                    "error": "No context packs generated from test failures",
                    "plan": None,
                }

            first_failure = context_packs[0]
            
            # Phase 2: Build context-aware prompt with learning from history
            planning_prompt = self._build_enhanced_planning_prompt(
                first_failure, test_output
            )

            messages = [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": planning_prompt},
            ]

            # Log LLM interaction if logger is available
            if self.llm_logger:
                self.llm_logger("planner", "system", self.system_message, self.model_name, 
                               {"context": "planning_prompt"})
                self.llm_logger("planner", "user", planning_prompt, self.model_name,
                               {"failure_type": first_failure['failure_type'], 
                                "test_file": first_failure['test_file']})

            response = self.llm.generate(messages)

            # Log LLM response
            if self.llm_logger:
                self.llm_logger("planner", "assistant", response, self.model_name,
                               {"planning_phase": "analyze_and_plan"})

            # Phase 2: Enhanced conversation memory with learning context
            interaction = {
                "timestamp": datetime.datetime.now().isoformat(),
                "input": {
                    "test_output_summary": test_output[:200] + "...",
                    "failure_type": first_failure['failure_type'],
                    "test_file": first_failure['test_file'],
                    "test_function": first_failure['test_function'],
                },
                "output": response,
                "analysis": analysis_result,
                "learning_context": self._extract_planning_patterns(),
            }
            self.conversation_history.append(interaction)

            try:
                plan = json.loads(response)
                
                # Validate and enhance plan with historical insights
                enhanced_plan = self._enhance_plan_with_insights(plan, first_failure)
                
                return {
                    "success": True,
                    "plan": enhanced_plan,
                    "analysis": analysis_result,
                    "raw_response": response,
                    "planning_insights": self._get_planning_insights(first_failure),
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "plan": {"raw": response},
                    "analysis": analysis_result,
                    "raw_response": response,
                }

        except Exception as exc:
            logger.error(f"Error in planner agent: {exc}")
            return {"success": False, "error": str(exc), "plan": None}

    def _build_enhanced_planning_prompt(
        self, first_failure: Dict[str, Any], test_output: str
    ) -> str:
        """
        Phase 2: Build planning prompt with historical learning context.
        
        Args:
            first_failure: Primary failure to analyze
            test_output: Full test output
            
        Returns:
            Enhanced planning prompt with historical context
        """
        base_prompt = f"""
Analyze this test failure and create a plan:

Test Function: {first_failure['test_function']}
Test File: {first_failure['test_file']}
Failure Type: {first_failure['failure_type']}
Error: {first_failure['error_message']}

Context:
{chr(10).join(first_failure['context_parts'])}

Create a JSON plan for fixing this test failure.
Remember: ONLY modify files under tests/**.
"""

        # Add historical insights if available
        historical_context = self._get_relevant_historical_context(first_failure)
        if historical_context:
            base_prompt += f"""

HISTORICAL INSIGHTS:
{historical_context}

Consider these patterns when creating your plan."""

        return base_prompt

    def _get_relevant_historical_context(self, failure: Dict[str, Any]) -> str:
        """
        Extract relevant historical context for similar failures.
        
        Args:
            failure: Current failure information
            
        Returns:
            Relevant historical context string
        """
        if not self.conversation_history:
            return ""

        failure_type = failure.get('failure_type', '')
        test_file = failure.get('test_file', '')
        
        relevant_patterns = []
        
        # Look for similar failure types or files in history
        for interaction in self.conversation_history[-5:]:  # Last 5 interactions
            input_data = interaction.get('input', {})
            if (input_data.get('failure_type') == failure_type or 
                input_data.get('test_file') == test_file):
                
                learning = interaction.get('learning_context', {})
                if learning.get('successful_strategies'):
                    relevant_patterns.extend(learning['successful_strategies'])

        if relevant_patterns:
            return f"Similar failures were successfully handled using: {'; '.join(relevant_patterns[:3])}"
        
        return ""

    def _enhance_plan_with_insights(
        self, plan: Dict[str, Any], failure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance the generated plan with historical insights and validation.
        
        Args:
            plan: Generated plan
            failure: Failure context
            
        Returns:
            Enhanced plan with insights
        """
        # Add confidence scoring based on historical success
        historical_success = self._calculate_historical_success_rate(failure)
        
        enhanced_plan = plan.copy()
        enhanced_plan['confidence'] = historical_success
        enhanced_plan['historical_context'] = self._get_planning_insights(failure)
        
        return enhanced_plan

    def _calculate_historical_success_rate(self, failure: Dict[str, Any]) -> float:
        """
        Calculate confidence based on historical success with similar failures.
        
        Args:
            failure: Current failure context
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not self.conversation_history:
            return 0.5  # Default confidence

        failure_type = failure.get('failure_type', '')
        similar_cases = []
        
        for interaction in self.conversation_history:
            input_data = interaction.get('input', {})
            if input_data.get('failure_type') == failure_type:
                # Check for explicit plan_success field or infer from successful_strategies
                learning = interaction.get('learning_context', {})
                if 'plan_success' in learning:
                    similar_cases.append(learning['plan_success'])
                elif 'successful_strategies' in learning:
                    # If there are successful strategies, assume success
                    has_success = len(learning['successful_strategies']) > 0
                    similar_cases.append(has_success)
                else:
                    # Assume neutral/partial success for recorded interactions
                    similar_cases.append(True)
        
        if similar_cases:
            success_rate = sum(similar_cases) / len(similar_cases)
            return max(0.3, min(0.9, success_rate))  # Clamp between 0.3 and 0.9
        
        return 0.5

    def _get_planning_insights(self, failure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate insights for the current planning session.
        
        Args:
            failure: Current failure context
            
        Returns:
            Planning insights dictionary
        """
        return {
            "failure_type": failure.get('failure_type'),
            "complexity_assessment": self._assess_failure_complexity(failure),
            "recommended_approach": self._get_recommended_approach(failure),
            "risk_factors": self._identify_risk_factors(failure),
        }

    def _extract_planning_patterns(self) -> Dict[str, Any]:
        """
        Extract learning patterns from conversation history.
        
        Returns:
            Learning patterns dictionary
        """
        if not self.conversation_history:
            return {}

        failure_types = []
        successful_strategies = []
        
        for interaction in self.conversation_history:
            input_data = interaction.get('input', {})
            if input_data.get('failure_type'):
                failure_types.append(input_data['failure_type'])
            
            learning = interaction.get('learning_context', {})
            if learning.get('plan_success'):
                successful_strategies.append("successful_plan")

        return {
            "common_failure_types": list(set(failure_types)),
            "successful_strategies": successful_strategies,
            "total_planning_sessions": len(self.conversation_history),
        }

    def _assess_failure_complexity(self, failure: Dict[str, Any]) -> str:
        """Assess the complexity of the current failure."""
        error_msg = failure.get('error_message', '')
        
        if 'assert' in error_msg.lower():
            return "low"  # Simple assertion fixes
        elif 'import' in error_msg.lower():
            return "medium"  # Import-related issues
        elif any(word in error_msg.lower() for word in ['syntax', 'indentation', 'parse']):
            return "medium"  # Syntax issues
        else:
            return "high"  # Complex logic or unknown issues

    def _get_recommended_approach(self, failure: Dict[str, Any]) -> str:
        """Get recommended approach based on failure type."""
        failure_type = failure.get('failure_type', '')
        
        approach_map = {
            'ASSERT_MISMATCH': 'assertion_correction',
            'IMPORT_ERROR': 'import_fix',
            'SYNTAX_ERROR': 'syntax_correction',
            'ATTRIBUTE_ERROR': 'attribute_fix',
        }
        
        return approach_map.get(failure_type, 'general_debugging')

    def _identify_risk_factors(self, failure: Dict[str, Any]) -> list:
        """Identify potential risk factors for the fix."""
        risks = []
        
        error_msg = failure.get('error_message', '').lower()
        
        if 'production' in error_msg or 'config' in error_msg:
            risks.append("may_affect_production")
        if 'database' in error_msg or 'db' in error_msg:
            risks.append("database_related")
        if 'network' in error_msg or 'api' in error_msg:
            risks.append("external_dependency")
            
        return risks
