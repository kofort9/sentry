# Reusable Agentic Framework Guide

> **See Also**: For project overview and installation, see [README.md](../../README.md). For CAMEL implementation details, see [CAMEL session notes](../../notes/camel-sessions/).

## Overview

This framework provides a **reusable foundation** for building multi-agent workflows extracted from our successful CAMEL implementation. It enables rapid development of domain-specific agentic systems while maintaining consistent patterns for observability, error recovery, and tool integration.

This framework is actively used in the Sentries project for:
- **TestSentry CAMEL implementation** (`sentries/testsentry_camel.py`)
- **CAMEL coordinator** (`sentries/camel/coordinator.py`)
- **Custom agent workflows** built on the framework abstractions

## 🏗️ Architecture

The framework consists of several core components:

```
Framework
├── agents.py          # Abstract agent classes and interfaces
├── coordinators.py    # Workflow orchestration patterns
├── tools.py           # Tool system and registry
├── llm.py            # LLM integration abstractions
├── observability.py  # Monitoring and logging
├── error_recovery.py # Error handling and retry logic
└── workflows.py      # Workflow builder and engine
```

## 🤖 Core Concepts

### 1. Agents

**Base Agent Types:**
- `BaseAgent`: Abstract base for all agents
- `LLMAgent`: Agents that primarily use LLM interactions
- `ToolAgent`: Agents that primarily use tools/functions

**Agent Roles:**
```python
class AgentRole(Enum):
    ANALYZER = "analyzer"       # Analyzes input and extracts insights
    PLANNER = "planner"         # Creates structured plans
    EXECUTOR = "executor"       # Executes plans into actions
    VALIDATOR = "validator"     # Validates outputs
    COORDINATOR = "coordinator" # Orchestrates other agents
    OBSERVER = "observer"       # Monitors workflows
```

### 2. Tools

Tools are reusable components that agents use to perform specific operations:

**Tool Categories:**
- `ANALYSIS`: Data analysis and insights
- `GENERATION`: Content/code generation
- `VALIDATION`: Validation and verification
- `TRANSFORMATION`: Data transformation
- `INTEGRATION`: External system integration
- `UTILITY`: General utilities

### 3. Workflows

Workflows define how agents collaborate:

**Step Types:**
- `SEQUENTIAL`: Execute agents one after another
- `PARALLEL`: Execute multiple agents simultaneously
- `CONDITIONAL`: Execute based on conditions
- `LOOP`: Repeat execution with conditions

## 🚀 Quick Start

### Creating a Simple Workflow

```python
from sentries.framework import (
    WorkflowBuilder, LLMAgent, ToolAgent, AgentConfig, AgentRole,
    MockLLMWrapper, BaseTool, ToolCategory, ToolMetadata
)

# 1. Create a custom tool
class DataProcessingTool(BaseTool):
    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="DataProcessingTool",
            category=ToolCategory.TRANSFORMATION,
            description="Processes input data",
            required_params=["data"]
        )

    def execute(self, data):
        return {"processed": f"Processed: {data}"}

# 2. Create agents
analyzer_config = AgentConfig(
    name="analyzer",
    role=AgentRole.ANALYZER,
    model_name="mock-model",
    system_message="You analyze data and extract insights.",
    tools=["DataProcessingTool"]
)

analyzer = LLMAgent(
    config=analyzer_config,
    llm_wrapper=MockLLMWrapper(["Analysis complete: insights found"])
)

# 3. Build workflow
workflow = (WorkflowBuilder("DataPipeline", "Simple data processing workflow")
            .add_agent("analyzer", analyzer)
            .add_tool(DataProcessingTool())
            .add_sequential_step("analyze", ["analyzer"])
            .build())

# 4. Execute workflow
result = workflow.execute_workflow("sample data")
print(f"Success: {not result.has_errors()}")
```

## 📖 Detailed Examples

### Complete Multi-Agent Workflow

See `examples/docsentry_workflow.py` for a comprehensive example that demonstrates:

- **Custom domain-specific tools** (DocumentAnalysis, DocumentGeneration)
- **Specialized agents** with different roles (Analyzer, Planner, Updater)
- **Sequential workflow steps** with error recovery
- **Observability integration** with LLM interaction logging
- **Tool registry** and dependency management

### TestSentry → Framework Migration

The original TestSentry implementation has been refactored using this framework:

**Before (Domain-Specific):**
```python
class CAMELCoordinator:
    def __init__(self, planner_model, patcher_model):
        self.planner = PlannerAgent(planner_model)
        self.patcher = PatcherAgent(patcher_model)

    def process_test_failures(self, test_output):
        # Hard-coded workflow
        pass
```

**After (Framework-Based):**
```python
# Create reusable workflow
workflow = (WorkflowBuilder("TestSentry", "Test fixing workflow")
            .add_agent("planner", PlannerAgent(planner_model))
            .add_agent("patcher", PatcherAgent(patcher_model))
            .add_sequential_step("plan_and_patch", ["planner", "patcher"])
            .build())

# Execute with observability
result = workflow.execute_workflow(test_output)
```

## 🔧 Advanced Features

### 1. Configuration-Driven Workflows

Define workflows in YAML/JSON:

```yaml
name: "DocumentUpdater"
description: "Updates documentation automatically"
steps:
  - name: "analyze"
    step_type: "sequential"
    agents: ["analyzer"]
  - name: "plan_and_execute"
    step_type: "parallel"
    agents: ["planner", "updater"]
  - name: "validate"
    step_type: "conditional"
    condition: "results['plan_and_execute']['success']"
    agents: ["validator"]
```

Load and execute:
```python
workflow = WorkflowEngine.from_config_file("workflow.yaml", agents=my_agents)
result = workflow.execute_workflow(input_data)
```

### 2. Error Recovery

Built-in error classification and recovery:

```python
from sentries.framework import ErrorRecoverySystem, ErrorCategory

# Create recovery system
recovery = ErrorRecoverySystem(max_retries=3)

# Add custom recovery strategy
def custom_network_recovery(error_info, context):
    # Custom recovery logic
    return True

recovery.add_recovery_strategy(ErrorCategory.NETWORK, custom_network_recovery)

# Use in workflow
workflow = (WorkflowBuilder("RobustWorkflow")
            .set_error_recovery(recovery)
            .build())
```

### 3. Observability

Multiple observer types for monitoring:

```python
from sentries.framework import ConsoleObserver, MemoryObserver

# Console logging
console_observer = ConsoleObserver(log_level=LogLevel.INFO)

# Memory storage (for dashboards)
memory_observer = MemoryObserver(max_events=1000)

# Use in workflow
workflow = (WorkflowBuilder("MonitoredWorkflow")
            .set_observer(memory_observer)
            .build())

# Get observability data
interactions = memory_observer.get_llm_interactions()
agent_stats = memory_observer.get_agent_stats()
```

### 4. Tool Composition

Create complex tools from simple ones:

```python
from sentries.framework import ComposeTool, FunctionTool

# Create simple function tools
def analyze_data(data): return {"analysis": data}
def validate_results(results): return {"valid": True}

# Compose into pipeline
analysis_tool = FunctionTool(analyze_data)
validation_tool = FunctionTool(validate_results)
pipeline_tool = ComposeTool([analysis_tool, validation_tool], "DataPipeline")

# Use in agent
agent_config = AgentConfig(
    name="processor",
    role=AgentRole.EXECUTOR,
    tools=["DataPipeline"]
)
```

## 🔀 Migration Patterns

### From Monolithic to Agentic

**Step 1: Identify Responsibilities**
```python
# Before: Single function doing everything
def process_request(request):
    analysis = analyze(request)
    plan = create_plan(analysis)
    result = execute(plan)
    return validate(result)

# After: Separate agents
analyzer = AnalyzerAgent(...)
planner = PlannerAgent(...)
executor = ExecutorAgent(...)
validator = ValidatorAgent(...)
```

**Step 2: Extract Tools**
```python
# Before: Embedded logic
class RequestProcessor:
    def process(self, request):
        # 50 lines of processing logic
        pass

# After: Reusable tool
class RequestProcessingTool(BaseTool):
    def execute(self, request):
        # Focused processing logic
        pass
```

**Step 3: Define Workflow**
```python
workflow = (WorkflowBuilder("RequestProcessor")
            .add_agent("analyzer", analyzer)
            .add_agent("planner", planner)
            .add_agent("executor", executor)
            .add_agent("validator", validator)
            .add_sequential_step("main", ["analyzer", "planner", "executor"])
            .add_conditional_step("validate", "results['main']['success']", ["validator"])
            .build())
```

## 📊 Performance Considerations

### Resource Management

1. **LLM Usage Optimization**
   - Use `LLMPool` for load balancing across multiple models
   - Implement request batching where possible
   - Cache common responses

2. **Memory Management**
   - Set appropriate history limits on agents
   - Use `MemoryObserver.clear_history()` periodically
   - Limit tool registry size

3. **Parallel Execution**
   - Use `PARALLEL` steps for independent operations
   - Consider async versions for I/O-bound tools
   - Balance parallelism with resource constraints

### Monitoring

```python
# Get framework performance metrics
workflow_info = workflow.get_workflow_info()
print(f"Execution history: {len(workflow_info['execution_history'])}")

# Get LLM usage stats
for agent_name, agent in workflow.agents.items():
    if hasattr(agent, 'llm'):
        stats = agent.llm.get_usage_stats()
        print(f"{agent_name} LLM usage: {stats['total_tokens']} tokens")
```

## 🧪 Testing

### Unit Testing Agents

```python
import unittest
from sentries.framework import MockLLMWrapper

class TestMyAgent(unittest.TestCase):
    def setUp(self):
        mock_llm = MockLLMWrapper(['{"result": "test response"}'])
        self.agent = MyAgent(config, llm_wrapper=mock_llm)

    def test_process(self):
        result = self.agent.process("test input")
        self.assertTrue(result["success"])
```

### Integration Testing Workflows

```python
def test_workflow():
    # Use mock LLMs for testing
    workflow = create_test_workflow_with_mocks()

    # Execute with test data
    result = workflow.execute_workflow("test input")

    # Verify results
    assert not result.has_errors()
    assert len(result.step_results) == expected_steps
```

## 🔮 Future Extensions

The framework is designed for extensibility:

1. **Async Support**: Add `AsyncAgent` and `AsyncCoordinator` classes
2. **Distributed Execution**: Implement remote agent execution
3. **Advanced LLM Features**: Support for streaming, function calling
4. **Visual Workflow Designer**: Web UI for building workflows
5. **Integration Plugins**: Pre-built integrations for common services

## 📝 Best Practices

1. **Agent Design**
   - Keep agents focused on single responsibilities
   - Use clear, descriptive system messages
   - Implement robust error handling

2. **Tool Development**
   - Make tools stateless and reusable
   - Provide comprehensive metadata
   - Validate inputs thoroughly

3. **Workflow Design**
   - Start simple, add complexity gradually
   - Use conditional steps for branching logic
   - Include validation steps after critical operations

4. **Observability**
   - Always include observability in production workflows
   - Monitor LLM token usage and costs
   - Log workflow execution patterns

5. **Testing**
   - Test agents independently before integration
   - Use mocks for external dependencies
   - Validate workflow execution paths

## 💡 Contributing

To extend the framework:

1. **New Agent Types**: Inherit from `BaseAgent`, implement `process()`
2. **New Tools**: Inherit from `BaseTool`, implement `execute()` and `_create_metadata()`
3. **New Coordinators**: Inherit from `BaseCoordinator`, implement `execute_workflow()`
4. **New Observers**: Inherit from `WorkflowObserver`, implement logging methods

---

**🎯 The framework enables you to build sophisticated multi-agent workflows while maintaining consistency, observability, and reusability across different domains.**
