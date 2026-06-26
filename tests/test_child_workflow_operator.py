"""Tests for the durable child_workflow operator (uplift #3)."""

from highway_dsl import ChildWorkflowOperator, OperatorType, Workflow, WorkflowBuilder


def test_child_workflows_builder_produces_operator() -> None:
    children = {
        "a": {"workflow_name": "summarize", "inputs": {"url": "{{u1}}"}},
        "b": {"workflow_name": "summarize", "inputs": {"url": "{{u2}}"}},
    }
    wf = (
        WorkflowBuilder("parent_cw")
        .child_workflows("fanout", children, result_key="kids")
        .build()
    )
    task = wf.tasks["fanout"]
    assert isinstance(task, ChildWorkflowOperator)
    assert task.children == children
    assert task.result_key == "kids"
    dumped = wf.model_dump(mode="json")["tasks"]["fanout"]
    assert dumped["operator_type"] == OperatorType.CHILD_WORKFLOW.value
    assert dumped["children"] == children


def test_child_workflow_convenience_wraps_single() -> None:
    wf = (
        WorkflowBuilder("parent_one")
        .child_workflow("kid", "summarize", inputs={"x": 1}, result_key="r")
        .build()
    )
    task = wf.tasks["kid"]
    assert isinstance(task, ChildWorkflowOperator)
    assert task.children == {"kid": {"workflow_name": "summarize", "inputs": {"x": 1}}}
    assert task.result_key == "r"


def test_child_workflow_json_roundtrip() -> None:
    wf = (
        WorkflowBuilder("parent_rt")
        .task("init", "tools.shell.run", args=["echo go"])
        .child_workflows(
            "fanout",
            {"a": {"workflow_name": "child_a", "inputs": {"n": 1}}},
            result_key="kids",
            timeout_seconds=300,
            dependencies=["init"],
        )
        .build()
    )
    json_str = wf.to_json()
    assert '"operator_type": "child_workflow"' in json_str
    loaded = Workflow.from_json(json_str)
    assert wf.model_dump(mode="json") == loaded.model_dump(mode="json")
    loaded_task = loaded.tasks["fanout"]
    assert isinstance(loaded_task, ChildWorkflowOperator)
    assert loaded_task.children["a"]["workflow_name"] == "child_a"
    assert loaded_task.timeout_seconds == 300
    assert "init" in loaded_task.dependencies


def test_child_workflow_validator_deserializes_dict() -> None:
    data = {
        "name": "cw_validate",
        "version": "2.0.0",
        "tasks": {
            "fanout": {
                "task_id": "fanout",
                "operator_type": "child_workflow",
                "children": {"a": {"workflow_name": "child_a", "inputs": {}}},
                "dependencies": [],
            }
        },
    }
    wf = Workflow.model_validate(data)
    task = wf.tasks["fanout"]
    assert isinstance(task, ChildWorkflowOperator)
    assert task.children["a"]["workflow_name"] == "child_a"


def test_child_workflow_depends_on_alias() -> None:
    wf = (
        WorkflowBuilder("parent_dep")
        .task("init", "tools.shell.run", args=["echo go"])
        .child_workflow("kid", "child_a", inputs={}, depends_on=["init"])
        .build()
    )
    assert "init" in wf.tasks["kid"].dependencies


def test_child_workflow_nested_in_while_loop() -> None:
    from highway_dsl import WhileOperator

    data = {
        "name": "cw_in_loop",
        "version": "2.0.0",
        "tasks": {
            "loop": {
                "task_id": "loop",
                "operator_type": "while",
                "condition": "{{keep_going}}",
                "loop_body": [
                    {
                        "task_id": "kid",
                        "operator_type": "child_workflow",
                        "children": {"a": {"workflow_name": "child_a", "inputs": {}}},
                    }
                ],
            }
        },
    }
    wf = Workflow.model_validate(data)
    loop = wf.tasks["loop"]
    assert isinstance(loop, WhileOperator)
    body_op = loop.loop_body[0]
    assert isinstance(body_op, ChildWorkflowOperator)
    assert body_op.children["a"]["workflow_name"] == "child_a"
