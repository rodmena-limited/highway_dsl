# workflow_dsl.py
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum
from datetime import datetime, timedelta
import yaml
import json
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


class OperatorType(Enum):
    TASK = "task"
    CONDITION = "condition"
    WAIT = "wait"
    PARALLEL = "parallel"
    FOREACH = "foreach"
    SWITCH = "switch"
    TRY_CATCH = "try_catch"


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        delay: timedelta = timedelta(seconds=5),
        backoff_factor: float = 2.0,
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff_factor = backoff_factor


class TimeoutPolicy:
    def __init__(self, timeout: timedelta, kill_on_timeout: bool = True):
        self.timeout = timeout
        self.kill_on_timeout = kill_on_timeout


@dataclass
class BaseOperator(ABC):
    task_id: str
    operator_type: OperatorType
    dependencies: List[str] = field(default_factory=list)
    retry_policy: Optional[RetryPolicy] = None
    timeout_policy: Optional[TimeoutPolicy] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseOperator":
        pass


@dataclass
class TaskOperator(BaseOperator):
    function: str = None
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    result_key: Optional[str] = None

    def __init__(
        self,
        task_id: str,
        function: str,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        result_key: Optional[str] = None,
        dependencies: List[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
        timeout_policy: Optional[TimeoutPolicy] = None,
        metadata: Dict[str, Any] = None,
    ):
        super().__init__(
            task_id=task_id,
            operator_type=OperatorType.TASK,
            dependencies=dependencies or [],
            retry_policy=retry_policy,
            timeout_policy=timeout_policy,
            metadata=metadata or {},
        )
        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}
        self.result_key = result_key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operator_type": self.operator_type.value,
            "function": self.function,
            "args": self.args,
            "kwargs": self.kwargs,
            "result_key": self.result_key,
            "dependencies": self.dependencies,
            "retry_policy": {
                "max_retries": self.retry_policy.max_retries,
                "delay": self.retry_policy.delay.total_seconds(),
                "backoff_factor": self.retry_policy.backoff_factor,
            }
            if self.retry_policy
            else None,
            "timeout_policy": {
                "timeout": self.timeout_policy.timeout.total_seconds(),
                "kill_on_timeout": self.timeout_policy.kill_on_timeout,
            }
            if self.timeout_policy
            else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskOperator":
        retry_policy = None
        timeout_policy = None

        if data.get("retry_policy"):
            retry_policy = RetryPolicy(
                max_retries=data["retry_policy"]["max_retries"],
                delay=timedelta(seconds=data["retry_policy"]["delay"]),
                backoff_factor=data["retry_policy"]["backoff_factor"],
            )

        if data.get("timeout_policy"):
            timeout_policy = TimeoutPolicy(
                timeout=timedelta(seconds=data["timeout_policy"]["timeout"]),
                kill_on_timeout=data["timeout_policy"]["kill_on_timeout"],
            )

        return cls(
            task_id=data["task_id"],
            function=data["function"],
            args=data.get("args", []),
            kwargs=data.get("kwargs", {}),
            result_key=data.get("result_key"),
            dependencies=data.get("dependencies", []),
            retry_policy=retry_policy,
            timeout_policy=timeout_policy,
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConditionOperator(BaseOperator):
    condition: str = None
    if_true: str = None
    if_false: str = None

    def __init__(
        self,
        task_id: str,
        condition: str,
        if_true: str,
        if_false: str,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None,
    ):
        super().__init__(
            task_id=task_id,
            operator_type=OperatorType.CONDITION,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operator_type": self.operator_type.value,
            "condition": self.condition,
            "if_true": self.if_true,
            "if_false": self.if_false,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConditionOperator":
        return cls(
            task_id=data["task_id"],
            condition=data["condition"],
            if_true=data["if_true"],
            if_false=data["if_false"],
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WaitOperator(BaseOperator):
    wait_for: Union[timedelta, datetime, str] = None

    def __init__(
        self,
        task_id: str,
        wait_for: Union[timedelta, datetime, str],
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None,
    ):
        super().__init__(
            task_id=task_id,
            operator_type=OperatorType.WAIT,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self.wait_for = wait_for

    def to_dict(self) -> Dict[str, Any]:
        wait_for = self.wait_for
        if isinstance(wait_for, timedelta):
            wait_for = f"duration:{wait_for.total_seconds()}"
        elif isinstance(wait_for, datetime):
            wait_for = f"datetime:{wait_for.isoformat()}"

        return {
            "task_id": self.task_id,
            "operator_type": self.operator_type.value,
            "wait_for": wait_for,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WaitOperator":
        wait_for = data["wait_for"]
        if wait_for.startswith("duration:"):
            wait_for = timedelta(seconds=float(wait_for.split(":")[1]))
        elif wait_for.startswith("datetime:"):
            wait_for = datetime.fromisoformat(wait_for.split(":", 1)[1])

        return cls(
            task_id=data["task_id"],
            wait_for=wait_for,
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ParallelOperator(BaseOperator):
    branches: Dict[str, List[str]] = field(default_factory=dict)

    def __init__(
        self,
        task_id: str,
        branches: Dict[str, List[str]],
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None,
    ):
        super().__init__(
            task_id=task_id,
            operator_type=OperatorType.PARALLEL,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self.branches = branches

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operator_type": self.operator_type.value,
            "branches": self.branches,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParallelOperator":
        return cls(
            task_id=data["task_id"],
            branches=data["branches"],
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ForEachOperator(BaseOperator):
    items: str = None
    task_chain: List[str] = field(default_factory=list)

    def __init__(
        self,
        task_id: str,
        items: str,
        task_chain: List[str],
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None,
    ):
        super().__init__(
            task_id=task_id,
            operator_type=OperatorType.FOREACH,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        self.items = items
        self.task_chain = task_chain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "operator_type": self.operator_type.value,
            "items": self.items,
            "task_chain": self.task_chain,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForEachOperator":
        return cls(
            task_id=data["task_id"],
            items=data["items"],
            task_chain=data["task_chain"],
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


class Workflow:
    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.tasks: Dict[str, BaseOperator] = {}
        self.variables: Dict[str, Any] = {}
        self.start_task: Optional[str] = None

    def add_task(self, task: BaseOperator) -> "Workflow":
        self.tasks[task.task_id] = task
        return self

    def set_variables(self, variables: Dict[str, Any]) -> "Workflow":
        self.variables.update(variables)
        return self

    def set_start_task(self, task_id: str) -> "Workflow":
        self.start_task = task_id
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "variables": self.variables,
            "start_task": self.start_task,
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        workflow = cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
        )

        workflow.variables = data.get("variables", {})
        workflow.start_task = data.get("start_task")

        operator_classes = {
            OperatorType.TASK.value: TaskOperator,
            OperatorType.CONDITION.value: ConditionOperator,
            OperatorType.WAIT.value: WaitOperator,
            OperatorType.PARALLEL.value: ParallelOperator,
            OperatorType.FOREACH.value: ForEachOperator,
        }

        for task_id, task_data in data["tasks"].items():
            operator_class = operator_classes[task_data["operator_type"]]
            workflow.tasks[task_id] = operator_class.from_dict(task_data)

        return workflow

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "Workflow":
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Workflow":
        data = json.loads(json_str)
        return cls.from_dict(data)


class WorkflowBuilder:
    def __init__(self, name: str):
        self.workflow = Workflow(name)
        self._current_task: Optional[str] = None

    def task(self, task_id: str, function: str, **kwargs) -> "WorkflowBuilder":
        task = TaskOperator(task_id=task_id, function=function, **kwargs)
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def condition(
        self, task_id: str, condition: str, if_true: str, if_false: str
    ) -> "WorkflowBuilder":
        task = ConditionOperator(
            task_id=task_id, condition=condition, if_true=if_true, if_false=if_false
        )
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def wait(
        self, task_id: str, wait_for: Union[timedelta, datetime, str]
    ) -> "WorkflowBuilder":
        task = WaitOperator(task_id=task_id, wait_for=wait_for)
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def parallel(
        self, task_id: str, branches: Dict[str, List[str]]
    ) -> "WorkflowBuilder":
        task = ParallelOperator(task_id=task_id, branches=branches)
        if self._current_task:
            task.dependencies.append(self._current_task)
        self.workflow.add_task(task)
        self._current_task = task_id
        return self

    def foreach(
        self, task_id: str, items: str, task_chain: List[str]
    ) -> "WorkflowBuilder":
        task = ForEachOperator(task_id=task_id, items=items, task_chain=task_chain)
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
                max_retries, delay, backoff_factor
            )
        return self

    def timeout(
        self, timeout: timedelta, kill_on_timeout: bool = True
    ) -> "WorkflowBuilder":
        if self._current_task and isinstance(
            self.workflow.tasks[self._current_task], TaskOperator
        ):
            self.workflow.tasks[self._current_task].timeout_policy = TimeoutPolicy(
                timeout, kill_on_timeout
            )
        return self

    def build(self) -> Workflow:
        if not self.workflow.start_task and self.workflow.tasks:
            self.workflow.start_task = next(iter(self.workflow.tasks.keys()))
        return self.workflow
