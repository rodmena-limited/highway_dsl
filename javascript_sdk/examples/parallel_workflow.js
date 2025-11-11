// parallel_workflow.js - Parallel processing example

// Browser-compatible version (no require)
function createParallelWorkflow() {
    const builder = new HighwayDSL.WorkflowBuilder("parallel_workflow");

    builder.parallel("process_data", {
        "branch1": (b) => b.task("task1", "process.branch1", { description: "Process Branch 1" }),
        "branch2": (b) => b.task("task2", "process.branch2", { description: "Process Branch 2" }),
        "branch3": (b) => b.task("task3", "process.branch3", { description: "Process Branch 3" })
    }).task("final_task", "process.finalize", { description: "Finalize Processing" });

    const workflow = builder.build();
    return workflow;
}

// Demo code for the visualizer
const demoCode = `// Parallel workflow with multiple branches
const builder = new HighwayDSL.WorkflowBuilder("parallel_workflow");

builder.parallel("process_data", {
    "branch1": (b) => b.task("task1", "process.branch1", { description: "Process Branch 1" }),
    "branch2": (b) => b.task("task2", "process.branch2", { description: "Process Branch 2" }),
    "branch3": (b) => b.task("task3", "process.branch3", { description: "Process Branch 3" })
}).task("final_task", "process.finalize", { description: "Finalize Processing" });

const workflow = builder.build();

return workflow;`;

// Export for browser use
if (typeof window !== 'undefined') {
    window.parallelWorkflowExample = {
        create: createParallelWorkflow,
        demoCode: demoCode
    };
}