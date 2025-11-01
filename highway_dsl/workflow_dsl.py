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

    model_config = ConfigDict(use_enum_values=True, arbitrary_types_allowed=True)


class TaskOperator(BaseOperator):
    function: str
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    result_key: Optional[str] = None
    operator_type: OperatorType = Field(OperatorType.TASK, frozen=True)


class ConditionOperator(BaseOperator):
    condition: str
    if_true: str
    if_false: str
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
    task_chain: List[str] = Field(default_factory=list)
    operator_type: OperatorType = Field(OperatorType.FOREACH, frozen=True)


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
    def __init__(self, name: str, existing_workflow: Optional[Workflow] = None):
        if existing_workflow:
            self.workflow = existing_workflow
        else:
            self.workflow = Workflow(name=name)
        self._current_task: Optional[str] = None

    def task(self, task_id: str, function: str, **kwargs) -> "WorkflowBuilder":
        task = TaskOperator(task_id=task_id, function=function, **kwargs)
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def condition(
        self, task_id: str, condition: str, if_true: str, if_false: str, **kwargs
    ) -> "WorkflowBuilder":
        task = ConditionOperator(
            task_id=task_id,
            condition=condition,
            if_true=if_true,
            if_false=if_false,
            **kwargs,
        )
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def wait(
        self, task_id: str, wait_for: Union[timedelta, datetime, str], **kwargs
    ) -> "WorkflowBuilder":
        task = WaitOperator(task_id=task_id, wait_for=wait_for, **kwargs)
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def parallel(
        self, task_id: str, branches: Dict[str, List[str]], **kwargs
    ) -> "WorkflowBuilder":
        task = ParallelOperator(task_id=task_id, branches=branches, **kwargs)
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def foreach(
        self, task_id: str, items: str, task_chain: List[str], **kwargs
    ) -> "WorkflowBuilder":
        task = ForEachOperator(
            task_id=task_id, items=items, task_chain=task_chain, **kwargs
        )
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
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
