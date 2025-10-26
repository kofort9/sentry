"""
Example implementation using the reusable framework: DocSentry.

This demonstrates how to use the framework to build a documentation
updating workflow using the same patterns as TestSentry but for a different domain.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from sentries.framework import (
        AgentConfig,
        AgentRole,
        BaseTool,
        ErrorRecoverySystem,
        LLMAgent,
        MemoryObserver,
        MockLLMWrapper,
        ToolAgent,
        ToolCategory,
        ToolMetadata,
        ToolRegistry,
        WorkflowBuilder,
        WorkflowEngine,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback for standalone runs
    sys.path.insert(0, str(PROJECT_ROOT))
    from sentries.framework import (
        AgentConfig,
        AgentRole,
        BaseTool,
        ErrorRecoverySystem,
        LLMAgent,
        MemoryObserver,
        MockLLMWrapper,
        ToolAgent,
        ToolCategory,
        ToolMetadata,
        ToolRegistry,
        WorkflowBuilder,
        WorkflowEngine,
    )


# Domain-specific tools for documentation workflow
class DocumentAnalysisTool(BaseTool):
    """Tool for analyzing documentation files and extracting outdated sections."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="DocumentAnalysisTool",
            category=ToolCategory.ANALYSIS,
            description="Analyzes documentation files to find outdated or inconsistent content",
            required_params=["doc_path"],
            optional_params=["format_type"],
        )

    def execute(self, doc_path: str, format_type: str = "markdown") -> Dict[str, Any]:
        """Analyze a documentation file for issues."""
        self.validate_inputs(doc_path, format_type=format_type)

        # Mock analysis results
        return {
            "file_path": doc_path,
            "format": format_type,
            "issues_found": [
                {
                    "type": "outdated_version",
                    "section": "Installation",
                    "line_number": 15,
                    "description": "References version 1.2.0 but current is 1.5.0",
                },
                {
                    "type": "broken_link",
                    "section": "API Reference",
                    "line_number": 42,
                    "description": "Link to /api/v1/users returns 404",
                },
            ],
            "suggestions": [
                "Update version references throughout document",
                "Verify all external links are working",
            ],
        }


class DocumentGenerationTool(BaseTool):
    """Tool for generating updated documentation content."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="DocumentGenerationTool",
            category=ToolCategory.GENERATION,
            description="Generates updated documentation content based on plans",
            required_params=["plan", "current_content"],
            optional_params=["style_guide"],
        )

    def execute(
        self, plan: Dict[str, Any], current_content: str, style_guide: str = None
    ) -> Dict[str, Any]:
        """Generate updated documentation content."""
        self.validate_inputs(plan, current_content, style_guide=style_guide)

        # Mock content generation
        updated_content = current_content.replace("version 1.2.0", "version 1.5.0")

        return {
            "success": True,
            "updated_content": updated_content,
            "changes_made": [
                {
                    "type": "version_update",
                    "old_value": "version 1.2.0",
                    "new_value": "version 1.5.0",
                    "line_number": 15,
                }
            ],
            "diff": "- version 1.2.0\n+ version 1.5.0",
        }


class DocumentValidationTool(BaseTool):
    """Tool for validating updated documentation."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="DocumentValidationTool",
            category=ToolCategory.VALIDATION,
            description="Validates updated documentation for accuracy and consistency",
            required_params=["content"],
            optional_params=["validation_rules"],
        )

    def execute(self, content: str, validation_rules: List[str] = None) -> Dict[str, Any]:
        """Validate documentation content."""
        self.validate_inputs(content, validation_rules=validation_rules)

        # Mock validation
        return {
            "valid": True,
            "warnings": [],
            "errors": [],
            "score": 95,
            "checks_performed": [
                "spelling_and_grammar",
                "link_validation",
                "format_consistency",
                "content_accuracy",
            ],
        }


# Domain-specific agents for documentation workflow
class DocumentAnalyzerAgent(LLMAgent):
    """Agent that analyzes documentation and identifies issues."""

    def __init__(self, model_name: str, **kwargs):
        config = AgentConfig(
            name="DocumentAnalyzer",
            role=AgentRole.ANALYZER,
            model_name=model_name,
            system_message="""You are DocSentry's analyzer agent.
Your job is to analyze documentation files and identify areas that need updates.

SCOPE:
- Analyze documentation for outdated information
- Check for broken links and references
- Identify inconsistencies in formatting or content
- Suggest improvements for clarity and accuracy

OUTPUT FORMAT:
{
  "analysis": "Summary of issues found",
  "priority_issues": ["list of high priority issues"],
  "recommendations": ["list of recommended actions"],
  "confidence": 0.85
}""",
            tools=["DocumentAnalysisTool"],
        )
        super().__init__(config, **kwargs)

    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process documentation for analysis."""
        try:
            # Use analysis tool
            analysis_tool = self.get_tool("DocumentAnalysisTool")
            if analysis_tool:
                tool_result = analysis_tool.execute(doc_path=str(input_data))
            else:
                tool_result = {"issues_found": [], "suggestions": []}

            # Create analysis prompt
            messages = [
                {"role": "system", "content": self.config.system_message},
                {
                    "role": "user",
                    "content": (
                        "Analyze this documentation file: "
                        f"{input_data}\n\nTool analysis: {tool_result}"
                    ),
                },
            ]

            # Generate LLM response
            response = self._generate_response(messages)

            # Parse structured response
            try:
                structured_result = self._parse_json_response(response)
            except Exception:
                # Fallback if JSON parsing fails
                structured_result = {
                    "analysis": response,
                    "priority_issues": tool_result.get("issues_found", []),
                    "recommendations": tool_result.get("suggestions", []),
                    "confidence": 0.7,
                }

            return {
                "success": True,
                "analysis": structured_result,
                "tool_result": tool_result,
                "raw_response": response,
            }

        except Exception as e:
            return {"success": False, "error": str(e), "analysis": None}


class DocumentPlannerAgent(LLMAgent):
    """Agent that creates structured plans for documentation updates."""

    def __init__(self, model_name: str, **kwargs):
        config = AgentConfig(
            name="DocumentPlanner",
            role=AgentRole.PLANNER,
            model_name=model_name,
            system_message="""You are DocSentry's planner agent.
Your job is to create structured plans for updating documentation based on analysis.

SCOPE:
- Create actionable plans for documentation updates
- Prioritize changes by importance and impact
- Ensure updates maintain document consistency
- Consider user experience and accessibility

OUTPUT FORMAT:
{
  "plan": "Clear description of planned updates",
  "target_sections": ["list of sections to update"],
  "update_strategy": "approach for making updates",
  "estimated_effort": "low/medium/high"
}""",
            tools=[],
        )
        super().__init__(config, **kwargs)

    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a plan based on documentation analysis."""
        try:
            analysis_result = input_data

            messages = [
                {"role": "system", "content": self.config.system_message},
                {
                    "role": "user",
                    "content": f"Create an update plan based on this analysis: {analysis_result}",
                },
            ]

            response = self._generate_response(messages)

            try:
                plan = self._parse_json_response(response)
            except Exception:
                plan = {
                    "plan": response,
                    "target_sections": ["Installation", "API Reference"],
                    "update_strategy": "incremental_updates",
                    "estimated_effort": "medium",
                }

            return {"success": True, "plan": plan, "raw_response": response}

        except Exception as e:
            return {"success": False, "error": str(e), "plan": None}


class DocumentUpdaterAgent(ToolAgent):
    """Agent that executes documentation updates."""

    def __init__(self, **kwargs):
        config = AgentConfig(
            name="DocumentUpdater",
            role=AgentRole.EXECUTOR,
            model_name="",  # Tool-based agent doesn't need LLM
            system_message="Executes documentation updates based on plans",
            tools=["DocumentGenerationTool", "DocumentValidationTool"],
        )
        super().__init__(config, **kwargs)

    def process(self, input_data: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute documentation updates based on plan."""
        try:
            plan = input_data
            current_content = context.get(
                "current_content", "# Example Documentation\n\nThis is version 1.2.0"
            )

            # Generate updated content
            generation_tool = self.get_tool("DocumentGenerationTool")
            generation_result = generation_tool.execute(plan=plan, current_content=current_content)

            if not generation_result.get("success"):
                return {"success": False, "error": "Content generation failed"}

            # Validate updated content
            validation_tool = self.get_tool("DocumentValidationTool")
            validation_result = validation_tool.execute(
                content=generation_result["updated_content"]
            )

            return {
                "success": True,
                "updated_content": generation_result["updated_content"],
                "changes": generation_result["changes_made"],
                "diff": generation_result["diff"],
                "validation": validation_result,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


def create_docsentry_workflow() -> WorkflowEngine:
    """Create a complete DocSentry workflow using the framework."""

    # Create mock LLM for demonstration
    mock_llm = MockLLMWrapper(
        responses=[
            (
                '{"analysis": "Documentation contains outdated version references", '
                '"priority_issues": ["version_mismatch"], '
                '"recommendations": ["update_versions"], "confidence": 0.9}'
            ),
            (
                '{"plan": "Update version references and fix broken links", '
                '"target_sections": ["Installation"], '
                '"update_strategy": "systematic_update", "estimated_effort": "low"}'
            ),
        ]
    )

    # Create tool registry
    tools = ToolRegistry()
    tools.register_tool(DocumentAnalysisTool())
    tools.register_tool(DocumentGenerationTool())
    tools.register_tool(DocumentValidationTool())

    # Create observer for monitoring
    observer = MemoryObserver()

    # Create error recovery system
    error_recovery = ErrorRecoverySystem(max_retries=2)

    # Create agents
    analyzer = DocumentAnalyzerAgent(
        "mock-model", llm_wrapper=mock_llm, tool_registry=tools, observer=observer
    )
    planner = DocumentPlannerAgent(
        "mock-model", llm_wrapper=mock_llm, tool_registry=tools, observer=observer
    )
    updater = DocumentUpdaterAgent(tool_registry=tools, observer=observer)

    # Build workflow
    workflow = (
        WorkflowBuilder("DocSentry", "Automated documentation updating workflow")
        .add_agent("analyzer", analyzer)
        .add_agent("planner", planner)
        .add_agent("updater", updater)
        .set_observer(observer)
        .set_error_recovery(error_recovery)
        .add_sequential_step("analyze_and_plan", ["analyzer", "planner"])
        .add_sequential_step("update_docs", ["updater"])
        .build()
    )

    return workflow


def run_docsentry_example():
    """Run the DocSentry workflow example."""
    print("🔧 Creating DocSentry workflow using the reusable framework...")

    # Create workflow
    workflow = create_docsentry_workflow()

    # Validate workflow
    validation = workflow.validate_workflow()
    print(f"Workflow validation: {'✅ Valid' if validation['valid'] else '❌ Invalid'}")
    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"  - {issue}")

    print("\n📊 Workflow Information:")
    info = workflow.get_workflow_info()
    print(f"  - Agents: {len(info['agents'])}")
    print(f"  - Steps: {info['config']['steps']}")
    print(f"  - Tools: {info['tools']['total_tools']}")

    print("\n🚀 Executing DocSentry workflow...")

    # Execute workflow
    input_data = "/docs/api-guide.md"
    context = {
        "current_content": ("# API Guide\n\nThis guide covers version 1.2.0 of our API."),
        "project_version": "1.5.0",
    }

    result = workflow.execute_workflow(input_data, context)

    print("\n📋 Workflow Results:")
    print(f"  - Success: {not result.has_errors()}")
    print(f"  - Steps completed: {len(result.step_results)}")
    print(f"  - Execution time: {result.get_execution_summary()['duration_seconds']:.2f}s")

    # Display step results
    for step_name, step_data in result.step_results.items():
        print(f"\n  Step '{step_name}':")
        print(f"    - Success: {step_data['success']}")
        if step_data["success"]:
            print(f"    - Result: {str(step_data['result'])[:100]}...")

        # Display observability data
        if hasattr(workflow.observer, "get_llm_interactions"):
            interactions = workflow.observer.get_llm_interactions(count=5)
            print(f"\n💬 LLM Interactions: {len(interactions)}")
            for interaction in interactions[:2]:  # Show first 2
                print(
                    "  - "
                    f"{interaction['agent_name']} ({interaction['llm_role']}): "
                    f"{interaction['content'][:50]}..."
                )

    print("\n✨ DocSentry workflow completed!")

    return result


if __name__ == "__main__":
    # Run the example
    result = run_docsentry_example()

    print("\n" + "=" * 60)
    print("🎯 Framework Demonstration Complete!")
    print("=" * 60)
    print(
        """
This example shows how the reusable framework can be used to build
new agentic workflows for different domains:

✅ Defined domain-specific tools (DocumentAnalysis, DocumentGeneration, etc.)
✅ Created specialized agents (Analyzer, Planner, Updater)
✅ Built workflow with sequential steps and error recovery
✅ Integrated observability and monitoring
✅ Executed end-to-end documentation updating workflow

The same framework patterns used for TestSentry can now be applied
to any multi-agent workflow domain!
    """
    )
