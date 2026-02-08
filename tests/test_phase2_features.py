"""Tests for Phase 2 Workflow Patterns: Dynamic MI, Cancel/Complete ForEach, Workflow Deadline."""

import pytest

from highway_dsl.workflow_dsl import (
    ForEachOperator,
    OperatorType,
    TaskOperator,
    Workflow,
    WorkflowBuilder,
)


# ── ForEachOperator Dynamic Field Tests ──────────────────────────────────


class TestForEachDynamic:
    def test_default_dynamic_is_false(self):
        op = ForEachOperator(task_id="fe1", items="{{items}}")
        assert op.dynamic is False

    def test_dynamic_true(self):
        op = ForEachOperator(task_id="fe1", items="{{items}}", dynamic=True)
        assert op.dynamic is True

    def test_dynamic_false_explicit(self):
        op = ForEachOperator(task_id="fe1", items="{{items}}", dynamic=False)
        assert op.dynamic is False

    def test_dynamic_serialization_roundtrip(self):
        op = ForEachOperator(task_id="fe1", items="{{items}}", dynamic=True)
        data = op.model_dump(mode="json")
        restored = ForEachOperator.model_validate(data)
        assert restored.dynamic is True
        assert restored.task_id == "fe1"

    def test_dynamic_false_not_in_json_by_default(self):
        """dynamic=False should still serialize (it's explicit in the model)."""
        op = ForEachOperator(task_id="fe1", items="{{items}}", dynamic=False)
        data = op.model_dump(mode="json")
        assert "dynamic" in data

    def test_dynamic_with_parallel(self):
        op = ForEachOperator(
            task_id="fe1", items="{{items}}", dynamic=True, parallel=True,
        )
        assert op.dynamic is True
        assert op.parallel is True

    def test_dynamic_in_workflow_builder(self):
        builder = WorkflowBuilder("dynamic_test")
        builder.foreach(
            "process_items",
            items="{{items}}",
            loop_body=lambda b: b.task("process", "tools.noop"),
            dynamic=True,
        )
        wf = builder.build()
        fe = wf.tasks["process_items"]
        assert isinstance(fe, ForEachOperator)
        assert fe.dynamic is True

    def test_dynamic_in_workflow_json_roundtrip(self):
        builder = WorkflowBuilder("dynamic_json_test")
        builder.foreach(
            "loop",
            items="{{data}}",
            loop_body=lambda b: b.task("step", "tools.noop"),
            dynamic=True,
        )
        wf = builder.build()
        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        fe = restored.tasks["loop"]
        assert isinstance(fe, ForEachOperator)
        assert fe.dynamic is True


# ── Workflow Deadline Tests ──────────────────────────────────────────────


class TestWorkflowDeadline:
    def test_default_no_deadline(self):
        wf = Workflow(name="test_wf")
        assert wf.deadline_seconds is None
        assert wf.deadline_action == "fail"

    def test_deadline_seconds_set(self):
        wf = Workflow(name="test_wf", deadline_seconds=3600)
        assert wf.deadline_seconds == 3600

    def test_deadline_action_fail(self):
        wf = Workflow(name="test_wf", deadline_seconds=60, deadline_action="fail")
        assert wf.deadline_action == "fail"

    def test_deadline_action_cancel(self):
        wf = Workflow(name="test_wf", deadline_seconds=60, deadline_action="cancel")
        assert wf.deadline_action == "cancel"

    def test_deadline_action_invalid_rejected(self):
        with pytest.raises(ValueError, match="deadline_action must be one of"):
            Workflow(name="test_wf", deadline_seconds=60, deadline_action="abort")

    def test_deadline_seconds_zero_rejected(self):
        with pytest.raises(ValueError, match="deadline_seconds must be positive"):
            Workflow(name="test_wf", deadline_seconds=0)

    def test_deadline_seconds_negative_rejected(self):
        with pytest.raises(ValueError, match="deadline_seconds must be positive"):
            Workflow(name="test_wf", deadline_seconds=-10)

    def test_deadline_action_without_seconds_allowed(self):
        """deadline_action can be set even without deadline_seconds (no-op)."""
        wf = Workflow(name="test_wf", deadline_action="cancel")
        assert wf.deadline_seconds is None
        assert wf.deadline_action == "cancel"

    def test_deadline_serialization_roundtrip(self):
        wf = Workflow(
            name="test_wf",
            deadline_seconds=1800,
            deadline_action="cancel",
        )
        data = wf.model_dump(mode="json")
        restored = Workflow.model_validate(data)
        assert restored.deadline_seconds == 1800
        assert restored.deadline_action == "cancel"

    def test_deadline_json_roundtrip(self):
        builder = WorkflowBuilder("deadline_test")
        builder.task("step1", "tools.noop")
        wf = builder.build()
        # Manually set deadline (builder doesn't have a method yet)
        wf.deadline_seconds = 600
        wf.deadline_action = "fail"
        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        assert restored.deadline_seconds == 600
        assert restored.deadline_action == "fail"

    def test_deadline_none_serialization(self):
        wf = Workflow(name="test_wf")
        data = wf.model_dump(mode="json")
        assert data["deadline_seconds"] is None
        assert data["deadline_action"] == "fail"


# ── Builder Deadline Support Tests ───────────────────────────────────────


class TestBuilderDeadline:
    def test_builder_with_deadline(self):
        builder = WorkflowBuilder(
            "deadline_wf",
            deadline_seconds=300,
            deadline_action="fail",
        )
        builder.task("t1", "tools.noop")
        wf = builder.build()
        assert wf.deadline_seconds == 300
        assert wf.deadline_action == "fail"

    def test_builder_deadline_cancel(self):
        builder = WorkflowBuilder(
            "deadline_wf",
            deadline_seconds=600,
            deadline_action="cancel",
        )
        builder.task("t1", "tools.noop")
        wf = builder.build()
        assert wf.deadline_seconds == 600
        assert wf.deadline_action == "cancel"

    def test_builder_no_deadline(self):
        builder = WorkflowBuilder("no_deadline_wf")
        builder.task("t1", "tools.noop")
        wf = builder.build()
        assert wf.deadline_seconds is None


# ── Integration: Phase 2 Features Combined ───────────────────────────────


class TestPhase2Integration:
    def test_dynamic_foreach_with_deadline(self):
        builder = WorkflowBuilder(
            "combined_test",
            deadline_seconds=900,
            deadline_action="cancel",
        )
        builder.foreach(
            "process_dynamic",
            items="{{items}}",
            loop_body=lambda b: b.task("handle", "tools.noop"),
            dynamic=True,
        )
        wf = builder.build()
        assert wf.deadline_seconds == 900
        fe = wf.tasks["process_dynamic"]
        assert isinstance(fe, ForEachOperator)
        assert fe.dynamic is True

        # Full JSON roundtrip
        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        assert restored.deadline_seconds == 900
        assert restored.deadline_action == "cancel"
        fe2 = restored.tasks["process_dynamic"]
        assert fe2.dynamic is True
