"""Tests for Phase 1 Workflow Patterns: DataGuard, MultiChoice, Terminate."""

import json

import pytest

from highway_dsl.workflow_dsl import (
    BaseOperator,
    DataGuard,
    MultiChoiceBranch,
    MultiChoiceOperator,
    OperatorType,
    TaskOperator,
    TerminateOperator,
    Workflow,
    WorkflowBuilder,
)


# ── DataGuard Model Tests ───────────────────────────────────────────────


class TestDataGuard:
    def test_basic_exists_guard(self):
        guard = DataGuard(variable="{{flight_number}}", check="exists")
        assert guard.variable == "{{flight_number}}"
        assert guard.check == "exists"
        assert guard.value is None
        assert guard.message == ""

    def test_not_null_guard(self):
        guard = DataGuard(
            variable="{{passenger_count}}",
            check="not_null",
            message="Passenger count is required",
        )
        assert guard.check == "not_null"
        assert guard.message == "Passenger count is required"

    def test_equals_guard(self):
        guard = DataGuard(
            variable="{{status}}",
            check="equals",
            value="ready",
        )
        assert guard.check == "equals"
        assert guard.value == "ready"

    def test_not_equals_guard(self):
        guard = DataGuard(
            variable="{{status}}",
            check="not_equals",
            value="cancelled",
        )
        assert guard.check == "not_equals"
        assert guard.value == "cancelled"

    def test_in_range_guard(self):
        guard = DataGuard(
            variable="{{temperature}}",
            check="in_range",
            value=[0, 100],
        )
        assert guard.check == "in_range"
        assert guard.value == [0, 100]

    def test_in_range_requires_two_element_list(self):
        with pytest.raises(ValueError, match="in_range check requires value="):
            DataGuard(variable="{{x}}", check="in_range", value=42)

    def test_in_range_requires_exactly_two_elements(self):
        with pytest.raises(ValueError, match="in_range check requires value="):
            DataGuard(variable="{{x}}", check="in_range", value=[1, 2, 3])

    def test_matches_regex_guard(self):
        guard = DataGuard(
            variable="{{flight_code}}",
            check="matches_regex",
            value=r"^[A-Z]{2}\d{3,4}$",
        )
        assert guard.check == "matches_regex"

    def test_type_check_guard(self):
        guard = DataGuard(
            variable="{{count}}",
            check="type_check",
            value="int",
        )
        assert guard.check == "type_check"

    def test_in_set_guard(self):
        guard = DataGuard(
            variable="{{gate}}",
            check="in_set",
            value=["A1", "A2", "B1", "B2"],
        )
        assert guard.check == "in_set"
        assert guard.value == ["A1", "A2", "B1", "B2"]

    def test_in_set_requires_list(self):
        with pytest.raises(ValueError, match="in_set check requires value="):
            DataGuard(variable="{{x}}", check="in_set", value="A1")

    def test_invalid_check_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid check type"):
            DataGuard(variable="{{x}}", check="greater_than", value=5)

    def test_guard_serialization_roundtrip(self):
        guard = DataGuard(
            variable="{{count}}",
            check="in_range",
            value=[1, 100],
            message="Count out of range",
        )
        data = guard.model_dump()
        restored = DataGuard.model_validate(data)
        assert restored == guard

    def test_guard_json_roundtrip(self):
        guard = DataGuard(
            variable="{{status}}",
            check="equals",
            value="active",
        )
        json_str = guard.model_dump_json()
        restored = DataGuard.model_validate_json(json_str)
        assert restored == guard


# ── BaseOperator Guard Fields Tests ──────────────────────────────────────


class TestOperatorGuards:
    def test_task_operator_default_no_guards(self):
        task = TaskOperator(task_id="t1", function="tools.noop")
        assert task.preconditions == []
        assert task.postconditions == []

    def test_task_operator_with_preconditions(self):
        guards = [
            DataGuard(variable="{{flight}}", check="exists"),
            DataGuard(variable="{{gate}}", check="not_null"),
        ]
        task = TaskOperator(
            task_id="t1",
            function="tools.noop",
            preconditions=guards,
        )
        assert len(task.preconditions) == 2
        assert task.preconditions[0].check == "exists"

    def test_task_operator_with_postconditions(self):
        guards = [
            DataGuard(variable="{{result}}", check="not_null", message="Task must produce result"),
        ]
        task = TaskOperator(
            task_id="t1",
            function="tools.noop",
            postconditions=guards,
        )
        assert len(task.postconditions) == 1

    def test_guards_survive_workflow_serialization(self):
        builder = WorkflowBuilder("guard_test")
        builder.task("t1", "tools.noop")
        builder.precondition("{{input}}", "exists", message="Input required")
        builder.postcondition("{{t1__result}}", "not_null")
        wf = builder.build()

        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        task = restored.tasks["t1"]
        assert len(task.preconditions) == 1
        assert task.preconditions[0].variable == "{{input}}"
        assert len(task.postconditions) == 1


# ── MultiChoiceOperator Tests ───────────────────────────────────────────


class TestMultiChoiceOperator:
    def test_basic_multi_choice(self):
        op = MultiChoiceOperator(
            task_id="mc1",
            branches={
                "high_priority": MultiChoiceBranch(condition="{{priority}} == 'high'"),
                "large_order": MultiChoiceBranch(condition="{{amount}} > 1000"),
            },
        )
        assert op.operator_type in (OperatorType.MULTI_CHOICE, OperatorType.MULTI_CHOICE.value)
        assert len(op.branches) == 2
        assert op.minimum_branches == 1

    def test_minimum_branches_validation(self):
        op = MultiChoiceOperator(
            task_id="mc1",
            branches={"a": MultiChoiceBranch(condition="true")},
            minimum_branches=0,
        )
        assert op.minimum_branches == 0

    def test_minimum_branches_negative_rejected(self):
        with pytest.raises(ValueError):
            MultiChoiceOperator(
                task_id="mc1",
                branches={"a": MultiChoiceBranch(condition="true")},
                minimum_branches=-1,
            )

    def test_multi_choice_serialization_roundtrip(self):
        op = MultiChoiceOperator(
            task_id="mc1",
            branches={
                "b1": MultiChoiceBranch(condition="{{x}} > 0", tasks=["t1", "t2"]),
                "b2": MultiChoiceBranch(condition="{{y}} > 0", tasks=["t3"]),
            },
            minimum_branches=1,
            timeout=300,
        )
        data = op.model_dump(mode="json")
        restored = MultiChoiceOperator.model_validate(data)
        assert restored.task_id == "mc1"
        assert len(restored.branches) == 2
        assert restored.branches["b1"].condition == "{{x}} > 0"

    def test_multi_choice_builder(self):
        builder = WorkflowBuilder("mc_test")
        builder.multi_choice(
            "route_order",
            branches={
                "high_priority": (
                    "{{priority}} == 'high'",
                    lambda b: b.task("handle_high", "tools.noop"),
                ),
                "large_order": (
                    "{{amount}} > 1000",
                    lambda b: b.task("handle_large", "tools.noop"),
                ),
            },
            minimum_branches=1,
        )
        wf = builder.build()
        assert "route_order" in wf.tasks
        mc = wf.tasks["route_order"]
        assert isinstance(mc, MultiChoiceOperator)
        assert len(mc.branches) == 2
        assert len(mc.branch_workflows) == 2

    def test_multi_choice_in_workflow_json(self):
        builder = WorkflowBuilder("mc_json_test")
        builder.multi_choice(
            "dispatch",
            branches={
                "email": (
                    "{{notify_email}}",
                    lambda b: b.task("send_email", "tools.email.send"),
                ),
                "sms": (
                    "{{notify_sms}}",
                    lambda b: b.task("send_sms", "tools.sms.send"),
                ),
            },
        )
        wf = builder.build()
        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        assert "dispatch" in restored.tasks
        mc = restored.tasks["dispatch"]
        assert isinstance(mc, MultiChoiceOperator)
        assert mc.branches["email"].condition == "{{notify_email}}"


# ── TerminateOperator Tests ──────────────────────────────────────────────


class TestTerminateOperator:
    def test_basic_terminate(self):
        op = TerminateOperator(task_id="stop")
        assert op.operator_type in (OperatorType.TERMINATE, OperatorType.TERMINATE.value)
        assert op.status == "completed"
        assert op.result == {}
        assert op.reason == ""

    def test_terminate_with_failed_status(self):
        op = TerminateOperator(
            task_id="abort",
            status="failed",
            reason="Safety check failed",
            result={"error": "critical_failure"},
        )
        assert op.status == "failed"
        assert op.reason == "Safety check failed"

    def test_terminate_with_cancelled_status(self):
        op = TerminateOperator(task_id="cancel", status="cancelled")
        assert op.status == "cancelled"

    def test_terminate_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="Terminate status must be one of"):
            TerminateOperator(task_id="bad", status="aborted")

    def test_terminate_serialization_roundtrip(self):
        op = TerminateOperator(
            task_id="stop",
            status="completed",
            result={"final_count": 42},
            reason="All processing complete",
        )
        data = op.model_dump(mode="json")
        restored = TerminateOperator.model_validate(data)
        assert restored.task_id == op.task_id
        assert restored.status == op.status
        assert restored.result == op.result
        assert restored.reason == op.reason

    def test_terminate_builder(self):
        builder = WorkflowBuilder("term_test")
        builder.task("check", "tools.noop")
        builder.terminate(
            "abort",
            status="failed",
            reason="Emergency shutdown",
            result={"code": "EMERG"},
        )
        wf = builder.build()
        assert "abort" in wf.tasks
        term = wf.tasks["abort"]
        assert isinstance(term, TerminateOperator)
        assert term.status == "failed"
        assert term.reason == "Emergency shutdown"

    def test_terminate_in_workflow_json(self):
        builder = WorkflowBuilder("term_json")
        builder.task("setup", "tools.noop")
        builder.terminate("done", status="completed", reason="Finished")
        wf = builder.build()
        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        term = restored.tasks["done"]
        assert isinstance(term, TerminateOperator)
        assert term.status == "completed"


# ── Builder Guard Chaining Tests ─────────────────────────────────────────


class TestBuilderGuardChaining:
    def test_precondition_requires_current_task(self):
        builder = WorkflowBuilder("guard_chain")
        with pytest.raises(ValueError, match="precondition.*must be called after"):
            builder.precondition("{{x}}", "exists")

    def test_postcondition_requires_current_task(self):
        builder = WorkflowBuilder("guard_chain")
        with pytest.raises(ValueError, match="postcondition.*must be called after"):
            builder.postcondition("{{x}}", "exists")

    def test_multiple_guards_chain(self):
        builder = WorkflowBuilder("multi_guard")
        builder.task("process", "tools.noop")
        builder.precondition("{{input}}", "exists")
        builder.precondition("{{input}}", "not_null")
        builder.postcondition("{{process__result}}", "not_null")
        wf = builder.build()
        task = wf.tasks["process"]
        assert len(task.preconditions) == 2
        assert len(task.postconditions) == 1

    def test_guards_on_different_tasks(self):
        builder = WorkflowBuilder("multi_task_guard")
        builder.task("t1", "tools.noop")
        builder.precondition("{{a}}", "exists")
        builder.task("t2", "tools.noop")
        builder.precondition("{{b}}", "not_null")
        wf = builder.build()
        assert len(wf.tasks["t1"].preconditions) == 1
        assert wf.tasks["t1"].preconditions[0].variable == "{{a}}"
        assert len(wf.tasks["t2"].preconditions) == 1
        assert wf.tasks["t2"].preconditions[0].variable == "{{b}}"


# ── Integration: All New Operators in One Workflow ───────────────────────


class TestPhase1Integration:
    def test_full_workflow_with_all_phase1_features(self):
        builder = WorkflowBuilder("phase1_demo", version="1.0.0")

        # Task with guards
        builder.task("validate_input", "tools.noop")
        builder.precondition("{{order_id}}", "exists", message="Order ID required")
        builder.precondition("{{order_id}}", "matches_regex", value=r"^ORD-\d+$")
        builder.postcondition("{{validate_input__result}}", "not_null")

        # Multi-choice based on conditions
        builder.multi_choice(
            "route",
            branches={
                "express": (
                    "{{priority}} == 'express'",
                    lambda b: b.task("express_ship", "tools.noop"),
                ),
                "standard": (
                    "{{priority}} == 'standard'",
                    lambda b: b.task("standard_ship", "tools.noop"),
                ),
                "international": (
                    "{{country}} != 'US'",
                    lambda b: b.task("intl_ship", "tools.noop"),
                ),
            },
            minimum_branches=1,
        )

        # Conditional termination
        builder.task("check_complete", "tools.noop")
        builder.terminate(
            "early_exit",
            status="completed",
            reason="Order shipped",
            result={"shipped": True},
        )

        wf = builder.build()
        assert len(wf.tasks) >= 4  # validate + route + check + terminate
        json_str = wf.to_json()
        restored = Workflow.from_json(json_str)
        assert len(restored.tasks) == len(wf.tasks)

    def test_operator_type_enum_values(self):
        assert OperatorType.MULTI_CHOICE.value == "multi_choice"
        assert OperatorType.TERMINATE.value == "terminate"
