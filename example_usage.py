# example_usage.py
import json
from datetime import timedelta
from highway_dsl.workflow_dsl import (
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


def create_complex_workflow() -> Workflow:
    """Create a complex workflow using the Python DSL"""

    # Using the builder pattern for linear parts
    workflow = (
        WorkflowBuilder("data_processing_pipeline")
        .task("start", "workflows.tasks.initialize", result_key="init_data")
        .task(
            "validate",
            "workflows.tasks.validate_data",
            args=["{{init_data}}"],
            result_key="validated_data",
        )
        .condition(
            "check_quality",
            condition="{{validated_data.quality_score}} > 0.8",
            if_true="high_quality_processing",
            if_false="standard_processing",
        )
        .build()
    )

    # Add additional tasks that don't fit the linear flow
    workflow.add_task(
        TaskOperator(
            task_id="high_quality_processing",
            function="workflows.tasks.advanced_processing",
            args=["{{validated_data}}"],
            dependencies=["check_quality"],
            retry_policy=RetryPolicy(max_retries=5, delay=timedelta(seconds=10), backoff_factor=2.0),
            operator_type=OperatorType.TASK,
        )
    )

    workflow.add_task(
        TaskOperator(
            task_id="standard_processing",
            function="workflows.tasks.basic_processing",
            args=["{{validated_data}}"],
            dependencies=["check_quality"],
            operator_type=OperatorType.TASK,
        )
    )

    # Add parallel processing
    workflow.add_task(
        ParallelOperator(
            task_id="parallel_processing",
            branches={
                "branch_a": ["transform_a", "enrich_a"],
                "branch_b": ["transform_b", "enrich_b"],
            },
            dependencies=["high_quality_processing", "standard_processing"],
            operator_type=OperatorType.PARALLEL,
        )
    )

    # Add parallel branch tasks
    for branch in ["a", "b"]:
        workflow.add_task(
                    TaskOperator(
                        task_id=f"transform_{branch}",
                        function=f"workflows.tasks.transform_{branch}",
                        dependencies=["parallel_processing"],
                        result_key=f"transformed_{branch}",
                        operator_type=OperatorType.TASK,
                    )        )

        workflow.add_task(
                    TaskOperator(
                        task_id=f"enrich_{branch}",
                        function="workflows.tasks.enrich_data",
                        args=[f"{{{{transformed_{branch}}}}}"],
                        dependencies=[f"transform_{branch}"],
                        result_key=f"enriched_{branch}",
                        operator_type=OperatorType.TASK,
                    )        )

    # Continue with builder for the remaining linear flow
    builder = WorkflowBuilder(workflow.name, existing_workflow=workflow)
    builder._current_task = "enrich_b"
    workflow = (
        builder.task(
            "aggregate",
            "workflows.tasks.aggregate_results",
            dependencies=[
                "enrich_a",
                "enrich_b",
            ],  # Explicit dependencies for non-linear
            result_key="final_result",
        )
        .wait("wait_notification", timedelta(hours=1))
        .task("notify", "workflows.tasks.send_notification", args=["{{final_result}}"])
        .build()
    )

    workflow.set_variables(
        {
            "environment": "production",
            "batch_size": 1000,
            "notify_email": "team@company.com",
        }
    )

    return workflow


def demonstrate_basic_workflow():
    """Show a simple complete workflow using just the builder"""

    workflow = (
        WorkflowBuilder("simple_etl")
        .task("extract", "etl.extract_data", result_key="raw_data")
        .task(
            "transform",
            "etl.transform_data",
            args=["{{raw_data}}"],
            result_key="transformed_data",
        )
        .retry(max_retries=3, delay=timedelta(seconds=10))
        .task("load", "etl.load_data", args=["{{transformed_data}}"])
        .timeout(timeout=timedelta(minutes=30))
        .wait("wait_next", timedelta(hours=24))
        .task("cleanup", "etl.cleanup")
        .build()
    )

    workflow.set_variables(
        {"database_url": "postgresql://localhost/mydb", "chunk_size": 1000}
    )

    return workflow


def demonstrate_yaml_workflow():
    """Show how to create the same workflow in YAML"""

    yaml_content = """
name: simple_etl
version: 1.0.0
description: Simple ETL workflow with retry and timeout
variables:
  database_url: postgresql://localhost/mydb
  chunk_size: 1000
start_task: extract
tasks:
  extract:
    task_id: extract
    operator_type: task
    function: etl.extract_data
    result_key: raw_data
    dependencies: []
    metadata: {}
    
  transform:
    task_id: transform
    operator_type: task
    function: etl.transform_data
    args: ["{{raw_data}}"]
    result_key: transformed_data
    dependencies: ["extract"]
    retry_policy:
      max_retries: 3
      delay: 10.0
      backoff_factor: 2.0
    metadata: {}
    
  load:
    task_id: load
    operator_type: task
    function: etl.load_data
    args: ["{{transformed_data}}"]
    dependencies: ["transform"]
    timeout_policy:
      timeout: 1800.0
      kill_on_timeout: true
    metadata: {}
    
  wait_next:
    task_id: wait_next
    operator_type: wait
    wait_for: "duration:86400.0"
    dependencies: ["load"]
    metadata: {}
    
  cleanup:
    task_id: cleanup
    operator_type: task
    function: etl.cleanup
    dependencies: ["wait_next"]
    metadata: {}
"""

    workflow = Workflow.from_yaml(yaml_content)
    return workflow


def demonstrate_interoperability():
    """Show conversion between different formats"""

    print("=== Creating workflow in Python ===")
    python_workflow = demonstrate_basic_workflow()
    print(f"Workflow: {python_workflow.name}")
    print(f"Tasks: {list(python_workflow.tasks.keys())}")

    print("\n=== Converting to YAML ===")
    yaml_output = python_workflow.to_yaml()
    print(yaml_output)

    print("\n=== Converting to JSON ===")
    json_output = python_workflow.to_json()
    print(json_output)

    print("\n=== Loading from YAML ===")
    workflow_from_yaml = Workflow.from_yaml(yaml_output)
    print(f"Loaded workflow: {workflow_from_yaml.name}")

    print("\n=== Loading from JSON ===")
    workflow_from_json = Workflow.from_json(json_output)
    print(f"Loaded workflow: {workflow_from_json.name}")

    # Verify round-trip conversion
    def sort_dict_recursively(d):
        if not isinstance(d, dict):
            return d
        return {k: sort_dict_recursively(v) for k, v in sorted(d.items())}

    print("\nPython Workflow Dump:")
    python_dump = json.loads(python_workflow.model_dump_json())
    print(json.dumps(sort_dict_recursively(python_dump), indent=2))

    print("\nYAML Loaded Workflow Dump:")
    yaml_dump = json.loads(workflow_from_yaml.model_dump_json())
    print(json.dumps(sort_dict_recursively(yaml_dump), indent=2))

    print("\nJSON Loaded Workflow Dump:")
    json_dump = json.loads(workflow_from_json.model_dump_json())
    print(json.dumps(sort_dict_recursively(json_dump), indent=2))

    assert sort_dict_recursively(python_dump) == sort_dict_recursively(yaml_dump)
    assert sort_dict_recursively(python_dump) == sort_dict_recursively(json_dump)
    print("\n✅ All formats are interoperable!")


if __name__ == "__main__":

    # Run demonstrations
    demonstrate_interoperability()

    print("\n" + "=" * 50)
    print("COMPLEX WORKFLOW EXAMPLE")
    print("=" * 50)

    complex_workflow = create_complex_workflow()
    print(f"Complex workflow: {complex_workflow.name}")
    print(f"Tasks: {list(complex_workflow.tasks.keys())}")

    print("\nComplex workflow JSON:")
    print(complex_workflow.to_json())
