"""Graphviz DOT file generation for Highway workflows.

This module provides functionality to generate Graphviz DOT files from Highway workflow
definitions, supporting visualization of workflow structure including parallel operators,
nested workflows, and execution status.
"""

from typing import Any


def _sanitize_dot_id(name: str) -> str:
    """Sanitize name for DOT node ID.

    DOT node IDs cannot contain: colons, spaces, dots, or start with digits.
    Colons are especially problematic as they're used for port specifications.
    """
    sanitized = name.replace(":", "_").replace("-", "_").replace(".", "_").replace(" ", "_")
    sanitized = sanitized.replace("*", "x")  # Asterisks in cron expressions
    sanitized = sanitized.replace("+", "p")  # Plus signs in timestamps
    # Ensure doesn't start with digit
    if sanitized and sanitized[0].isdigit():
        sanitized = "n" + sanitized
    return sanitized


def _is_internal(name: str) -> bool:
    """Check if a task/step name is internal (should be hidden from visualization)."""
    return name.startswith(("datashard-log-", "durable_cron:"))


def generate_dot(
    workflow_definition: dict[str, Any],
    execution_steps: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a Graphviz DOT file from a workflow definition.

    Args:
        workflow_definition: Workflow definition dict (from WorkflowBuilder.build().model_dump())
        execution_steps: Optional list of execution steps with status info.
                        Each step should have: {"name": str, "status": str, "order": int}

    Returns:
        DOT file content as a string

    Example:
        >>> from highway_dsl import WorkflowBuilder
        >>> builder = WorkflowBuilder(name="example")
        >>> builder.task("task1", "tools.shell.run", args=["echo hello"])
        >>> workflow = builder.build()
        >>> dot_content = generate_dot(workflow.model_dump(mode="json"))
    """
    tasks = workflow_definition.get("tasks", {})
    start_task = workflow_definition.get("start_task")

    # Build steps dict from execution_steps
    steps_dict = {}
    if execution_steps:
        for step in execution_steps:
            step_name = step.get("name")
            if step_name:
                steps_dict[step_name] = step

    # Build map of branch task names for parallel operators (recursive)
    parallel_branch_tasks = {}  # Maps branch_task_name -> parent_parallel_task
    all_branch_task_names = set()  # All task names that are branches

    def extract_parallel_branches(tasks_dict: dict, depth: int = 0, max_depth: int = 5) -> None:
        """Recursively extract parallel branch tasks from nested workflows."""
        if depth > max_depth:
            return
        for task_name, task_def in tasks_dict.items():
            if task_def.get("operator_type") == "parallel":
                branch_workflows = task_def.get("branch_workflows", {})
                for branch_name, branch_workflow in branch_workflows.items():
                    branch_tasks = branch_workflow.get("tasks", {})
                    for branch_task_name in branch_tasks.keys():
                        parallel_branch_tasks[branch_task_name] = task_name
                        all_branch_task_names.add(branch_task_name)
                    # Recurse into nested branch tasks
                    extract_parallel_branches(branch_tasks, depth + 1, max_depth)

    extract_parallel_branches(tasks)

    # Build comprehensive task list (top-level + nested parallel operators)
    all_tasks = {}  # Maps task_name -> task_def

    def collect_all_tasks(tasks_dict: dict, depth: int = 0, max_depth: int = 5) -> None:
        """Recursively collect all tasks including nested parallel operators."""
        if depth > max_depth:
            return
        for task_name, task_def in tasks_dict.items():
            all_tasks[task_name] = task_def
            if task_def.get("operator_type") == "parallel":
                branch_workflows = task_def.get("branch_workflows", {})
                for branch_workflow in branch_workflows.values():
                    branch_tasks = branch_workflow.get("tasks", {})
                    collect_all_tasks(branch_tasks, depth + 1, max_depth)

    collect_all_tasks(tasks)

    # Group steps by their parent task
    task_names = set(all_tasks.keys())
    task_steps: dict[str, list] = {task_name: [] for task_name in task_names}

    # Assign steps to tasks
    for step_name, step_data in steps_dict.items():
        # Check if this step is a parallel branch task
        if step_name in parallel_branch_tasks:
            parent_parallel = parallel_branch_tasks[step_name]
            task_steps[parent_parallel].append(step_data)
        # Check if step name matches a task name
        elif step_name in task_names:
            task_steps[step_name].append(step_data)
        # Otherwise assign to last matched task (for ctx.step() calls)
        else:
            # Find the task this step belongs to based on execution order
            assigned = False
            for task_name in sorted(
                task_names, key=lambda t: steps_dict.get(t, {}).get("order", 99999)
            ):
                if task_name in steps_dict and steps_dict[task_name]["order"] <= step_data["order"]:
                    task_steps[task_name].append(step_data)
                    assigned = True
                    break
            if not assigned and start_task:
                task_steps[start_task].append(step_data)

    # Start building DOT content
    dot_lines = [
        "digraph workflow {",
        "    bgcolor=transparent;",
        "    rankdir=TB;",
        '    node [shape=box, style=filled, fontname="JetBrains Mono", fontsize=10, fontcolor=white, fillcolor="#000000", color="#444444", penwidth=1];',
        '    edge [fontname="JetBrains Mono", color="#666666", arrowsize=0.7];',
        "",
        "    // Start and End nodes",
        '    start [id="node-start", label="START", shape=box, fillcolor="#1a1a1a", fontcolor="#4CAF50"];',
        '    end [id="node-end", label="END", shape=box, fillcolor="#1a1a1a", fontcolor="#4CAF50"];',
        "",
    ]

    if not tasks:
        # Empty workflow
        dot_lines.append("    start -> end;")
    else:
        # Create flat nodes for each task (no clusters)
        for task_name, _task_def in all_tasks.items():
            # Skip internal tasks
            if _is_internal(task_name):
                continue

            # Skip branch tasks - they're already shown under their parent parallel operator
            # EXCEPT if they are themselves parallel operators (nested parallelism)
            if task_name in all_branch_task_names and _task_def.get("operator_type") != "parallel":
                continue

            task_id = _sanitize_dot_id(task_name)
            # Filter out internal steps
            task_step_list = [
                s for s in task_steps.get(task_name, []) if not _is_internal(s["name"])
            ]

            dot_lines.append(f"    // Task: {task_name}")

            if task_step_list:
                # Check if this is a parallel operator
                is_parallel = _task_def.get("operator_type") == "parallel"

                # Create all step nodes first
                step_ids = []
                for step in task_step_list:
                    step_name_raw = step["name"]
                    # Skip internal steps
                    if _is_internal(step_name_raw):
                        continue

                    step_id = _sanitize_dot_id(f"{task_name}_{step_name_raw}")
                    step_ids.append(step_id)

                    # All boxes: pure black fill, dark gray border, white text
                    # Note: Using title element instead of tooltip to avoid malformed SVG <a> tags
                    dot_lines.append(
                        f'    {step_id} [id="step-{step_id}", label="{step_name_raw}"];'
                    )

                # For parallel operators, use rank=same to show steps side-by-side
                if is_parallel and len(step_ids) > 1:
                    rank_line = "    {rank=same; " + "; ".join(step_ids) + ";}"
                    dot_lines.append(rank_line)
                # For sequential tasks, connect steps with arrows
                elif not is_parallel:
                    for i in range(len(step_ids) - 1):
                        dot_lines.append(f"    {step_ids[i]} -> {step_ids[i+1]};")
            else:
                # No execution yet - show placeholder
                placeholder_id = f"{task_id}_placeholder"
                dot_lines.append(
                    f'    {placeholder_id} [id="step-{placeholder_id}", label="{task_name}"];'
                )

            dot_lines.append("")

        # Add edges between tasks based on definition
        if start_task and not _is_internal(start_task):
            start_task_id = _sanitize_dot_id(start_task)
            # Find first step in start task (filtered)
            start_steps = [
                s for s in task_steps.get(start_task, []) if not _is_internal(s["name"])
            ]
            if start_steps:
                first_step_id = _sanitize_dot_id(f"{start_task}_{start_steps[0]['name']}")
                dot_lines.append(f"    start -> {first_step_id};")
            else:
                placeholder_id = f"{start_task_id}_placeholder"
                dot_lines.append(f"    start -> {placeholder_id};")

        # Connect tasks based on dependencies
        for task_name, task_def in tasks.items():
            # Skip internal tasks
            if _is_internal(task_name):
                continue
            task_id = _sanitize_dot_id(task_name)
            dependencies = task_def.get("dependencies", [])
            # Filter internal steps
            task_step_list = [
                s for s in task_steps.get(task_name, []) if not _is_internal(s["name"])
            ]

            if dependencies:
                for dep_task in dependencies:
                    # Skip internal dependency tasks
                    if _is_internal(dep_task):
                        continue
                    if dep_task in tasks:
                        # Filter internal steps from dependency
                        dep_steps = [
                            s for s in task_steps.get(dep_task, []) if not _is_internal(s["name"])
                        ]
                        # Connect last step of dependency to first step of this task
                        if dep_steps and task_step_list:
                            from_id = _sanitize_dot_id(f"{dep_task}_{dep_steps[-1]['name']}")
                            to_id = _sanitize_dot_id(f"{task_name}_{task_step_list[0]['name']}")
                            dot_lines.append(f"    {from_id} -> {to_id};")
                        elif dep_steps:
                            from_id = _sanitize_dot_id(f"{dep_task}_{dep_steps[-1]['name']}")
                            to_id = f"{task_id}_placeholder"
                            dot_lines.append(f"    {from_id} -> {to_id};")
                        elif task_step_list:
                            from_id = f"{_sanitize_dot_id(dep_task)}_placeholder"
                            to_id = _sanitize_dot_id(f"{task_name}_{task_step_list[0]['name']}")
                            dot_lines.append(f"    {from_id} -> {to_id};")

        # Connect end tasks to End node
        tasks_with_dependents = set()
        for task_def in tasks.values():
            for dep in task_def.get("dependencies", []):
                tasks_with_dependents.add(dep)

        end_tasks = [t for t in tasks if t not in tasks_with_dependents and not _is_internal(t)]
        for task_name in end_tasks:
            # Filter internal steps from task_steps_list
            task_steps_list = [
                s for s in task_steps.get(task_name, []) if not _is_internal(s["name"])
            ]
            if task_steps_list:
                last_step_id = _sanitize_dot_id(f"{task_name}_{task_steps_list[-1]['name']}")
                dot_lines.append(f"    {last_step_id} -> end;")
            else:
                placeholder_id = f"{_sanitize_dot_id(task_name)}_placeholder"
                dot_lines.append(f"    {placeholder_id} -> end;")

    dot_lines.append("}")
    return "\n".join(dot_lines)
