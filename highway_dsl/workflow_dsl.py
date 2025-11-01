# workflow_dsl.py
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum
from datetime import datetime, timedelta
import yaml
import json
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, model_validator, ConfigDict


class OperatorType(Enum):
    TASK = "task"
    CONDITION = "condition"
    WAIT = "wait"
    PARALLEL = "parallel"
    FOREACH = "foreach"
    SWITCH = "switch"
    TRY_CATCH = "try_catch"
    WHILE = "while"


class RetryPolicy(BaseModel):
    max_retries: int = Field(3, description="Maximum number of retries")
    delay: timedelta = Field(timedelta(seconds=5), description="Delay between retries")
    backoff_factor: float = Field(2.0, description="Factor by which to increase delay")


class TimeoutPolicy(BaseModel):
    timeout: timedelta = Field(..., description="Timeout duration")
    kill_on_timeout: bool = Field(
        True, description="Whether to kill the task on timeout"
    )


class BaseOperator(BaseModel, ABC):
    task_id: str
    operator_type: OperatorType
    dependencies: List[str] = Field(default_factory=list)
    retry_policy: Optional[RetryPolicy] = None
    timeout_policy: Optional[TimeoutPolicy] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_internal_loop_task: bool = Field(
        default=False, exclude=True
    )  # Mark if task is internal to a loop

    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class TaskOperator(BaseOperator):
    function: str
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    result_key: Optional[str] = None
    operator_type: OperatorType = Field(OperatorType.TASK, frozen=True)


class ConditionOperator(BaseOperator):
    condition: str
    if_true: Optional[str]
    if_false: Optional[str]
    operator_type: OperatorType = Field(OperatorType.CONDITION, frozen=True)


class WaitOperator(BaseOperator):
    wait_for: Union[timedelta, datetime, str]
    operator_type: OperatorType = Field(OperatorType.WAIT, frozen=True)

    @model_validator(mode="before")
    @classmethod
    def parse_wait_for(cls, data: Any) -> Any:
        if isinstance(data, dict) and "wait_for" in data:
            wait_for = data["wait_for"]
            if isinstance(wait_for, str):
                if wait_for.startswith("duration:"):
                    data["wait_for"] = timedelta(seconds=float(wait_for.split(":")[1]))
                elif wait_for.startswith("datetime:"):
                    data["wait_for"] = datetime.fromisoformat(wait_for.split(":", 1)[1])
        return data

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        wait_for = data["wait_for"]
        if isinstance(wait_for, timedelta):
            data["wait_for"] = f"duration:{wait_for.total_seconds()}"
        elif isinstance(wait_for, datetime):
            data["wait_for"] = f"datetime:{wait_for.isoformat()}"
        return data


class ParallelOperator(BaseOperator):
    branches: Dict[str, List[str]] = Field(default_factory=dict)
    operator_type: OperatorType = Field(OperatorType.PARALLEL, frozen=True)


class ForEachOperator(BaseOperator):
    items: str
    loop_body: List[
        Union[
            TaskOperator,
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            "ForEachOperator",
            "WhileOperator",
        ]
    ] = Field(default_factory=list)
    operator_type: OperatorType = Field(OperatorType.FOREACH, frozen=True)


class WhileOperator(BaseOperator):
    condition: str
    loop_body: List[
        Union[
            TaskOperator,
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            ForEachOperator,
            "WhileOperator",
        ]
    ] = Field(default_factory=list)
    operator_type: OperatorType = Field(OperatorType.WHILE, frozen=True)


class Workflow(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    tasks: Dict[
        str,
        Union[
            TaskOperator,
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            ForEachOperator,
            WhileOperator,
        ],
    ] = Field(default_factory=dict)
    variables: Dict[str, Any] = Field(default_factory=dict)
    start_task: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def validate_tasks(cls, data: Any) -> Any:
        if isinstance(data, dict) and "tasks" in data:
            validated_tasks = {}
            operator_classes: Dict[str, Type[BaseOperator]] = {
                OperatorType.TASK.value: TaskOperator,
                OperatorType.CONDITION.value: ConditionOperator,
                OperatorType.WAIT.value: WaitOperator,
                OperatorType.PARALLEL.value: ParallelOperator,
                OperatorType.FOREACH.value: ForEachOperator,
                OperatorType.WHILE.value: WhileOperator,
            }
            for task_id, task_data in data["tasks"].items():
                operator_type = task_data.get("operator_type")
                if operator_type and operator_type in operator_classes:
                    operator_class = operator_classes[operator_type]
                    validated_tasks[task_id] = operator_class.model_validate(task_data)
                else:
                    raise ValueError(f"Unknown operator type: {operator_type}")
            data["tasks"] = validated_tasks
        return data

    def add_task(
        self,
        task: Union[
            TaskOperator,
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            ForEachOperator,
            WhileOperator,
        ],
    ) -> "Workflow":
        self.tasks[task.task_id] = task
        return self

    def set_variables(self, variables: Dict[str, Any]) -> "Workflow":
        self.variables.update(variables)
        return self

    def set_start_task(self, task_id: str) -> "Workflow":
        self.start_task = task_id
        return self

    def to_yaml(self) -> str:
        data = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        return yaml.dump(data, default_flow_style=False)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

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
        existing_workflow: Optional[Workflow] = None,
        parent: Optional["WorkflowBuilder"] = None,
    ):
        if existing_workflow:
            self.workflow = existing_workflow
        else:
            self.workflow = Workflow(name=name)
        self._current_task: Optional[str] = None
        self.parent = parent

    def _add_task(
        self,
        task: Union[
            TaskOperator,
            ConditionOperator,
            WaitOperator,
            ParallelOperator,
            ForEachOperator,
            WhileOperator,
        ],
        **kwargs,
    ) -> None:
        dependencies = kwargs.get("dependencies", [])
        if self._current_task and not dependencies:
            dependencies.append(self._current_task)

        task.dependencies = sorted(list(set(dependencies)))

        self.workflow.add_task(task)
        self._current_task = task.task_id

    def task(self, task_id: str, function: str, **kwargs) -> "WorkflowBuilder":
        task = TaskOperator(task_id=task_id, function=function, **kwargs)
        self._add_task(task, **kwargs)
        return self

    def condition(
        self,
        task_id: str,
        condition: str,
        if_true: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        if_false: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        **kwargs,
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
        self, task_id: str, wait_for: Union[timedelta, datetime, str], **kwargs
    ) -> "WorkflowBuilder":
        task = WaitOperator(task_id=task_id, wait_for=wait_for, **kwargs)
        self._add_task(task, **kwargs)
        return self

    def parallel(
        self,
        task_id: str,
        branches: Dict[str, Callable[["WorkflowBuilder"], "WorkflowBuilder"]],
        **kwargs,
    ) -> "WorkflowBuilder":
        branch_builders = {}
        for name, branch_func in branches.items():
            branch_builder = branch_func(
                WorkflowBuilder(f"{task_id}_{name}", parent=self)
            )
            branch_builders[name] = branch_builder

        branch_tasks = {
            name: list(builder.workflow.tasks.keys())
            for name, builder in branch_builders.items()
        }

        task = ParallelOperator(task_id=task_id, branches=branch_tasks, **kwargs)

        self._add_task(task, **kwargs)

        for builder in branch_builders.values():
            for task_obj in builder.workflow.tasks.values():
                # Only add the parallel task as dependency to non-internal tasks,
                # preserve original dependencies
                if (
                    not getattr(task_obj, "is_internal_loop_task", False)
                    and task_id not in task_obj.dependencies
                ):
                    task_obj.dependencies.append(task_id)
                self.workflow.add_task(task_obj)

        self._current_task = task_id
        return self

    def foreach(
        self,
        task_id: str,
        items: str,
        loop_body: Callable[["WorkflowBuilder"], "WorkflowBuilder"],
        **kwargs,
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
        **kwargs,
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
            self.workflow.tasks[self._current_task], TaskOperator
        ):
            self.workflow.tasks[self._current_task].retry_policy = RetryPolicy(
                max_retries=max_retries, delay=delay, backoff_factor=backoff_factor
            )
        return self

    def timeout(
        self, timeout: timedelta, kill_on_timeout: bool = True
    ) -> "WorkflowBuilder":
        if self._current_task and isinstance(
            self.workflow.tasks[self._current_task], TaskOperator
        ):
            self.workflow.tasks[self._current_task].timeout_policy = TimeoutPolicy(
                timeout=timeout, kill_on_timeout=kill_on_timeout
            )
        return self

    def build(self) -> Workflow:
        if not self.workflow.start_task and self.workflow.tasks:
            self.workflow.start_task = next(iter(self.workflow.tasks.keys()))
        return self.workflow
