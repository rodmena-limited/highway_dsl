from highway_dsl.workflow_dsl import (
    OperatorType,
    ReflexiveOperator,
    Workflow,
    WorkflowBuilder,
)


def test_reflexive_operator_init():
    """Test direct initialization of ReflexiveOperator."""
    op = ReflexiveOperator(
        task_id="reflexive_task",
        generator="tools.llm.call",
        generator_kwargs={"model": "gpt-4"},
        verifier="tools.python.run",
        verifier_kwargs={"timeout": 30},
        max_turns=5,
        correction_prompt_template="Fix the code: {code}",
        description="A reflexive loop task",
    )

    assert op.task_id == "reflexive_task"
    assert op.operator_type == OperatorType.REFLEXIVE
    assert op.generator == "tools.llm.call"
    assert op.generator_kwargs == {"model": "gpt-4"}
    assert op.verifier == "tools.python.run"
    assert op.verifier_kwargs == {"timeout": 30}
    assert op.max_turns == 5
    assert op.correction_prompt_template == "Fix the code: {code}"
    assert op.description == "A reflexive loop task"


def test_reflexive_operator_defaults():
    """Test default values for ReflexiveOperator."""
    op = ReflexiveOperator(
        task_id="reflexive_task",
        generator="tools.llm.call",
        verifier="tools.python.run",
    )

    assert op.max_turns == 3
    assert op.generator_kwargs == {}
    assert op.verifier_kwargs == {}
    assert op.correction_prompt_template is None


def test_workflow_builder_reflexive():
    """Test adding reflexive task via WorkflowBuilder."""
    builder = WorkflowBuilder("test_workflow")
    builder.reflexive(
        task_id="gen_code",
        generator="tools.llm.call",
        generator_kwargs={
            "provider": "ollama",
            "model": "deepseek-v3.1:671b-cloud",
            "prompt": "Write fibonacci in Python",
        },
        verifier="tools.python.run",
        max_turns=4,
        description="Generate code with reflexive loop",
    )

    workflow = builder.build()

    assert "gen_code" in workflow.tasks
    task = workflow.tasks["gen_code"]
    assert isinstance(task, ReflexiveOperator)
    assert task.operator_type == OperatorType.REFLEXIVE
    assert task.generator == "tools.llm.call"
    assert task.verifier == "tools.python.run"
    assert task.max_turns == 4
    assert task.description == "Generate code with reflexive loop"
    assert task.generator_kwargs["model"] == "deepseek-v3.1:671b-cloud"


def test_reflexive_operator_serialization():
    """Test YAML serialization of ReflexiveOperator."""
    builder = WorkflowBuilder("test_workflow")
    builder.reflexive(
        task_id="reflexive_task",
        generator="my_gen",
        verifier="my_ver",
        max_turns=2,
    )
    workflow = builder.build()

    yaml_output = workflow.to_yaml()

    # Simple check if keys are present in YAML
    assert "operator_type: reflexive" in yaml_output
    assert "generator: my_gen" in yaml_output
    assert "verifier: my_ver" in yaml_output
    assert "max_turns: 2" in yaml_output

    # Test deserialization
    loaded_workflow = Workflow.from_yaml(yaml_output)
    task = loaded_workflow.tasks["reflexive_task"]
    assert isinstance(task, ReflexiveOperator)
    assert task.generator == "my_gen"
    assert task.verifier == "my_ver"
    assert task.max_turns == 2
