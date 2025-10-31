import os
import uuid
import logging as logging_library
from abc import ABC, abstractmethod
from argparse import Namespace
from datetime import datetime
from typing import Union

from highway.time_block import TimeBlock
from highway.workflow_model import WorkflowModel, TaskExecution
from highway.status_exception import StatusException
from highway.task import Task

logging = logging_library.getLogger(__name__)


class Processor(ABC):
    """In case that the operator has not passed a list of specific
    entries this method will be called to get the default list of
    entries

    Following methods are abstract and have to be implemented

    * get_default_entries
    * get_entry
    * filter
    * process_entries
    * write_entry
    * close
    """

    def __init__(self, consider_date: Union[datetime, str] = None):
        super().__init__()
        self.statistics = {}
        self.time_statistics = {}

        consider_date = consider_date or os.getenv("consider_date", datetime.now())

        if isinstance(consider_date, datetime):
            self.consider_date = consider_date
        else:
            self.consider_date = datetime.strptime(consider_date, "%d.%m.%Y")

    @abstractmethod
    def get_default_entries(self) -> WorkflowModel:
        """retrieve a list of default entries keys

        :return: a list of objects
        :rtype: list
        """

    @abstractmethod
    def get_entry(
        self,
        selection,
    ) -> WorkflowModel:
        """Retrieve an entry by selection"""

    def filter_by_already_finished(self, entry: WorkflowModel) -> bool:
        """Filter by status

        :param entry: Entry which should be filtered
        :type entry: WorkflowModel
        :return: return whether this entry is eligible or not
        :rtype: bool
        """
        if entry.finished:
            self.statistic_increment("process", "already_finished")
            return False
        return True

    def filter_by_due_date(self, entry: WorkflowModel) -> bool:
        """Filter by due date

        :param entry: Entry which should be filtered
        :type entry: WorkflowModel
        :return: return whether this entry is eligible or not
        :rtype: bool
        """
        if entry.due_date:
            larger = entry.due_date.startswith(">")
            smaller = entry.due_date.startswith("<")
            if larger or smaller:
                iso_date = datetime.fromisoformat(entry.due_date[1:])
                if larger:
                    if self.consider_date <= iso_date:
                        self.statistic_increment("filter", "not_ripe")
                        return False
                elif smaller:
                    if self.consider_date >= iso_date:
                        self.statistic_increment("filter", "not_ripe")
                        return False
            else:
                iso_date = self.consider_date.isoformat()
                consider = iso_date[: len(entry.due_date)]
                if consider != entry.due_date:
                    self.statistic_increment("filter", "not_ripe")
                    return False
        return True

    def filter(self, entry: WorkflowModel) -> bool:
        """Base filter to exclude entries which are already done. Besides
        that, if a due date is set, only entries will be eligible if the
        consider date is fitting into the date filter.

        :param entry: Entry which should be filtered
        :type entry: WorkflowModel
        :return: return whether this entry is eligible or not
        :rtype: bool
        """
        if not self.filter_by_already_finished(entry):
            return False

        if not self.filter_by_due_date(entry):
            return False

        return True

    @abstractmethod
    def get_tasks(self) -> list[Task]: ...

    def process_tasks(self, entry: WorkflowModel, dry_run: bool = False):
        tasks = self.get_tasks()
        for index, task in enumerate(tasks):
            task_name = task.__class__.__name__
            increment = ["tasks", task_name]
            executions = entry.get_execution(task.__class__)
            repeat = None

            if len(executions) > 0:
                execution = executions[0]
                repeat = execution.repeat(self.consider_date, len(executions))

                if execution.processed and not repeat:
                    self.statistic_increment(*increment, "already_processed")
                    logging.info(
                        "task '%s' already processed for entry '%s'", task_name, entry
                    )
                    continue

                if execution.error_id and not repeat:
                    self.statistic_increment(*increment, "already_failed")
                    logging.info(
                        "task '%s' already failed for entry '%s'", task_name, entry
                    )
                    return False

                if execution.status and not repeat:
                    self.statistic_increment(*increment, "already_interrupted")
                    logging.info("task '%s' interrupted for '%s'", task_name, entry)
                    return False

                self.statistic_increment(*increment, "repeat")
                logging.info("repeat task '%s' for entry '%s'", task_name, entry)

            execution = entry.new_execution(task.__class__)

            interrupt = False

            try:
                with self.get_time_statistic("process_entry"):
                    execution.status = task.process_entry(entry, dry_run)
                execution.processed = True
                self.statistic_increment(*increment, "processed")
                logging.info(
                    "successfully processed task '%s' for entry '%s'", task_name, entry
                )
            except StatusException as status_exception:
                self.statistic_increment(*increment, "status_exception")
                interrupt = True
                execution.status = status_exception.status
                execution.processed = False
                self.statistic_increment(*increment, "status_skipped")
                logging.info(
                    "task '%s' has been skipped for entry '%s'", task_name, entry
                )
            except Exception as ex:
                self.statistic_increment(*increment, "failed")
                interrupt = True
                execution.processed = False
                execution.error_id = uuid.uuid4()

                logging.error(
                    f"Failed '{task_name}' with error id: "
                    f"'{execution.error_id}' \n{entry.get_markdown_info()}",
                    exc_info=ex,
                )

            if not interrupt and index == (len(tasks) - 1):
                entry.finished = datetime.now()
                entry.executions = None

            with self.get_time_statistic("write_entry"):
                self.write_entry(entry, execution)

            if interrupt:
                self.statistic_increment(*increment, "status_interrupted")
                logging.info("interrupted task '%s' for entry '%s'", task_name, entry)
                return False

        return True

    def process_entries(
        self, selections: list[any] = None, limit: int = None, dry_run: bool = False
    ):
        """Process a list of entries. We don't care about the content
        type of that list.

        :param entries: a list of entries, defaults to None
        :type entries: list[any], optional
        :param limit: how many entries should be processed,
            defaults to None
        :type limit: int, optional
        :param dryrun: nothing will happen, defaults to False
        :type dryrun: bool, optional
        """
        entries_processed = 0

        if selections:
            selected_entries = [self.get_entry(selection) for selection in selections]
        else:
            with self.get_time_statistic("get_default_entries"):
                selected_entries = self.get_default_entries()

        logging.info("'%d' default entries", len(selected_entries))

        for entry in selected_entries:
            if limit and entries_processed == limit:
                break
            if entry:
                if self.filter(entry):
                    self.statistic_increment("process", "eligible")
                    with self.get_time_statistic("process_tasks"):
                        processed = self.process_tasks(entry, dry_run)
                    entries_processed += 1
                else:
                    self.statistic_increment("process", "not_eligible")
        self.close()

    def process(self, args: Namespace):
        """Parse argparse Namespace arguments

        :param args: Namespace arguments
        :type args: Namespace
        """
        with self.get_time_statistic("process_entries"):
            self.process_entries(args.subs, args.limit, args.dryrun)

    def get_statistics(self, args: Namespace):
        """pass the statistics

        :param args: command line arguments
        :type args: Namespace
        :return: the statistics
        :rtype: dict
        """

        time_statistics = {}
        for name, time_block in self.time_statistics.items():
            time_statistics[name] = time_block.dict()
        self.statistics["time_statistics"] = time_statistics
        return self.statistics

    def statistic_increment(self, *subs):
        """Increment a specified element in the statistics. Non-existing
        elements will be created automatically:

        .. code-block:
            self.statistic_increment('entries', 'success')
            self.statistic_increment('entries', 'success')
            self.statistic_increment('entries', 'failed')

        will create the following dictionary

        .. code-block:
            {
                'entries': {
                    'success': 2,
                    'failed': 1
                }
            }
        """
        selection = self.statistics
        for sub in subs[:-1]:
            selection = selection.setdefault(sub, {})
        selection[subs[-1]] = selection.get(subs[-1], 0) + 1

    def get_time_statistic(self, name: str):
        return self.time_statistics.setdefault(name, TimeBlock())

    @abstractmethod
    def write_entry(self, entry: WorkflowModel, execution: TaskExecution) -> dict:
        """Write an entry

        :param entry: Entry which should be processed
        :type entry: WorkflowModel
        :return: parsed entry
        :rtype: dict
        """

    @abstractmethod
    def close(self):
        """do something at the end of the process.
        e.g. write cached entries to the disk or close the output file
        """
