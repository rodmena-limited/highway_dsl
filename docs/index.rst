.. Highway DSL Documentation master file
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Highway DSL Documentation
=====================================

**Highway DSL** is a Python-based domain-specific language for defining production-grade workflows with Temporal-style coordination patterns. It is part of the larger **Highway** project, an advanced workflow engine capable of running complex DAG-based workflows with durability guarantees.

.. image:: https://badge.fury.io/py/highway-dsl.svg
   :target: https://badge.fury.io/py/highway-dsl
   :alt: PyPI version

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://img.shields.io/badge/Status-LTS%20Stable-blue
   :target: https://pypi.org/project/highway-dsl/
   :alt: LTS Stable

.. image:: https://img.shields.io/badge/Version-2.0.2-green
   :target: https://github.com/rodmena-limited/highway_dsl
   :alt: Version

.. image:: https://github.com/rodmena-limited/highway_dsl/actions/workflows/publish.yml/badge.svg
   :target: https://github.com/rodmena-limited/highway_dsl/actions/workflows/publish.yml
   :alt: Publish to PyPI

Version 2.0.2 - LTS Stable Release
------------------------------------

This is a **Long-Term Support (LTS)** release consolidating all features from the 1.x series into a stable, production-ready API. No breaking changes will be introduced in the 2.x series, making it safe for production deployments.

Key Features
------------

* **Fluent API**: A powerful and intuitive ``WorkflowBuilder`` for defining workflows programmatically
* **Pydantic-based**: All models are built on Pydantic, providing robust data validation, serialization, and documentation
* **Rich Operators**: 11 operator types for handling various workflow scenarios:

  * ``Task`` - Basic workflow steps
  * ``Activity`` - Lightweight workflow steps
  * ``Condition`` (if/else) - Conditional branching
  * ``Parallel`` - Execute multiple branches simultaneously
  * ``ForEach`` - Iterate over collections with proper dependency management
  * ``Wait`` - Pause execution for scheduled tasks
  * ``While`` - Execute loops based on conditions
  * ``EmitEvent`` - Emit events for cross-workflow coordination
  * ``WaitForEvent`` - Wait for external events with timeout
  * ``Switch`` - Multi-branch routing (switch/case)
  * ``Join`` - Temporal-style explicit coordination with join modes

* **Scheduling**: Built-in support for cron-based scheduling, start dates, and catchup configuration
* **Event-Driven**: First-class support for event emission and waiting
* **Callback Hooks**: Durable success/failure handlers as workflow nodes
* **YAML/JSON Interoperability**: Workflows can be defined in Python and exported to YAML or JSON, and vice-versa
* **Retry and Timeout Policies**: Built-in error handling and execution time management
* **Extensible**: The DSL is designed to be extensible with custom operators and policies

Quick Start
-----------

Here's a simple example of how to define a workflow using the ``WorkflowBuilder``:

.. code-block:: python

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

Installation
------------

.. code-block:: bash

   pip install highway-dsl

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
   examples
   specification

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`