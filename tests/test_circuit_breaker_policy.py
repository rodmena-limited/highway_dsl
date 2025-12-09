"""Tests for CircuitBreakerPolicy (Issue #247).

Verifies:
1. CircuitBreakerPolicy serialization to JSON
2. CircuitBreakerPolicy deserialization from JSON
3. Integration with task() and activity() builder methods
4. Exception filtering via catch_exceptions/ignore_exceptions
"""

import json
from datetime import timedelta

import pytest

from highway_dsl import (
    CircuitBreakerPolicy,
    RetryPolicy,
    TimeoutPolicy,
    WorkflowBuilder,
)


class TestCircuitBreakerPolicySerialization:
    """Test CircuitBreakerPolicy JSON serialization."""

    def test_default_values(self):
        """Default values should be sensible."""
        policy = CircuitBreakerPolicy()
        assert policy.failure_threshold == 5
        assert policy.success_threshold == 2
        assert policy.isolation_duration == timedelta(seconds=30)
        assert policy.catch_exceptions is None
        assert policy.ignore_exceptions is None

    def test_custom_values(self):
        """Custom values should be preserved."""
        policy = CircuitBreakerPolicy(
            failure_threshold=3,
            success_threshold=1,
            isolation_duration=timedelta(seconds=60),
            catch_exceptions=["ConnectionError", "TimeoutError"],
            ignore_exceptions=["ValidationError"],
        )
        assert policy.failure_threshold == 3
        assert policy.success_threshold == 1
        assert policy.isolation_duration == timedelta(seconds=60)
        assert policy.catch_exceptions == ["ConnectionError", "TimeoutError"]
        assert policy.ignore_exceptions == ["ValidationError"]

    def test_model_dump_serializes_timedelta(self):
        """model_dump should convert timedelta to seconds for JSON compatibility."""
        policy = CircuitBreakerPolicy(isolation_duration=timedelta(minutes=2))
        data = policy.model_dump()

        assert "isolation_duration_seconds" in data
        assert data["isolation_duration_seconds"] == 120.0
        # isolation_duration should be removed for clean JSON
        assert "isolation_duration" not in data

    def test_json_roundtrip(self):
        """Policy should survive JSON roundtrip."""
        original = CircuitBreakerPolicy(
            failure_threshold=10,
            success_threshold=3,
            isolation_duration=timedelta(seconds=45),
            catch_exceptions=["RuntimeError"],
        )

        # Serialize to JSON
        json_str = json.dumps(original.model_dump())

        # Deserialize from JSON
        data = json.loads(json_str)
        restored = CircuitBreakerPolicy(**data)

        assert restored.failure_threshold == original.failure_threshold
        assert restored.success_threshold == original.success_threshold
        assert restored.isolation_duration == timedelta(seconds=45)
        assert restored.catch_exceptions == original.catch_exceptions


class TestCircuitBreakerPolicyWithWorkflowBuilder:
    """Test CircuitBreakerPolicy integration with WorkflowBuilder."""

    def test_task_with_circuit_breaker_policy(self):
        """task() should accept circuit_breaker_policy parameter."""
        builder = WorkflowBuilder(name="test_cb_task")

        builder.task(
            "http_call",
            "tools.http.get",
            args=["https://example.com"],
            result_key="response",
            circuit_breaker_policy=CircuitBreakerPolicy(
                failure_threshold=3,
                success_threshold=1,
                isolation_duration=timedelta(seconds=30),
            ),
        )

        workflow = builder.build()
        task = workflow.tasks["http_call"]

        assert task.circuit_breaker_policy is not None
        assert task.circuit_breaker_policy.failure_threshold == 3

    def test_activity_with_circuit_breaker_policy(self):
        """activity() should accept circuit_breaker_policy parameter."""
        builder = WorkflowBuilder(name="test_cb_activity")

        builder.activity(
            "long_running_task",
            "tools.shell.run",
            args=["sleep 10"],
            result_key="shell_result",
            circuit_breaker_policy=CircuitBreakerPolicy(
                failure_threshold=5,
                catch_exceptions=["ShellCommandError"],
                ignore_exceptions=["TimeoutError"],
            ),
        )

        workflow = builder.build()
        activity = workflow.tasks["long_running_task"]

        assert activity.circuit_breaker_policy is not None
        assert activity.circuit_breaker_policy.failure_threshold == 5
        assert activity.circuit_breaker_policy.catch_exceptions == ["ShellCommandError"]

    def test_workflow_json_includes_circuit_breaker_policy(self):
        """Workflow JSON should include circuit_breaker_policy for tasks/activities."""
        builder = WorkflowBuilder(name="test_cb_json")

        builder.activity(
            "protected_call",
            "tools.http.post",
            args=["https://api.example.com/data", {"key": "value"}],
            circuit_breaker_policy=CircuitBreakerPolicy(
                failure_threshold=10,
                isolation_duration=timedelta(minutes=1),
            ),
        )

        workflow = builder.build()
        workflow_json = workflow.to_json()
        workflow_dict = json.loads(workflow_json)

        # Find the activity task by task_id in the tasks dict
        task = workflow_dict["tasks"]["protected_call"]
        assert "circuit_breaker_policy" in task
        assert task["circuit_breaker_policy"]["failure_threshold"] == 10
        # Pydantic serializes timedelta as ISO8601 duration (PT1M = 1 minute)
        assert task["circuit_breaker_policy"]["isolation_duration"] == "PT1M"

    def test_task_without_circuit_breaker_policy(self):
        """Tasks without circuit_breaker_policy should have None."""
        builder = WorkflowBuilder(name="test_no_cb")

        builder.task(
            "simple_task",
            "tools.shell.run",
            args=["echo hello"],
        )

        workflow = builder.build()
        task = workflow.tasks["simple_task"]

        assert task.circuit_breaker_policy is None

    def test_combined_policies(self):
        """Circuit breaker should work alongside retry and timeout policies."""
        builder = WorkflowBuilder(name="test_combined")

        builder.task(
            "resilient_call",
            "tools.http.get",
            args=["https://flaky-api.example.com"],
            retry_policy=RetryPolicy(max_retries=3, delay=timedelta(seconds=5)),
            timeout_policy=TimeoutPolicy(timeout=timedelta(seconds=30)),
            circuit_breaker_policy=CircuitBreakerPolicy(
                failure_threshold=5,
                isolation_duration=timedelta(seconds=60),
            ),
        )

        workflow = builder.build()
        task = workflow.tasks["resilient_call"]

        assert task.retry_policy is not None
        assert task.retry_policy.max_retries == 3
        assert task.timeout_policy is not None
        assert task.timeout_policy.timeout == timedelta(seconds=30)
        assert task.circuit_breaker_policy is not None
        assert task.circuit_breaker_policy.failure_threshold == 5


class TestExceptionFiltering:
    """Test catch_exceptions and ignore_exceptions filtering logic."""

    def test_catch_exceptions_only_counts_listed(self):
        """Only exceptions in catch_exceptions should count as failures."""
        policy = CircuitBreakerPolicy(
            catch_exceptions=["ConnectionError", "TimeoutError"],
        )
        assert policy.catch_exceptions == ["ConnectionError", "TimeoutError"]
        assert policy.ignore_exceptions is None

    def test_ignore_exceptions_excludes_listed(self):
        """Exceptions in ignore_exceptions should not count as failures."""
        policy = CircuitBreakerPolicy(
            ignore_exceptions=["ValidationError", "ValueError"],
        )
        assert policy.ignore_exceptions == ["ValidationError", "ValueError"]
        assert policy.catch_exceptions is None

    def test_both_filters_can_coexist(self):
        """Both catch and ignore can be set (ignore takes precedence)."""
        policy = CircuitBreakerPolicy(
            catch_exceptions=["RuntimeError", "IOError"],
            ignore_exceptions=["ValidationError"],
        )
        assert policy.catch_exceptions == ["RuntimeError", "IOError"]
        assert policy.ignore_exceptions == ["ValidationError"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
