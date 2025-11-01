import json
from datetime import timedelta
try:
    from highway_dsl import (
        Workflow,
        WorkflowBuilder,
        TaskOperator,
        ConditionOperator,
        ParallelOperator,
        WaitOperator,
        ForEachOperator,
        RetryPolicy,
        TimeoutPolicy,
        OperatorType,
    )
except ImportError:
    print("Error: highway_dsl library not found. Please install it.")
    exit()

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
    # This requires defining the "task_chain" (sub-workflow)
    # that will be executed for each item.
    # The task_chain IDs are: "analyze", "check_review", "route_by_review"
    workflow.add_task(
        ForEachOperator(
            task_id="process_all_tasks",
            items="{{task_list_obj.tasks}}",
            task_chain=["analyze", "check_review", "route_by_review"],
            dependencies=["get_pending_tasks"],
        )
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
            args=["{{item.text}}"], # Assuming 'item' is the loop variable
            result_key="sentiment_analysis",
            # No dependencies, as it's the start of the task_chain
        )
    )
    workflow.add_task(
        TaskOperator(
            task_id="check_review",
            function="agent.needs_human_review",
            args=["{{sentiment_analysis.sentiment}}"],
            result_key="review_check",
            dependencies=["analyze"],
        )
    )
    # 3. Add the conditional (if/else) operator
    workflow.add_task(
        ConditionOperator(
            task_id="route_by_review",
            condition="{{review_check.review_needed}}",
            if_true="human_review_branch_start", # ID of task to run if true
            if_false="auto_approve_branch_start", # ID of task to run if false
            dependencies=["check_review"],
        )
    )

    # --- Define the "auto-approve" branch ---
    workflow.add_task(
        TaskOperator(
            task_id="auto_approve_branch_start",
            function="agent.generate_response",
            args=["{{item.text}}"],
            result_key="auto_response",
            dependencies=["route_by_review"],
        )
    )
    workflow.add_task(
        TaskOperator(
            task_id="send_auto_response",
            function="agent.send_final_response",
            args=["{{item.id}}", "{{auto_response.response}}"],
            dependencies=["auto_approve_branch_start"],
        )
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
        )
    )
    # Define tasks *inside* the parallel branches
    workflow.add_task(
        TaskOperator(
            task_id="generate_draft",
            function="agent.generate_response",
            args=["{{item.text}}"],
            result_key="draft_response",
            dependencies=["human_review_branch_start"],
        )
    )
    workflow.add_task(
        TaskOperator(
            task_id="find_docs",
            function="agent.find_documentation",
            args=["{{item.text}}"],
            result_key="docs",
            dependencies=["human_review_branch_start"],
        )
    )
    
    # 5. Fan-in: A task that waits for *both* parallel branches
    workflow.add_task(
        TaskOperator(
            task_id="request_approval",
            function="human.request_human_approval",
            args=["{{item}}", "{{draft_response.response}}", "{{docs.doc_url}}"],
            result_key="approval",
            dependencies=["generate_draft", "find_docs"], # Waits for both
            timeout_policy=TimeoutPolicy(timeout=timedelta(hours=4)),
        )
    )
    
    # 6. Another conditional based on human approval
    workflow.add_task(
        ConditionOperator(
            task_id="process_approval",
            condition="{{approval.approved}}",
            if_true="send_human_approved_response",
            if_false="archive_rejected_task",
            dependencies=["request_approval"],
        )
    )
    workflow.add_task(
        TaskOperator(
            task_id="send_human_approved_response",
            function="agent.send_final_response",
            args=["{{item.id}}", "{{approval.final_response}}"],
            dependencies=["process_approval"],
        )
    )
    workflow.add_task(
        TaskOperator(
            task_id="archive_rejected_task",
            function="agent.archive_task",
            args=["{{item.id}}", "Rejected by human review"],
            dependencies=["process_approval"],
        )
    )

    # 7. Final aggregation task (fan-in for the ForEach loop)
    # We re-attach the builder to fluently add the last step.
    builder = WorkflowBuilder(workflow.name, existing_workflow=workflow)
    
    # Manually set the builder's last task to the ForEach operator,
    # so the next task depends on it.
    builder._current_task = "process_all_tasks"
    
    workflow = (
        builder.task(
            "create_summary_report",
            "agent.create_summary_report",
            # Assumes the ForEach operator aggregates results
            args=["{{process_all_tasks_results}}"],
            result_key="final_report",
        )
        .build()
    )

    workflow.set_variables(
        {"api_key": "xyz-123", "default_user": "agent_bot"}
    )
    
    return workflow


if __name__ == "__main__":
    complex_workflow = demonstrate_complex_agentic_workflow()

    print("--- COMPLEX AGENTIC WORKFLOW YAML (CORRECTED) ---")
    try:
        print(complex_workflow.to_yaml())
        print("-------------------------------------------------")
        print("\n✅ Successfully generated complex workflow YAML.")
        print(f"Total tasks defined: {len(complex_workflow.tasks)}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
