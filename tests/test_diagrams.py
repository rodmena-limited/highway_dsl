from highway_dsl.workflow_dsl import (
    WorkflowBuilder,
)

def test_simple_diagram_generation():
    builder = WorkflowBuilder("simple")
    builder.task("t1", "tools.shell.run", description="Task 1")
    builder.task("t2", "tools.shell.run", description="Task 2")
    workflow = builder.build()
    
    mermaid = workflow.to_mermaid()
    assert "stateDiagram-v2" in mermaid
    assert 'state "Task 1" as t1' in mermaid
    assert "t1 --> t2" in mermaid
    assert "t2 --> [*]" in mermaid

    dot = workflow.to_graphviz()
    assert "digraph workflow" in dot
    assert 'label="Task 1"' in dot
    assert "t1 -> t2;" in dot

def test_parallel_diagram_generation():
    builder = WorkflowBuilder("parallel")
    
    builder.parallel(
        "fork",
        branches={
            "branch_a": lambda b: b.task("a1", "cmd"),
            "branch_b": lambda b: b.task("b1", "cmd"),
        }
    )
    
    workflow = builder.build()
    mermaid = workflow.to_mermaid()
    
    # Check for composite state
    assert 'state "fork" as fork {' in mermaid
    assert 'state "branch_a" as fork_branch_a {' in mermaid
    assert 'state "a1" as a1' in mermaid
    
    # Check for class assignment
    assert "class fork parallel" in mermaid

    dot = workflow.to_graphviz()
    assert "subgraph cluster_fork {" in dot
    assert "subgraph cluster_fork_branch_a {" in dot
    assert 'label="branch_a";' in dot

def test_loops_diagram_generation():
    builder = WorkflowBuilder("loops")
    
    builder.foreach(
        "process_items",
        items="{{items}}",
        loop_body=lambda b: b.task("process", "cmd")
    )
    
    workflow = builder.build()
    mermaid = workflow.to_mermaid()
    
    assert 'state "process_items (ForEach)" as process_items {' in mermaid
    assert 'state "process" as process' in mermaid
    assert "class process_items loop" in mermaid

    dot = workflow.to_graphviz()
    assert "subgraph cluster_process_items {" in dot
    assert 'label="process_items Loop";' in dot

def test_conditional_diagram_generation():
    builder = WorkflowBuilder("cond")
    
    builder.condition(
        "check",
        condition="x > 10",
        if_true=lambda b: b.task("true_op", "cmd"),
        if_false=lambda b: b.task("false_op", "cmd")
    )
    
    workflow = builder.build()
    mermaid = workflow.to_mermaid()
    
    assert "check --> true_op : True" in mermaid
    assert "check --> false_op : False" in mermaid
    assert "class check condition" in mermaid
    
    dot = workflow.to_graphviz()
    assert 'check -> true_op [label="True"' in dot
    assert 'check -> false_op [label="False"' in dot

def test_switch_diagram_generation():
    builder = WorkflowBuilder("sw")
    
    builder.task("t1", "cmd")
    builder.task("c1", "cmd")
    builder.task("c2", "cmd")
    builder.task("def", "cmd")
    
    builder.switch(
        "route",
        switch_on="{{val}}",
        cases={"a": "c1", "b": "c2"},
        default="def",
        dependencies=["t1"]
    )
    
    workflow = builder.build()
    mermaid = workflow.to_mermaid()
    
    assert "route --> c1 : a" in mermaid
    assert "route --> c2 : b" in mermaid
    assert "route --> def : Default" in mermaid
    
    dot = workflow.to_graphviz()
    assert 'route -> c1 [label="a"];' in dot
    assert 'route -> def [label="Default"' in dot

def test_reflexive_diagram_generation():
    builder = WorkflowBuilder("reflexive_wf")
    builder.reflexive(
        "gen",
        generator="gen_tool",
        verifier="ver_tool"
    )
    
    workflow = builder.build()
    mermaid = workflow.to_mermaid()
    
    assert 'state "gen (Reflexive)" as gen' in mermaid
    assert "class gen reflexive" in mermaid
    
    dot = workflow.to_graphviz()
    assert 'fillcolor="#ff00ff"' in dot

def test_sanitization():
    builder = WorkflowBuilder("sanitize")
    builder.task("my-task:1.0", "cmd", description='Task "quote"')
    
    workflow = builder.build()
    mermaid = workflow.to_mermaid()
    
    assert "my_task_1_0" in mermaid
    assert "Task 'quote'" in mermaid # Quotes replaced
    
    dot = workflow.to_graphviz()
    assert "my_task_1_0" in dot
    assert 'label="Task \"quote\""' in dot # Quotes escaped

