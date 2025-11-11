// simple_workflow.js - Basic workflow example

// Browser-compatible version (no require)
function createSimpleWorkflow() {
    const builder = new HighwayDSL.WorkflowBuilder("simple_workflow");

    builder.task("start_task", "my_function.start")
           .condition("check_condition", "{{data.is_valid}}", 
               (trueBranch) => trueBranch.task("success_task", "my_function.success"),
               (falseBranch) => falseBranch.task("failure_task", "my_function.failure")
           );

    const workflow = builder.build();
    workflow.setVariables({ data: { is_valid: true } });

    return workflow;
}

// Demo code for the visualizer
const demoCode = `// Simple workflow with task and condition
const builder = new HighwayDSL.WorkflowBuilder("simple_workflow");

builder.task("start_task", "my_function.start")
       .condition("check_condition", "{{data.is_valid}}", 
           (trueBranch) => trueBranch.task("success_task", "my_function.success"),
           (falseBranch) => falseBranch.task("failure_task", "my_function.failure")
       );

const workflow = builder.build();
workflow.setVariables({ data: { is_valid: true } });

return workflow;`;

// Export for browser use
if (typeof window !== 'undefined') {
    window.simpleWorkflowExample = {
        create: createSimpleWorkflow,
        demoCode: demoCode
    };
}