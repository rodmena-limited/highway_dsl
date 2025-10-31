from __future__ import annotations
import uuid
from typing import Optional, Union
from datetime import datetime, timedelta, date
from pydantic import BaseModel, constr


class RepeatAfterCycle(BaseModel):
    after_cycle: int
    current_cycle: int = 0


class RepeatAfterDatetime(BaseModel):
    date_time: datetime


class RepeatAfterTime(BaseModel):
    seconds: int = 0
    minutes: int = 0
    hours: int = 0
    days: int = 0

    def get_timedelta(self):
        return timedelta(
            days=self.days, hours=self.hours, minutes=self.minutes, seconds=self.seconds
        )


class Status(BaseModel):
    """Task status

    :param repeat: define if this task should be repeated
    :type repeat: bool, RepeatAfterCycle, RepeatAfterTime, RepeatAfterDatetime
    :param message: status message
    :type message: str
    """

    repeat: Union[bool, RepeatAfterCycle, RepeatAfterTime, RepeatAfterDatetime] = None
    message: str = None
    max_reruns: int = None


class TaskExecution(BaseModel):
    name: str
    execution_time: Optional[datetime] = datetime.now()
    processed: Optional[bool] = False
    error_id: Optional[uuid.UUID] = None
    status: Status = None
    run_count: int = None

    def repeat(
        self, consider_datetime: datetime = datetime.now(), run_count: int = None
    ) -> Status:
        if self.status and (repeat := self.status.repeat):
            max_reruns = self.status.max_reruns
            if max_reruns and run_count and run_count >= max_reruns:
                return

            if type(repeat) == bool:
                return self.status
            if type(repeat) == RepeatAfterCycle:
                repeat.current_cycle += 1
                if repeat.current_cycle >= repeat.after_cycle:
                    return self.status
            elif type(repeat) == RepeatAfterTime:
                execute_after = self.execution_time - repeat.get_timedelta()
                if execute_after > consider_datetime:
                    return self.status
            elif type(repeat) == RepeatAfterDatetime:
                if consider_datetime > repeat.date_time:
                    return self.status


class WorkflowModel(BaseModel):
    """Implements a base scenario model which implements some basic
    properties"""

    due_date: Optional[constr(pattern=r"(>|<){0,1}[\d-]+")]
    """Define a due date if necessary. The following schemas are allowed:

        - 2023-03-14 11:12
          only on March 14, 2023 at 11:12 a.m

        - 2023-03-14 11
          only on March 14, 2023 at 11 a.m

        - 2023/03/14
          only on March 14, 2023

        - >2023/03/14
          only after March 14, 2023

        - <2023/03/14
          only before March 14, 2023
    """

    source: Optional[str]
    """Define a source which is responsible for this entry"""

    executions: Optional[list[TaskExecution]]
    """executions which where executed"""

    finished: Optional[datetime]
    """Definition if instance is already processed successfully"""

    def get_execution(self, execution) -> list[TaskExecution]:
        """retrieve a list of task executions for the given Workflow object

        :param execution: execution type
        :type execution: str or object
        :return: a list of executions, ordered by execution time
        :rtype: list[TaskExecution]
        """
        name = execution
        if type(execution) != str:
            name = execution.__name__

        return list(
            sorted(
                (
                    execution
                    for execution in (self.executions or [])
                    if execution.name == name
                ),
                key=lambda e: e.execution_time,
                reverse=True,
            )
        )

    def new_execution(self, execution) -> TaskExecution:
        """create a new execution

        :param execution: execution type
        :type execution: str or object
        :return: return a new execution
        :rtype: TaskExecution
        """
        name = execution
        if type(execution) != str:
            name = execution.__name__

        if self.executions is None:
            self.executions = []
        execution = TaskExecution(name=name)
        self.executions.append(execution)
        return execution

    def has_processed(self, execution) -> list[TaskExecution]:
        """check if execution got successfully processed for the given
        Workflow object.

        :param execution: execution type
        :type execution: str or object
        :return: a list of executions, ordered by execution time
        :rtype: list[TaskExecution]
        """
        return [
            execution
            for execution in self.get_execution(execution)
            if execution.processed == True
        ]

    def get_markdown_info(self):
        return f"*source:* {self.source}"

    def type_cast(self, type):
        object.__setattr__(self, "__class__", type)
        super().__init__()
