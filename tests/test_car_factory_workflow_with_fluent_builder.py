from datetime import timedelta
from pathlib import Path

import yaml

from highway_dsl import (
    RetryPolicy,
    TimeoutPolicy,
    WorkflowBuilder,
)


def create_vehicle_sub_workflow_builder(builder: WorkflowBuilder) -> WorkflowBuilder:
    """
    Defines the sub-workflow for building a single vehicle.
    This workflow is built fluently using the new builder features.
    """

    # 1. Get detailed specs for the specific vehicle
    builder.task(
        "check_vehicle_specs",
        "factory.mes.get_specs_for_vin",
        args=["{{item.vin}}"],  # 'item' is the context from the ForEach loop
        result_key="specs",
    )

    # 2. Conditional: Is this an EV or an ICE car? (Uses new fluent builder)
    builder.condition(
        "route_by_drivetrain",
        condition="{{specs.drivetrain_type}} == 'EV'",
        if_true=lambda b: b.task(
            "build_ev_drivetrain",
            "factory.assembly.build_battery_and_motor",
            args=["{{specs.battery_sku}}", "{{specs.motor_sku}}"],
            result_key="drivetrain_assembly",
        ),
        if_false=lambda b: b.task(
            "build_ice_drivetrain",
            "factory.assembly.build_engine_and_transmission",
            args=["{{specs.engine_sku}}", "{{specs.transmission_sku}}"],
            result_key="drivetrain_assembly",
        ),
    )

    # 3. Parallel Assembly (Uses new fluent builder)
    # This automatically depends on the 'route_by_drivetrain' conditional.
    builder.parallel(
        "parallel_main_assembly",
        branches={
            "frame_build": lambda b: b.task(
                "weld_frame",
                "factory.robotics.weld_chassis",
                args=["{{specs.frame_model}}"],
            ).task("prime_frame", "factory.robotics.apply_primer"),
            "electronics_build": lambda b: b.task(
                "assemble_electronics_harness",
                "factory.assembly.build_electronics",
                args=["{{specs.electronics_package}}"],
            ),
            "drivetrain_prep": lambda b: b.task(
                "mount_drivetrain_subassembly",
                "factory.assembly.prep_drivetrain_for_marriage",
                args=["{{drivetrain_assembly}}"],
            ),
        },
    )

    # 4. Synchronization (Fan-In): "Marriage" of parts
    # This task automatically depends on all branches of the parallel step.
    builder.task(
        "final_assembly",
        "factory.assembly.final_marriage",
        args=["{{item.vin}}"],
        dependencies=[
            "prime_frame",
            "assemble_electronics_harness",
            "mount_drivetrain_subassembly",
        ],
        result_key="assembled_vehicle",
    )

    # 5. Paint and Initial QA
    builder.task(
        "paint_vehicle",
        "factory.robotics.paint_body",
        args=["{{assembled_vehicle}}", "{{specs.color}}"],
    )
    builder.task(
        "begin_qa_inspection",
        "human.qa.inspect_vehicle",
        args=["{{item.vin}}"],
        result_key="qa_report",  # e.g., {"passed": false, "issues": [...]}
        dependencies=["paint_vehicle"],
        timeout_policy=TimeoutPolicy(timeout=timedelta(hours=2), kill_on_timeout=True),
    )

    # 6. QA Rework (Uses new WhileLoop operator)
    # This replaces the complex, limited conditional logic from before.
    builder.while_loop(
        "qa_rework_loop",
        condition="{{qa_report.passed}} == false",
        loop_body=lambda b: b.task(
            "perform_rework",
            "human.rework.fix_issues",
            args=["{{item.vin}}", "{{qa_report.issues}}"],
            result_key="rework_report",
        ).task(
            "re_inspect_vehicle",
            "human.qa.inspect_rework",
            args=["{{item.vin}}", "{{rework_report}}"],
            result_key="qa_report",  # Critically, this updates the loop variable
        ),
    )

    # 7. Mark as complete (depends on the while_loop finishing)
    builder.task(
        "mark_vehicle_complete",
        "factory.mes.update_status",
        args=["{{item.vin}}", "BUILT"],
        dependencies=["qa_rework_loop"],
    )

    return builder


def demonstrate_car_factory_workflow():
    """
    Defines the main car factory workflow, integrating the
    vehicle sub-workflow with the ForEach operator.
    """

    # 1. Define the main workflow builder
    main_builder = WorkflowBuilder("car_factory_build_v2")
    main_builder.task(
        "get_build_manifest",
        "factory.erp.get_daily_build_manifest",
        result_key="manifest",
        retry_policy=RetryPolicy(max_retries=5, delay=timedelta(minutes=1)),
    )

    # 2. Use the fluent ForEach operator
    main_builder.foreach(
        "build_vehicle_loop",
        items="{{manifest.vehicles}}",
        loop_body=lambda b: create_vehicle_sub_workflow_builder(b),
    )

    # 5. Add final aggregation steps
    #    These depend on the *entire loop* finishing.
    main_builder.task(
        "generate_shipping_labels",
        "factory.logistics.print_labels_for_manifest",
        args=["{{manifest.id}}", "{{build_vehicle_loop_results}}"],
        result_key="shipping_labels",
        dependencies=["build_vehicle_loop"],
    )
    main_builder.task(
        "notify_logistics",
        "factory.erp.notify_logistics_of_completion",
        args=["{{manifest.id}}"],
        dependencies=["generate_shipping_labels"],
    )

    workflow = main_builder.build()
    workflow.set_variables(
        {"erp_api_key": "secret_abc_123", "mes_endpoint": "http://10.0.0.5/api"},
    )

    return workflow


def extract_yaml_content(content):
    """Extract only the YAML portion from the output file"""
    lines = content.split("\n")

    # The YAML content starts after the header line and ends before the footer
    # Header: "--- CAR FACTORY WORKFLOW YAML (FLUENT + WHILE LOOP) ---" at line 0
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
        if line == "---------------------------------------------":
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
                == "---------------------------------------------"
            ):
                yaml_end -= 1
            break

    # Extract and return the YAML content
    yaml_content = "\n".join(lines[yaml_start:yaml_end])
    return yaml_content.strip()


def test_car_factory_workflow_with_fluent_builder():
    """Test the car factory workflow with fluent builder generates expected YAML"""
    workflow = demonstrate_car_factory_workflow()
    generated_yaml = workflow.to_yaml()
    generated_data = yaml.safe_load(generated_yaml)

    # Load expected output
    expected_file = (
        Path(__file__).parent / "data" / "car_factory_workflow_with_fluent_builder.yaml"
    )
    with open(expected_file) as f:
        content = f.read()
        expected_content = extract_yaml_content(content)
        expected_data = yaml.safe_load(expected_content)

    # Compare the structure and key elements
    assert generated_data["name"] == expected_data["name"]
    assert len(generated_data["tasks"]) == len(expected_data["tasks"])

    # Check that certain key tasks exist
    assert "get_build_manifest" in generated_data["tasks"]
    assert "build_vehicle_loop" in generated_data["tasks"]
    assert "check_vehicle_specs" in generated_data["tasks"]
    assert "route_by_drivetrain" in generated_data["tasks"]
    assert "mark_vehicle_complete" in generated_data["tasks"]
    assert generated_data["tasks"]["get_build_manifest"]["operator_type"] == "task"
    assert generated_data["tasks"]["build_vehicle_loop"]["operator_type"] == "foreach"
    assert (
        generated_data["tasks"]["route_by_drivetrain"]["operator_type"] == "condition"
    )

    # Validate the generated YAML matches expected (ignoring the header)
    assert generated_data["name"] == expected_data["name"]
    assert generated_data["version"] == expected_data["version"]
    assert set(generated_data["tasks"].keys()) == set(expected_data["tasks"].keys())


if __name__ == "__main__":
    test_car_factory_workflow_with_fluent_builder()
