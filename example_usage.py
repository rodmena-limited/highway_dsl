# example_usage.py
import json
from datetime import timedelta
from highway_dsl import (
    Workflow,
    WorkflowBuilder,
    TaskOperator,
    ConditionOperator,
    ParallelOperator,
    WaitOperator,
    WhileOperator,
    RetryPolicy,
    TimeoutPolicy,
    OperatorType,
)


def demonstrate_while_loop():
    """Demonstrate the while loop operator"""
    builder = WorkflowBuilder("qa_rework_workflow")

    builder.task("start_qa", "workflows.tasks.start_qa", result_key="qa_results")

    builder.while_loop(
        "qa_rework_loop",
        condition="{{qa_results.status}} == 'failed'",
        loop_body=lambda b: b.task(
            "perform_rework", "workflows.tasks.perform_rework"
        ).task("re_run_qa", "workflows.tasks.run_qa", result_key="qa_results"),
    )

    builder.task(
        "finalize_product",
        "workflows.tasks.finalize_product",
        dependencies=["qa_rework_loop"],
    )

    workflow = builder.build()

    workflow.set_variables({"product_id": "product-123"})

    return workflow


def create_complex_workflow() -> Workflow:
    """Create a complex workflow using the Python DSL"""

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
            retry_policy=RetryPolicy(
                max_retries=5, delay=timedelta(seconds=10), backoff_factor=2.0
            ),
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
                "transform_a", "workflows.tasks.transform_a", result_key="transformed_a"
            ).task(
                "enrich_a",
                "workflows.tasks.enrich_data",
                args=["{{transformed_a}}"],
                result_key="enriched_a",
            ),
            "branch_b": lambda b: b.task(
                "transform_b", "workflows.tasks.transform_b", result_key="transformed_b"
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
        "notify", "workflows.tasks.send_notification", args=["{{final_result}}"]
    )

    workflow = builder.build()

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

    print("\n" + "=" * 50)
    print("WHILE LOOP WORKFLOW EXAMPLE")
    print("=" * 50)

    while_loop_workflow = demonstrate_while_loop()
    print(f"While loop workflow: {while_loop_workflow.name}")
    print(f"Tasks: {list(while_loop_workflow.tasks.keys())}")

    print("\nWhile loop workflow JSON:")
    print(while_loop_workflow.to_json())
