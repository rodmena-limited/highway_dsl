# Highway DSL

[![PyPI version](https://badge.fury.io/py/highway-dsl.svg)](https://badge.fury.io/py/highway-dsl)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Highway DSL** is a Python-based domain-specific language for defining complex workflows in a clear, concise, and fluent manner. It is part of the larger **Highway** project, an advanced workflow engine capable of running complex DAG-based workflows.

## Features

*   **Fluent API:** A powerful and intuitive `WorkflowBuilder` for defining workflows programmatically.
*   **Pydantic-based:** All models are built on Pydantic, providing robust data validation, serialization, and documentation.
*   **Rich Operators:** A comprehensive set of operators for handling various workflow scenarios:
    *   `Task`
    *   `Condition` (if/else)
    *   `Parallel`
    *   `ForEach`
    *   `Wait`
    *   `While`
*   **YAML/JSON Interoperability:** Workflows can be defined in Python and exported to YAML or JSON, and vice-versa.
*   **Extensible:** The DSL is designed to be extensible with custom operators and policies.

## Installation

```bash
pip install highway-dsl
```

## Quick Start

Here's a simple example of how to define a workflow using the `WorkflowBuilder`:

```python
from datetime import timedelta
from highway_dsl import WorkflowBuilder

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

print(workflow.to_yaml())
```

## Advanced Usage

### Conditional Logic

```python
from highway_dsl import WorkflowBuilder, RetryPolicy
from datetime import timedelta

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
        retry_policy=RetryPolicy(max_retries=5, delay=timedelta(seconds=10), backoff_factor=2.0),
    ),
    if_false=lambda b: b.task(
        "standard_processing",
        "workflows.tasks.basic_processing",
        args=["{{validated_data}}"],
    ),
)

workflow = builder.build()
```

### While Loops

```python
from highway_dsl import WorkflowBuilder

builder = WorkflowBuilder("qa_rework_workflow")

builder.task("start_qa", "workflows.tasks.start_qa", result_key="qa_results")

builder.while_loop(
    "qa_rework_loop",
    condition="{{qa_results.status}} == 'failed'",
    loop_body=lambda b: b.task("perform_rework", "workflows.tasks.perform_rework").task(
        "re_run_qa", "workflows.tasks.run_qa", result_key="qa_results"
    ),
)

builder.task("finalize_product", "workflows.tasks.finalize_product", dependencies=["qa_rework_loop"])

workflow = builder.build()
```

## Development

To set up the development environment:

```bash
git clone https://github.com/your-username/highway.git
cd highway
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy .
```