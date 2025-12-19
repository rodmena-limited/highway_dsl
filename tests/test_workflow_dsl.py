import json
from datetime import datetime, timedelta

import pytest

from highway_dsl import (
    ConditionOperator,
    ForEachOperator,
    OperatorType,
    ParallelOperator,
    RetryPolicy,
    TaskOperator,
    TimeoutPolicy,
    WaitOperator,
    WhileOperator,
    Workflow,
    WorkflowBuilder,
)


def test_workflow_builder_while_loop():
    workflow = (
        WorkflowBuilder("while_loop_workflow")
        .task("initial", "init_func")
        .while_loop(
            "loop",
            "i < 5",
            lambda b: b.task("loop_task", "loop_func"),
        )
        .build()
    )
    assert "loop" in workflow.tasks
    assert workflow.tasks["loop"].dependencies == ["initial"]
    assert isinstance(workflow.tasks["loop"], WhileOperator)
    assert "loop_task" in workflow.tasks


def sort_dict_recursively(d):
    if not isinstance(d, dict):
        return d
    return {k: sort_dict_recursively(v) for k, v in sorted(d.items())}


def test_workflow_creation():
    workflow = Workflow(
        name="test_workflow",
        version="1.0.0",
        description="A test workflow",
    )
    assert workflow.name == "test_workflow"
    assert workflow.version == "1.0.0"
    assert workflow.description == "A test workflow"
    assert workflow.tasks == {}
    assert workflow.variables == {}
    assert workflow.start_task is None


def test_add_task_to_workflow():
    workflow = Workflow(name="test_workflow")
    task = TaskOperator(task_id="task1", function="func1")
    workflow.add_task(task)
    assert "task1" in workflow.tasks
    assert workflow.tasks["task1"] == task


def test_set_variables():
    workflow = Workflow(name="test_workflow")
    workflow.set_variables({"key1": "value1"})
    assert workflow.variables == {"key1": "value1"}
    workflow.set_variables({"key2": "value2"})
    assert workflow.variables == {"key1": "value1", "key2": "value2"}


def test_set_start_task():
    workflow = Workflow(name="test_workflow")
    workflow.set_start_task("task1")
    assert workflow.start_task == "task1"


def test_retry_policy_model():
    policy = RetryPolicy(max_retries=5, delay=timedelta(seconds=10), backoff_factor=2.5)
    assert policy.max_retries == 5
    assert policy.delay == timedelta(seconds=10)
    assert policy.backoff_factor == 2.5


def test_timeout_policy_model():
    policy = TimeoutPolicy(timeout=timedelta(minutes=5), kill_on_timeout=False)
    assert policy.timeout == timedelta(minutes=5)
    assert policy.kill_on_timeout is False


def test_task_operator_model():
    task = TaskOperator(
        task_id="task1",
        function="func1",
        args=["arg1"],
        kwargs={"kwarg1": "value1"},
        result_key="res1",
        dependencies=["dep1"],
        retry_policy=RetryPolicy(max_retries=1),
        timeout_policy=TimeoutPolicy(timeout=timedelta(seconds=30)),
        metadata={"meta1": "data1"},
    )
    assert task.task_id == "task1"
    assert task.operator_type == OperatorType.TASK
    assert task.function == "func1"
    assert task.args == ["arg1"]
    assert task.kwargs == {"kwarg1": "value1"}
    assert task.result_key == "res1"
    assert task.dependencies == ["dep1"]
    assert task.retry_policy is not None
    assert task.retry_policy.max_retries == 1
    assert task.timeout_policy is not None
    assert task.timeout_policy.timeout == timedelta(seconds=30)
    assert task.metadata == {"meta1": "data1"}


def test_condition_operator_model():
    condition = ConditionOperator(
        task_id="cond1",
        condition="x > 5",
        if_true="task_true",
        if_false="task_false",
        dependencies=["prev_task"],
    )
    assert condition.task_id == "cond1"
    assert condition.operator_type == OperatorType.CONDITION
    assert condition.condition == "x > 5"
    assert condition.if_true == "task_true"
    assert condition.if_false == "task_false"
    assert condition.dependencies == ["prev_task"]


def test_wait_operator_model():
    wait_duration = WaitOperator(task_id="wait1", wait_for=timedelta(hours=1))
    assert wait_duration.wait_for == timedelta(hours=1)
    assert wait_duration.operator_type == OperatorType.WAIT

    now = datetime.now().replace(microsecond=0)
    wait_datetime = WaitOperator(task_id="wait2", wait_for=now)
    assert wait_datetime.wait_for == now

    wait_string = WaitOperator(task_id="wait3", wait_for="event_name")
    assert wait_string.wait_for == "event_name"


def test_parallel_operator_model():
    parallel = ParallelOperator(
        task_id="parallel1",
        branches={"branch_a": ["task_a1", "task_a2"], "branch_b": ["task_b1"]},
    )
    assert parallel.task_id == "parallel1"
    assert parallel.operator_type == OperatorType.PARALLEL
    assert parallel.branches == {
        "branch_a": ["task_a1", "task_a2"],
        "branch_b": ["task_b1"],
    }


def test_foreach_operator_model():
    task = TaskOperator(task_id="task1", function="func1")
    foreach = ForEachOperator(task_id="foreach1", items="data_list", loop_body=[task])
    assert foreach.task_id == "foreach1"
    assert foreach.operator_type == OperatorType.FOREACH
    assert foreach.items == "data_list"
    assert foreach.loop_body == [task]


def test_while_operator_model():
    task = TaskOperator(task_id="task1", function="func1")
    while_op = WhileOperator(
        task_id="while1",
        condition="x < 5",
        loop_body=[task],
        dependencies=["prev_task"],
    )
    assert while_op.task_id == "while1"
    assert while_op.operator_type == OperatorType.WHILE
    assert while_op.condition == "x < 5"
    assert while_op.loop_body == [task]
    assert while_op.dependencies == ["prev_task"]


def test_wait_operator_serialization():
    # Test with timedelta - now uses ISO 8601 duration format (PT<seconds>S)
    wait_duration = WaitOperator(task_id="wait1", wait_for=timedelta(hours=1))
    dump = wait_duration.model_dump()
    assert dump["wait_for"] == "PT3600.0S"  # ISO 8601 duration format

    # Test with datetime - uses ISO 8601 datetime format
    now = datetime.now().replace(microsecond=0)
    wait_datetime = WaitOperator(task_id="wait2", wait_for=now)
    dump = wait_datetime.model_dump()
    assert dump["wait_for"] == now.isoformat()  # ISO 8601 datetime format

    # Test with string (no conversion)
    wait_string = WaitOperator(task_id="wait3", wait_for="event_name")
    dump = wait_string.model_dump()
    assert dump["wait_for"] == "event_name"

    # Test parsing of different data types
    assert WaitOperator.model_validate(
        {"task_id": "t", "wait_for": "duration:60"},
    ).wait_for == timedelta(seconds=60)
    now_iso = now.isoformat()
    assert (
        WaitOperator.model_validate(
            {"task_id": "t", "wait_for": f"datetime:{now_iso}"},
        ).wait_for
        == now
    )
    assert (
        WaitOperator.model_validate({"task_id": "t", "wait_for": "event"}).wait_for
        == "event"
    )


def test_workflow_builder_simple_chain():
    workflow = (
        WorkflowBuilder("simple_chain")
        .task("start", "func_start", result_key="start_res")
        .task("middle", "func_middle", args=["{{start_res}}"])
        .build()
    )
    assert workflow.name == "simple_chain"
    assert "start" in workflow.tasks
    assert "middle" in workflow.tasks
    assert workflow.tasks["middle"].dependencies == ["start"]
    assert workflow.start_task == "start"


def test_workflow_builder_with_retry_and_timeout():
    workflow = (
        WorkflowBuilder("retry_timeout_workflow")
        .task("step1", "func1")
        .retry(max_retries=5, delay=timedelta(seconds=15))
        .timeout(timeout=timedelta(minutes=1))
        .build()
    )
    step1_task = workflow.tasks["step1"]
    assert step1_task.retry_policy is not None
    assert step1_task.retry_policy.max_retries == 5
    assert step1_task.retry_policy.delay == timedelta(seconds=15)
    assert step1_task.timeout_policy is not None
    assert step1_task.timeout_policy.timeout == timedelta(minutes=1)


def test_workflow_builder_condition():
    workflow = (
        WorkflowBuilder("conditional_workflow")
        .task("initial", "init_func")
        .condition(
            "check",
            "val > 10",
            if_true=lambda b: b.task("high", "high_func"),
            if_false=lambda b: b.task("low", "low_func"),
        )
        .build()
    )
    assert "check" in workflow.tasks
    check_task = workflow.tasks["check"]
    assert check_task.dependencies == ["initial"]
    assert isinstance(check_task, ConditionOperator)
    assert check_task.if_true == "high"
    assert check_task.if_false == "low"
    assert "high" in workflow.tasks
    assert "low" in workflow.tasks


def test_workflow_builder_parallel():
    workflow = (
        WorkflowBuilder("parallel_workflow")
        .task("init", "init_func")
        .parallel(
            "parallel_step",
            branches={
                "b1": lambda b: b.task("t1", "t1_func"),
                "b2": lambda b: b.task("t2", "t2_func"),
            },
        )
        .build()
    )
    assert "parallel_step" in workflow.tasks
    assert workflow.tasks["parallel_step"].dependencies == ["init"]
    # After fork-only fix, branch tasks are stored in branch_workflows, not parent tasks
    parallel_op = workflow.tasks["parallel_step"]
    assert isinstance(parallel_op, ParallelOperator)
    assert "b1" in parallel_op.branch_workflows
    assert "b2" in parallel_op.branch_workflows
    assert "t1" in parallel_op.branch_workflows["b1"]["tasks"]
    assert "t2" in parallel_op.branch_workflows["b2"]["tasks"]


def test_workflow_builder_foreach():
    workflow = (
        WorkflowBuilder("foreach_workflow")
        .task("fetch_items", "fetch_func")
        .foreach(
            "loop_items",
            "items_list",
            lambda b: b.task("process_item", "process_func"),
        )
        .build()
    )
    assert "loop_items" in workflow.tasks
    assert workflow.tasks["loop_items"].dependencies == ["fetch_items"]
    assert "process_item" in workflow.tasks
    assert workflow.tasks["process_item"].dependencies == ["loop_items"]


def test_workflow_yaml_round_trip():
    original_workflow = (
        WorkflowBuilder("yaml_test")
        .task("start", "func_start", result_key="start_res")
        .retry(max_retries=2, delay=timedelta(seconds=5))
        .wait("wait_step", timedelta(minutes=1))
        .task("end", "func_end", args=["{{start_res}}"])
        .build()
    )
    original_workflow.set_variables({"env": "dev"})

    yaml_output = original_workflow.to_yaml()
    loaded_workflow = Workflow.from_yaml(yaml_output)
    assert sort_dict_recursively(
        json.loads(original_workflow.model_dump_json()),
    ) == sort_dict_recursively(json.loads(loaded_workflow.model_dump_json()))


def test_workflow_json_round_trip():
    original_workflow = (
        WorkflowBuilder("json_test")
        .task("stepA", "funcA")
        .timeout(timeout=timedelta(seconds=60), kill_on_timeout=False)
        .condition(
            "check_val",
            "val == 'ok'",
            if_true=lambda b: b.task("success", "success_func"),
            if_false=lambda b: b.task("fail", "fail_func"),
        )
        .build()
    )
    original_workflow.set_variables({"user": "test"})

    json_output = original_workflow.to_json()
    loaded_workflow = Workflow.from_json(json_output)

    assert sort_dict_recursively(
        json.loads(original_workflow.model_dump_json()),
    ) == sort_dict_recursively(json.loads(loaded_workflow.model_dump_json()))


def test_complex_workflow_creation_and_serialization():
    # This test re-uses the logic from example_usage.py's create_complex_workflow
    # to ensure it works with the new Pydantic models and can be serialized/deserialized.
    builder = WorkflowBuilder("data_processing_pipeline")

    builder.task("start", "workflows.tasks.initialize", result_key="init_data")
    builder.task(
        "validate",
        "workflows.tasks.validate_data",
        args=["{{init_data}}"],
        result_key="validated_data",
    )

    builder.condition(
        "check_quality",
        condition="{{validated_data.quality_score}} > 0.8",
        if_true=lambda b: b.task(
            "high_quality_processing",
            "workflows.tasks.advanced_processing",
            args=["{{validated_data}}"],
            retry_policy=RetryPolicy(max_retries=5, delay=timedelta(seconds=10)),
        ),
        if_false=lambda b: b.task(
            "standard_processing",
            "workflows.tasks.basic_processing",
            args=["{{validated_data}}"],
        ),
    )

    builder.parallel(
        "parallel_processing",
        branches={
            "branch_a": lambda b: b.task(
                "transform_a",
                "workflows.tasks.transform_a",
                result_key="transformed_a",
            ).task(
                "enrich_a",
                "workflows.tasks.enrich_data",
                args=["{{transformed_a}}"],
                result_key="enriched_a",
            ),
            "branch_b": lambda b: b.task(
                "transform_b",
                "workflows.tasks.transform_b",
                result_key="transformed_b",
            ).task(
                "enrich_b",
                "workflows.tasks.enrich_data",
                args=["{{transformed_b}}"],
                result_key="enriched_b",
            ),
        },
        dependencies=["high_quality_processing", "standard_processing"],
    )

    builder.task(
        "aggregate",
        "workflows.tasks.aggregate_results",
        dependencies=["enrich_a", "enrich_b"],
        result_key="final_result",
    )
    builder.wait("wait_notification", timedelta(hours=1))
    builder.task(
        "notify",
        "workflows.tasks.send_notification",
        args=["{{final_result}}"],
    )

    workflow = builder.build()

    workflow.set_variables(
        {
            "environment": "production",
            "batch_size": 1000,
            "notify_email": "team@company.com",
        },
    )

    # Test serialization and deserialization
    yaml_output = workflow.to_yaml()
    loaded_workflow_from_yaml = Workflow.from_yaml(yaml_output)
    assert sort_dict_recursively(
        json.loads(workflow.model_dump_json()),
    ) == sort_dict_recursively(json.loads(loaded_workflow_from_yaml.model_dump_json()))

    json_output = workflow.to_json()
    loaded_workflow_from_json = Workflow.from_json(json_output)
    assert sort_dict_recursively(
        json.loads(workflow.model_dump_json()),
    ) == sort_dict_recursively(json.loads(loaded_workflow_from_json.model_dump_json()))


def test_unknown_operator_type_raises_error():
    yaml_content = """
    name: test
    tasks:
      task1:
        operator_type: unknown_operator
    """
    with pytest.raises(ValueError, match="Unknown operator type: unknown_operator"):
        Workflow.from_yaml(yaml_content)
