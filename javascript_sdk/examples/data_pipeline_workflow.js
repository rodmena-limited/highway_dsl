// data_pipeline_workflow.js - Advanced data pipeline with loops and error handling

// Browser-compatible version (no require)
function createDataPipelineWorkflow() {
    const builder = new HighwayDSL.WorkflowBuilder("advanced_data_pipeline");

    builder.task("initialize_pipeline", "pipeline.init", 
        { description: "Initialize Pipeline" })
    .parallel("extract_sources", {
        "api_data": (b) => b.task("extract_api", "pipeline.extract.api", 
            { description: "Extract API Data", resultKey: "api_data" }),
        "database_data": (b) => b.task("extract_db", "pipeline.extract.database", 
            { description: "Extract Database Data", resultKey: "db_data" }),
        "file_data": (b) => b.task("extract_files", "pipeline.extract.files", 
            { description: "Extract File Data", resultKey: "file_data" })
    })
    .foreach("process_datasets", "{{datasets}}",
        (loopBuilder) => loopBuilder
            .task("validate_dataset", "pipeline.validate.dataset", 
                { description: "Validate Dataset", resultKey: "validation_result" })
            .condition("check_validation", "{{validation_result.is_valid}}",
                (trueBranch) => trueBranch
                    .task("transform_dataset", "pipeline.transform.dataset", 
                        { description: "Transform Dataset" })
                    .task("load_dataset", "pipeline.load.dataset", 
                        { description: "Load Dataset" }),
                (falseBranch) => falseBranch
                    .task("log_validation_error", "pipeline.log.error", 
                        { description: "Log Validation Error" })
                    .task("skip_dataset", "pipeline.skip.invalid", 
                        { description: "Skip Invalid Dataset" })
            )
    )
    .task("aggregate_results", "pipeline.aggregate.results", 
        { description: "Aggregate Results", 
          timeoutPolicy: new HighwayDSL.TimeoutPolicy({ minutes: 30 }, true) 
        })
    .task("generate_reports", "pipeline.reports.generate", 
        { description: "Generate Reports" })
    .task("cleanup_resources", "pipeline.cleanup", 
        { description: "Cleanup Resources" });

    const workflow = builder.build();
    workflow.setVariables({
        datasets: ["sales", "inventory", "customers", "products"],
        api_endpoint: "https://api.data.com/v1",
        db_connection: "postgresql://localhost:5432",
        output_path: "/data/output"
    });

    return workflow;
}

// Demo code for the visualizer
const demoCode = `// Advanced data pipeline with loops and error handling
const builder = new HighwayDSL.WorkflowBuilder("advanced_data_pipeline");

builder.task("initialize_pipeline", "pipeline.init", 
    { description: "Initialize Pipeline" })
.parallel("extract_sources", {
    "api_data": (b) => b.task("extract_api", "pipeline.extract.api", 
        { description: "Extract API Data", resultKey: "api_data" }),
    "database_data": (b) => b.task("extract_db", "pipeline.extract.database", 
        { description: "Extract Database Data", resultKey: "db_data" }),
    "file_data": (b) => b.task("extract_files", "pipeline.extract.files", 
        { description: "Extract File Data", resultKey: "file_data" })
})
.foreach("process_datasets", "{{datasets}}",
    (loopBuilder) => loopBuilder
        .task("validate_dataset", "pipeline.validate.dataset", 
            { description: "Validate Dataset", resultKey: "validation_result" })
        .condition("check_validation", "{{validation_result.is_valid}}",
            (trueBranch) => trueBranch
                .task("transform_dataset", "pipeline.transform.dataset", 
                    { description: "Transform Dataset" })
                .task("load_dataset", "pipeline.load.dataset", 
                    { description: "Load Dataset" }),
            (falseBranch) => falseBranch
                .task("log_validation_error", "pipeline.log.error", 
                    { description: "Log Validation Error" })
                .task("skip_dataset", "pipeline.skip.invalid", 
                    { description: "Skip Invalid Dataset" })
        )
)
.task("aggregate_results", "pipeline.aggregate.results", 
    { description: "Aggregate Results", 
      timeoutPolicy: new HighwayDSL.TimeoutPolicy({ minutes: 30 }, true) 
    })
.task("generate_reports", "pipeline.reports.generate", 
    { description: "Generate Reports" })
.task("cleanup_resources", "pipeline.cleanup", 
    { description: "Cleanup Resources" });

const workflow = builder.build();
workflow.setVariables({
    datasets: ["sales", "inventory", "customers", "products"],
    api_endpoint: "https://api.data.com/v1",
    db_connection: "postgresql://localhost:5432",
    output_path: "/data/output"
});

return workflow;`;

// Export for browser use
if (typeof window !== 'undefined') {
    window.dataPipelineWorkflowExample = {
        create: createDataPipelineWorkflow,
        demoCode: demoCode
    };
}