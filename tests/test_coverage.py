"""Additional tests to improve code coverage."""

from datetime import datetime, timedelta

import pytest

from highway_dsl import (
    Duration,
    JoinMode,
    RetryPolicy,
    Workflow,
    WorkflowBuilder,
    generate_dot,
)


class TestDuration:
    """Test Duration helper class."""

    def test_seconds(self):
        assert Duration.seconds(30) == timedelta(seconds=30)
        assert Duration.seconds(0.5) == timedelta(seconds=0.5)

    def test_minutes(self):
        assert Duration.minutes(5) == timedelta(minutes=5)
        assert Duration.minutes(1.5) == timedelta(minutes=1.5)

    def test_hours(self):
        assert Duration.hours(2) == timedelta(hours=2)
        assert Duration.hours(0.5) == timedelta(hours=0.5)

    def test_days(self):
        assert Duration.days(1) == timedelta(days=1)
        assert Duration.days(0.5) == timedelta(days=0.5)

    def test_weeks(self):
        assert Duration.weeks(1) == timedelta(weeks=1)
        assert Duration.weeks(2) == timedelta(weeks=2)


class TestWorkflowValidation:
    """Test workflow name and version validation."""

    def test_valid_workflow_name(self):
        workflow = Workflow(name="valid_workflow", version="1.0.0")
        assert workflow.name == "valid_workflow"

    def test_invalid_workflow_name_double_underscore(self):
        with pytest.raises(ValueError, match="cannot contain '__'"):
            Workflow(name="invalid__name", version="1.0.0")

    def test_invalid_workflow_name_uppercase(self):
        with pytest.raises(ValueError, match="must start with lowercase"):
            Workflow(name="InvalidName", version="1.0.0")

    def test_invalid_workflow_name_starts_with_number(self):
        with pytest.raises(ValueError, match="must start with lowercase"):
            Workflow(name="1invalid", version="1.0.0")

    def test_invalid_version_double_underscore(self):
        with pytest.raises(ValueError, match="cannot contain '__'"):
            Workflow(name="valid", version="1__0")


class TestWorkflowScheduling:
    """Test workflow scheduling methods."""

    def test_set_schedule(self):
        builder = WorkflowBuilder("scheduled")
        builder.set_schedule("0 2 * * *")
        workflow = builder.build()
        assert workflow.schedule == "0 2 * * *"

    def test_set_start_date(self):
        builder = WorkflowBuilder("scheduled")
        start = datetime(2025, 1, 1)
        builder.set_start_date(start)
        workflow = builder.build()
        assert workflow.start_date == start

    def test_set_catchup(self):
        builder = WorkflowBuilder("scheduled")
        builder.set_catchup(True)
        workflow = builder.build()
        assert workflow.catchup is True

    def test_set_paused(self):
        builder = WorkflowBuilder("scheduled")
        builder.set_paused(True)
        workflow = builder.build()
        assert workflow.is_paused is True

    def test_add_tags(self):
        builder = WorkflowBuilder("tagged")
        builder.add_tags("production", "critical")
        workflow = builder.build()
        assert "production" in workflow.tags
        assert "critical" in workflow.tags

    def test_set_max_active_runs(self):
        builder = WorkflowBuilder("limited")
        builder.set_max_active_runs(5)
        workflow = builder.build()
        assert workflow.max_active_runs == 5

    def test_set_default_retry_policy(self):
        builder = WorkflowBuilder("retry")
        policy = RetryPolicy(max_retries=5, delay=timedelta(seconds=30))
        builder.set_default_retry_policy(policy)
        workflow = builder.build()
        assert workflow.default_retry_policy is not None
        assert workflow.default_retry_policy.max_retries == 5


class TestWorkflowMetadata:
    """Test workflow metadata methods."""

    def test_set_description(self):
        builder = WorkflowBuilder("test")
        builder.set_description("Test workflow description")
        workflow = builder.build()
        assert workflow.description == "Test workflow description"

    def test_set_version(self):
        builder = WorkflowBuilder("test", version="1.0.0")
        builder.set_version("2.0.0")
        workflow = builder.build()
        assert workflow.version == "2.0.0"


class TestParallelWithJoin:
    """Test parallel_with_join method."""

    def test_parallel_with_join_basic(self):
        builder = WorkflowBuilder("parallel_test")
        builder.parallel_with_join(
            "data_processing",
            branches={
                "branch_a": lambda b: b.task("a", "func_a"),
                "branch_b": lambda b: b.task("b", "func_b"),
            },
            timeout_seconds=120,
        )
        workflow = builder.build()

        # Should have parallel task and join task
        assert "data_processing" in workflow.tasks
        assert "data_processing_join" in workflow.tasks

        # Join task should depend on parallel task
        join_task = workflow.tasks["data_processing_join"]
        assert "data_processing" in join_task.dependencies

    def test_parallel_with_join_custom_result_key(self):
        builder = WorkflowBuilder("parallel_test")
        builder.parallel_with_join(
            "processing",
            branches={
                "a": lambda b: b.task("a", "func_a"),
            },
            join_result_key="custom_results",
        )
        workflow = builder.build()
        join_task = workflow.tasks["processing_join"]
        assert join_task.result_key == "custom_results"


class TestWorkflowBuilderHandlerTask:
    """Test on_success and on_failure callbacks."""

    def test_on_success_callback(self):
        builder = WorkflowBuilder("callback_test")
        builder.task("main", "main_func")
        builder.on_success("success_handler")
        builder.task("success_handler", "handler_func")
        workflow = builder.build()

        # on_success sets on_success_task_id on the task that was current when called
        main_task = workflow.tasks["main"]
        assert main_task.on_success_task_id == "success_handler"

    def test_on_failure_callback(self):
        builder = WorkflowBuilder("callback_test")
        builder.task("risky", "risky_func")
        builder.on_failure("alert")
        builder.task("alert", "send_alert")  # Define the handler task after
        workflow = builder.build()

        risky_task = workflow.tasks["risky"]
        assert risky_task.on_failure_task_id == "alert"


class TestGraphvizExport:
    """Test graphviz_export module."""

    def test_generate_dot_basic(self):
        builder = WorkflowBuilder("test")
        builder.task("t1", "func1")
        builder.task("t2", "func2")
        workflow = builder.build()

        # Use mode="json" to ensure enum values are serialized as strings
        dot = generate_dot(workflow.model_dump(mode="json"))
        assert "digraph workflow" in dot
        assert "t1" in dot
        assert "t2" in dot

    def test_generate_dot_invalid_definition(self):
        # Test with invalid workflow definition
        invalid_def = {"invalid": "data"}
        dot = generate_dot(invalid_def)
        assert "digraph error" in dot
        assert "Error parsing workflow definition" in dot


class TestWorkflowBuilderDependsOn:
    """Test depends_on alias for dependencies."""

    def test_depends_on_alias(self):
        builder = WorkflowBuilder("alias_test")
        builder.task("a", "func_a")
        builder.task("b", "func_b", depends_on=["a"])
        workflow = builder.build()

        task_b = workflow.tasks["b"]
        assert "a" in task_b.dependencies

    def test_depends_on_with_dependencies(self):
        # When both are specified, dependencies takes precedence
        builder = WorkflowBuilder("both_test")
        builder.task("a", "func_a")
        builder.task("b", "func_b", dependencies=["a"], depends_on=["x"])
        workflow = builder.build()

        task_b = workflow.tasks["b"]
        assert "a" in task_b.dependencies


class TestActivityOperator:
    """Test ActivityOperator builder method."""

    def test_activity_basic(self):
        from highway_dsl import OperatorType

        builder = WorkflowBuilder("activity_test")
        builder.activity("act1", "long_running.func", args=["arg1"])
        workflow = builder.build()

        assert "act1" in workflow.tasks
        task = workflow.tasks["act1"]
        assert task.operator_type == OperatorType.ACTIVITY

    def test_activity_with_depends_on(self):
        builder = WorkflowBuilder("activity_test")
        builder.task("start", "setup")
        builder.activity("act1", "long_running.func", depends_on=["start"])
        workflow = builder.build()

        task = workflow.tasks["act1"]
        assert "start" in task.dependencies


class TestJoinOperator:
    """Test join operator via builder."""

    def test_join_with_all_of(self):
        from highway_dsl import OperatorType

        builder = WorkflowBuilder("join_test")
        builder.task("start", "init")
        builder.task("a", "func_a", dependencies=["start"])
        builder.task("b", "func_b", dependencies=["start"])
        builder.join("sync", join_tasks=["a", "b"], join_mode=JoinMode.ALL_OF)
        workflow = builder.build()

        assert "sync" in workflow.tasks
        join_task = workflow.tasks["sync"]
        assert join_task.operator_type == OperatorType.JOIN


class TestMcpServerImport:
    """Test MCP server import handling."""

    def test_get_mcp_server_import_error(self):
        # This tests the import error handling when MCP is not installed
        from highway_dsl import get_mcp_server

        # The MCP module may or may not be installed, so we just test the function exists
        # and returns something or raises ImportError
        try:
            result = get_mcp_server()
            # If it returns, it should be the mcp server object
            assert result is not None
        except ImportError as e:
            # If MCP is not installed, should get a clear error message
            assert "MCP support requires the mcp extra" in str(e)
