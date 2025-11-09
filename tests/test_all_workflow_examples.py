"""
Test suite to validate all the workflow examples work as expected
"""

from tests.test_agentic_ai_software_workflow import test_agentic_ai_software_workflow
from tests.test_car_factory_workflow import test_car_factory_workflow
from tests.test_car_factory_workflow_with_fluent_builder import (
    test_car_factory_workflow_with_fluent_builder,
)
from tests.test_complex_agentic_workflow import test_complex_agentic_workflow
from tests.test_example_usage import test_example_usage_workflows


def test_all_workflow_examples():
    """Run all workflow example tests"""
    test_car_factory_workflow()
    test_car_factory_workflow_with_fluent_builder()
    test_complex_agentic_workflow()
    test_example_usage_workflows()
    test_agentic_ai_software_workflow()


if __name__ == "__main__":
    test_all_workflow_examples()
