from datetime import timedelta
from pathlib import Path

import yaml

from highway_dsl import (
    ConditionOperator,
    ForEachOperator,
    ParallelOperator,
    RetryPolicy,
    TaskOperator,
    TimeoutPolicy,
    WorkflowBuilder,
)


def demonstrate_car_factory_workflow():
    """
    Defines an extremely complex workflow for a car factory,
    pushing the limits of the DSL's graph capabilities.
    """

    # 1. Start with the builder for the initial task
    workflow = (
        WorkflowBuilder("car_factory_build_v1")
        .task(
            "get_build_manifest",
            "factory.erp.get_daily_build_manifest",
            result_key="manifest",
            retry_policy=RetryPolicy(max_retries=5, delay=timedelta(minutes=1)),
        )
        .build()
    )

    # 2. Add the main ForEach loop to iterate over each vehicle in the manifest
    # The 'task_chain' defines the sub-workflow for *one* vehicle.
    workflow.add_task(
        ForEachOperator(
            task_id="build_vehicle_loop",
            items="{{manifest.vehicles}}",  # e.g., [{"vin": "...", "model": "...", "type": "EV"}, ...]
            task_chain=["check_vehicle_specs"],  # Entry point for the sub-workflow
            dependencies=["get_build_manifest"],
        ),
    )

    # --- Define the "Build One Vehicle" Sub-Workflow ---
    # All tasks from here until the final 'builder.task' are part
    # of the ForEach 'task_chain', executed for each 'item'.

    # 3. Get detailed specs for the specific vehicle
    workflow.add_task(
        TaskOperator(
            task_id="check_vehicle_specs",
            function="factory.mes.get_specs_for_vin",
            args=["{{item.vin}}"],
            result_key="specs",
            # This task has no dependencies *within the chain*
            # as it is the entry point.
        ),
    )

    # 4. Conditional: Is this an EV or an ICE car?
    workflow.add_task(
        ConditionOperator(
            task_id="route_by_drivetrain",
            condition="{{specs.drivetrain_type}} == 'EV'",
            if_true="build_ev_drivetrain",
            if_false="build_ice_drivetrain",
            dependencies=["check_vehicle_specs"],
        ),
    )

    # --- Drivetrain Branches (mutually exclusive) ---
    workflow.add_task(
        TaskOperator(
            task_id="build_ev_drivetrain",
            function="factory.assembly.build_battery_and_motor",
            args=["{{specs.battery_sku}}", "{{specs.motor_sku}}"],
            result_key="drivetrain_assembly",
            dependencies=["route_by_drivetrain"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="build_ice_drivetrain",
            function="factory.assembly.build_engine_and_transmission",
            args=["{{specs.engine_sku}}", "{{specs.transmission_sku}}"],
            result_key="drivetrain_assembly",
            dependencies=["route_by_drivetrain"],
        ),
    )

    # 5. Parallel Assembly: Build frame, electronics, and run diagnostics
    #    This is a "fan-in-fan-out". It waits for *either* drivetrain
    #    branch to finish, then fans out to 3 parallel tracks.
    workflow.add_task(
        ParallelOperator(
            task_id="parallel_main_assembly",
            branches={
                "frame_build": ["weld_frame", "prime_frame"],
                "electronics_build": ["assemble_electronics_harness"],
                "drivetrain_prep": ["mount_drivetrain_subassembly"],
            },
            # This task depends on *both* conditional outcomes.
            # Since only one will run, the dependency logic in the
            # engine must be "run if at least one dependency is met"
            # (or, more simply, it depends on the *drivetrain_assembly*
            # result, which is output by both tasks).
            # For simplicity, we'll depend on the tasks themselves.
            dependencies=["build_ev_drivetrain", "build_ice_drivetrain"],
        ),
    )

    # --- Tasks inside the Parallel Branches ---
    workflow.add_task(
        TaskOperator(
            task_id="weld_frame",
            function="factory.robotics.weld_chassis",
            args=["{{specs.frame_model}}"],
            dependencies=["parallel_main_assembly"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="prime_frame",
            function="factory.robotics.apply_primer",
            dependencies=["weld_frame"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="assemble_electronics_harness",
            function="factory.assembly.build_electronics",
            args=["{{specs.electronics_package}}"],
            dependencies=["parallel_main_assembly"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="mount_drivetrain_subassembly",
            function="factory.assembly.prep_drivetrain_for_marriage",
            args=["{{drivetrain_assembly}}"],
            dependencies=["parallel_main_assembly"],
        ),
    )

    # 6. Synchronization (Fan-In): "Marriage" of parts
    #    Waits for all parallel branches to complete.
    workflow.add_task(
        TaskOperator(
            task_id="final_assembly",
            function="factory.assembly.final_marriage",
            args=["{{item.vin}}"],
            dependencies=[
                "prime_frame",  # End of frame_build branch
                "assemble_electronics_harness",  # End of electronics_build
                "mount_drivetrain_subassembly",  # End of drivetrain_prep
            ],
            result_key="assembled_vehicle",
        ),
    )

    # 7. Paint the fully assembled body
    workflow.add_task(
        TaskOperator(
            task_id="paint_vehicle",
            function="factory.robotics.paint_body",
            args=["{{assembled_vehicle}}", "{{specs.color}}"],
            dependencies=["final_assembly"],
        ),
    )

    # 8. Human-in-the-Loop Quality Assurance (with timeout)
    workflow.add_task(
        TaskOperator(
            task_id="begin_qa_inspection",
            function="human.qa.inspect_vehicle",
            args=["{{item.vin}}"],
            result_key="qa_report",
            dependencies=["paint_vehicle"],
            timeout_policy=TimeoutPolicy(timeout=timedelta(hours=2)),
        ),
    )

    # 9. QA Conditional: Did it pass?
    workflow.add_task(
        ConditionOperator(
            task_id="check_qa_results",
            condition="{{qa_report.passed}}",
            if_true="mark_vehicle_complete",  # End of this loop
            if_false="perform_rework",  # Go to rework sub-path
            dependencies=["begin_qa_inspection"],
        ),
    )

    # --- Rework Sub-Path (if QA fails) ---
    workflow.add_task(
        TaskOperator(
            task_id="perform_rework",
            function="human.rework.fix_issues",
            args=["{{item.vin}}", "{{qa_report.issues}}"],
            result_key="rework_report",
            dependencies=["check_qa_results"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="final_rework_qa",
            function="human.qa.inspect_rework",
            args=["{{item.vin}}", "{{rework_report}}"],
            result_key="final_qa_status",
            dependencies=["perform_rework"],
        ),
    )

    # 10. Final check. This demonstrates the "fixed rework attempts"
    #     limitation of a DAG.
    workflow.add_task(
        ConditionOperator(
            task_id="check_final_qa",
            condition="{{final_qa_status.passed}}",
            if_true="mark_vehicle_complete",  # Pass: End of this loop
            if_false="flag_for_manual_intervention",  # Fail: End of this loop
            dependencies=["final_rework_qa"],
        ),
    )

    # --- Loop "Sink" (End) Tasks ---
    # These tasks are the defined "ends" of the sub-workflow.
    # The ForEach operator knows an iteration is done when one of these is hit.
    workflow.add_task(
        TaskOperator(
            task_id="mark_vehicle_complete",
            function="factory.mes.update_status",
            args=["{{item.vin}}", "BUILT"],
            dependencies=["check_qa_results", "check_final_qa"],
        ),
    )
    workflow.add_task(
        TaskOperator(
            task_id="flag_for_manual_intervention",
            function="factory.mes.update_status",
            args=["{{item.vin}}", "QA_FAIL_MANUAL_HOLD"],
            dependencies=["check_final_qa"],
        ),
    )

    # --- End of "Build One Vehicle" Sub-Workflow ---

    # 11. Final Aggregation Step (after the ForEach loop)
    # Re-attach the builder to add a final step that depends
    # on the *entire loop* finishing.
    builder = WorkflowBuilder(workflow.name, existing_workflow=workflow)
    builder._current_task = "build_vehicle_loop"  # Depends on the loop itself

    workflow = (
        builder.task(
            "generate_shipping_labels",
            "factory.logistics.print_labels_for_manifest",
            args=["{{manifest.id}}", "{{build_vehicle_loop_results}}"],
            result_key="shipping_labels",
        )
        .task(
            "notify_logistics",
            "factory.erp.notify_logistics_of_completion",
            args=["{{manifest.id}}"],
        )
        .build()
    )

    workflow.set_variables(
        {"erp_api_key": "secret_abc_123", "mes_endpoint": "http://10.0.0.5/api"},
    )

    return workflow


def extract_yaml_content(content):
    """Extract only the YAML portion from the output file"""
    lines = content.split("\n")

    # The YAML content starts after the header line and ends before the footer
    # Header: "--- CAR FACTORY WORKFLOW YAML (COMPLEX) ---" at line 0
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
                or lines[yaml_end - 1].strip() == "---------------------------------------------"
            ):
                yaml_end -= 1
            break

    # Extract and return the YAML content
    yaml_content = "\n".join(lines[yaml_start:yaml_end])
    return yaml_content.strip()


def test_car_factory_workflow():
    """Test the car factory workflow generates expected YAML"""
    workflow = demonstrate_car_factory_workflow()
    generated_yaml = workflow.to_yaml()
    generated_data = yaml.safe_load(generated_yaml)

    # Load expected output
    expected_file = Path(__file__).parent / "data" / "car_factory_workflow.yaml"
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
    assert "mark_vehicle_complete" in generated_data["tasks"]
    assert generated_data["tasks"]["get_build_manifest"]["operator_type"] == "task"
    assert generated_data["tasks"]["build_vehicle_loop"]["operator_type"] == "foreach"

    # Validate the generated YAML matches expected (ignoring the header)
    assert generated_data["name"] == expected_data["name"]
    assert generated_data["version"] == expected_data["version"]
    assert set(generated_data["tasks"].keys()) == set(expected_data["tasks"].keys())


if __name__ == "__main__":
    test_car_factory_workflow()
