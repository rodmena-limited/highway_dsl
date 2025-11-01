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
        WhileOperator,  # Import the new operator
        RetryPolicy,
        TimeoutPolicy,
        OperatorType,
    )
except ImportError:
    print("Error: highway_dsl library not found. Please install it.")
    exit()


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
        timeout_policy=TimeoutPolicy(timeout=timedelta(hours=2)),
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
        {"erp_api_key": "secret_abc_123", "mes_endpoint": "http://10.0.0.5/api"}
    )

    return workflow


if __name__ == "__main__":
    car_factory_workflow = demonstrate_car_factory_workflow()

    print("--- CAR FACTORY WORKFLOW YAML (FLUENT + WHILE LOOP) ---")
    try:
        print(car_factory_workflow.to_yaml())
        print("-----------------------------------------------------")
        print("\n✅ Successfully generated complex factory workflow YAML.")
        print(f"Total tasks defined: {len(car_factory_workflow.tasks)}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
