# Highway DSL JavaScript Examples

This directory contains comprehensive examples demonstrating the capabilities of the Highway DSL JavaScript implementation.

## Example Workflows

### 1. **Simple Workflow** (`simple_workflow.js`)
- Basic task and condition workflow
- Demonstrates conditional branching
- Simple variable usage

### 2. **Parallel Workflow** (`parallel_workflow.js`)
- Parallel processing with multiple branches
- Task descriptions for better visualization
- Sequential task execution after parallel branches

### 3. **Bank ETL Workflow** (`bank_etl_workflow.js`)
- Complex ETL (Extract, Transform, Load) pipeline
- Retry policies and timeout configurations
- Multiple data source ingestion
- Data validation and transformation

### 4. **E-commerce Workflow** (`ecommerce_workflow.js`)
- Order processing pipeline
- Inventory checking with conditional logic
- Payment processing and fulfillment
- Notification and analytics integration

### 5. **Data Pipeline Workflow** (`data_pipeline_workflow.js`)
- Advanced data processing pipeline
- Parallel data extraction from multiple sources
- ForEach loop for dataset processing
- Error handling and validation
- Resource cleanup

## Usage

### In Node.js
```javascript
const createWorkflow = require('./examples/simple_workflow.js');
const workflow = createWorkflow();
console.log(workflow.toJSON());
```

### In Browser Demo
Each example includes a `demoCode` property that can be used directly in the visualizer:

```javascript
// Copy the demoCode from any example file and paste into the visualizer
const exampleCode = simpleWorkflowExample.demoCode;
```

## Features Demonstrated

- **Task Operators**: Basic function execution with arguments and results
- **Condition Operators**: Conditional branching with true/false paths
- **Parallel Operators**: Concurrent task execution
- **ForEach Operators**: Loop-based processing of collections
- **Retry Policies**: Automatic retry with exponential backoff
- **Timeout Policies**: Task execution time limits
- **Variables**: Workflow-level configuration and data
- **Descriptions**: Human-readable task labels for better visualization

## Integration with Visualizer

All examples are compatible with the Highway DSL visualizer. Each file includes:
- Complete workflow creation function
- Demo code string for direct use in the visualizer
- Proper error handling and validation

## Testing

Run any example:
```bash
node examples/simple_workflow.js
```

Or use in the visualizer by copying the `demoCode` content into the editor.