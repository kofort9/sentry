"""
Abstract base classes for tools in the reusable framework.
"""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type


class ToolCategory(Enum):
    """Categories of tools for organization."""

    ANALYSIS = "analysis"  # Data analysis and insights
    GENERATION = "generation"  # Content/code generation
    VALIDATION = "validation"  # Validation and verification
    TRANSFORMATION = "transformation"  # Data transformation
    INTEGRATION = "integration"  # External system integration
    UTILITY = "utility"  # General utilities
    OBSERVATION = "observation"  # Monitoring and logging


@dataclass
class ToolMetadata:
    """Metadata for tool registration and discovery."""

    name: str
    category: ToolCategory
    description: str
    input_types: List[Type] = field(default_factory=list)
    output_type: Optional[Type] = None
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    version: str = "1.0.0"


class BaseTool(ABC):
    """
    Abstract base class for all tools in the framework.

    Tools are reusable components that agents can use to perform
    specific operations like analysis, validation, or integration.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._metadata = self._create_metadata()

    @abstractmethod
    def _create_metadata(self) -> ToolMetadata:
        """Create metadata for this tool."""
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the tool's main functionality.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tool execution result
        """
        pass

    def validate_inputs(self, *args, **kwargs) -> bool:
        """Validate tool inputs before execution."""
        # Check required parameters
        for param in self._metadata.required_params:
            if param not in kwargs:
                raise ValueError(
                    f"Required parameter '{param}' missing for tool '{self._metadata.name}'"
                )

        # Basic type checking if specified
        if self._metadata.input_types and args:
            for i, (arg, expected_type) in enumerate(zip(args, self._metadata.input_types)):
                if not isinstance(arg, expected_type):
                    raise TypeError(
                        f"Argument {i} should be {expected_type.__name__}, got {type(arg).__name__}"
                    )

        return True

    def get_metadata(self) -> ToolMetadata:
        """Get tool metadata."""
        return self._metadata

    def get_usage_info(self) -> Dict[str, Any]:
        """Get usage information for the tool."""
        return {
            "name": self._metadata.name,
            "category": self._metadata.category.value,
            "description": self._metadata.description,
            "required_params": self._metadata.required_params,
            "optional_params": self._metadata.optional_params,
            "input_types": [t.__name__ for t in self._metadata.input_types],
            "output_type": (
                self._metadata.output_type.__name__ if self._metadata.output_type else None
            ),
            "example_usage": self._get_example_usage(),
        }

    def _get_example_usage(self) -> str:
        """Generate example usage string."""
        params = []
        for param in self._metadata.required_params:
            params.append(f"{param}=...")

        return f"tool.execute({', '.join(params)})"


class AnalysisTool(BaseTool):
    """Base class for analysis tools."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.__class__.__name__,
            category=ToolCategory.ANALYSIS,
            description="Base analysis tool",
        )


class GenerationTool(BaseTool):
    """Base class for generation tools."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.__class__.__name__,
            category=ToolCategory.GENERATION,
            description="Base generation tool",
        )


class ValidationTool(BaseTool):
    """Base class for validation tools."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.__class__.__name__,
            category=ToolCategory.VALIDATION,
            description="Base validation tool",
        )


class TransformationTool(BaseTool):
    """Base class for transformation tools."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.__class__.__name__,
            category=ToolCategory.TRANSFORMATION,
            description="Base transformation tool",
        )


class IntegrationTool(BaseTool):
    """Base class for integration tools."""

    def _create_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.__class__.__name__,
            category=ToolCategory.INTEGRATION,
            description="Base integration tool",
        )


class ToolRegistry:
    """
    Registry for managing and discovering tools.

    Provides tool registration, discovery, and dependency management.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._dependencies: Dict[str, List[str]] = {}

    def register_tool(self, tool: BaseTool, name: str = None) -> None:
        """Register a tool in the registry."""
        metadata = tool.get_metadata()
        tool_name = name or metadata.name

        self._tools[tool_name] = tool
        self._metadata[tool_name] = metadata
        self._dependencies[tool_name] = metadata.dependencies

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: ToolCategory = None) -> List[str]:
        """List available tools, optionally filtered by category."""
        if category:
            return [
                name for name, metadata in self._metadata.items() if metadata.category == category
            ]
        return list(self._tools.keys())

    def get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        """Get metadata for a specific tool."""
        return self._metadata.get(name)

    def get_tools_by_category(self, category: ToolCategory) -> Dict[str, BaseTool]:
        """Get all tools in a specific category."""
        return {
            name: tool
            for name, tool in self._tools.items()
            if self._metadata[name].category == category
        }

    def validate_dependencies(self, tool_name: str) -> bool:
        """Validate that all dependencies for a tool are available."""
        if tool_name not in self._dependencies:
            return True

        for dep in self._dependencies[tool_name]:
            if dep not in self._tools:
                return False

        return True

    def get_dependency_chain(self, tool_name: str) -> List[str]:
        """Get the full dependency chain for a tool."""
        visited = set()
        chain = []

        def _collect_deps(name: str):
            if name in visited:
                return
            visited.add(name)

            for dep in self._dependencies.get(name, []):
                _collect_deps(dep)
                chain.append(dep)

        _collect_deps(tool_name)
        return chain

    def create_tool_chain(self, tool_names: List[str]) -> List[BaseTool]:
        """Create a chain of tools with proper dependency ordering."""
        all_deps = set()
        for name in tool_names:
            all_deps.update(self.get_dependency_chain(name))

        # Add requested tools
        all_deps.update(tool_names)

        # Sort by dependencies (simple topological sort)
        ordered_names: List[str] = []
        remaining = set(all_deps)

        while remaining:
            # Find tools with no unresolved dependencies
            ready = []
            for name in remaining:
                deps = set(self._dependencies.get(name, []))
                if deps.issubset(set(ordered_names)):
                    ready.append(name)

            if not ready:
                raise ValueError("Circular dependency detected in tool chain")

            ordered_names.extend(ready)
            remaining -= set(ready)

        return [self._tools[name] for name in ordered_names if name in self._tools]

    def get_registry_info(self) -> Dict[str, Any]:
        """Get information about the registry state."""
        categories: Dict[str, List[str]] = {}
        for metadata in self._metadata.values():
            category = metadata.category.value
            if category not in categories:
                categories[category] = []
            categories[category].append(metadata.name)

        return {
            "total_tools": len(self._tools),
            "categories": categories,
            "dependencies": self._dependencies,
            "tools_by_category": {
                category.value: len(self.get_tools_by_category(category))
                for category in ToolCategory
            },
        }


class FunctionTool(BaseTool):
    """
    Wrapper to convert regular functions into tools.

    Useful for quickly integrating existing functions into the tool system.
    """

    def __init__(
        self, func: Callable, metadata: ToolMetadata = None, config: Dict[str, Any] = None
    ):
        self.func = func
        self._func_metadata = metadata
        super().__init__(config)

    def _create_metadata(self) -> ToolMetadata:
        if self._func_metadata:
            return self._func_metadata

        # Auto-generate metadata from function signature
        sig = inspect.signature(self.func)
        required_params = []
        optional_params = []

        for param_name, param in sig.parameters.items():
            if param.default == param.empty:
                required_params.append(param_name)
            else:
                optional_params.append(param_name)

        return ToolMetadata(
            name=self.func.__name__,
            category=ToolCategory.UTILITY,
            description=self.func.__doc__ or "Function-based tool",
            required_params=required_params,
            optional_params=optional_params,
        )

    def execute(self, *args, **kwargs) -> Any:
        """Execute the wrapped function."""
        self.validate_inputs(*args, **kwargs)
        return self.func(*args, **kwargs)


class ComposeTool(BaseTool):
    """
    Tool that composes multiple tools into a pipeline.

    Executes tools in sequence, passing output from one to the next.
    """

    def __init__(self, tools: List[BaseTool], name: str = "ComposedTool"):
        self.tools = tools
        self.compose_name = name
        super().__init__()

    def _create_metadata(self) -> ToolMetadata:
        all_deps = []
        for tool in self.tools:
            all_deps.extend(tool.get_metadata().dependencies)

        return ToolMetadata(
            name=self.compose_name,
            category=ToolCategory.UTILITY,
            description=f"Composed tool with {len(self.tools)} steps",
            dependencies=list(set(all_deps)),
        )

    def execute(self, input_data: Any) -> Any:
        """Execute tools in sequence."""
        result = input_data

        for i, tool in enumerate(self.tools):
            try:
                result = tool.execute(result)
            except Exception as e:
                raise ValueError(
                    f"Error in composed tool step {i} ({tool.get_metadata().name}): {e}"
                )

        return result
