This is a workflow engine domain specific language (DSL) called highway_dsl.
this will be part of a larger project named highway, which is a advanced workflow engine, able to run complex DAG workflows.

This DSL is designed to define workflows in a clear and concise manner, allowing users to specify tasks, dependencies, and execution parameters.



for your information, the final highway project will have the following features:

I. Core Workflow Definition & Execution
1. Declarative Workflow DSL (Domain-Specific Language):
    * The ability to define workflows in a structured, readable format (e.g., YAML, JSON) or a Python-native DSL, separate from the business logic code.
    * This enables version control, auditing, and tooling around the workflow definitions themselves.
2. Directed Acyclic Graph (DAG) Support:
    * The fundamental model for representing tasks and their dependencies. Must support complex topologies: sequential, parallel, fan-out/fan-in.
3. Rich Task Types:
    * Simple Functions: Execute a Python function.
    * External Commands: Run shell commands or scripts.
    * HTTP Requests: Call RESTful APIs, with retry logic and authentication.
    * Sub-Workflows: Compose workflows within workflows for modularity and reusability.
    * Human Tasks: A task that pauses the workflow and waits for human input or approval via a UI.
4. Dynamic Workflows:
    * The ability to generate or modify the workflow graph at runtime based on the output of previous tasks or external data. This is crucial for handling variable-length lists or conditional paths that aren't known at design time.
5. Powerful Control Flow:
    * Conditional Branching: if/else, switch based on task outputs or workflow context.
    * Loops & Iteration: for and while loops over collections to process items.
    * Error Handling & Conditional Retrying: Specify which exceptions are retriable, with a backoff strategy (e.g., exponential backoff).
II. Execution Engine & Reliability
1. Stateful Execution with Persistence:
    * No in-memory only state. The entire state of a workflow execution (including input, output, and intermediate results) must be persisted to a durable datastore (e.g., PostgreSQL, Redis). This is non-negotiable for reliability, allowing the engine to survive crashes and restarts.
2. Exactly-Once (or At-Least-Once) Task Execution:
    * The engine must guarantee that a task is never executed more than once for the same logical operation, or it must provide idempotency mechanisms to make duplicate execution safe. This prevents double-spending or duplicate side effects.
3. Durability & Checkpointing:
    * The workflow state should be checkpointed before and after every task execution. If the worker crashes during task execution, upon restart, it should be able to resume from the last known good state.
4. Horizontally Scalable Architecture:
    * A decoupled architecture with a central orchestrator/coordinator and a pool of stateless workers. This allows you to scale the number of workers up and down based on load.
5. Pluggable Backends:
    * Support for different backend stores (e.g., PostgreSQL for strong consistency, Redis for performance) and message brokers (e.g., RabbitMQ, Redis Pub/Sub, Apache Kafka) for task queues.




read @highway_dsl.py, @example_usage.py and @output.log for more information.
This projct is the DSL part, here is what you need to do

0- remember to add any missing functionalty or features that would enhance the usability of the DSL or the workflow engine itself.
1- rewrite the model with Pydantic models to ensure data validation and serialization.
2- rewrite the usage examples to use the new Pydantic models.
3- run full unit and integration tests to ensure everything works as expected, using pytest.
4- Add a proper README.md for users.
5- run mypy to ensure type checking is properly done.
6- you need to reach 95% code coverage for the whole project.
7- use python and pip command to manage dependencies, add necessary dependencies to pyproject.toml file, but avoid heavy dependencies unless absolutely necessary.
8- make sure structure of the project is clean and follows best practices.
9- after all is done, test the whole project end to end to ensure everything is working as expected.
10- write a SUMMARY.md file to summarize the changes made and instructions for future developers.
