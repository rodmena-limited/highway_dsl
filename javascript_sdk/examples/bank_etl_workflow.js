// bank_etl_workflow.js - Complex bank ETL example

// Browser-compatible version (no require)
function createBankETLWorkflow() {
    const builder = new HighwayDSL.WorkflowBuilder("bank_etl_workflow");

    builder.parallel("ingest_data", {
        "accounts": (b) => b.task("ingest_accounts", "bank.ingest.accounts", 
            { description: "Ingest Account Data", resultKey: "accounts_data" }),
        "transactions": (b) => b.task("ingest_transactions", "bank.ingest.transactions", 
            { description: "Ingest Transaction Data", resultKey: "transactions_data" }),
        "customers": (b) => b.task("ingest_customers", "bank.ingest.customers", 
            { description: "Ingest Customer Data", resultKey: "customers_data" })
    })
    .task("validate_data", "bank.validate.all", 
        { description: "Validate All Data", 
          dependencies: ["ingest_data"],
          timeoutPolicy: new HighwayDSL.TimeoutPolicy({ hours: 1 }, true) 
        })
    .task("transform_data", "bank.transform.process", 
        { description: "Transform Data", 
          dependencies: ["validate_data"],
          retryPolicy: new HighwayDSL.RetryPolicy(3, { seconds: 10 }, 2.0) 
        })
    .task("load_warehouse", "bank.load.warehouse", 
        { description: "Load to Data Warehouse", 
          dependencies: ["transform_data"] 
        });

    const workflow = builder.build();
    workflow.setVariables({
        db_host: "localhost:5432",
        warehouse_url: "https://warehouse.bank.com/api",
        batch_size: 1000
    });

    return workflow;
}

// Demo code for the visualizer
const demoCode = `// Complex bank ETL workflow
const builder = new HighwayDSL.WorkflowBuilder("bank_etl_workflow");

builder.parallel("ingest_data", {
    "accounts": (b) => b.task("ingest_accounts", "bank.ingest.accounts", 
        { description: "Ingest Account Data", resultKey: "accounts_data" }),
    "transactions": (b) => b.task("ingest_transactions", "bank.ingest.transactions", 
        { description: "Ingest Transaction Data", resultKey: "transactions_data" }),
    "customers": (b) => b.task("ingest_customers", "bank.ingest.customers", 
        { description: "Ingest Customer Data", resultKey: "customers_data" })
})
.task("validate_data", "bank.validate.all", 
    { description: "Validate All Data", 
      dependencies: ["ingest_data"],
      timeoutPolicy: new HighwayDSL.TimeoutPolicy({ hours: 1 }, true) 
    })
.task("transform_data", "bank.transform.process", 
    { description: "Transform Data", 
      dependencies: ["validate_data"],
      retryPolicy: new HighwayDSL.RetryPolicy(3, { seconds: 10 }, 2.0) 
    })
.task("load_warehouse", "bank.load.warehouse", 
    { description: "Load to Data Warehouse", 
      dependencies: ["transform_data"] 
    });

const workflow = builder.build();
workflow.setVariables({
    db_host: "localhost:5432",
    warehouse_url: "https://warehouse.bank.com/api",
    batch_size: 1000
});

return workflow;`;

// Export for browser use
if (typeof window !== 'undefined') {
    window.bankETLWorkflowExample = {
        create: createBankETLWorkflow,
        demoCode: demoCode
    };
}