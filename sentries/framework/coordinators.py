"""
Abstract base classes for coordinators in the reusable framework.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
import datetime
import asyncio


class StepType(Enum):
    """Types of steps in a workflow."""
    SEQUENTIAL = "sequential"    # Execute one agent after another
    PARALLEL = "parallel"        # Execute multiple agents simultaneously
    CONDITIONAL = "conditional"  # Execute based on condition
    LOOP = "loop"               # Repeat execution with condition
    ERROR_HANDLER = "error_handler"  # Handle errors from previous steps


@dataclass
class WorkflowStep:
    """Definition of a single step in a workflow."""
    name: str
    step_type: StepType
    agents: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # Python expression for conditional steps
    max_iterations: int = 1          # For loop steps
    timeout_seconds: Optional[float] = None
    retry_count: int = 0
    error_handler: Optional[str] = None  # Name of error handling step
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    """Configuration for a complete workflow."""
    name: str
    description: str
    steps: List[WorkflowStep]
    global_timeout_seconds: Optional[float] = None
    error_recovery: bool = True
    observability: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowContext:
    """
    Context object that flows through workflow execution.
    
    Contains data, intermediate results, and execution state.
    """
    
    def __init__(self, initial_data: Any = None, metadata: Dict[str, Any] = None):
        self.initial_data = initial_data
        self.metadata = metadata or {}
        self.step_results: Dict[str, Any] = {}
        self.agent_outputs: Dict[str, Any] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.start_time = datetime.datetime.now()
        self.current_step: Optional[str] = None
    
    def add_step_result(self, step_name: str, result: Any, success: bool = True):
        """Add result from a workflow step."""
        self.step_results[step_name] = {
            "result": result,
            "success": success,
            "timestamp": datetime.datetime.now().isoformat(),
        }
    
    def add_agent_output(self, agent_name: str, output: Any):
        """Add output from an agent execution."""
        self.agent_outputs[agent_name] = output
    
    def add_error(self, error: Exception, step_name: str = None, agent_name: str = None):
        """Add an error to the context."""
        error_record = {
            "error": str(error),
            "error_type": type(error).__name__,
            "step": step_name,
            "agent": agent_name,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        self.errors.append(error_record)
    
    def get_latest_result(self, step_name: str = None) -> Any:
        """Get the most recent result, optionally from specific step."""
        if step_name:
            return self.step_results.get(step_name, {}).get("result")
        
        if self.step_results:
            latest_step = max(self.step_results.keys(), 
                            key=lambda k: self.step_results[k]["timestamp"])
            return self.step_results[latest_step]["result"]
        
        return None
    
    def has_errors(self) -> bool:
        """Check if any errors occurred during execution."""
        return len(self.errors) > 0
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of workflow execution."""
        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        
        return {
            "duration_seconds": duration,
            "steps_completed": len(self.step_results),
            "agents_executed": len(self.agent_outputs),
            "errors_occurred": len(self.errors),
            "success": not self.has_errors() and len(self.step_results) > 0,
            "final_result": self.get_latest_result(),
        }


class BaseCoordinator(ABC):
    """
    Abstract base class for workflow coordinators.
    
    Coordinates execution of multiple agents according to a workflow definition.
    """
    
    def __init__(self, workflow_config: WorkflowConfig, error_recovery_system=None, observer=None):
        self.config = workflow_config
        self.error_recovery = error_recovery_system
        self.observer = observer
        
        self.agents: Dict[str, Any] = {}  # Registry of available agents
        self.execution_history: List[Dict[str, Any]] = []
        
    def register_agent(self, name: str, agent: Any):
        """Register an agent for use in workflows."""
        self.agents[name] = agent
    
    def get_agent(self, name: str) -> Optional[Any]:
        """Get a registered agent by name."""
        return self.agents.get(name)
    
    @abstractmethod
    def execute_workflow(self, input_data: Any, context: Dict[str, Any] = None) -> WorkflowContext:
        """
        Execute the complete workflow.
        
        Args:
            input_data: Initial data to process
            context: Additional context for execution
            
        Returns:
            WorkflowContext with execution results
        """
        pass
    
    def _execute_step(self, step: WorkflowStep, workflow_context: WorkflowContext) -> Any:
        """Execute a single workflow step."""
        workflow_context.current_step = step.name
        
        try:
            if step.step_type == StepType.SEQUENTIAL:
                return self._execute_sequential_step(step, workflow_context)
            elif step.step_type == StepType.PARALLEL:
                return self._execute_parallel_step(step, workflow_context)
            elif step.step_type == StepType.CONDITIONAL:
                return self._execute_conditional_step(step, workflow_context)
            elif step.step_type == StepType.LOOP:
                return self._execute_loop_step(step, workflow_context)
            else:
                raise ValueError(f"Unknown step type: {step.step_type}")
                
        except Exception as e:
            workflow_context.add_error(e, step_name=step.name)
            
            # Try error recovery if configured
            if step.error_handler and self.error_recovery:
                return self._handle_step_error(step, e, workflow_context)
            else:
                raise
    
    def _execute_sequential_step(self, step: WorkflowStep, workflow_context: WorkflowContext) -> List[Any]:
        """Execute agents sequentially."""
        results = []
        
        for agent_name in step.agents:
            agent = self.get_agent(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found in coordinator")
            
            # Get input for this agent (output from previous agent or initial data)
            if results:
                agent_input = results[-1]
            else:
                agent_input = workflow_context.get_latest_result() or workflow_context.initial_data
            
            # Execute agent
            agent_output = self._execute_agent(agent, agent_input, workflow_context.metadata)
            workflow_context.add_agent_output(agent_name, agent_output)
            results.append(agent_output)
        
        return results
    
    def _execute_parallel_step(self, step: WorkflowStep, workflow_context: WorkflowContext) -> List[Any]:
        """Execute agents in parallel."""
        # For now, implement synchronous "parallel" execution
        # Could be enhanced with actual async execution later
        results = []
        input_data = workflow_context.get_latest_result() or workflow_context.initial_data
        
        for agent_name in step.agents:
            agent = self.get_agent(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found in coordinator")
            
            agent_output = self._execute_agent(agent, input_data, workflow_context.metadata)
            workflow_context.add_agent_output(agent_name, agent_output)
            results.append(agent_output)
        
        return results
    
    def _execute_conditional_step(self, step: WorkflowStep, workflow_context: WorkflowContext) -> Any:
        """Execute step based on condition."""
        if not step.condition:
            raise ValueError("Conditional step requires a condition")
        
        # Simple condition evaluation (could be enhanced with safer eval)
        try:
            # Create context for condition evaluation
            condition_context = {
                "context": workflow_context,
                "results": workflow_context.step_results,
                "agents": workflow_context.agent_outputs,
                "errors": workflow_context.errors,
            }
            
            should_execute = eval(step.condition, {"__builtins__": {}}, condition_context)
            
            if should_execute:
                return self._execute_sequential_step(step, workflow_context)
            else:
                return None
                
        except Exception as e:
            raise ValueError(f"Error evaluating condition '{step.condition}': {e}")
    
    def _execute_loop_step(self, step: WorkflowStep, workflow_context: WorkflowContext) -> List[Any]:
        """Execute step in a loop."""
        results = []
        
        for iteration in range(step.max_iterations):
            if step.condition:
                # Evaluate continue condition
                condition_context = {
                    "context": workflow_context,
                    "results": workflow_context.step_results,
                    "agents": workflow_context.agent_outputs,
                    "iteration": iteration,
                }
                
                should_continue = eval(step.condition, {"__builtins__": {}}, condition_context)
                if not should_continue:
                    break
            
            iteration_result = self._execute_sequential_step(step, workflow_context)
            results.append(iteration_result)
        
        return results
    
    def _execute_agent(self, agent: Any, input_data: Any, context: Dict[str, Any]) -> Any:
        """Execute a single agent with error handling and observability."""
        start_time = datetime.datetime.now()
        
        try:
            result = agent.process(input_data, context)
            duration = (datetime.datetime.now() - start_time).total_seconds()
            
            # Log successful execution
            if self.observer:
                self.observer.log_agent_execution(
                    agent_name=getattr(agent, 'config', {}).get('name', str(agent)),
                    duration=duration,
                    success=True
                )
            
            return result
            
        except Exception as e:
            duration = (datetime.datetime.now() - start_time).total_seconds()
            
            # Log failed execution
            if self.observer:
                self.observer.log_agent_execution(
                    agent_name=getattr(agent, 'config', {}).get('name', str(agent)),
                    duration=duration,
                    success=False,
                    error=str(e)
                )
            
            # Try error recovery if available
            if self.error_recovery:
                recovered_result = self.error_recovery.with_recovery(
                    lambda: agent.process(input_data, context),
                    context={"agent": str(agent), "input": str(input_data)[:100]}
                )
                return recovered_result
            
            raise
    
    def _handle_step_error(self, step: WorkflowStep, error: Exception, workflow_context: WorkflowContext) -> Any:
        """Handle errors in workflow steps."""
        if self.error_recovery:
            return self.error_recovery.handle_error(error, context={
                "step": step.name,
                "workflow": self.config.name,
            })
        else:
            raise error
    
    def get_status(self) -> Dict[str, Any]:
        """Get current coordinator status."""
        return {
            "workflow_name": self.config.name,
            "registered_agents": list(self.agents.keys()),
            "total_steps": len(self.config.steps),
            "executions_completed": len(self.execution_history),
            "error_recovery_enabled": self.error_recovery is not None,
            "observability_enabled": self.observer is not None,
        }
