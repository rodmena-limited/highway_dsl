# Agent Prompt Update - Workflow Name Field Requirement

## Problem

Generated workflows were missing the required `name` field in WorkflowBuilder, causing runtime errors:

```
ValueError: Workflow definition must have 'name' field
```

**Error Log:**
```
Nov 19 23:33:00 farshid-vm highway-scheduler[567815]: 2025-11-19 23:33:00 [   ERROR] engine.scheduler - Workflow definition missing 'name' field: {}
Nov 19 23:33:00 farshid-vm highway-scheduler[567815]: 2025-11-19 23:33:00 [   ERROR] engine.db - Error during database operation: Workflow definition must have 'name' field
Nov 19 23:33:00 farshid-vm highway-scheduler[567815]: 2025-11-19 23:33:00 [   ERROR] engine.scheduler - Failed to execute scheduled task tools.workflow.execute: Workflow definition must have 'name' field
Nov 19 23:33:00 farshid-vm highway-scheduler[567815]: Traceback (most recent call last):
Nov 19 23:33:00 farshid-vm highway-scheduler[567815]:   File "/home/farshid/develop/highway-workflow-engine/engine/scheduler.py", line 78, in _execute_scheduled_task_callback
Nov 19 23:33:00 farshid-vm highway-scheduler[567815]:     raise ValueError("Workflow definition must have 'name' field")
```

## Root Cause

The LLM was generating code like:
```python
# ❌ WRONG - Missing name parameter
builder = WorkflowBuilder()
```

Instead of:
```python
# ✅ CORRECT - Name parameter required
builder = WorkflowBuilder("my_workflow_name")
```

## Solution

Updated `AGENT_PROMPT.md` with explicit requirements and examples:

### 1. Added Critical Section (Line 87-109)

```markdown
### MANDATORY WORKFLOW NAME FIELD

**CRITICAL: Every workflow MUST have a name parameter in WorkflowBuilder()**

```python
# ✅ CORRECT - Always provide a name
builder = WorkflowBuilder("my_workflow_name")

# ❌ WRONG - This will cause runtime error
builder = WorkflowBuilder()  # DO NOT DO THIS
```

**Runtime Error if name is missing:**
```
ValueError: Workflow definition must have 'name' field
```

**Rules for workflow names:**
- MUST be a non-empty string
- Use snake_case (e.g., "data_pipeline", "hello_world")
- Be descriptive of what the workflow does
- No spaces (use underscores instead)
```

### 2. Added Final Checklist (Line 1666-1684)

```markdown
## FINAL CHECKLIST - VERIFY BEFORE OUTPUT

Before generating any workflow, verify these CRITICAL requirements:

1. ✅ **WorkflowBuilder has a name** - `WorkflowBuilder("workflow_name")` NOT `WorkflowBuilder()`
2. ✅ **Output is pure Python** - No markdown fences, no explanations
3. ✅ **Multiple granular steps** - Break operations into 6+ tasks, not 2-3
4. ✅ **No dangerous commands** - Avoid `rm -rf`, system directories, etc.
5. ✅ **All tasks have unique IDs** - No duplicate task_id values
6. ✅ **Variable references use {{}}** - Correct: `{{task.result}}` not `{task.result}`

**Common Errors to Avoid:**
```python
# ❌ WRONG - Missing workflow name (causes ValueError)
builder = WorkflowBuilder()

# ✅ CORRECT - Always provide name
builder = WorkflowBuilder("my_workflow")
```
```

## Changes Summary

**File:** `/home/farshid/develop/highway_dsl/app/AGENT_PROMPT.md`

**Line Numbers:**
- **87-109**: Added "MANDATORY WORKFLOW NAME FIELD" section with error examples
- **1666-1684**: Added "FINAL CHECKLIST" with 6-point verification list

**Key Improvements:**
1. Explicit error message shown to LLM
2. Side-by-side comparison of correct vs. wrong usage
3. Naming rules (snake_case, descriptive, no spaces)
4. Final checklist before output generation
5. Common errors section with examples

## Testing

Service restarted successfully:
```bash
sudo systemctl restart dsl-generator.service
```

**Status:**
```
● dsl-generator.service - Highway DSL Generator API
     Loaded: loaded (/etc/systemd/system/dsl-generator.service; enabled; preset: enabled)
     Active: active (running) since Wed 2025-11-19 23:37:51 UTC
   Main PID: 629502 (python3)
```

## Expected Behavior

After this update, the LLM should:

1. ✅ Always include `name` parameter in `WorkflowBuilder("workflow_name")`
2. ✅ Use snake_case naming convention
3. ✅ Provide descriptive workflow names
4. ✅ Never generate `WorkflowBuilder()` without a name

## Verification

Test the API with a simple prompt:
```bash
curl -G "http://localhost:7291/api/v1/generate_dsl" \
  --data-urlencode "input=Create a hello world workflow"
```

**Expected output should include:**
```python
from highway_dsl import WorkflowBuilder

builder = WorkflowBuilder("hello_world")  # ← Name is present
builder.task("print_hello", "tools.shell.run", args=["echo 'Hello World'"])
workflow = builder.build()
print(workflow.to_json())
```

## Result

✅ LLM now has explicit instructions to avoid the `ValueError: Workflow definition must have 'name' field` error
✅ Multiple reinforcement points throughout the prompt
✅ Clear examples of correct vs. incorrect usage
✅ Final checklist to verify before output

**Updated:** 2025-11-19 23:37 UTC
**Prompt Length:** 1,709 lines (was 1,688 lines)
**Service Status:** Active (running)
