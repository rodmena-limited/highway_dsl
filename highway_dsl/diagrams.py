from typing import List, Mapping, Set

from highway_dsl.workflow_dsl import (
    BaseOperator,
    ConditionOperator,
    EmitEventOperator,
    ForEachOperator,
    ParallelOperator,
    ReflexiveOperator,
    SwitchOperator,
    WaitForEventOperator,
    WaitOperator,
    WhileOperator,
    Workflow,
)


class DiagramGenerator:
    """Robust diagram generator for Highway DSL workflows.

    Handles:
    - Recursive nesting (Parallel, Loops)
    - Conditional branching
    - Event operators
    - Switch cases
    - Reflexive loops
    - Explicit coordination (Join)
    """

    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self._generated_ids: Set[str] = set()

    def _sanitize_id(self, name: str) -> str:
        """Sanitize a name to be safe for Mermaid/Graphviz IDs."""
        safe = (
            name.replace("-", "_").replace(" ", "_").replace(":", "_").replace(".", "_")
        )
        if safe and safe[0].isdigit():
            safe = "_" + safe
        return safe

    def to_mermaid(self) -> str:
        """Generate Mermaid stateDiagram-v2 code."""
        lines = ["stateDiagram-v2"]
        lines.append(
            '    classDef default fill:#1a1a1a,stroke:#333,stroke-width:1px,color:white,font-family:"JetBrains Mono";'
        )
        lines.append(
            "    classDef condition fill:#2c3e50,stroke:#f1c40f,stroke-width:2px,color:white;"
        )
        lines.append(
            "    classDef parallel fill:#2c3e50,stroke:#3498db,stroke-width:2px,color:white;"
        )
        lines.append(
            "    classDef loop fill:#2c3e50,stroke:#e67e22,stroke-width:2px,color:white;"
        )
        lines.append(
            "    classDef event fill:#2c3e50,stroke:#9b59b6,stroke-width:2px,color:white;"
        )
        lines.append(
            "    classDef wait fill:#2c3e50,stroke:#95a5a6,stroke-width:2px,color:white;"
        )
        lines.append(
            "    classDef error fill:#c0392b,stroke:#e74c3c,stroke-width:2px,color:white;"
        )
        lines.append(
            "    classDef reflexive fill:#2c3e50,stroke:#ff00ff,stroke-width:2px,color:white;"
        )

        # Render tasks
        self._render_mermaid_tasks(self.workflow.tasks, lines, indent=4)

        # Render dependencies
        self._render_mermaid_dependencies(self.workflow, lines, indent=4)

        return "\n".join(lines)

    def _render_mermaid_tasks(
        self, tasks: Mapping[str, BaseOperator], lines: List[str], indent: int
    ) -> None:
        prefix = " " * indent

        # Sort tasks to ensure deterministic output
        for task_id, task in sorted(tasks.items()):
            safe_id = self._sanitize_id(task_id)
            desc = task.description or task_id
            # Escape quotes in description
            desc = desc.replace('"', "'")

            if isinstance(task, ParallelOperator):
                lines.append(f'{prefix}state "{desc}" as {safe_id} {{')
                branch_names = sorted(task.branch_workflows.keys())
                for i, branch_name in enumerate(branch_names):
                    branch_wf_data = task.branch_workflows[branch_name]
                    # Convert dict back to Workflow object for easier handling if needed,
                    # or just process the dict structure which mimics Workflow

                    # We need to reconstitute operators from data to use isinstance checks
                    # Or we can write a helper to parse them.
                    # Since we are in the same process, we can use Workflow.model_validate
                    try:
                        # Create a dummy workflow to parse tasks
                        branch_wf = Workflow.model_validate(branch_wf_data)
                        branch_tasks = branch_wf.tasks
                    except Exception:
                        # Fallback if validation fails (shouldn't happen if valid)
                        branch_tasks = {}

                    lines.append(
                        f'{prefix}    state "{branch_name}" as {safe_id}_{self._sanitize_id(branch_name)} {{'
                    )
                    self._render_mermaid_tasks(branch_tasks, lines, indent + 8)

                    # Render internal dependencies for the branch
                    self._render_mermaid_dependencies(branch_wf, lines, indent + 8)

                    lines.append(f"{prefix}    }}")

                    if i < len(branch_names) - 1:
                        lines.append(f"{prefix}    --")
                lines.append(f"{prefix}}}")
                lines.append(f"{prefix}class {safe_id} parallel")

            elif isinstance(task, ForEachOperator):
                lines.append(f'{prefix}state "{desc} (ForEach)" as {safe_id} {{')
                # ForEach loop_body is a list of operators
                # We need to treat them as a mini-workflow
                dummy_tasks = {op.task_id: op for op in task.loop_body}
                self._render_mermaid_tasks(dummy_tasks, lines, indent + 4)

                # Render internal dependencies
                # We need a dummy workflow context
                dummy_wf = Workflow(
                    name="dummy",
                    tasks=dummy_tasks,
                    schedule=None,
                    start_date=None,
                    catchup=False,
                    is_paused=False,
                    max_active_runs=1,
                    default_retry_policy=None,
                )
                self._render_mermaid_dependencies(dummy_wf, lines, indent + 4)

                lines.append(f"{prefix}}}")
                lines.append(f"{prefix}class {safe_id} loop")

            elif isinstance(task, WhileOperator):
                lines.append(f'{prefix}state "{desc} (While)" as {safe_id} {{')
                dummy_tasks = {op.task_id: op for op in task.loop_body}
                self._render_mermaid_tasks(dummy_tasks, lines, indent + 4)

                dummy_wf = Workflow(
                    name="dummy",
                    tasks=dummy_tasks,
                    schedule=None,
                    start_date=None,
                    catchup=False,
                    is_paused=False,
                    max_active_runs=1,
                    default_retry_policy=None,
                )
                self._render_mermaid_dependencies(dummy_wf, lines, indent + 4)

                lines.append(f"{prefix}}}")
                lines.append(f"{prefix}class {safe_id} loop")

            elif isinstance(task, ConditionOperator):
                lines.append(f'{prefix}state "{desc}?" as {safe_id}')
                lines.append(f"{prefix}class {safe_id} condition")

            elif isinstance(task, SwitchOperator):
                lines.append(f'{prefix}state "{desc} (Switch)" as {safe_id}')
                lines.append(f"{prefix}class {safe_id} condition")

            elif isinstance(task, (EmitEventOperator, WaitForEventOperator)):
                lines.append(f'{prefix}state "{desc}" as {safe_id}')
                lines.append(f"{prefix}class {safe_id} event")

            elif isinstance(task, WaitOperator):
                lines.append(f'{prefix}state "{desc}" as {safe_id}')
                lines.append(f"{prefix}class {safe_id} wait")

            elif isinstance(task, ReflexiveOperator):
                lines.append(f'{prefix}state "{desc} (Reflexive)" as {safe_id}')
                lines.append(f"{prefix}class {safe_id} reflexive")

            else:
                lines.append(f'{prefix}state "{desc}" as {safe_id}')

            # Notes
            if task.description:
                lines.append(
                    f"{prefix}note right of {safe_id}: {task.operator_type.value}"
                )

    def _render_mermaid_dependencies(
        self, workflow: Workflow, lines: List[str], indent: int
    ) -> None:
        prefix = " " * indent
        tasks = workflow.tasks

        # Start node

        # Identify start tasks (no dependencies or start_task explicitly set)
        start_tasks = []
        if workflow.start_task and workflow.start_task in tasks:
            start_tasks.append(workflow.start_task)
        else:
            for t_id, t in tasks.items():
                if not t.dependencies:
                    start_tasks.append(t_id)

        # For sub-workflows (like loops/branches), we might not have a global start
        # If no tasks have dependencies, they are all start tasks

        for t_id in start_tasks:
            if t_id in tasks:  # Verify existence
                lines.append(f"{prefix}[*] --> {self._sanitize_id(t_id)}")

        for task_id, task in sorted(tasks.items()):
            safe_id = self._sanitize_id(task_id)

            # Standard dependencies
            for dep in sorted(task.dependencies):
                if dep in tasks:  # Ensure dep exists in this scope
                    lines.append(f"{prefix}{self._sanitize_id(dep)} --> {safe_id}")

            # Condition branches
            if isinstance(task, ConditionOperator):
                if task.if_true and task.if_true in tasks:
                    lines.append(
                        f"{prefix}{safe_id} --> {self._sanitize_id(task.if_true)} : True"
                    )
                if task.if_false and task.if_false in tasks:
                    lines.append(
                        f"{prefix}{safe_id} --> {self._sanitize_id(task.if_false)} : False"
                    )

            # Switch branches
            if isinstance(task, SwitchOperator):
                for case_val, target_id in task.cases.items():
                    if target_id in tasks:
                        lines.append(
                            f"{prefix}{safe_id} --> {self._sanitize_id(target_id)} : {case_val}"
                        )
                if task.default and task.default in tasks:
                    lines.append(
                        f"{prefix}{safe_id} --> {self._sanitize_id(task.default)} : Default"
                    )

            # Callback hooks
            if task.on_success_task_id and task.on_success_task_id in tasks:
                lines.append(
                    f"{prefix}{safe_id} --> {self._sanitize_id(task.on_success_task_id)} : On Success"
                )
            if task.on_failure_task_id and task.on_failure_task_id in tasks:
                lines.append(
                    f"{prefix}{safe_id} --> {self._sanitize_id(task.on_failure_task_id)} : On Failure"
                )

            # Check if it's a leaf node
            # A node is a leaf if no other task depends on it AND it's not a condition/switch routing to something
            is_leaf = True

            # Check if referenced by others
            for other_task in tasks.values():
                if task_id in other_task.dependencies:
                    is_leaf = False
                    break

            # Check internal routing logic (conditions/switches don't flow to [*] naturally unless they are terminals)
            if isinstance(task, ConditionOperator):
                if task.if_true or task.if_false:
                    is_leaf = False  # It flows to branches
            if isinstance(task, SwitchOperator):
                if task.cases or task.default:
                    is_leaf = False

            # Loop operators contain their own flows, but the operator itself flows to next tasks
            # If no tasks depend on the loop operator, it goes to [*]

            if is_leaf:
                lines.append(f"{prefix}{safe_id} --> [*]")

    def to_graphviz(self) -> str:
        """Generate Graphviz DOT code."""
        lines = [
            "digraph workflow {",
            "    bgcolor=transparent;",
            "    rankdir=TB;",
            '    node [shape=box, style="filled,rounded", fontname="Arial", fontsize=10, fontcolor=white, fillcolor="#1a1a1a", color="#444444", penwidth=1];',
            '    edge [fontname="Arial", fontsize=9, color="#666666", arrowsize=0.7];',
            "",
            '    start [label="START", shape=circle, fillcolor="#2ecc71", width=0.5, style=filled];',
            '    end [label="END", shape=doublecircle, fillcolor="#e74c3c", width=0.5, style=filled];',
            "",
        ]

        self._render_graphviz_tasks(self.workflow.tasks, lines, indent=4)
        self._render_graphviz_dependencies(self.workflow, lines, indent=4)

        lines.append("}")
        return "\n".join(lines)

    def _render_graphviz_tasks(
        self, tasks: Mapping[str, BaseOperator], lines: List[str], indent: int
    ) -> None:
        prefix = " " * indent

        for task_id, task in sorted(tasks.items()):
            safe_id = self._sanitize_id(task_id)
            label = self._escape_dot_label(task.description or task_id)

            attrs = f'label="{label}"'

            # Styling based on type
            if isinstance(task, ParallelOperator):
                lines.append(f"{prefix}subgraph cluster_{safe_id} {{")
                lines.append(f'{prefix}    label="{label}";')
                lines.append(f'{prefix}    style="dashed,rounded";')
                lines.append(f'{prefix}    color="#3498db";')
                lines.append(f'{prefix}    fontcolor="#3498db";')

                # Render branches as sub-clusters
                for i, (branch_name, branch_wf_data) in enumerate(
                    task.branch_workflows.items()
                ):
                    branch_safe_id = f"{safe_id}_{self._sanitize_id(branch_name)}"
                    lines.append(f"{prefix}    subgraph cluster_{branch_safe_id} {{")
                    lines.append(f'{prefix}        label="{branch_name}";')
                    lines.append(f'{prefix}        color="#95a5a6";')
                    lines.append(f'{prefix}        fontcolor="#95a5a6";')

                    try:
                        branch_wf = Workflow.model_validate(branch_wf_data)
                        self._render_graphviz_tasks(branch_wf.tasks, lines, indent + 8)
                        self._render_graphviz_dependencies(
                            branch_wf, lines, indent + 8, is_root=False
                        )
                    except Exception:
                        pass

                    lines.append(f"{prefix}    }}")

                lines.append(f"{prefix}}}")
                # Invisible node for connections to the cluster
                # Graphviz doesn't support edges to clusters well, so we point to the first node inside or a dummy
                # For simplicity, we create a node for the parallel op itself to represent the "fork" point
                lines.append(
                    f'{prefix}{safe_id} [label="FORK: {label}", shape=diamond, fillcolor="#3498db", style=filled];'
                )

            elif isinstance(task, (ForEachOperator, WhileOperator)):
                lines.append(f"{prefix}subgraph cluster_{safe_id} {{")
                lines.append(f'{prefix}    label="{label} Loop";')
                lines.append(f'{prefix}    style="dashed,rounded";')
                lines.append(f'{prefix}    color="#e67e22";')
                lines.append(f'{prefix}    fontcolor="#e67e22";')

                dummy_tasks = {op.task_id: op for op in task.loop_body}
                self._render_graphviz_tasks(dummy_tasks, lines, indent + 4)

                dummy_wf = Workflow(
                    name="dummy",
                    tasks=dummy_tasks,
                    schedule=None,
                    start_date=None,
                    catchup=False,
                    is_paused=False,
                    max_active_runs=1,
                    default_retry_policy=None,
                )
                self._render_graphviz_dependencies(
                    dummy_wf, lines, indent + 4, is_root=False
                )

                lines.append(f"{prefix}}}")
                lines.append(
                    f'{prefix}{safe_id} [label="{label}", shape=hexagon, fillcolor="#e67e22", style=filled];'
                )

            elif isinstance(task, ConditionOperator):
                lines.append(
                    f'{prefix}{safe_id} [{attrs}, shape=diamond, fillcolor="#f1c40f", fontcolor=black];'
                )

            elif isinstance(task, SwitchOperator):
                lines.append(
                    f'{prefix}{safe_id} [{attrs}, shape=diamond, fillcolor="#f1c40f", fontcolor=black];'
                )

            elif isinstance(task, (EmitEventOperator, WaitForEventOperator)):
                lines.append(
                    f'{prefix}{safe_id} [{attrs}, shape=cds, fillcolor="#9b59b6"];'
                )

            elif isinstance(task, WaitOperator):
                lines.append(
                    f'{prefix}{safe_id} [{attrs}, shape=hourglass, fillcolor="#95a5a6"];'
                )

            elif isinstance(task, ReflexiveOperator):
                lines.append(
                    f'{prefix}{safe_id} [{attrs}, shape=component, fillcolor="#ff00ff"];'
                )

            else:
                lines.append(f"{prefix}{safe_id} [{attrs}];")

    def _render_graphviz_dependencies(
        self, workflow: Workflow, lines: List[str], indent: int, is_root: bool = True
    ) -> None:
        prefix = " " * indent
        tasks = workflow.tasks

        # Start connections
        start_tasks = []
        if workflow.start_task and workflow.start_task in tasks:
            start_tasks.append(workflow.start_task)
        else:
            for t_id, t in tasks.items():
                if not t.dependencies:
                    start_tasks.append(t_id)

        if is_root:
            for t_id in start_tasks:
                if t_id in tasks:
                    lines.append(f"{prefix}start -> {self._sanitize_id(t_id)};")

        for task_id, task in sorted(tasks.items()):
            safe_id = self._sanitize_id(task_id)

            for dep in sorted(task.dependencies):
                if dep in tasks:
                    lines.append(f"{prefix}{self._sanitize_id(dep)} -> {safe_id};")

            if isinstance(task, ConditionOperator):
                if task.if_true and task.if_true in tasks:
                    lines.append(
                        f'{prefix}{safe_id} -> {self._sanitize_id(task.if_true)} [label="True", color="#2ecc71", fontcolor="#2ecc71"];'
                    )
                if task.if_false and task.if_false in tasks:
                    lines.append(
                        f'{prefix}{safe_id} -> {self._sanitize_id(task.if_false)} [label="False", color="#e74c3c", fontcolor="#e74c3c"];'
                    )

            if isinstance(task, SwitchOperator):
                for case_val, target_id in task.cases.items():
                    if target_id in tasks:
                        label = self._escape_dot_label(case_val)
                        lines.append(
                            f'{prefix}{safe_id} -> {self._sanitize_id(target_id)} [label="{label}"];'
                        )
                if task.default and task.default in tasks:
                    lines.append(
                        f'{prefix}{safe_id} -> {self._sanitize_id(task.default)} [label="Default", style=dashed];'
                    )

            # Callback hooks
            if task.on_success_task_id and task.on_success_task_id in tasks:
                lines.append(
                    f'{prefix}{safe_id} -> {self._sanitize_id(task.on_success_task_id)} [label="On Success", color="#2ecc71", style=dotted];'
                )
            if task.on_failure_task_id and task.on_failure_task_id in tasks:
                lines.append(
                    f'{prefix}{safe_id} -> {self._sanitize_id(task.on_failure_task_id)} [label="On Failure", color="#e74c3c", style=dotted];'
                )

            # End connections (only for root workflow to avoid clutter in subgraphs)
            if is_root:
                is_leaf = True
                for other_task in tasks.values():
                    if task_id in other_task.dependencies:
                        is_leaf = False
                        break
                if isinstance(task, ConditionOperator) and (
                    task.if_true or task.if_false
                ):
                    is_leaf = False
                if isinstance(task, SwitchOperator) and (task.cases or task.default):
                    is_leaf = False

                if is_leaf:
                    lines.append(f"{prefix}{safe_id} -> end;")

    def _escape_dot_label(self, label: str) -> str:
        return label.replace('"', '"')
