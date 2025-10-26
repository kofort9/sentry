"""
Workflow engine and builder for the reusable framework.
"""

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import yaml

from .agents import BaseAgent
from .coordinators import BaseCoordinator, StepType, WorkflowConfig, WorkflowContext, WorkflowStep
from .error_recovery import ErrorRecoverySystem
from .llm import BaseLLMWrapper
from .observability import ConsoleObserver, WorkflowObserver
from .tools import BaseTool, ToolRegistry


class WorkflowBuilder:
    """
    Builder for creating workflows programmatically.

    Provides a fluent API for defining multi-agent workflows.
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.agents: Dict[str, BaseAgent] = {}
        self.tools: ToolRegistry = ToolRegistry()
        self.llm_wrappers: Dict[str, BaseLLMWrapper] = {}
        self.observer: Optional[WorkflowObserver] = None
        self.error_recovery: Optional[ErrorRecoverySystem] = None

    def add_agent(self, name: str, agent: BaseAgent) -> "WorkflowBuilder":
        """Add an agent to the workflow."""
        self.agents[name] = agent
        return self

    def add_tool(self, tool: BaseTool, name: str = None) -> "WorkflowBuilder":
        """Add a tool to the workflow tool registry."""
        self.tools.register_tool(tool, name)
        return self

    def add_llm(self, name: str, llm: BaseLLMWrapper) -> "WorkflowBuilder":
        """Add an LLM wrapper to the workflow."""
        self.llm_wrappers[name] = llm
        return self

    def set_observer(self, observer: WorkflowObserver) -> "WorkflowBuilder":
        """Set the observability system."""
        self.observer = observer
        return self

    def set_error_recovery(self, error_recovery: ErrorRecoverySystem) -> "WorkflowBuilder":
        """Set the error recovery system."""
        self.error_recovery = error_recovery
        return self

    def add_sequential_step(self, name: str, agent_names: List[str], **kwargs) -> "WorkflowBuilder":
        """Add a sequential execution step."""
        step = WorkflowStep(name=name, step_type=StepType.SEQUENTIAL, agents=agent_names, **kwargs)
        self.steps.append(step)
        return self

    def add_parallel_step(self, name: str, agent_names: List[str], **kwargs) -> "WorkflowBuilder":
        """Add a parallel execution step."""
        step = WorkflowStep(name=name, step_type=StepType.PARALLEL, agents=agent_names, **kwargs)
        self.steps.append(step)
        return self

    def add_conditional_step(
        self, name: str, condition: str, agent_names: List[str], **kwargs
    ) -> "WorkflowBuilder":
        """Add a conditional execution step."""
        step = WorkflowStep(
            name=name,
            step_type=StepType.CONDITIONAL,
            condition=condition,
            agents=agent_names,
            **kwargs,
        )
        self.steps.append(step)
        return self

    def add_loop_step(
        self,
        name: str,
        agent_names: List[str],
        condition: str = None,
        max_iterations: int = 5,
        **kwargs,
    ) -> "WorkflowBuilder":
        """Add a loop execution step."""
        step = WorkflowStep(
            name=name,
            step_type=StepType.LOOP,
            agents=agent_names,
            condition=condition,
            max_iterations=max_iterations,
            **kwargs,
        )
        self.steps.append(step)
        return self

    def build(self) -> "WorkflowEngine":
        """Build the workflow engine."""
        config = WorkflowConfig(name=self.name, description=self.description, steps=self.steps)

        engine = WorkflowEngine(
            config=config, observer=self.observer, error_recovery=self.error_recovery
        )

        # Register agents
        for name, agent in self.agents.items():
            engine.register_agent(name, agent)

        # Set tool registry
        engine.tool_registry = self.tools

        return engine

    def to_dict(self) -> Dict[str, Any]:
        """Export workflow configuration as dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "steps": [asdict(step) for step in self.steps],
            "agents": {
                name: {
                    "type": type(agent).__name__,
                    "config": asdict(agent.config) if hasattr(agent, "config") else {},
                }
                for name, agent in self.agents.items()
            },
            "tools": self.tools.get_registry_info(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Export workflow configuration as JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_yaml(self) -> str:
        """Export workflow configuration as YAML."""
        return yaml.dump(self.to_dict(), default_flow_style=False)


class WorkflowEngine(BaseCoordinator):
    """
    Concrete implementation of workflow execution engine.

    Executes workflows defined by WorkflowConfig with full observability,
    error recovery, and tool integration.
    """

    def __init__(
        self,
        config: WorkflowConfig,
        observer: WorkflowObserver = None,
        error_recovery: ErrorRecoverySystem = None,
    ):
        super().__init__(config, error_recovery, observer or ConsoleObserver())
        self.tool_registry = ToolRegistry()

    def execute_workflow(self, input_data: Any, context: Dict[str, Any] = None) -> WorkflowContext:
        """Execute the complete workflow."""
        workflow_context = WorkflowContext(input_data, context or {})

        # Log workflow start
        self.observer.log_workflow_start(
            workflow_name=self.config.name, input_data=input_data, metadata=context
        )

        start_time = workflow_context.start_time
        success = True
        error_message = None

        try:
            # Execute each step in sequence
            for step in self.config.steps:
                step_result = self._execute_step(step, workflow_context)
                workflow_context.add_step_result(step.name, step_result, success=True)

                # Check for early termination conditions
                if workflow_context.has_errors() and not self.config.error_recovery:
                    break

        except Exception as e:
            success = False
            error_message = str(e)
            workflow_context.add_error(e)

        finally:
            # Log workflow end
            duration = (workflow_context.start_time - start_time).total_seconds()
            self.observer.log_workflow_end(
                workflow_name=self.config.name,
                success=success,
                duration=duration,
                result=workflow_context.get_latest_result(),
                error=error_message,
            )

            # Record in execution history
            execution_record = {
                "workflow_name": self.config.name,
                "timestamp": start_time.isoformat(),
                "duration_seconds": duration,
                "success": success,
                "steps_completed": len(workflow_context.step_results),
                "error": error_message,
                "summary": workflow_context.get_execution_summary(),
            }
            self.execution_history.append(execution_record)

        return workflow_context

    def validate_workflow(self) -> Dict[str, Any]:
        """Validate the workflow configuration."""
        issues = []

        # Check that all referenced agents exist
        for step in self.config.steps:
            for agent_name in step.agents:
                if agent_name not in self.agents:
                    issues.append(
                        f"Agent '{agent_name}' referenced in step '{step.name}' not found"
                    )

        # Check conditional expressions
        for step in self.config.steps:
            if step.condition:
                try:
                    # Basic syntax check
                    compile(step.condition, "<string>", "eval")
                except SyntaxError as e:
                    issues.append(f"Invalid condition syntax in step '{step.name}': {e}")

        # Check for circular dependencies in tools
        for agent_name, agent in self.agents.items():
            if hasattr(agent, "tools"):
                for tool_name in agent.tools:
                    if not self.tool_registry.validate_dependencies(tool_name):
                        issues.append(
                            "Tool dependencies not satisfied for "
                            f"'{tool_name}' in agent '{agent_name}'"
                        )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "agents_count": len(self.agents),
            "steps_count": len(self.config.steps),
            "tools_count": len(self.tool_registry.list_tools()),
        }

    def get_workflow_info(self) -> Dict[str, Any]:
        """Get comprehensive workflow information."""
        validation = self.validate_workflow()

        return {
            "config": {
                "name": self.config.name,
                "description": self.config.description,
                "steps": len(self.config.steps),
            },
            "agents": {name: agent.get_status() for name, agent in self.agents.items()},
            "tools": self.tool_registry.get_registry_info(),
            "validation": validation,
            "execution_history": self.execution_history[-10:],  # Last 10 executions
            "system_status": {
                "error_recovery_enabled": self.error_recovery is not None,
                "observability_enabled": self.observer is not None,
            },
        }

    @classmethod
    def from_config_file(
        cls, config_path: str, agents: Dict[str, BaseAgent] = None, tools: List[BaseTool] = None
    ) -> "WorkflowEngine":
        """Load workflow from configuration file."""
        import os

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            if config_path.endswith(".json"):
                config_data = json.load(f)
            elif config_path.endswith(".yaml") or config_path.endswith(".yml"):
                config_data = yaml.safe_load(f)
            else:
                raise ValueError("Config file must be JSON or YAML")

        # Build workflow config
        steps = []
        for step_data in config_data.get("steps", []):
            step = WorkflowStep(
                name=step_data["name"],
                step_type=StepType(step_data["step_type"]),
                agents=step_data.get("agents", []),
                condition=step_data.get("condition"),
                max_iterations=step_data.get("max_iterations", 1),
                timeout_seconds=step_data.get("timeout_seconds"),
                retry_count=step_data.get("retry_count", 0),
                error_handler=step_data.get("error_handler"),
                metadata=step_data.get("metadata", {}),
            )
            steps.append(step)

        config = WorkflowConfig(
            name=config_data["name"],
            description=config_data.get("description", ""),
            steps=steps,
            global_timeout_seconds=config_data.get("global_timeout_seconds"),
            error_recovery=config_data.get("error_recovery", True),
            observability=config_data.get("observability", True),
        )

        # Create engine
        engine = cls(config)

        # Register agents if provided
        if agents:
            for name, agent in agents.items():
                engine.register_agent(name, agent)

        # Register tools if provided
        if tools:
            for tool in tools:
                engine.tool_registry.register_tool(tool)

        return engine

    def export_config(self, output_path: str, format: str = "yaml"):
        """Export workflow configuration to file."""
        builder = WorkflowBuilder(self.config.name, self.config.description)
        builder.steps = self.config.steps
        builder.agents = self.agents
        builder.tools = self.tool_registry

        if format.lower() == "json":
            content = builder.to_json()
        elif format.lower() in ["yaml", "yml"]:
            content = builder.to_yaml()
        else:
            raise ValueError("Format must be 'json' or 'yaml'")

        with open(output_path, "w") as f:
            f.write(content)


def create_simple_workflow(
    name: str, agents: List[BaseAgent], observer: WorkflowObserver = None
) -> WorkflowEngine:
    """
    Create a simple sequential workflow from a list of agents.

    Convenience function for basic use cases.
    """
    builder = WorkflowBuilder(name, f"Simple sequential workflow with {len(agents)} agents")

    if observer:
        builder.set_observer(observer)

    # Add all agents
    agent_names = []
    for i, agent in enumerate(agents):
        agent_name = getattr(agent, "config", {}).get("name", f"agent_{i}")
        builder.add_agent(agent_name, agent)
        agent_names.append(agent_name)

    # Create single sequential step
    builder.add_sequential_step("main", agent_names)

    return builder.build()
