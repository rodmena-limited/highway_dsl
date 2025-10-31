from abc import ABC, abstractmethod
from typing import Optional

from highway.workflow_model import WorkflowModel, Status


class Task(ABC):
    def __init__(self, processor) -> None:
        super().__init__()
        self.processor = processor

    @abstractmethod
    def process_entry(
        self, entry: WorkflowModel, dryrun: bool = False
    ) -> Optional[Status]: ...

    def statistic_increment(self, *args):
        self.processor.statistic_increment(self.__class__.__name__, *args)

    @property
    def name(self):
        processor_name = self.processor.__class__.__name__
        task_name = self.__class__.__name__
        return f"{processor_name}.{task_name}"
