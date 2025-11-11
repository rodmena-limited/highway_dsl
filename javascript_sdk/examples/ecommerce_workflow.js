// ecommerce_workflow.js - E-commerce order processing example

// Browser-compatible version (no require)
function createEcommerceWorkflow() {
    const builder = new HighwayDSL.WorkflowBuilder("ecommerce_order_processing");

    builder.task("receive_order", "ecommerce.orders.receive", 
        { description: "Receive New Order", resultKey: "order_data" })
    .task("validate_order", "ecommerce.orders.validate", 
        { description: "Validate Order Details", 
          dependencies: ["receive_order"],
          retryPolicy: new HighwayDSL.RetryPolicy(2, { seconds: 5 }, 1.5) 
        })
    .condition("check_inventory", "{{order_data.items_in_stock}}",
        (trueBranch) => trueBranch
            .task("process_payment", "ecommerce.payments.process", 
                { description: "Process Payment" })
            .task("fulfill_order", "ecommerce.orders.fulfill", 
                { description: "Fulfill Order" }),
        (falseBranch) => falseBranch
            .task("notify_backorder", "ecommerce.notifications.backorder", 
                { description: "Notify Backorder" })
            .task("restock_inventory", "ecommerce.inventory.restock", 
                { description: "Restock Inventory" })
    )
    .task("send_confirmation", "ecommerce.notifications.confirm", 
        { description: "Send Order Confirmation" })
    .task("update_analytics", "ecommerce.analytics.track", 
        { description: "Update Analytics" });

    const workflow = builder.build();
    workflow.setVariables({
        payment_gateway: "stripe",
        notification_service: "sendgrid",
        analytics_endpoint: "https://analytics.shop.com"
    });

    return workflow;
}

// Demo code for the visualizer
const demoCode = `// E-commerce order processing workflow
const builder = new HighwayDSL.WorkflowBuilder("ecommerce_order_processing");

builder.task("receive_order", "ecommerce.orders.receive", 
    { description: "Receive New Order", resultKey: "order_data" })
.task("validate_order", "ecommerce.orders.validate", 
    { description: "Validate Order Details", 
      dependencies: ["receive_order"],
      retryPolicy: new HighwayDSL.RetryPolicy(2, { seconds: 5 }, 1.5) 
    })
.condition("check_inventory", "{{order_data.items_in_stock}}",
    (trueBranch) => trueBranch
        .task("process_payment", "ecommerce.payments.process", 
            { description: "Process Payment" })
        .task("fulfill_order", "ecommerce.orders.fulfill", 
            { description: "Fulfill Order" }),
    (falseBranch) => falseBranch
        .task("notify_backorder", "ecommerce.notifications.backorder", 
            { description: "Notify Backorder" })
        .task("restock_inventory", "ecommerce.inventory.restock", 
            { description: "Restock Inventory" })
)
.task("send_confirmation", "ecommerce.notifications.confirm", 
    { description: "Send Order Confirmation" })
.task("update_analytics", "ecommerce.analytics.track", 
    { description: "Update Analytics" });

const workflow = builder.build();
workflow.setVariables({
    payment_gateway: "stripe",
    notification_service: "sendgrid",
    analytics_endpoint: "https://analytics.shop.com"
});

return workflow;`;

// Export for browser use
if (typeof window !== 'undefined') {
    window.ecommerceWorkflowExample = {
        create: createEcommerceWorkflow,
        demoCode: demoCode
    };
}