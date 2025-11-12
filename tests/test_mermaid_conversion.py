import os  # noqa: F401
from pathlib import Path

import pytest

from highway_dsl import (
    ConditionOperator,
    ForEachOperator,
    ParallelOperator,
    TaskOperator,
    WhileOperator,
    Workflow,
)


# Define the output directory for Mermaid diagrams
MERMAID_TEST_RESULTS_DIR = Path("/tmp/highway_dsl/mermaid_test_results")


@pytest.fixture(scope="session", autouse=True)
def create_mermaid_test_dir():
    """Create the directory for Mermaid test results if it doesn't exist."""
    MERMAID_TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def save_mermaid_file(workflow_name: str, mermaid_content: str):
    """Saves the Mermaid diagram to a file."""
    file_path = MERMAID_TEST_RESULTS_DIR / f"{workflow_name}.mermaid"
    file_path.write_text(mermaid_content)


def test_single_task_workflow_to_mermaid():
    # Create a workflow with a single task
    workflow = Workflow(name="single_task_workflow", start_task="task1")
    workflow.add_task(TaskOperator(task_id="task1", function="func1"))

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    [*] --> task1
    task1 --> [*]"""

    # Compare the generated diagram with the expected one
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_simple_linear_workflow_to_mermaid():
    # Create a simple linear workflow
    workflow = Workflow(name="simple_linear_workflow", start_task="task1")
    workflow.add_task(TaskOperator(task_id="task1", function="func1"))
    workflow.add_task(TaskOperator(task_id="task2", function="func2", dependencies=["task1"]))
    workflow.add_task(TaskOperator(task_id="task3", function="func3", dependencies=["task2"]))

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    task1 --> task2
    task2 --> task3
    [*] --> task1
    task3 --> [*]"""

    # Compare the generated diagram with the expected one
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_conditional_workflow_to_mermaid():
    # Create a conditional workflow
    workflow = Workflow(name="conditional_workflow", start_task="start_task")
    workflow.add_task(TaskOperator(task_id="start_task", function="start_func"))
    workflow.add_task(
        ConditionOperator(
            task_id="condition",
            condition="x > 10",
            if_true="true_task",
            if_false="false_task",
            dependencies=["start_task"],
        )
    )
    workflow.add_task(TaskOperator(task_id="true_task", function="true_func"))
    workflow.add_task(TaskOperator(task_id="false_task", function="false_func"))
    workflow.add_task(
        TaskOperator(
            task_id="end_task", function="end_func", dependencies=["true_task", "false_task"]
        )
    )

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    [*] --> start_task
    start_task --> condition
    condition --> true_task : True
    condition --> false_task : False
    true_task --> end_task
    false_task --> end_task
    end_task --> [*]"""

    # Compare the generated diagram with the expected one
    # Normalize line endings and remove leading/trailing whitespace
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_parallel_workflow_to_mermaid():
    # Create a parallel workflow
    workflow = Workflow(name="parallel_workflow", start_task="start_task")
    workflow.add_task(TaskOperator(task_id="start_task", function="start_func"))
    workflow.add_task(
        ParallelOperator(
            task_id="parallel_task",
            branches={"b1": ["t1"], "b2": ["t2"]},
            dependencies=["start_task"],
        )
    )
    workflow.add_task(
        TaskOperator(task_id="t1", function="t1_func", dependencies=["parallel_task"])
    )
    workflow.add_task(
        TaskOperator(task_id="t2", function="t2_func", dependencies=["parallel_task"])
    )
    workflow.add_task(
        TaskOperator(task_id="end_task", function="end_func", dependencies=["t1", "t2"])
    )

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    [*] --> start_task
    start_task --> parallel_task
    state parallel_task {
        state "Branch 1" as b1
        --
        state "Branch 2" as b2
    }
    parallel_task --> t1
    parallel_task --> t2
    t1 --> end_task
    t2 --> end_task
    end_task --> [*]"""

    # Compare the generated diagram with the expected one
    # Normalize line endings and remove leading/trailing whitespace
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_while_workflow_with_composite_state_to_mermaid():
    # Create a while workflow
    workflow = Workflow(name="while_workflow_with_composite_state", start_task="start_task")
    workflow.add_task(TaskOperator(task_id="start_task", function="start_func"))
    workflow.add_task(
        WhileOperator(
            task_id="while_task",
            condition="x > 10",
            loop_body=[TaskOperator(task_id="t1", function="t1_func", description="Task 1")],
            dependencies=["start_task"],
        )
    )
    workflow.add_task(
        TaskOperator(task_id="end_task", function="end_func", dependencies=["while_task"])
    )

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    [*] --> start_task
    start_task --> while_task
    state while_task {
        state "Task 1" as t1
    }
    while_task --> end_task
    end_task --> [*]"""

    # Compare the generated diagram with the expected one
    # Normalize line endings and remove leading/trailing whitespace
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_foreach_workflow_with_composite_state_to_mermaid():
    # Create a foreach workflow
    workflow = Workflow(name="foreach_workflow_with_composite_state", start_task="start_task")
    workflow.add_task(TaskOperator(task_id="start_task", function="start_func"))
    workflow.add_task(
        ForEachOperator(
            task_id="foreach_task",
            items="items",
            loop_body=[TaskOperator(task_id="t1", function="t1_func", description="Task 1")],
            dependencies=["start_task"],
        )
    )
    workflow.add_task(
        TaskOperator(task_id="end_task", function="end_func", dependencies=["foreach_task"])
    )

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    [*] --> start_task
    start_task --> foreach_task
    state foreach_task {
        state "Task 1" as t1
    }
    foreach_task --> end_task
    end_task --> [*]"""

    # Compare the generated diagram with the expected one
    # Normalize line endings and remove leading/trailing whitespace
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_parallel_workflow_with_composite_state_to_mermaid():
    # Create a parallel workflow
    workflow = Workflow(name="parallel_workflow_with_composite_state", start_task="start_task")
    workflow.add_task(TaskOperator(task_id="start_task", function="start_func"))
    workflow.add_task(
        ParallelOperator(
            task_id="parallel_task",
            branches={"b1": ["t1"], "b2": ["t2"]},
            dependencies=["start_task"],
        )
    )
    workflow.add_task(
        TaskOperator(task_id="t1", function="t1_func", dependencies=["parallel_task"])
    )
    workflow.add_task(
        TaskOperator(task_id="t2", function="t2_func", dependencies=["parallel_task"])
    )
    workflow.add_task(
        TaskOperator(task_id="end_task", function="end_func", dependencies=["t1", "t2"])
    )

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    [*] --> start_task
    start_task --> parallel_task
    state parallel_task {
        state "Branch 1" as b1
        --
        state "Branch 2" as b2
    }
    parallel_task --> t1
    parallel_task --> t2
    t1 --> end_task
    t2 --> end_task
    end_task --> [*]"""

    # Compare the generated diagram with the expected one
    # Normalize line endings and remove leading/trailing whitespace
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )


def test_state_with_description_to_mermaid():
    # Create a workflow with a state that has a description
    workflow = Workflow(name="state_with_description_workflow", start_task="task1")
    workflow.add_task(
        TaskOperator(
            task_id="task1", function="func1", description="This is a task with a description"
        )
    )
    workflow.add_task(TaskOperator(task_id="task2", function="func2", dependencies=["task1"]))

    # Generate the Mermaid diagram
    mermaid_diagram = workflow.to_mermaid()
    save_mermaid_file(workflow.name, mermaid_diagram)

    # Define the expected Mermaid diagram
    expected_mermaid = """stateDiagram-v2
    state "This is a task with a description" as task1
    [*] --> task1
    task1 --> task2
    task2 --> [*]"""

    # Compare the generated diagram with the expected one
    assert "\n".join(sorted(mermaid_diagram.strip().split("\n"))) == "\n".join(
        sorted(expected_mermaid.strip().split("\n"))
    )
