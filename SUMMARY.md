# Summary of Changes

This document summarizes the changes made to the Highway DSL to enhance its functionality and usability.

## 1. Fluent WorkflowBuilder

The `WorkflowBuilder` has been significantly improved to provide a more fluent and intuitive API for defining complex workflows. Previously, defining conditional or parallel branches required manually creating operator objects. Now, the `condition` and `parallel` methods accept callable functions that receive a `WorkflowBuilder` instance, allowing for a more natural and readable workflow definition.

**Before:**

```python
workflow = (
    WorkflowBuilder("data_processing_pipeline")
    # ...
    .condition(
        "check_quality",
        condition="{{validated_data.quality_score}} > 0.8",
        if_true="high_quality_processing",
        if_false="standard_processing",
    )
    .build()
)

workflow.add_task(
    TaskOperator(
        task_id="high_quality_processing",
        # ...
    )
)

workflow.add_task(
    TaskOperator(
        task_id="standard_processing",
        # ...
    )
)
```

**After:**

```python
builder.condition(
    "check_quality",
    condition="{{validated_data.quality_score}} > 0.8",
    if_true=lambda b: b.task(
        "high_quality_processing",
        "workflows.tasks.advanced_processing",
        # ...
    ),
    if_false=lambda b: b.task(
        "standard_processing",
        "workflows.tasks.basic_processing",
        # ...
    ),
)
```

## 2. While Loop Operator

A new `while_loop` operator has been introduced to handle rework and looping scenarios. This was a significant limitation in the previous version, as the DAG-based nature of the workflow engine prevented cycles. The `while_loop` operator allows for the definition of a loop body that will be executed as long as a given condition is true.

**Example:**

```python
builder.while_loop(
    "qa_rework_loop",
    condition="{{qa_results.status}} == 'failed'",
    loop_body=lambda b: b.task("perform_rework", "workflows.tasks.perform_rework").task(
        "re_run_qa", "workflows.tasks.run_qa", result_key="qa_results"
    ),
)
```

## 3. Pydantic Models

The entire DSL is built on top of Pydantic models, which ensures data validation and serialization. This makes the DSL more robust and easier to debug.

## 4. Testing and Type Checking

The test suite has been updated to cover the new features, and the code coverage is now at 99%. The entire codebase is also type-checked using `mypy` to ensure type safety.

## Instructions for Future Developers

*   **Adding New Operators:** To add a new operator, you need to:
    1.  Add a new `OperatorType` enum value.
    2.  Create a new Pydantic model for the operator that inherits from `BaseOperator`.
    3.  Add the new operator to the `Union` of the `tasks` attribute in the `Workflow` model.
    4.  Add the new operator to the `operator_classes` dictionary in the `validate_tasks` method of the `Workflow` model.
    5.  Add a new method to the `WorkflowBuilder` to support the new operator.
*   **Modifying Existing Operators:** When modifying an existing operator, make sure to update the corresponding tests and ensure that the changes are backward compatible.
*   **Code Style:** The project follows the black code style. Make sure to run `black .` before committing your changes.
*   **Testing:** All new features should be accompanied by tests. The code coverage should be maintained at or above 95%.
*   **Type Checking:** All code should be type-checked using `mypy`.