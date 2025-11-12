"""
Example workflow demonstrating Highway DSL v1.1.0 features:
- Scheduling (Phase 1)
- Event-based operators (Phase 2)
- Callback hooks (Phase 3)
- Switch operator (Phase 4)
"""

from datetime import datetime, timedelta

from highway_dsl import RetryPolicy, Workflow, WorkflowBuilder


def create_scheduled_event_workflow() -> Workflow:
    """
    Demonstrates all new features in Highway DSL v1.1.0:

    1. Scheduled execution with cron
    2. Event emission and waiting
    3. Success/failure callbacks
    4. Switch/case logic
    5. Tags and metadata
    """

    # Create builder with scheduling metadata (Phase 1)
    builder = (
        WorkflowBuilder("scheduled_event_demo")
        .set_schedule("0 2 * * *")  # Run daily at 2 AM
        .set_start_date(datetime(2025, 1, 1, tzinfo=None))  # noqa: DTZ001 - Example workflow, timezone not required
        .set_catchup(False)
        .add_tags("demo", "events", "scheduled")
        .set_max_active_runs(1)
        .set_default_retry_policy(
            RetryPolicy(max_retries=2, delay=timedelta(seconds=30), backoff_factor=2.0)
        )
    )

    # Regular task
    builder.task(
        "fetch_data",
        "data.fetch",
        result_key="raw_data",
        description="Fetch data from external source",
    )

    # Task with failure callback (Phase 3)
    builder.task(
        "process_data",
        "data.process",
        args=["{{raw_data}}"],
        result_key="processed_data",
        description="Process the fetched data",
    )

    # Define failure handler task
    builder.task(
        "send_failure_alert",
        "alerts.send",
        args=["Processing failed"],
        description="Alert on processing failure",
    )

    # Set up failure callback
    builder.on_failure("send_failure_alert")

    # Switch operator (Phase 4) - route based on data quality
    builder.switch(
        "route_by_quality",
        switch_on="{{processed_data.quality}}",
        cases={
            "high": "high_quality_path",
            "medium": "medium_quality_path",
            "low": "low_quality_path",
        },
        default="unknown_quality_handler",
        description="Route based on data quality score",
    )

    # Different paths for different quality levels
    builder.task(
        "high_quality_path",
        "data.publish_premium",
        args=["{{processed_data}}"],
        dependencies=["route_by_quality"],
        description="Publish to premium channel",
    )

    builder.task(
        "medium_quality_path",
        "data.publish_standard",
        args=["{{processed_data}}"],
        dependencies=["route_by_quality"],
        description="Publish to standard channel",
    )

    builder.task(
        "low_quality_path",
        "data.publish_basic",
        args=["{{processed_data}}"],
        dependencies=["route_by_quality"],
        description="Publish to basic channel",
    )

    builder.task(
        "unknown_quality_handler",
        "errors.log_unknown_quality",
        dependencies=["route_by_quality"],
        description="Handle unknown quality score",
    )

    # Emit event (Phase 2) - notify other workflows
    builder.emit_event(
        "emit_completion",
        event_name="data_pipeline_completed",
        payload={"workflow": "scheduled_event_demo", "status": "success"},
        dependencies=[
            "high_quality_path",
            "medium_quality_path",
            "low_quality_path",
            "unknown_quality_handler",
        ],
        description="Emit completion event for downstream workflows",
    )

    # Success callback (Phase 3)
    builder.task(
        "send_success_notification",
        "notifications.send",
        args=["Pipeline completed successfully"],
        description="Notify on successful completion",
    )

    builder.on_success("send_success_notification")

    return builder.build()


def create_event_waiting_workflow() -> Workflow:
    """
    Example workflow that waits for an event from another workflow.
    Demonstrates event-based coordination (Phase 2).
    """

    builder = WorkflowBuilder("event_listener_workflow").add_tags("events", "listener")

    # Start task
    builder.task(
        "prepare",
        "workflow.prepare",
        description="Prepare for event",
    )

    # Wait for event (Phase 2) with timeout
    builder.wait_for_event(
        "wait_for_upstream",
        event_name="data_pipeline_completed",
        timeout_seconds=3600,  # 1 hour timeout
        description="Wait for upstream pipeline to complete",
    )

    # Set up failure callback for the wait_for_upstream task
    # This must be called immediately after creating the task that needs the handler
    builder.on_failure("handle_timeout")

    # Process after event received (only runs if wait_for_event succeeds)
    builder.task(
        "process_event",
        "workflow.process_event",
        args=["{{wait_for_upstream.payload}}"],
        description="Process the received event",
    )

    # Failure handler for timeout - this task should NOT depend on previous tasks
    # It's a handler that runs when wait_for_upstream fails
    builder.task(
        "handle_timeout",
        "errors.handle_timeout",
        args=["Upstream pipeline timed out"],
        description="Handle event timeout",
    )

    return builder.build()


if __name__ == "__main__":
    # Example 1: Scheduled workflow with events and callbacks
    workflow1 = create_scheduled_event_workflow()

    # Example 2: Event listener workflow
    workflow2 = create_event_waiting_workflow()
