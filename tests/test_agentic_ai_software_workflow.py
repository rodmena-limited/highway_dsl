from datetime import timedelta
from pathlib import Path

import yaml

from highway_dsl import (
    WorkflowBuilder,
)


def demonstrate_agentic_dev_platform_workflow():
    """
    Defines a massive, complex workflow for an AI agent that
    builds, tests, and deploys a full software platform using TDD.
    """

    builder = WorkflowBuilder("ai_agent_platform_builder_v1")

    # --- PHASE 1: SETUP & TEST GENERATION ---
    builder.task(
        "analyze_requirements",
        "llm.analyzer.ingest_specification",
        args=["{{project_spec_url}}"],
        result_key="project_plan",
    )
    builder.task(
        "setup_git_repository",
        "vcs.git.clone_and_setup_repo",
        args=["{{project_plan.repo_url}}"],
        result_key="workspace",
        dependencies=["analyze_requirements"],
    )

    # Parallel: Generate test suites for all microservices in the plan
    builder.foreach(
        "test_generation_loop",
        items="{{project_plan.microservices}}",
        loop_body=lambda fb: fb.task(
            "generate_test_stubs",
            "llm.test_generator.create_e2e_tests",
            args=["{{workspace}}", "{{item.service_name}}", "{{item.api_spec}}"],
        ).task(
            "commit_tests_to_git",
            "vcs.git.commit_files",
            args=[
                "{{workspace}}",
                "ci(tests): add initial test suite for {{item.service_name}}",
            ],
        ),
        dependencies=["setup_git_repository"],
    )

    # First test run: aggregate all failing tests to bootstrap the build loop
    builder.task(
        "run_initial_test_suite",
        "ci.run_all_tests",
        args=["{{workspace}}"],
        result_key="test_run_results",
        dependencies=["test_generation_loop"],
    )

    # --- PHASE 2: TDD BUILD & REFACTOR LOOP ---
    # This loop continues until all tests pass.
    builder.while_loop(
        "main_build_loop",
        condition="{{test_run_results.all_passed}} == false",
        loop_body=lambda wb: wb.task(
            "plan_next_coding_step",
            "llm.planner.analyze_failing_tests",
            args=["{{project_plan}}", "{{test_run_results.failing_tests}}"],
            result_key="coding_plan",  # e.g., {"action": "implement", "target": "user_api.create_user"}
        )
        .condition(
            "check_plan_action",
            condition="{{coding_plan.action}} == 'implement'",
            # IF "implement": Write new code
            if_true=lambda ib: ib.task(
                "implement_code",
                "llm.coder.write_implementation",
                args=[
                    "{{workspace}}",
                    "{{coding_plan.target}}",
                    "{{coding_plan.prompt}}",
                ],
                result_key="code_diff",
            ),
            # ELSE "refactor": Refactor existing code
            if_false=lambda rb: rb.task(
                "refactor_code",
                "llm.refactor.rewrite_code",
                args=[
                    "{{workspace}}",
                    "{{coding_plan.target}}",
                    "{{coding_plan.reason}}",
                ],
                result_key="code_diff",
            ),
        )
        .task(
            "apply_and_commit_code",
            "vcs.git.apply_and_commit",
            args=["{{workspace}}", "{{code_diff}}", "feat: {{coding_plan.target}}"],
        )
        # Re-run all tests in parallel to get the next loop's condition
        .parallel(
            "run_full_test_suite",
            branches={
                "unit": lambda b: b.task(
                    "run_unit_tests",
                    "ci.run_unit_tests",
                    args=["{{workspace}}"],
                    result_key="unit_results",
                ),
                "integration": lambda b: b.task(
                    "run_integration_tests",
                    "ci.run_integration_tests",
                    args=["{{workspace}}"],
                    result_key="int_results",
                ),
                "e2e": lambda b: b.task(
                    "run_e2e_tests",
                    "ci.run_e2e_tests",
                    args=["{{workspace}}"],
                    result_key="e2e_results",
                ),
            },
        )
        .task(
            "aggregate_test_results",
            "ci.aggregate_results",
            args=["{{unit_results}}", "{{int_results}}", "{{e2e_results}}"],
            result_key="test_run_results",  # This updates the loop condition variable
        ),
        dependencies=["run_initial_test_suite"],
    )

    # --- PHASE 3: DEPLOYMENT ---
    # This phase only starts after the main_build_loop is complete.
    builder.task(
        "provision_infrastructure",
        "iac.terraform.apply",
        args=["./terraform"],
        result_key="infra_outputs",
        dependencies=["main_build_loop"],
    )

    # Deploy all microservices in parallel using Ansible
    builder.parallel(
        "run_ansible_deployments",
        branches={
            "api": lambda b: b.task(
                "ansible_deploy_api",
                "deploy.ansible.run_playbook",
                args=["playbooks/api.yml"],
            ),
            "frontend": lambda b: b.task(
                "ansible_deploy_frontend",
                "deploy.ansible.run_playbook",
                args=["playbooks/frontend.yml"],
            ),
            "database": lambda b: b.task(
                "ansible_deploy_db",
                "deploy.ansible.run_playbook",
                args=["playbooks/database.yml"],
            ),
            "workers": lambda b: b.task(
                "ansible_deploy_workers",
                "deploy.ansible.run_playbook",
                args=["playbooks/workers.yml"],
            ),
        },
        dependencies=["provision_infrastructure"],
    )

    # Wait for services to come online
    builder.wait(
        "wait_for_services_health",
        timedelta(minutes=5),
        dependencies=["run_ansible_deployments"],
    )

    # --- PHASE 4: OBSERVABILITY & FINAL VERIFICATION ---
    # Setup monitoring and logging in parallel
    builder.parallel(
        "setup_observability",
        branches={
            "metrics": lambda b: b.task(
                "configure_prometheus",
                "observe.prometheus.apply_config",
                args=["{{infra_outputs.service_endpoints}}"],
            ),
            "logging": lambda b: b.task(
                "configure_loki",
                "observe.loki.apply_config",
                args=["{{infra_outputs.log_streams}}"],
            ),
            "tracing": lambda b: b.task(
                "configure_tempo",
                "observe.tempo.apply_config",
            ),
        },
        dependencies=["wait_for_services_health"],
    )

    # Final check: Run smoke tests AND verify observability data is flowing
    builder.task(
        "run_production_smoke_tests",
        "ci.run_smoke_tests",
        args=["{{infra_outputs.app_url}}"],
        result_key="smoke_test_results",
        dependencies=["setup_observability"],
    )
    builder.task(
        "verify_observability_data",
        "observe.prometheus.query_metrics",
        args=["{{project_plan.key_metrics}}"],
        result_key="metrics_check",
        dependencies=["run_production_smoke_tests"],
    )

    # Final step: report success
    builder.task(
        "notify_user_on_slack",
        "notify.slack.send_message",
        args=["Platform build and deployment complete. Metrics are active."],
        dependencies=["verify_observability_data"],
    )

    # Build the final workflow object
    workflow = builder.build()
    workflow.set_variables(
        {
            "project_spec_url": "http://s3.com/specs/my_project.md",
            "ci_runner_pool": "default-pool",
        },
    )

    return workflow


def extract_yaml_content(content):
    """Extract only the YAML portion from the output file"""
    lines = content.split("\n")

    # The YAML content starts after the header line and ends before the footer
    # Header: "--- AI AGENTIC DEVELOPER WORKFLOW YAML (MASSIVE) ---" at line 0
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
        if line == "---------------------------------------------------":
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
                == "---------------------------------------------------"
            ):
                yaml_end -= 1
            break

    # Extract and return the YAML content
    yaml_content = "\n".join(lines[yaml_start:yaml_end])
    return yaml_content.strip()


def test_agentic_ai_software_workflow():
    """Test the agentic AI software workflow generates expected YAML"""
    workflow = demonstrate_agentic_dev_platform_workflow()
    generated_yaml = workflow.to_yaml()
    generated_data = yaml.safe_load(generated_yaml)

    # Load expected output
    expected_file = (
        Path(__file__).parent / "data" / "test_driven_agentic_ai_software_workflow.yaml"
    )
    with open(expected_file) as f:
        content = f.read()
        expected_content = extract_yaml_content(content)
        expected_data = yaml.safe_load(expected_content)

    # Compare the structure and key elements
    assert generated_data["name"] == expected_data["name"]
    assert len(generated_data["tasks"]) == len(expected_data["tasks"])

    # Check that certain key tasks exist
    assert "analyze_requirements" in generated_data["tasks"]
    assert "test_generation_loop" in generated_data["tasks"]
    assert "main_build_loop" in generated_data["tasks"]
    assert "provision_infrastructure" in generated_data["tasks"]
    assert "run_ansible_deployments" in generated_data["tasks"]
    assert "notify_user_on_slack" in generated_data["tasks"]

    # Check operator types
    assert generated_data["tasks"]["test_generation_loop"]["operator_type"] == "foreach"
    assert generated_data["tasks"]["main_build_loop"]["operator_type"] == "while"
    assert (
        generated_data["tasks"]["run_ansible_deployments"]["operator_type"]
        == "parallel"
    )
    assert generated_data["tasks"]["analyze_requirements"]["operator_type"] == "task"

    # Validate the generated YAML matches expected (ignoring the header)
    assert generated_data["name"] == expected_data["name"]
    assert generated_data["version"] == expected_data["version"]
    assert set(generated_data["tasks"].keys()) == set(expected_data["tasks"].keys())


if __name__ == "__main__":
    test_agentic_ai_software_workflow()
