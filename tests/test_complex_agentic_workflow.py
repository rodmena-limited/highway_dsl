from datetime import timedelta
from pathlib import Path

import yaml

from highway_dsl import (
    ConditionOperator,
    ForEachOperator,
    ParallelOperator,
    TaskOperator,
    TimeoutPolicy,
    WorkflowBuilder,
)


def demonstrate_complex_agentic_workflow():
    """
    Defines a complex agentic workflow using the DSL's
    correct syntax, including manual graph construction.
    """

    # 1. Start with the builder for the first step
    workflow = (
        WorkflowBuilder("customer_support_agent_v2")
        .task(
            "get_pending_tasks",
            "agent.get_pending_tasks",
            result_key="task_list_obj",
        )
        .build()
    )

    # 2. Add the ForEach operator to loop over the tasks.
    # The loop_body tasks (analyze, check_review, route_by_review) are added
    # separately below. This defines the iteration structure.
    workflow.add_task(
        ForEachOperator(
            task_id="process_all_tasks",
            items="{{task_list_obj.tasks}}",
            dependencies=["get_pending_tasks"],
        ),
    )

    # --- Define the "process_one_task" sub-workflow ---
    # These tasks are part of the ForEach task_chain.
    # Note: The DSL does not seem to have a way to pass the
    # loop item ("task") to the sub-tasks automatically,
    # so we assume the execution engine handles this context.

    workflow.add_task(
        TaskOperator(
            task_id="analyze",
            function="agent.analyze_sentiment",
            args=["{{item.text}}"],  # Assuming 'item' is the loop variable
            result_key="sentiment_analysis",
            # No dependencies, as it's the start of the task_chain
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="check_review",
            function="agent.needs_human_review",
            args=["{{sentiment_analysis.sentiment}}"],
            result_key="review_check",
            dependencies=["analyze"],
        ),
    )
    # 3. Add the conditional (if/else) operator
    workflow.add_task(
        ConditionOperator(
            task_id="route_by_review",
            condition="{{review_check.review_needed}}",
            if_true="human_review_branch_start",  # ID of task to run if true
            if_false="auto_approve_branch_start",  # ID of task to run if false
            dependencies=["check_review"],
        ),
    )

    # --- Define the "auto-approve" branch ---
    workflow.add_task(
        TaskOperator(
            task_id="auto_approve_branch_start",
            function="agent.generate_response",
            args=["{{item.text}}"],
            result_key="auto_response",
            dependencies=["route_by_review"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="send_auto_response",
            function="agent.send_final_response",
            args=["{{item.id}}", "{{auto_response.response}}"],
            dependencies=["auto_approve_branch_start"],
        ),
    )

    # --- Define the "human review" branch (with parallelism) ---

    # 4. Add the Parallel operator
    workflow.add_task(
        ParallelOperator(
            task_id="human_review_branch_start",
            # Defines the parallel branches by listing the task IDs
            # that form the *end* of each branch.
            branches={
                "branch_draft": ["generate_draft"],
                "branch_docs": ["find_docs"],
            },
            dependencies=["route_by_review"],
        ),
    )
    # Define tasks *inside* the parallel branches
    workflow.add_task(
        TaskOperator(
            task_id="generate_draft",
            function="agent.generate_response",
            args=["{{item.text}}"],
            result_key="draft_response",
            dependencies=["human_review_branch_start"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="find_docs",
            function="agent.find_documentation",
            args=["{{item.text}}"],
            result_key="docs",
            dependencies=["human_review_branch_start"],
        ),
    )

    # 5. Fan-in: A task that waits for *both* parallel branches
    workflow.add_task(
        TaskOperator(
            task_id="request_approval",
            function="human.request_human_approval",
            args=["{{item}}", "{{draft_response.response}}", "{{docs.doc_url}}"],
            result_key="approval",
            dependencies=["generate_draft", "find_docs"],  # Waits for both
            timeout_policy=TimeoutPolicy(timeout=timedelta(hours=4)),
        ),
    )

    # 6. Another conditional based on human approval
    workflow.add_task(
        ConditionOperator(
            task_id="process_approval",
            condition="{{approval.approved}}",
            if_true="send_human_approved_response",
            if_false="archive_rejected_task",
            dependencies=["request_approval"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="send_human_approved_response",
            function="agent.send_final_response",
            args=["{{item.id}}", "{{approval.final_response}}"],
            dependencies=["process_approval"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="archive_rejected_task",
            function="agent.archive_task",
            args=["{{item.id}}", "Rejected by human review"],
            dependencies=["process_approval"],
        ),
    )

    # 7. Final aggregation task (fan-in for the ForEach loop)
    # We re-attach the builder to fluently add the last step.
    builder = WorkflowBuilder(workflow.name, existing_workflow=workflow)

    # Manually set the builder's last task to the ForEach operator,
    # so the next task depends on it.
    builder._current_task = "process_all_tasks"

    workflow = builder.task(
        "create_summary_report",
        "agent.create_summary_report",
        # Assumes the ForEach operator aggregates results
        args=["{{process_all_tasks_results}}"],
        result_key="final_report",
    ).build()

    workflow.set_variables({"api_key": "xyz-123", "default_user": "agent_bot"})

    return workflow


def extract_yaml_content(content):
    """Extract only the YAML portion from the output file"""
    lines = content.split("\n")

    # The YAML content starts after the header line and ends before the footer
    # Header: "--- COMPLEX AGENTIC WORKFLOW YAML (CORRECTED) ---" at line 0
    # YAML starts from line 1 (description: '')
    # Footer starts with the separator line and continues with success message

    # Find the first line that contains YAML content
    yaml_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("description:") or line.strip().startswith("name:"):
            yaml_start = i
            break

    # Find the end - look for the separator line before the footer
    yaml_end = len(lines)
    for i in range(len(lines) - 1, yaml_start, -1):
        line = lines[i].strip()
        if line == "-------------------------------------------------":
            # This is typically the start of the footer, so everything before this is YAML
            yaml_end = i
            break
        if "Successfully generated" in line:
            # Sometimes the separator might be missing, so look for the success message
            yaml_end = i
            # Then go backwards to find the actual end of YAML content
            while yaml_end > yaml_start and (
                lines[yaml_end - 1].strip() == ""
                or lines[yaml_end - 1].strip().startswith("---")
                or lines[yaml_end - 1].strip()
                == "-------------------------------------------------"
            ):
                yaml_end -= 1
            break

    # Extract and return the YAML content
    yaml_content = "\n".join(lines[yaml_start:yaml_end])
    return yaml_content.strip()


def test_complex_agentic_workflow():
    """Test the complex agentic workflow generates expected YAML"""
    workflow = demonstrate_complex_agentic_workflow()
    generated_yaml = workflow.to_yaml()
    generated_data = yaml.safe_load(generated_yaml)

    # Load expected output
    expected_file = Path(__file__).parent / "data" / "complex_agentic_workflow.yaml"
    with open(expected_file) as f:
        content = f.read()
        expected_content = extract_yaml_content(content)
        expected_data = yaml.safe_load(expected_content)

    # Compare the structure and key elements
    assert generated_data["name"] == expected_data["name"]
    assert len(generated_data["tasks"]) == len(expected_data["tasks"])

    # Check that certain key tasks exist
    assert "get_pending_tasks" in generated_data["tasks"]
    assert "process_all_tasks" in generated_data["tasks"]
    assert "analyze" in generated_data["tasks"]
    assert "route_by_review" in generated_data["tasks"]
    assert "create_summary_report" in generated_data["tasks"]
    assert generated_data["tasks"]["get_pending_tasks"]["operator_type"] == "task"
    assert generated_data["tasks"]["process_all_tasks"]["operator_type"] == "foreach"
    assert generated_data["tasks"]["route_by_review"]["operator_type"] == "condition"
    assert (
        generated_data["tasks"]["human_review_branch_start"]["operator_type"]
        == "parallel"
    )

    # Validate the generated YAML matches expected (ignoring the header)
    assert generated_data["name"] == expected_data["name"]
    assert generated_data["version"] == expected_data["version"]
    assert set(generated_data["tasks"].keys()) == set(expected_data["tasks"].keys())


if __name__ == "__main__":
    test_complex_agentic_workflow()
