from .graphviz_export import generate_dot
from .workflow_dsl import (
    ActivityOperator,
    BaseOperator,
    CircuitBreakerPolicy,
    ConditionOperator,
    Duration,
    EmitEventOperator,
    ForEachOperator,
    JoinMode,
    JoinOperator,
    OperatorType,
    ParallelOperator,
    ReflexiveOperator,
    RetryPolicy,
    SwitchOperator,
    TaskOperator,
    TimeoutPolicy,
    TriggerRule,
    WaitForEventOperator,
    WaitOperator,
    WhileOperator,
    Workflow,
    WorkflowBuilder,
)


__all__ = [
    "ActivityOperator",
    "BaseOperator",
    "CircuitBreakerPolicy",
    "ConditionOperator",
    "Duration",
    "EmitEventOperator",
    "ForEachOperator",
    "JoinMode",
    "JoinOperator",
    "OperatorType",
    "ParallelOperator",
    "ReflexiveOperator",
    "RetryPolicy",
    "SwitchOperator",
    "TaskOperator",
    "TimeoutPolicy",
    "TriggerRule",
    "WaitForEventOperator",
    "WaitOperator",
    "WhileOperator",
    "Workflow",
    "WorkflowBuilder",
    "generate_dot",
]


# Optional MCP server support (requires mcp extra)
from typing import Any


def get_mcp_server() -> Any:
    """Get the MCP server instance. Requires: pip install highway_dsl[mcp]"""
    try:
        from highway_dsl.mcp_server import mcp

        return mcp
    except ImportError as e:
        raise ImportError(
            "MCP support requires the mcp extra. "
            "Install with: pip install highway_dsl[mcp]"
        ) from e
