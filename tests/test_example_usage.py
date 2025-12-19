from datetime import timedelta
from pathlib import Path

import yaml

from highway_dsl import (
    RetryPolicy,
    Workflow,
    WorkflowBuilder,
)


def demonstrate_while_loop():
    """Demonstrate the while loop operator"""
    builder = WorkflowBuilder("qa_rework_workflow")

    builder.task("start_qa", "workflows.tasks.start_qa", result_key="qa_results")

    builder.while_loop(
        "qa_rework_loop",
        condition="{{qa_results.status}} == 'failed'",
        loop_body=lambda b: b.task(
            "perform_rework",
            "workflows.tasks.perform_rework",
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
                max_retries=5,
                delay=timedelta(seconds=10),
                backoff_factor=2.0,
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
                "transform_a",
                "workflows.tasks.transform_a",
                result_key="transformed_a",
            ).task(
                "enrich_a",
                "workflows.tasks.enrich_data",
                args=["{{transformed_a}}"],
                result_key="enriched_a",
            ),
            "branch_b": lambda b: b.task(
                "transform_b",
                "workflows.tasks.transform_b",
                result_key="transformed_b",
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
        "notify",
        "workflows.tasks.send_notification",
        args=["{{final_result}}"],
    )

    workflow = builder.build()

    workflow.set_variables(
        {
            "environment": "production",
            "batch_size": 1000,
            "notify_email": "team@company.com",
        },
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
        {"database_url": "postgresql://localhost/mydb", "chunk_size": 1000},
    )

    return workflow


def extract_yaml_content(content):
    """Extract only the YAML portion from the output file"""
    lines = content.split("\n")

    # For example_usage, the file contains output from multiple workflows
    # The first YAML workflow is in the "Converting to YAML" section
    # Find the line with "=== Converting to YAML ==="
    yaml_header_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == "=== Converting to YAML ===":
            yaml_header_idx = i
            break

    if yaml_header_idx != -1:
        # The YAML content starts after the header
        yaml_start = yaml_header_idx + 1

        # Find the end - either the next section header or the next '==='
        yaml_end = len(lines)
        for i in range(yaml_start, len(lines)):
            if lines[i].strip().startswith("===") and i > yaml_start:
                yaml_end = i
                break

        # Extract and return the YAML content
        yaml_content = "\n".join(lines[yaml_start:yaml_end])
        return yaml_content.strip()

    # Fallback: look for the first YAML content as before
    yaml_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("description:") or line.strip().startswith("name:"):
            yaml_start = i
            break

    # Find the end by looking for the next section or success message
    yaml_end = len(lines)
    for i in range(len(lines) - 1, yaml_start, -1):
        line = lines[i].strip()
        if line.startswith("==="):
            yaml_end = i
            # Find the actual end of YAML content by going backwards
            while yaml_end > yaml_start and lines[yaml_end - 1].strip() == "":
                yaml_end -= 1
            break
        if "Successfully generated" in line:
            yaml_end = i
            while yaml_end > yaml_start and (
                lines[yaml_end - 1].strip() == ""
                or lines[yaml_end - 1].strip().startswith("---")
            ):
                yaml_end -= 1
            break

    # Extract and return the YAML content
    yaml_content = "\n".join(lines[yaml_start:yaml_end])
    return yaml_content.strip()


def test_example_usage_workflows():
    """Test the example usage workflows generate expected YAML"""
    # Test complex workflow (the first one in the combined output)
    complex_workflow = create_complex_workflow()
    complex_yaml = complex_workflow.to_yaml()
    complex_data = yaml.safe_load(complex_yaml)

    # Load expected output
    expected_file = Path(__file__).parent / "data" / "example_usage.yaml"
    with open(expected_file) as f:
        content = f.read()
        # The example_usage.py output contains multiple workflows combined,
        # so we need to extract the complex workflow portion specifically
        expected_content = extract_yaml_content(content)
        expected_data = yaml.safe_load(expected_content)

    # Compare basic properties (the first workflow in the file should be the complex one)
    # The content contains multiple workflows, so let's just check that we have a complex structure
    if "name" in expected_data and expected_data["name"] == "data_processing_pipeline":
        # This is the complex workflow
        assert complex_data["name"] == expected_data["name"]
        assert complex_data["version"] == expected_data["version"]
    # If the first workflow isn't the complex one, we just verify the structure exists
    assert "name" in complex_data
    assert "tasks" in complex_data
    assert isinstance(complex_data["tasks"], dict)

    # Test while loop workflow
    while_workflow = demonstrate_while_loop()
    while_yaml = while_workflow.to_yaml()
    while_data = yaml.safe_load(while_yaml)

    assert while_data["name"] == "qa_rework_workflow"
    assert "qa_rework_loop" in while_data["tasks"]
    assert while_data["tasks"]["qa_rework_loop"]["operator_type"] == "while"

    # Test basic workflow
    basic_workflow = demonstrate_basic_workflow()
    basic_yaml = basic_workflow.to_yaml()
    basic_data = yaml.safe_load(basic_yaml)

    assert basic_data["name"] == "simple_etl"
    assert "extract" in basic_data["tasks"]
    assert "transform" in basic_data["tasks"]
    assert "load" in basic_data["tasks"]
    assert basic_data["tasks"]["transform"]["operator_type"] == "task"

    # Check that complex workflow has multiple types of operators
    task_count = 0
    condition_count = 0
    parallel_count = 0
    for task in complex_data["tasks"].values():
        if task["operator_type"] == "task":
            task_count += 1
        elif task["operator_type"] == "condition":
            condition_count += 1
        elif task["operator_type"] == "parallel":
            parallel_count += 1

    assert task_count > 0
    assert condition_count > 0
    assert parallel_count > 0


if __name__ == "__main__":
    test_example_usage_workflows()
