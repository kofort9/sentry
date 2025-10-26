"""
Observability and monitoring components for the reusable framework.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import datetime
import json
import logging


class LogLevel(Enum):
    """Log levels for observability."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(Enum):
    """Types of events in the framework."""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    AGENT_EXECUTION = "agent_execution"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_EXECUTION = "tool_execution"
    ERROR_OCCURRED = "error_occurred"
    ERROR_RECOVERED = "error_recovered"


@dataclass
class ObservabilityEvent:
    """Structured event for observability."""
    timestamp: str
    event_type: EventType
    source: str  # Agent name, coordinator name, etc.
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    level: LogLevel = LogLevel.INFO


class WorkflowObserver(ABC):
    """
    Abstract base class for workflow observability.
    
    Implementations can send data to different backends (logs, metrics, dashboards).
    """
    
    @abstractmethod
    def log_event(self, event: ObservabilityEvent):
        """Log an observability event."""
        pass
    
    @abstractmethod
    def log_workflow_start(self, workflow_name: str, input_data: Any, metadata: Dict[str, Any] = None):
        """Log workflow start."""
        pass
    
    @abstractmethod
    def log_workflow_end(self, workflow_name: str, success: bool, duration: float, 
                        result: Any = None, error: str = None):
        """Log workflow end."""
        pass
    
    @abstractmethod
    def log_agent_execution(self, agent_name: str, duration: float, success: bool, 
                          error: str = None, result_summary: str = None):
        """Log agent execution."""
        pass
    
    @abstractmethod
    def log_llm_interaction(self, agent_name: str, agent_role: str, llm_role: str, 
                          content: str, model: str = None, metadata: Dict[str, Any] = None):
        """Log LLM interaction."""
        pass
    
    @abstractmethod
    def log_tool_execution(self, agent_name: str, tool_name: str, duration: float, 
                         success: bool, result_summary: str = None, error: str = None):
        """Log tool execution."""
        pass


class ConsoleObserver(WorkflowObserver):
    """Observer that logs to console/stdout."""
    
    def __init__(self, log_level: LogLevel = LogLevel.INFO, include_timestamps: bool = True):
        self.log_level = log_level
        self.include_timestamps = include_timestamps
        self.logger = logging.getLogger("framework.observer")
        
        # Set up console handler if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s' if include_timestamps
                else '%(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
    
    def log_event(self, event: ObservabilityEvent):
        """Log event to console."""
        level_mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        
        log_level = level_mapping.get(event.level, logging.INFO)
        message = f"[{event.event_type.value}] {event.source}: {json.dumps(event.data, default=str)}"
        
        self.logger.log(log_level, message)
    
    def log_workflow_start(self, workflow_name: str, input_data: Any, metadata: Dict[str, Any] = None):
        """Log workflow start to console."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.WORKFLOW_START,
            source=workflow_name,
            data={"input_summary": str(input_data)[:100] + "..." if len(str(input_data)) > 100 else str(input_data)},
            metadata=metadata or {},
            level=LogLevel.INFO
        )
        self.log_event(event)
    
    def log_workflow_end(self, workflow_name: str, success: bool, duration: float, 
                        result: Any = None, error: str = None):
        """Log workflow end to console."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.WORKFLOW_END,
            source=workflow_name,
            data={
                "success": success,
                "duration_seconds": duration,
                "result_summary": str(result)[:100] + "..." if result and len(str(result)) > 100 else str(result),
                "error": error,
            },
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
        self.log_event(event)
    
    def log_agent_execution(self, agent_name: str, duration: float, success: bool, 
                          error: str = None, result_summary: str = None):
        """Log agent execution to console."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.AGENT_EXECUTION,
            source=agent_name,
            data={
                "duration_seconds": duration,
                "success": success,
                "error": error,
                "result_summary": result_summary,
            },
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
        self.log_event(event)
    
    def log_llm_interaction(self, agent_name: str, agent_role: str, llm_role: str, 
                          content: str, model: str = None, metadata: Dict[str, Any] = None):
        """Log LLM interaction to console."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.LLM_REQUEST if llm_role in ["system", "user"] else EventType.LLM_RESPONSE,
            source=agent_name,
            data={
                "agent_role": agent_role,
                "llm_role": llm_role,
                "content_length": len(content),
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "model": model,
            },
            metadata=metadata or {},
            level=LogLevel.DEBUG
        )
        self.log_event(event)
    
    def log_tool_execution(self, agent_name: str, tool_name: str, duration: float, 
                         success: bool, result_summary: str = None, error: str = None):
        """Log tool execution to console."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.TOOL_EXECUTION,
            source=f"{agent_name}.{tool_name}",
            data={
                "tool_name": tool_name,
                "duration_seconds": duration,
                "success": success,
                "result_summary": result_summary,
                "error": error,
            },
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
        self.log_event(event)


class MemoryObserver(WorkflowObserver):
    """Observer that stores events in memory for dashboard integration."""
    
    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self.events: List[ObservabilityEvent] = []
        self.workflow_sessions: Dict[str, Dict[str, Any]] = {}
        self.agent_stats: Dict[str, Dict[str, Any]] = {}
        self.llm_interactions: List[Dict[str, Any]] = []
    
    def log_event(self, event: ObservabilityEvent):
        """Store event in memory."""
        self.events.append(event)
        
        # Trim events to max size
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def log_workflow_start(self, workflow_name: str, input_data: Any, metadata: Dict[str, Any] = None):
        """Log and track workflow start."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.WORKFLOW_START,
            source=workflow_name,
            data={"input_summary": str(input_data)[:200] + "..." if len(str(input_data)) > 200 else str(input_data)},
            metadata=metadata or {}
        )
        self.log_event(event)
        
        # Track workflow session
        self.workflow_sessions[workflow_name] = {
            "start_time": event.timestamp,
            "status": "running",
            "metadata": metadata or {},
        }
    
    def log_workflow_end(self, workflow_name: str, success: bool, duration: float, 
                        result: Any = None, error: str = None):
        """Log and track workflow end."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.WORKFLOW_END,
            source=workflow_name,
            data={
                "success": success,
                "duration_seconds": duration,
                "result_summary": str(result)[:200] + "..." if result and len(str(result)) > 200 else str(result),
                "error": error,
            },
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
        self.log_event(event)
        
        # Update workflow session
        if workflow_name in self.workflow_sessions:
            self.workflow_sessions[workflow_name].update({
                "end_time": event.timestamp,
                "status": "completed" if success else "failed",
                "duration_seconds": duration,
                "success": success,
                "error": error,
            })
    
    def log_agent_execution(self, agent_name: str, duration: float, success: bool, 
                          error: str = None, result_summary: str = None):
        """Log and track agent execution."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.AGENT_EXECUTION,
            source=agent_name,
            data={
                "duration_seconds": duration,
                "success": success,
                "error": error,
                "result_summary": result_summary,
            },
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
        self.log_event(event)
        
        # Update agent stats
        if agent_name not in self.agent_stats:
            self.agent_stats[agent_name] = {
                "total_executions": 0,
                "successful_executions": 0,
                "total_duration": 0.0,
                "last_execution": None,
            }
        
        stats = self.agent_stats[agent_name]
        stats["total_executions"] += 1
        if success:
            stats["successful_executions"] += 1
        stats["total_duration"] += duration
        stats["last_execution"] = event.timestamp
    
    def log_llm_interaction(self, agent_name: str, agent_role: str, llm_role: str, 
                          content: str, model: str = None, metadata: Dict[str, Any] = None):
        """Log and store LLM interaction."""
        interaction = {
            "timestamp": datetime.datetime.now().isoformat(),
            "agent_name": agent_name,
            "agent_role": agent_role,
            "llm_role": llm_role,
            "content": content[:1000] + "..." if len(content) > 1000 else content,  # Truncate for memory
            "content_length": len(content),
            "model": model,
            "metadata": metadata or {},
        }
        
        self.llm_interactions.append(interaction)
        
        # Trim interactions to prevent memory bloat
        if len(self.llm_interactions) > self.max_events:
            self.llm_interactions = self.llm_interactions[-self.max_events:]
        
        # Also log as event
        event = ObservabilityEvent(
            timestamp=interaction["timestamp"],
            event_type=EventType.LLM_REQUEST if llm_role in ["system", "user"] else EventType.LLM_RESPONSE,
            source=agent_name,
            data={
                "agent_role": agent_role,
                "llm_role": llm_role,
                "content_length": len(content),
                "model": model,
            },
            metadata=metadata or {},
            level=LogLevel.DEBUG
        )
        self.log_event(event)
    
    def log_tool_execution(self, agent_name: str, tool_name: str, duration: float, 
                         success: bool, result_summary: str = None, error: str = None):
        """Log tool execution."""
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.TOOL_EXECUTION,
            source=f"{agent_name}.{tool_name}",
            data={
                "tool_name": tool_name,
                "duration_seconds": duration,
                "success": success,
                "result_summary": result_summary,
                "error": error,
            },
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
        self.log_event(event)
    
    def get_recent_events(self, count: int = 50, event_type: EventType = None) -> List[ObservabilityEvent]:
        """Get recent events, optionally filtered by type."""
        filtered_events = self.events
        if event_type:
            filtered_events = [e for e in self.events if e.event_type == event_type]
        
        return filtered_events[-count:]
    
    def get_workflow_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all workflow sessions."""
        return self.workflow_sessions
    
    def get_agent_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get agent statistics."""
        return self.agent_stats
    
    def get_llm_interactions(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent LLM interactions."""
        return self.llm_interactions[-count:]
    
    def clear_history(self):
        """Clear all stored observability data."""
        self.events.clear()
        self.workflow_sessions.clear()
        self.agent_stats.clear()
        self.llm_interactions.clear()


class AgentLogger:
    """
    Simplified logger for agent implementations.
    
    Provides easy-to-use logging methods that integrate with the observability system.
    """
    
    def __init__(self, agent_name: str, observer: WorkflowObserver = None):
        self.agent_name = agent_name
        self.observer = observer or ConsoleObserver()
        
        # Set up standard Python logger
        self.logger = logging.getLogger(f"agent.{agent_name}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, message: str, data: Dict[str, Any] = None):
        """Log info message."""
        self.logger.info(message)
        if data:
            event = ObservabilityEvent(
                timestamp=datetime.datetime.now().isoformat(),
                event_type=EventType.AGENT_EXECUTION,  # Generic event type
                source=self.agent_name,
                data=data,
                level=LogLevel.INFO
            )
            self.observer.log_event(event)
    
    def error(self, message: str, error: Exception = None, data: Dict[str, Any] = None):
        """Log error message."""
        self.logger.error(message, exc_info=error)
        
        error_data = data or {}
        if error:
            error_data.update({
                "error_message": str(error),
                "error_type": type(error).__name__,
            })
        
        event = ObservabilityEvent(
            timestamp=datetime.datetime.now().isoformat(),
            event_type=EventType.ERROR_OCCURRED,
            source=self.agent_name,
            data=error_data,
            level=LogLevel.ERROR
        )
        self.observer.log_event(event)
    
    def debug(self, message: str, data: Dict[str, Any] = None):
        """Log debug message."""
        self.logger.debug(message)
        if data:
            event = ObservabilityEvent(
                timestamp=datetime.datetime.now().isoformat(),
                event_type=EventType.AGENT_EXECUTION,
                source=self.agent_name,
                data=data,
                level=LogLevel.DEBUG
            )
            self.observer.log_event(event)
    
    def log_llm_call(self, role: str, content: str, model: str = None, metadata: Dict[str, Any] = None):
        """Log LLM interaction."""
        self.observer.log_llm_interaction(
            agent_name=self.agent_name,
            agent_role="unknown",  # Could be enhanced to track agent roles
            llm_role=role,
            content=content,
            model=model,
            metadata=metadata
        )
