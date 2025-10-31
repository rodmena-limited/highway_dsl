from __future__ import annotations
import time
from typing import Callable


class TimeBlock(object):
    """
    The TimeBlock class measures and analyzes the execution time of code blocks in Python.

    :param exit_callable: An optional callback function that will be invoked when the code block is exited.
    :type exit_callable: Callable[[float, TimeBlock], None]

    Methods:
    :meth:`__init__`:
        Initializes a new TimeBlock object.

    :meth:`__enter__`:
        Invoked when entering the code block. Increments measure_count and records the start time.

    :meth:`__exit__`:
        Invoked when exiting the code block.
        Calculates elapsed time, updates time metrics, and invokes exit_callable if provided.

    :meth:`dict`:
        Returns a dictionary with various time metrics for analysis.

    Example Usage:
    ::

        from time_block import TimeBlock

        def example_function():
            with TimeBlock() as tb:
                # Code block to measure execution time
                # ...

            # Access time metrics
            metrics = tb.dict()
            print(f"Overall Time: {metrics['overall_time']}")
            print(f"Average Time: {metrics['average_time']}")
            print(f"Measure Count: {metrics['measure_count']}")
            print(f"Minimum Time: {metrics['minimum_time']}")
            print(f"Maximum Time: {metrics['maximum_time']}")

    Notes:
    - Ensure that the `time` module is imported before using the TimeBlock class.
    - It is recommended to use the 'with' statement when using TimeBlock to ensure proper resource cleanup.
    - The exit_callable can be used to perform custom actions when a code block is exited,
      such as logging or reporting.
    """

    def __init__(
        self, exit_callable: Callable[[float, TimeBlock], None] = None
    ) -> None:
        self.start_time: float = None
        self.exit_callable = exit_callable
        self.overall_time = 0
        self.average_time = 0
        self.measure_count = 0
        self.minimum_time = None
        self.maximum_time = None

    def __enter__(self):
        self.measure_count += 1
        self.start_time = time.time()

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed_time = time.time() - self.start_time
        self.overall_time += elapsed_time
        self.average_time = self.overall_time / self.measure_count
        if not self.minimum_time or self.minimum_time > elapsed_time:
            self.minimum_time = elapsed_time
        if not self.maximum_time or self.maximum_time < elapsed_time:
            self.maximum_time = elapsed_time
        if self.exit_callable:
            self.exit_callable(elapsed_time, self)

    def dict(self):
        return {
            "overall_time": self.overall_time,
            "average_time": self.average_time,
            "measure_count": self.measure_count,
            "minimum_time": self.minimum_time,
            "maximum_time": self.maximum_time,
        }
