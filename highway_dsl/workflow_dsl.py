# workflow_dsl.py
import contextlib
import re
from abc import ABC
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Duration:
    """Helper class for creating common time durations without importing timedelta.

    Examples:
        >>> builder.wait("sleep", wait_for=Duration.seconds(30))
        >>> builder.retry(delay=Duration.minutes(5))
        >>> builder.timeout(timeout=Duration.hours(1))
    """

    @staticmethod
    def seconds(n: int | float) -> timedelta:
        """Create a duration of N seconds."""
        return timedelta(seconds=n)

    @staticmethod
    def minutes(n: int | float) -> timedelta:
        """Create a duration of N minutes."""
        return timedelta(minutes=n)

    @staticmethod
    def hours(n: int | float) -> timedelta:
        """Create a duration of N hours."""
        return timedelta(hours=n)

    @staticmethod
    def days(n: int | float) -> timedelta:
        """Create a duration of N days."""
        return timedelta(days=n)

    @staticmethod
    def weeks(n: int | float) -> timedelta:
        """Create a duration of N weeks."""
        return timedelta(weeks=n)


class OperatorType(Enum):
    TASK = "task"
    CONDITION = "condition"
    WAIT = "wait"
    PARALLEL = "parallel"
    FOREACH = "foreach"
    SWITCH = "switch"
    TRY_CATCH = "try_catch"
    WHILE = "while"
    EMIT_EVENT = "emit_event"
    WAIT_FOR_EVENT = "wait_for_event"
    JOIN = "join"
    ACTIVITY = "activity"
    REFLEXIVE = "reflexive"  # Issue #331: Sherlock reflexive loop


class JoinMode(Enum):
    """Join operator coordination modes (Temporal-style)."""

    ALL_OF = "all_of"  # Wait for all branches to complete (success or failure)
    ANY_OF = "any_of"  # Wait for any branch to complete
    ALL_SUCCESS = "all_success"  # Wait for all branches to succeed (fail if any fails)
    ONE_SUCCESS = "one_success"  # Wait for at least one branch to succeed


class TriggerRule(Enum):
    """Dependency trigger rules (Airflow-style smart joins) - DEPRECATED: Use JoinOperator."""

    ALL_SUCCESS = "all_success"  # All dependencies must succeed (default)
    ALL_DONE = "all_done"  # All dependencies reached final state (success or failure)
    ONE_SUCCESS = "one_success"  # At least one dependency succeeded
    ONE_DONE = "one_done"  # At least one dependency reached final state
    NONE_FAILED = "none_failed"  # No dependencies failed (success or skipped)


class RetryPolicy(BaseModel):
    max_retries: int = Field(3, description="Maximum number of retries")
    delay: timedelta = Field(timedelta(seconds=5), description="Delay between retries")
    backoff_factor: float = Field(2.0, description="Factor by which to increase delay")


class TimeoutPolicy(BaseModel):
    timeout: timedelta = Field(..., description="Timeout duration")
    kill_on_timeout: bool = Field(
        True,
        description="Whether to kill the task on timeout",
    )


class CircuitBreakerPolicy(BaseModel):
    """Per-activity circuit breaker configuration (Issue #247).

    When enabled, the activity will use its own circuit breaker instance
    instead of relying solely on workflow retry_policy. Useful for protecting
    against cascading failures from external dependencies.

    Default: disabled (workflow retry_policy is the single source of truth).
    """

    failure_threshold: int = Field(
        5,
        description="Number of consecutive failures before opening circuit",
        ge=1,
    )
    success_threshold: int = Field(
        2,
        description="Number of successes required to close circuit after isolation",
        ge=1,
    )
    isolation_duration: timedelta = Field(
        timedelta(seconds=30),
        description="Duration circuit stays open before allowing test request",
    )
    catch_exceptions: list[str] | None = Field(
        None,
        description="Exception class names to count as failures (None = all exceptions)",
    )
    ignore_exceptions: list[str] | None = Field(
        None,
        description="Exception class names to NOT count as failures (pass through)",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Custom serialization for timedelta."""
        data = super().model_dump(**kwargs)
        # Serialize timedelta to seconds for JSON compatibility
        if isinstance(self.isolation_duration, timedelta):
            data["isolation_duration_seconds"] = self.isolation_duration.total_seconds()
            # Remove the timedelta object to ensure JSON serialization works
            if "isolation_duration" in data:
                del data["isolation_duration"]
        return data

    @model_validator(mode="before")
    @classmethod
    def parse_isolation_duration(cls, data: Any) -> Any:
        """Parse isolation_duration from seconds if needed."""
        if isinstance(data, dict):
            # Support deserialization from seconds
            if (
                "isolation_duration_seconds" in data
                and "isolation_duration" not in data
            ):
                data["isolation_duration"] = timedelta(
                    seconds=data["isolation_duration_seconds"]
                )
        return data


class BaseOperator(BaseModel, ABC):
    task_id: str
    operator_type: OperatorType
    dependencies: list[str] = Field(default_factory=list)
    trigger_rule: TriggerRule = Field(
        TriggerRule.ALL_SUCCESS, description="Dependency trigger rule for smart joins"
    )
    retry_policy: RetryPolicy | None = None
    timeout_policy: TimeoutPolicy | None = None
    circuit_breaker_policy: CircuitBreakerPolicy | None = Field(
        None,
        description="Per-activity circuit breaker (Issue #247). Default: disabled.",
    )
    idempotency_key: str | None = Field(
        None, description="Key for idempotent execution (prevents duplicate runs)"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    description: str = Field(default="", description="Task description")
    result_key: str | None = Field(None, description="Key to store result in context")
    # Phase 3: Callback hooks
    on_success_task_id: str | None = Field(None, description="Task to run on success")
    on_failure_task_id: str | None = Field(None, description="Task to run on failure")
    # Mark if task is internal to a loop (must NOT be excluded for engine to see it)
    is_internal_loop_task: bool = Field(
        default=False, description="Task is internal to a loop body"
    )
    # PHASE 2.1: Mark if task is internal to a parallel branch
    is_internal_parallel_task: bool = Field(
        default=False, description="Task is internal to a parallel branch"
    )

    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class TaskOperator(BaseOperator):
    function: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    operator_type: OperatorType = Field(OperatorType.TASK, frozen=True)


class ActivityOperator(BaseOperator):
    """Long-running activity that executes outside workflow transaction."""

    function: str = Field(..., description="Function to execute")
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    operator_type: OperatorType = Field(OperatorType.ACTIVITY, frozen=True)


class ConditionOperator(BaseOperator):
    condition: str
    if_true: str | None
    if_false: str | None
    operator_type: OperatorType = Field(OperatorType.CONDITION, frozen=True)


class WaitOperator(BaseOperator):
    wait_for: timedelta | datetime | str
    operator_type: OperatorType = Field(OperatorType.WAIT, frozen=True)

    @model_validator(mode="before")
    @classmethod
    def parse_wait_for(cls, data: Any) -> Any:
        if isinstance(data, dict) and "wait_for" in data:
            wait_for = data["wait_for"]
            if isinstance(wait_for, str):
                if wait_for.startswith("PT"):
                    # ISO 8601 duration format
                    match = re.match(
                        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", wait_for
                    )
                    if match:
                        hours = int(match.group(1) or 0)
                        minutes = int(match.group(2) or 0)
                        seconds = float(match.group(3) or 0)
                        data["wait_for"] = timedelta(
                            hours=hours, minutes=minutes, seconds=seconds
                        )
                elif wait_for.startswith("duration:"):  # Backward compatibility
                    data["wait_for"] = timedelta(seconds=float(wait_for.split(":")[1]))
                elif wait_for.startswith("datetime:"):  # Backward compatibility
                    data["wait_for"] = datetime.fromisoformat(wait_for.split(":", 1)[1])
                else:
                    # Assume ISO 8601 datetime format
                    with contextlib.suppress(ValueError):
                        data["wait_for"] = datetime.fromisoformat(wait_for)
        return data

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        wait_for = self.wait_for
        if isinstance(wait_for, timedelta):
            data["wait_for"] = f"PT{wait_for.total_seconds()}S"
        elif isinstance(wait_for, datetime):
            data["wait_for"] = wait_for.isoformat()
        return data


class ParallelOperator(BaseOperator):
    branches: dict[str, list[str]] = Field(default_factory=dict)
    branch_workflows: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Complete workflow definitions for each branch (serialized)",
    )
    timeout: int | None = Field(
        None, description="Optional timeout in seconds for branch execution"
    )
    operator_type: OperatorType = Field(OperatorType.PARALLEL, frozen=True)


class ForEachOperator(BaseOperator):
    items: str
    loop_body: list[
        Union[
            TaskOperator,
            "ActivityOperator",
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            "ForEachOperator",
            "WhileOperator",
            "EmitEventOperator",
            "WaitForEventOperator",
            "SwitchOperator",
            "JoinOperator",
            "ReflexiveOperator",
        ]
    ] = Field(default_factory=list)
    parallel: bool = Field(
        default=False,
        description="Execute iterations in parallel (dynamic task mapping)",
    )
    operator_type: OperatorType = Field(OperatorType.FOREACH, frozen=True)


class WhileOperator(BaseOperator):
    condition: str
    loop_body: list[
        Union[
            TaskOperator,
            ActivityOperator,
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            ForEachOperator,
            "WhileOperator",
            "EmitEventOperator",
            "WaitForEventOperator",
            "SwitchOperator",
            "JoinOperator",
            "ReflexiveOperator",
        ]
    ] = Field(default_factory=list)
    operator_type: OperatorType = Field(OperatorType.WHILE, frozen=True)


class EmitEventOperator(BaseOperator):
    """Phase 2: Emit an event that other workflows can wait for."""

    event_name: str = Field(..., description="Name of the event to emit")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event payload data"
    )
    operator_type: OperatorType = Field(OperatorType.EMIT_EVENT, frozen=True)


class WaitForEventOperator(BaseOperator):
    """Phase 2: Wait for an external event with optional timeout."""

    event_name: str = Field(..., description="Name of the event to wait for")
    timeout_seconds: int | None = Field(
        None, description="Timeout in seconds (None = wait forever)"
    )
    operator_type: OperatorType = Field(OperatorType.WAIT_FOR_EVENT, frozen=True)


class JoinOperator(BaseOperator):
    """Temporal-style join operator for coordinating parallel branches.

    Waits for multiple tasks/branches to complete based on join_mode.
    Replaces brittle dependency-based joins with explicit coordination.
    """

    join_tasks: list[str] = Field(..., description="List of task IDs to wait for")
    join_mode: JoinMode = Field(
        JoinMode.ALL_OF, description="Coordination mode (all_of, any_of, etc.)"
    )
    operator_type: OperatorType = Field(OperatorType.JOIN, frozen=True)


class SwitchOperator(BaseOperator):
    """Phase 4: Multi-branch switch/case operator."""

    switch_on: str = Field(..., description="Expression to evaluate for switch")
    cases: dict[str, str] = Field(
        default_factory=dict, description="Map of case values to task IDs"
    )
    default: str | None = Field(None, description="Default task ID if no case matches")
    operator_type: OperatorType = Field(OperatorType.SWITCH, frozen=True)


class ReflexiveOperator(BaseOperator):
    """Issue #331: Reflexive Loop operator (Sherlock pattern).

    Implements the Reflexive Loop pattern from Sherlock paper (arXiv:2511.00330):
    Generate -> Verify -> Self-correct within a single atomic step.

    This operator serializes to an ActivityOperator using tools.agent.reflexive_loop,
    ensuring the retry loop happens outside the DB transaction to prevent
    connection exhaustion.

    Example:
        builder.reflexive(
            task_id="gen_code",
            generator="tools.llm.call",
            generator_kwargs={
                "provider": "ollama",
                "model": "deepseek-v3.1:671b-cloud",
                "prompt": "Write fibonacci in Python",
            },
            verifier="tools.python.run",
            max_turns=3,
        )
    """

    generator: str = Field(
        ..., description="Generator tool name (e.g., tools.llm.call)"
    )
    generator_kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Arguments for generator tool"
    )
    verifier: str = Field(
        ..., description="Verifier tool name (e.g., tools.python.run)"
    )
    verifier_kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Arguments for verifier tool"
    )
    max_turns: int = Field(3, description="Maximum correction attempts", ge=1, le=10)
    correction_prompt_template: str | None = Field(
        None, description="Custom template for correction prompts"
    )
    operator_type: OperatorType = Field(OperatorType.REFLEXIVE, frozen=True)


class Workflow(BaseModel):
    name: str
    version: str = "2.0.0"
    description: str = ""
    tasks: dict[
        str,
        TaskOperator
        | ActivityOperator
        | ConditionOperator
        | WaitOperator
        | ParallelOperator
        | ForEachOperator
        | WhileOperator
        | EmitEventOperator
        | WaitForEventOperator
        | SwitchOperator
        | JoinOperator
        | ReflexiveOperator,
    ] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    start_task: str | None = None

    # Phase 1: Scheduling metadata
    schedule: str | None = Field(
        None, description="Cron expression for scheduled execution"
    )
    start_date: datetime | None = Field(
        None, description="When the schedule becomes active"
    )
    catchup: bool = Field(False, description="Whether to backfill missed runs")
    is_paused: bool = Field(False, description="Whether the workflow is paused")
    tags: list[str] = Field(
        default_factory=list, description="Workflow categorization tags"
    )
    max_active_runs: int = Field(1, description="Maximum number of concurrent runs")
    default_retry_policy: RetryPolicy | None = Field(
        None, description="Default retry policy for all tasks"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_workflow_name_and_version(cls, data: Any) -> Any:
        """Validate workflow name and version don't contain '__' (double underscore).

        The double underscore is reserved as a separator for display purposes:
        {workflow_name}__{version}__{step_name}

        Workflow names must match: ^[a-z][a-z0-9_]*$ (lowercase, alphanumeric, single underscore)
        Workflow versions must match: ^[a-zA-Z0-9._-]+$ (semver compatible)
        """
        if isinstance(data, dict):
            name = data.get("name", "")
            version = data.get("version", "")

            # Check for double underscore (reserved separator)
            if "__" in name:
                msg = f"Workflow name '{name}' cannot contain '__' (double underscore) - it's reserved as a separator"
                raise ValueError(msg)

            if "__" in version:
                msg = f"Workflow version '{version}' cannot contain '__' (double underscore) - it's reserved as a separator"
                raise ValueError(msg)

            # Validate workflow name format
            if name and not re.match(r"^[a-z][a-z0-9_]*$", name):
                msg = f"Workflow name '{name}' must start with lowercase letter and contain only lowercase letters, digits, and single underscores"
                raise ValueError(msg)

            # Validate workflow version format (semver compatible)
            if version and not re.match(r"^[a-zA-Z0-9._-]+$", version):
                msg = f"Workflow version '{version}' must contain only alphanumeric characters, dots, hyphens, and underscores (semver compatible)"
                raise ValueError(msg)

        return data

    @model_validator(mode="before")
    @classmethod
    def validate_tasks(cls, data: Any) -> Any:
        if isinstance(data, dict) and "tasks" in data:
            validated_tasks = {}
            operator_classes: dict[str, type[BaseOperator]] = {
                OperatorType.TASK.value: TaskOperator,
                OperatorType.ACTIVITY.value: ActivityOperator,
                OperatorType.CONDITION.value: ConditionOperator,
                OperatorType.WAIT.value: WaitOperator,
                OperatorType.PARALLEL.value: ParallelOperator,
                OperatorType.FOREACH.value: ForEachOperator,
                OperatorType.WHILE.value: WhileOperator,
                OperatorType.EMIT_EVENT.value: EmitEventOperator,
                OperatorType.WAIT_FOR_EVENT.value: WaitForEventOperator,
                OperatorType.SWITCH.value: SwitchOperator,
                OperatorType.JOIN.value: JoinOperator,
                OperatorType.REFLEXIVE.value: ReflexiveOperator,
            }
            for task_id, task_data in data["tasks"].items():
                if isinstance(task_data, BaseOperator):
                    validated_tasks[task_id] = task_data
                    continue

                operator_type = task_data.get("operator_type")
                if operator_type and operator_type in operator_classes:
                    operator_class = operator_classes[operator_type]
                    validated_tasks[task_id] = operator_class.model_validate(task_data)
                else:
                    msg = f"Unknown operator type: {operator_type}"
                    raise ValueError(msg)
            data["tasks"] = validated_tasks
        return data

    def add_task(
        self,
        task: (
            TaskOperator
            | ActivityOperator
            | ConditionOperator
            | WaitOperator
            | ParallelOperator
            | ForEachOperator
            | WhileOperator
            | EmitEventOperator
            | WaitForEventOperator
            | SwitchOperator
            | JoinOperator
            | ReflexiveOperator
        ),
    ) -> "Workflow":
        self.tasks[task.task_id] = task
        return self

    def set_variables(self, variables: dict[str, Any]) -> "Workflow":
        self.variables.update(variables)
        return self

    def set_start_task(self, task_id: str) -> "Workflow":
        self.start_task = task_id
        return self

    # Phase 1: Scheduling methods
    def set_schedule(self, cron: str) -> "Workflow":
        """Set the cron schedule for this workflow."""
        self.schedule = cron
        return self

    def set_start_date(self, start_date: datetime) -> "Workflow":
        """Set when the schedule becomes active."""
        self.start_date = start_date
        return self

    def set_catchup(self, enabled: bool) -> "Workflow":
        """Set whether to backfill missed runs."""
        self.catchup = enabled
        return self

    def set_paused(self, paused: bool) -> "Workflow":
        """Set whether the workflow is paused."""
        self.is_paused = paused
        return self

    def add_tags(self, *tags: str) -> "Workflow":
        """Add tags to the workflow."""
        self.tags.extend(tags)
        return self

    def set_max_active_runs(self, count: int) -> "Workflow":
        """Set maximum number of concurrent runs."""
        self.max_active_runs = count
        return self

    def set_default_retry_policy(self, policy: RetryPolicy) -> "Workflow":
        """Set default retry policy for all tasks."""
        self.default_retry_policy = policy
        return self

    def to_yaml(self) -> str:
        data = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        return yaml.dump(data, default_flow_style=False)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_mermaid(self) -> str:
        """Convert workflow to Mermaid stateDiagram-v2 format.

        Uses the robust DiagramGenerator to handle nested structures,
        parallel branches, and all operator types correctly.
        """
        # Local import to avoid circular dependency
        from highway_dsl.diagrams import DiagramGenerator

        generator = DiagramGenerator(self)
        return generator.to_mermaid()

    def to_graphviz(self) -> str:
        """Convert workflow to Graphviz DOT format.

        Uses the robust DiagramGenerator to handle nested structures,
        parallel branches, and all operator types correctly.
        """
        # Local import to avoid circular dependency
        from highway_dsl.diagrams import DiagramGenerator

        generator = DiagramGenerator(self)
        return generator.to_graphviz()

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "Workflow":
        data = yaml.safe_load(yaml_str)
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Workflow":
        return cls.model_validate_json(json_str)


class WorkflowBuilder:
    def __init__(
        self,
        name: str,
        version: str = "2.0.0",
        existing_workflow: Workflow | None = None,
        parent: Optional["WorkflowBuilder"] = None,
    ) -> None:
        if existing_workflow:
            self.workflow = existing_workflow
        else:
            self.workflow = Workflow(
                name=name,
                version=version,
                description="",
                tasks={},
                variables={},
                start_task=None,
                schedule=None,
                start_date=None,
                catchup=False,
                is_paused=False,
                tags=[],
                max_active_runs=1,
                default_retry_policy=None,
            )
        self._current_task: str | None = None
        self.parent = parent

    def _add_task(
        self,
        task: (
            TaskOperator
            | ActivityOperator
            | ConditionOperator
            | WaitOperator
            | ParallelOperator
            | ForEachOperator
            | WhileOperator
            | EmitEventOperator
            | WaitForEventOperator
            | SwitchOperator
            | JoinOperator
            | ReflexiveOperator
        ),
        **kwargs: Any,
    ) -> None:
        dependencies = kwargs.get("dependencies", [])

        # Check if this task is intended to be a handler for another task
        # This can be determined by looking at whether any existing tasks
        # reference this task as their on_failure_task_id or on_success_task_id
        is_handler_task = False
        for other_task in self.workflow.tasks.values():
            # Check if any existing task has this task as its handler
            if (
                hasattr(other_task, "on_failure_task_id")
                and other_task.on_failure_task_id == task.task_id
            ) or (
                hasattr(other_task, "on_success_task_id")
                and other_task.on_success_task_id == task.task_id
            ):
                is_handler_task = True
                break

        # Only add the current task as dependency if:
        # 1. There IS a current task (not the first task)
        # 2. No explicit dependencies were provided
        # 3. This is NOT a handler task
        if self._current_task and not dependencies and not is_handler_task:
            dependencies.append(self._current_task)

        task.dependencies = sorted(set(dependencies))

        self.workflow.add_task(task)
        self._current_task = task.task_id

    def task(self, task_id: str, function: str, **kwargs: Any) -> "WorkflowBuilder":
        # Extract args and kwargs if provided, otherwise treat remaining kwargs as task params
        args = kwargs.pop("args", [])
        task_kwargs = kwargs.pop("kwargs", {})

        # Support depends_on as alias for dependencies
        if "depends_on" in kwargs and "dependencies" not in kwargs:
            kwargs["dependencies"] = kwargs.pop("depends_on")
        elif "depends_on" in kwargs:
            kwargs.pop(
                "depends_on"
            )  # Remove if both specified (dependencies takes precedence)

        # Operator configuration fields
        operator_fields = {
            "dependencies",
            "retry_policy",
            "timeout_policy",
            "circuit_breaker_policy",
            "idempotency_key",
            "metadata",
            "description",
            "result_key",
            "on_success_task_id",
            "on_failure_task_id",
            "trigger_rule",
        }

        # Separate operator config from task params
        operator_config = {k: v for k, v in kwargs.items() if k in operator_fields}
        task_params = {k: v for k, v in kwargs.items() if k not in operator_fields}

        # Merge task params into kwargs (task execution parameters)
        task_kwargs.update(task_params)

        task = TaskOperator(
            task_id=task_id,
            function=function,
            args=args,
            kwargs=task_kwargs,
            **operator_config,
        )
        self._add_task(task, **kwargs)
        return self

    def activity(self, task_id: str, function: str, **kwargs: Any) -> "WorkflowBuilder":
        """Add a long-running activity task that executes outside workflow transaction."""
        # Extract args and kwargs if provided
        args = kwargs.pop("args", [])
        task_kwargs = kwargs.pop("kwargs", {})

        # Support depends_on as alias for dependencies
        if "depends_on" in kwargs and "dependencies" not in kwargs:
            kwargs["dependencies"] = kwargs.pop("depends_on")
        elif "depends_on" in kwargs:
            kwargs.pop("depends_on")

        # Operator configuration fields
        operator_fields = {
            "dependencies",
            "retry_policy",
            "timeout_policy",
            "circuit_breaker_policy",
            "idempotency_key",
            "metadata",
            "description",
            "result_key",
            "on_success_task_id",
            "on_failure_task_id",
            "trigger_rule",
        }

        # Separate operator config from task params
        operator_config = {k: v for k, v in kwargs.items() if k in operator_fields}
        task_params = {k: v for k, v in kwargs.items() if k not in operator_fields}

        # Merge task params into kwargs (task execution parameters)
        task_kwargs.update(task_params)

        task = ActivityOperator(
            task_id=task_id,
            function=function,
            args=args,
            kwargs=task_kwargs,
            **operator_config,
        )
        self._add_task(task, **kwargs)
        return self

    def reflexive(
        self,
        task_id: str,
        generator: str,
        verifier: str,
        generator_kwargs: dict[str, Any] | None = None,
        verifier_kwargs: dict[str, Any] | None = None,
        max_turns: int = 3,
        correction_prompt_template: str | None = None,
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        """Add a reflexive loop task (Issue #331 - Sherlock pattern).

        Implements the Reflexive Loop pattern from Sherlock paper (arXiv:2511.00330):
        Generate -> Verify -> Self-correct within a single atomic step.

        IMPORTANT: This task MUST execute as an Activity (outside DB transaction)
        to prevent database connection exhaustion during the retry loop.

        Args:
            task_id: Unique identifier for this task
            generator: Generator tool name (e.g., "tools.llm.call")
            verifier: Verifier tool name (e.g., "tools.python.run")
            generator_kwargs: Arguments for generator tool
            verifier_kwargs: Arguments for verifier tool
            max_turns: Maximum correction attempts (1-10, default: 3)
            correction_prompt_template: Custom template for correction prompts
            **kwargs: Additional operator config (dependencies, retry_policy, etc.)

        Returns:
            Self for method chaining

        Example:
            builder.reflexive(
                task_id="gen_code",
                generator="tools.llm.call",
                generator_kwargs={
                    "provider": "ollama",
                    "model": "deepseek-v3.1:671b-cloud",
                    "prompt": "Write fibonacci in Python",
                },
                verifier="tools.python.run",
                max_turns=3,
            )
        """
        # Operator configuration fields
        operator_fields = {
            "dependencies",
            "retry_policy",
            "timeout_policy",
            "circuit_breaker_policy",
            "idempotency_key",
            "metadata",
            "description",
            "result_key",
            "on_success_task_id",
            "on_failure_task_id",
            "trigger_rule",
        }

        # Separate operator config from other params
        operator_config = {k: v for k, v in kwargs.items() if k in operator_fields}

        task = ReflexiveOperator(
            task_id=task_id,
            generator=generator,
            generator_kwargs=generator_kwargs or {},
            verifier=verifier,
            verifier_kwargs=verifier_kwargs or {},
            max_turns=max_turns,
            correction_prompt_template=correction_prompt_template,
            **operator_config,
        )
        self._add_task(task, **kwargs)
        return self

    def condition(
        self,
        task_id: str,
        condition: str,
        if_true: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        if_false: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        true_builder = if_true(WorkflowBuilder(f"{task_id}_true", parent=self))
        false_builder = if_false(WorkflowBuilder(f"{task_id}_false", parent=self))

        true_tasks = list(true_builder.workflow.tasks.keys())
        false_tasks = list(false_builder.workflow.tasks.keys())

        task = ConditionOperator(
            task_id=task_id,
            condition=condition,
            if_true=true_tasks[0] if true_tasks else None,
            if_false=false_tasks[0] if false_tasks else None,
            **kwargs,
        )

        self._add_task(task, **kwargs)

        for task_obj in true_builder.workflow.tasks.values():
            # Only add the condition task as dependency, preserve original dependencies
            if task_id not in task_obj.dependencies:
                task_obj.dependencies.append(task_id)
            self.workflow.add_task(task_obj)
        for task_obj in false_builder.workflow.tasks.values():
            # Only add the condition task as dependency, preserve original dependencies
            if task_id not in task_obj.dependencies:
                task_obj.dependencies.append(task_id)
            self.workflow.add_task(task_obj)

        self._current_task = task_id
        return self

    def wait(
        self,
        task_id: str,
        wait_for: timedelta | datetime | str,
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        task = WaitOperator(task_id=task_id, wait_for=wait_for, **kwargs)
        self._add_task(task, **kwargs)
        return self

    def parallel(
        self,
        task_id: str,
        branches: dict[str, Callable[["WorkflowBuilder"], "WorkflowBuilder"]],
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        branch_builders = {}
        for name, branch_func in branches.items():
            # Normalize branch name to lowercase for sub-workflow name validation
            normalized_name = name.lower()
            branch_builder = branch_func(
                WorkflowBuilder(f"{task_id}_{normalized_name}", parent=self),
            )
            branch_builders[name] = branch_builder

        branch_tasks = {
            name: list(builder.workflow.tasks.keys())
            for name, builder in branch_builders.items()
        }

        # Serialize complete branch workflows for execution
        branch_workflows = {
            name: builder.workflow.model_dump(mode="json")
            for name, builder in branch_builders.items()
        }

        task = ParallelOperator(
            task_id=task_id,
            branches=branch_tasks,
            branch_workflows=branch_workflows,
            **kwargs,
        )

        self._add_task(task, **kwargs)

        # NOTE: After Nov 16 2025 fork-only fix, branch tasks are NOT added to parent workflow
        # Branch tasks only execute inside spawned branch workflows via tools.workflow.execute_branch
        # This prevents double execution (once in parent, once in branch)

        self._current_task = task_id
        return self

    def parallel_with_join(
        self,
        task_id: str,
        branches: dict[str, Callable[["WorkflowBuilder"], "WorkflowBuilder"]],
        timeout_seconds: int = 300,
        join_result_key: str | None = None,
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        """Fork/join parallel execution with automatic join barrier (#408).

        This is a developer-friendly wrapper around parallel() that automatically
        adds the wait_for_parallel_branches task to rejoin all branches.

        The pattern:
            parallel_with_join("my_parallel", branches={...})

        Is equivalent to:
            parallel("my_parallel", branches={...}, result_key="my_parallel_data")
            task("my_parallel_join", "tools.workflow.wait_for_parallel_branches",
                 args=["{{my_parallel_data}}"], kwargs={"timeout_seconds": 300},
                 dependencies=["my_parallel"])

        Args:
            task_id: Unique identifier for the parallel group
            branches: Dictionary of branch_name -> builder function
            timeout_seconds: Timeout for waiting on branches (default: 5 minutes)
            join_result_key: Key to store joined results (default: {task_id}_results)
            **kwargs: Additional arguments for ParallelOperator

        Returns:
            WorkflowBuilder for chaining (current task is the join task)

        Example:
            builder.parallel_with_join(
                "data_processing",
                branches={
                    "process_users": lambda b: b.task(...),
                    "process_orders": lambda b: b.task(...),
                },
                timeout_seconds=120,
            ).task(
                "aggregate",  # Automatically depends on join task
                "tools.python.run",
                args=["aggregate_results"],
            )
        """
        # Set result_key for the parallel operator to capture fork metadata
        fork_result_key = f"{task_id}_fork_data"
        kwargs["result_key"] = fork_result_key

        # Create the parallel (fork) task
        self.parallel(task_id, branches, **kwargs)

        # Automatically add the join task
        join_task_id = f"{task_id}_join"
        join_result = join_result_key or f"{task_id}_results"

        self.task(
            join_task_id,
            "tools.workflow.wait_for_parallel_branches",
            args=[f"{{{{{fork_result_key}}}}}"],  # Template: {{fork_result_key}}
            kwargs={"timeout_seconds": timeout_seconds},
            dependencies=[task_id],
            result_key=join_result,
        )

        return self

    def foreach(
        self,
        task_id: str,
        items: str,
        loop_body: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        # Create a temporary builder for the loop body.
        temp_builder = WorkflowBuilder(f"{task_id}_loop", parent=self)
        loop_builder = loop_body(temp_builder)
        loop_tasks = list(loop_builder.workflow.tasks.values())

        # Mark all loop body tasks as internal to prevent parallel dependency injection
        for task_obj in loop_tasks:
            task_obj.is_internal_loop_task = True

        # Create the foreach operator
        task = ForEachOperator(
            task_id=task_id,
            items=items,
            loop_body=loop_tasks,
            **kwargs,
        )

        # Add the foreach task to workflow to establish initial dependencies
        self._add_task(task, **kwargs)

        # Add the foreach task as dependency to the FIRST task in the loop body
        # and preserve the original dependency chain within the loop
        if loop_tasks:
            first_task = loop_tasks[0]
            if task_id not in first_task.dependencies:
                first_task.dependencies.append(task_id)

            # Add all loop tasks to workflow
            for task_obj in loop_tasks:
                self.workflow.add_task(task_obj)

        self._current_task = task_id
        return self

    def while_loop(
        self,
        task_id: str,
        condition: str,
        loop_body: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        loop_builder = loop_body(WorkflowBuilder(f"{task_id}_loop", parent=self))
        loop_tasks = list(loop_builder.workflow.tasks.values())

        # Mark all loop body tasks as internal to prevent parallel dependency injection
        for task_obj in loop_tasks:
            task_obj.is_internal_loop_task = True

        task = WhileOperator(
            task_id=task_id,
            condition=condition,
            loop_body=loop_tasks,
            **kwargs,
        )

        self._add_task(task, **kwargs)

        # Fix: Only add the while task as dependency to the FIRST task in the loop body
        # and preserve the original dependency chain within the loop
        if loop_tasks:
            first_task = loop_tasks[0]
            if task_id not in first_task.dependencies:
                first_task.dependencies.append(task_id)

            # Add all loop tasks to workflow without modifying their dependencies further
            for task_obj in loop_tasks:
                self.workflow.add_task(task_obj)

        self._current_task = task_id
        return self

    def retry(
        self,
        max_retries: int = 3,
        delay: timedelta = timedelta(seconds=5),
        backoff_factor: float = 2.0,
    ) -> "WorkflowBuilder":
        if self._current_task and isinstance(
            self.workflow.tasks[self._current_task],
            TaskOperator,
        ):
            self.workflow.tasks[self._current_task].retry_policy = RetryPolicy(
                max_retries=max_retries,
                delay=delay,
                backoff_factor=backoff_factor,
            )
        return self

    def timeout(
        self,
        timeout: timedelta,
        kill_on_timeout: bool = True,
    ) -> "WorkflowBuilder":
        if self._current_task and isinstance(
            self.workflow.tasks[self._current_task],
            TaskOperator,
        ):
            self.workflow.tasks[self._current_task].timeout_policy = TimeoutPolicy(
                timeout=timeout,
                kill_on_timeout=kill_on_timeout,
            )
        return self

    # Phase 2: Event-based operators
    def emit_event(
        self, task_id: str, event_name: str, **kwargs: Any
    ) -> "WorkflowBuilder":
        """Emit an event that other workflows can wait for."""
        task = EmitEventOperator(task_id=task_id, event_name=event_name, **kwargs)
        self._add_task(task, **kwargs)
        return self

    def join(
        self, task_id: str, join_tasks: list[str], join_mode: JoinMode, **kwargs: Any
    ) -> "WorkflowBuilder":
        """Create a JoinOperator to coordinate multiple branches.

        Args:
            task_id: Unique task identifier
            join_tasks: List of task IDs to wait for
            join_mode: JoinMode (ALL_OF, ANY_OF, ALL_SUCCESS, ONE_SUCCESS)
            **kwargs: Additional arguments (dependencies, etc.)

        Returns:
            WorkflowBuilder for chaining
        """
        task = JoinOperator(
            task_id=task_id, join_tasks=join_tasks, join_mode=join_mode, **kwargs
        )
        self._add_task(task, **kwargs)
        return self

    def wait_for_event(
        self,
        task_id: str,
        event_name: str,
        timeout_seconds: int | None = None,
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        """Wait for an external event with optional timeout."""
        task = WaitForEventOperator(
            task_id=task_id,
            event_name=event_name,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )
        self._add_task(task, **kwargs)
        return self

    # Phase 3: Callback hooks (applies to current task)
    def on_success(self, success_task_id: str) -> "WorkflowBuilder":
        """Set the task to run when the current task succeeds."""
        if self._current_task:
            self.workflow.tasks[self._current_task].on_success_task_id = success_task_id
        return self

    def on_failure(self, failure_task_id: str) -> "WorkflowBuilder":
        """Set the task to run when the current task fails."""
        if self._current_task:
            self.workflow.tasks[self._current_task].on_failure_task_id = failure_task_id
        return self

    # Phase 4: Switch operator
    def switch(
        self,
        task_id: str,
        switch_on: str,
        cases: dict[str, str],
        default: str | None = None,
        **kwargs: Any,
    ) -> "WorkflowBuilder":
        """Multi-branch switch/case operator."""
        task = SwitchOperator(
            task_id=task_id,
            switch_on=switch_on,
            cases=cases,
            default=default,
            **kwargs,
        )
        self._add_task(task, **kwargs)
        return self

    # Workflow metadata methods
    def set_description(self, description: str) -> "WorkflowBuilder":
        """Set the workflow description."""
        self.workflow.description = description
        return self

    def set_version(self, version: str) -> "WorkflowBuilder":
        """Set the workflow version."""
        self.workflow.version = version
        return self

    # Phase 1: Scheduling methods (delegate to Workflow)
    def set_schedule(self, cron: str) -> "WorkflowBuilder":
        """Set the cron schedule for this workflow."""
        self.workflow.set_schedule(cron)
        return self

    def set_start_date(self, start_date: datetime) -> "WorkflowBuilder":
        """Set when the schedule becomes active."""
        self.workflow.set_start_date(start_date)
        return self

    def set_catchup(self, enabled: bool) -> "WorkflowBuilder":
        """Set whether to backfill missed runs."""
        self.workflow.set_catchup(enabled)
        return self

    def set_paused(self, paused: bool) -> "WorkflowBuilder":
        """Set whether the workflow is paused."""
        self.workflow.set_paused(paused)
        return self

    def add_tags(self, *tags: str) -> "WorkflowBuilder":
        """Add tags to the workflow."""
        self.workflow.add_tags(*tags)
        return self

    def set_max_active_runs(self, count: int) -> "WorkflowBuilder":
        """Set maximum number of concurrent runs."""
        self.workflow.set_max_active_runs(count)
        return self

    def set_default_retry_policy(self, policy: RetryPolicy) -> "WorkflowBuilder":
        """Set default retry policy for all tasks."""
        self.workflow.set_default_retry_policy(policy)
        return self

    def build(self) -> Workflow:
        """Build and validate the workflow.

        Validates:
        - Callback task references (on_success/on_failure)
        - Dependency references
        - Start task is set

        Returns:
            Validated workflow

        Raises:
            ValueError: If validation fails
        """
        # Validate callback references
        for task_id, task in self.workflow.tasks.items():
            if (
                task.on_success_task_id
                and task.on_success_task_id not in self.workflow.tasks
            ):
                raise ValueError(
                    f"Task '{task_id}' references non-existent on_success task "
                    f"'{task.on_success_task_id}'"
                )
            if (
                task.on_failure_task_id
                and task.on_failure_task_id not in self.workflow.tasks
            ):
                raise ValueError(
                    f"Task '{task_id}' references non-existent on_failure task "
                    f"'{task.on_failure_task_id}'"
                )

        # Set start task if not explicitly set
        if not self.workflow.start_task and self.workflow.tasks:
            self.workflow.start_task = next(iter(self.workflow.tasks.keys()))

        return self.workflow
