import yaml
from pathlib import Path


def demonstrate_car_factory_workflow():
    """Import and return the workflow from the old examples"""
    import sys
    from importlib.util import spec_from_file_location, module_from_spec

    # Load the example module
    example_path = (
        Path(__file__).parent.parent
        / "examples"
        / "old_examples"
        / "car_factory_workflow_with_fluent_builder.py"
    )
    spec = spec_from_file_location(
        "car_factory_workflow_with_fluent_builder", example_path
    )
    module = module_from_spec(spec)
    sys.modules["car_factory_workflow_with_fluent_builder"] = module
    spec.loader.exec_module(module)

    return module.demonstrate_car_factory_workflow()


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
        elif "Successfully generated" in line:
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
    with open(expected_file, "r") as f:
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
    print("✅ Car factory workflow with fluent builder test passed!")
