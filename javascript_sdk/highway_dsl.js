// highway_dsl.js - JavaScript implementation of Highway DSL
// Provides identical functionality to Python version with JSON output

class OperatorType {
    static TASK = "task";
    static CONDITION = "condition";
    static WAIT = "wait";
    static PARALLEL = "parallel";
    static FOREACH = "foreach";
    static SWITCH = "switch";
    static TRY_CATCH = "try_catch";
    static WHILE = "while";
    static EMIT_EVENT = "emit_event";
    static WAIT_FOR_EVENT = "wait_for_event";
}

class RetryPolicy {
    constructor(maxRetries = 3, delay = { seconds: 5 }, backoffFactor = 2.0) {
        this.max_retries = maxRetries;
        this.delay = delay;
        this.backoff_factor = backoffFactor;
    }
}

class TimeoutPolicy {
    constructor(timeout, killOnTimeout = true) {
        this.timeout = timeout;
        this.kill_on_timeout = killOnTimeout;
    }
}

class BaseOperator {
    constructor(taskId, operatorType, dependencies = [], retryPolicy = null, timeoutPolicy = null, metadata = {}, description = "", onSuccessTaskId = null, onFailureTaskId = null, isInternalLoopTask = false) {
        this.task_id = taskId;
        this.operator_type = operatorType;
        this.dependencies = dependencies;
        this.retry_policy = retryPolicy;
        this.timeout_policy = timeoutPolicy;
        this.metadata = metadata;
        this.description = description;
        this.on_success_task_id = onSuccessTaskId;
        this.on_failure_task_id = onFailureTaskId;
        this.is_internal_loop_task = isInternalLoopTask;
    }
}

class TaskOperator extends BaseOperator {
    constructor(taskId, functionName, args = [], kwargs = {}, resultKey = null, ...baseArgs) {
        super(taskId, OperatorType.TASK, ...baseArgs);
        this.function = functionName;
        this.args = args;
        this.kwargs = kwargs;
        this.result_key = resultKey;
    }
}

class ConditionOperator extends BaseOperator {
    constructor(taskId, condition, ifTrue = null, ifFalse = null, ...baseArgs) {
        super(taskId, OperatorType.CONDITION, ...baseArgs);
        this.condition = condition;
        this.if_true = ifTrue;
        this.if_false = ifFalse;
    }
}

class WaitOperator extends BaseOperator {
    constructor(taskId, waitFor, ...baseArgs) {
        super(taskId, OperatorType.WAIT, ...baseArgs);
        this.wait_for = this.parseWaitFor(waitFor);
    }

    parseWaitFor(waitFor) {
        if (typeof waitFor === 'string') {
            if (waitFor.startsWith('duration:')) {
                return { seconds: parseFloat(waitFor.split(':')[1]) };
            } else if (waitFor.startsWith('datetime:')) {
                return new Date(waitFor.split(':', 1)[1]).toISOString();
            }
        }
        return waitFor;
    }

    toJSON() {
        const base = { ...this };
        if (typeof this.wait_for === 'object' && this.wait_for.seconds !== undefined) {
            base.wait_for = `duration:${this.wait_for.seconds}`;
        } else if (this.wait_for instanceof Date) {
            base.wait_for = `datetime:${this.wait_for.toISOString()}`;
        }
        return base;
    }
}

class ParallelOperator extends BaseOperator {
    constructor(taskId, branches = {}, timeout = null, ...baseArgs) {
        super(taskId, OperatorType.PARALLEL, ...baseArgs);
        this.branches = branches;
        this.timeout = timeout;
    }
}

class ForEachOperator extends BaseOperator {
    constructor(taskId, items, loopBody = [], ...baseArgs) {
        super(taskId, OperatorType.FOREACH, ...baseArgs);
        this.items = items;
        this.loop_body = loopBody;
    }
}

class WhileOperator extends BaseOperator {
    constructor(taskId, condition, loopBody = [], ...baseArgs) {
        super(taskId, OperatorType.WHILE, ...baseArgs);
        this.condition = condition;
        this.loop_body = loopBody;
    }
}

class EmitEventOperator extends BaseOperator {
    constructor(taskId, eventName, payload = {}, ...baseArgs) {
        super(taskId, OperatorType.EMIT_EVENT, ...baseArgs);
        this.event_name = eventName;
        this.payload = payload;
    }
}

class WaitForEventOperator extends BaseOperator {
    constructor(taskId, eventName, timeoutSeconds = null, ...baseArgs) {
        super(taskId, OperatorType.WAIT_FOR_EVENT, ...baseArgs);
        this.event_name = eventName;
        this.timeout_seconds = timeoutSeconds;
    }
}

class SwitchOperator extends BaseOperator {
    constructor(taskId, switchOn, cases = {}, defaultCase = null, ...baseArgs) {
        super(taskId, OperatorType.SWITCH, ...baseArgs);
        this.switch_on = switchOn;
        this.cases = cases;
        this.default = defaultCase;
    }
}

class Workflow {
    constructor(name, version = "1.1.0", description = "", tasks = {}, variables = {}, startTask = null, schedule = null, startDate = null, catchup = false, isPaused = false, tags = [], maxActiveRuns = 1, defaultRetryPolicy = null) {
        this.name = name;
        this.version = version;
        this.description = description;
        this.tasks = tasks;
        this.variables = variables;
        this.start_task = startTask;
        this.schedule = schedule;
        this.start_date = startDate;
        this.catchup = catchup;
        this.is_paused = isPaused;
        this.tags = tags;
        this.max_active_runs = maxActiveRuns;
        this.default_retry_policy = defaultRetryPolicy;

        this.validateWorkflowNameAndVersion();
        this.validateTasks();
    }

    validateWorkflowNameAndVersion() {
        // Check for double underscore (reserved separator)
        if (this.name.includes('__')) {
            throw new Error(`Workflow name '${this.name}' cannot contain '__' (double underscore) - it's reserved as a separator`);
        }

        if (this.version.includes('__')) {
            throw new Error(`Workflow version '${this.version}' cannot contain '__' (double underscore) - it's reserved as a separator`);
        }

        // Validate workflow name format
        if (this.name && !/^[a-z][a-z0-9_]*$/.test(this.name)) {
            throw new Error(`Workflow name '${this.name}' must start with lowercase letter and contain only lowercase letters, digits, and single underscores`);
        }

        // Validate workflow version format (semver compatible)
        if (this.version && !/^[a-zA-Z0-9._-]+$/.test(this.version)) {
            throw new Error(`Workflow version '${this.version}' must contain only alphanumeric characters, dots, hyphens, and underscores (semver compatible)`);
        }
    }

    validateTasks() {
        const validatedTasks = {};
        const operatorClasses = {
            [OperatorType.TASK]: TaskOperator,
            [OperatorType.CONDITION]: ConditionOperator,
            [OperatorType.WAIT]: WaitOperator,
            [OperatorType.PARALLEL]: ParallelOperator,
            [OperatorType.FOREACH]: ForEachOperator,
            [OperatorType.WHILE]: WhileOperator,
            [OperatorType.EMIT_EVENT]: EmitEventOperator,
            [OperatorType.WAIT_FOR_EVENT]: WaitForEventOperator,
            [OperatorType.SWITCH]: SwitchOperator,
        };

        for (const [taskId, taskData] of Object.entries(this.tasks)) {
            const operatorType = taskData.operator_type;
            if (operatorType && operatorClasses[operatorType]) {
                const OperatorClass = operatorClasses[operatorType];
                validatedTasks[taskId] = new OperatorClass(taskId, ...Object.values(taskData));
            } else {
                throw new Error(`Unknown operator type: ${operatorType}`);
            }
        }
        this.tasks = validatedTasks;
    }

    addTask(task) {
        this.tasks[task.task_id] = task;
        return this;
    }

    setVariables(variables) {
        Object.assign(this.variables, variables);
        return this;
    }

    setStartTask(taskId) {
        this.start_task = taskId;
        return this;
    }

    setSchedule(cron) {
        this.schedule = cron;
        return this;
    }

    setStartDate(startDate) {
        this.start_date = startDate;
        return this;
    }

    setCatchup(enabled) {
        this.catchup = enabled;
        return this;
    }

    setPaused(paused) {
        this.is_paused = paused;
        return this;
    }

    addTags(...tags) {
        this.tags.push(...tags);
        return this;
    }

    setMaxActiveRuns(count) {
        this.max_active_runs = count;
        return this;
    }

    setDefaultRetryPolicy(policy) {
        this.default_retry_policy = policy;
        return this;
    }

    toJSON() {
        // Create a clean object without circular references
        const cleanObject = {
            name: this.name,
            version: this.version,
            description: this.description,
            tasks: {},
            variables: this.variables,
            start_task: this.start_task,
            schedule: this.schedule,
            start_date: this.start_date,
            catchup: this.catchup,
            is_paused: this.is_paused,
            tags: this.tags,
            max_active_runs: this.max_active_runs,
            default_retry_policy: this.default_retry_policy
        };

        // Convert tasks to plain objects
        for (const [taskId, task] of Object.entries(this.tasks)) {
            cleanObject.tasks[taskId] = this._taskToPlainObject(task);
        }

        return JSON.stringify(cleanObject, null, 2);
    }

    _taskToPlainObject(task) {
        const plainTask = { ...task };
        
        // Handle loop_body arrays for ForEachOperator and WhileOperator
        if (task.loop_body && Array.isArray(task.loop_body)) {
            plainTask.loop_body = task.loop_body.map(subTask => this._taskToPlainObject(subTask));
        }
        
        // Remove any circular references or complex objects
        delete plainTask.parent;
        
        return plainTask;
    }

    toMermaid() {
        const lines = ["stateDiagram-v2"];
        const allDependencies = new Set();
        const processedTransitions = new Set();

        // Collect all dependencies
        for (const task of Object.values(this.tasks)) {
            for (const dep of task.dependencies) {
                allDependencies.add(dep);
            }
        }

        // First pass: Add all states and incoming transitions
        for (const [taskId, task] of Object.entries(this.tasks)) {
            // Add state with description for regular tasks
            if (task.description && task.operator_type !== "foreach" && task.operator_type !== "while") {
                lines.push(`    state "${task.description}" as ${taskId}`);
            }

            // Add dependencies (incoming transitions) - but only for non-condition targets
            if (!task.dependencies.length) {
                if (this.start_task === taskId || !this.start_task) {
                    const transition = `[*] --> ${taskId}`;
                    if (!processedTransitions.has(transition)) {
                        lines.push(transition);
                        processedTransitions.add(transition);
                    }
                }
            } else {
                for (const dep of task.dependencies) {
                    // Only add incoming transitions if the target is not a condition operator
                    // Condition operators will get their transitions in the second pass
                    if (task.operator_type !== "condition") {
                        const transition = `${dep} --> ${taskId}`;
                        if (!processedTransitions.has(transition)) {
                            lines.push(transition);
                            processedTransitions.add(transition);
                        }
                    }
                }
            }

            // Add composite state for parallel operator
            if (task.operator_type === "parallel") {
                lines.push(`    state ${taskId} {`);
                const branches = Object.keys(task.branches);
                for (let i = 0; i < branches.length; i++) {
                    lines.push(`        state "Branch ${i + 1}" as ${branches[i]}`);
                    if (i < branches.length - 1) {
                        lines.push('        --');
                    }
                }
                lines.push('    }');
            }

            // Add composite state for foreach operator
            if (task.operator_type === "foreach") {
                lines.push(`    state ${taskId} {`);
                for (const subTask of task.loop_body) {
                    if (subTask.description) {
                        lines.push(`        state "${subTask.description}" as ${subTask.task_id}`);
                    } else {
                        lines.push(`        ${subTask.task_id}`);
                    }
                }
                lines.push('    }');
            }

            // Add composite state for while operator
            if (task.operator_type === "while") {
                lines.push(`    state ${taskId} {`);
                for (const subTask of task.loop_body) {
                    if (subTask.description) {
                        lines.push(`        state "${subTask.description}" as ${subTask.task_id}`);
                    } else {
                        lines.push(`        ${subTask.task_id}`);
                    }
                }
                lines.push('    }');
            }
        }

        // Second pass: Add conditional transitions and end states
        for (const [taskId, task] of Object.entries(this.tasks)) {
            // Add transitions for conditional operator (outgoing transitions)
            if (task.operator_type === "condition") {
                // First, add the incoming transition to the condition operator
                if (task.dependencies.length > 0) {
                    const dep = task.dependencies[0]; // Condition should have exactly one dependency
                    const incomingTransition = `${dep} --> ${taskId}`;
                    if (!processedTransitions.has(incomingTransition)) {
                        lines.push(incomingTransition);
                        processedTransitions.add(incomingTransition);
                    }
                }
                
                // Then add the labeled outgoing transitions
                if (task.if_true) {
                    const transition = `${taskId} --> ${task.if_true} : True`;
                    if (!processedTransitions.has(transition)) {
                        lines.push(transition);
                        processedTransitions.add(transition);
                    }
                }
                if (task.if_false) {
                    const transition = `${taskId} --> ${task.if_false} : False`;
                    if (!processedTransitions.has(transition)) {
                        lines.push(transition);
                        processedTransitions.add(transition);
                    }
                }
            }

            // End states - only add if not already connected elsewhere
            if (!allDependencies.has(taskId)) {
                // Don't add end state for condition operators that have branches
                if (task.operator_type === "condition") {
                    // Condition operators should not have end states since they branch
                    // Only add end state if neither branch leads anywhere
                    const hasTrueBranch = task.if_true && allDependencies.has(task.if_true);
                    const hasFalseBranch = task.if_false && allDependencies.has(task.if_false);
                    if (!hasTrueBranch && !hasFalseBranch) {
                        const transition = `${taskId} --> [*]`;
                        if (!processedTransitions.has(transition)) {
                            lines.push(transition);
                            processedTransitions.add(transition);
                        }
                    }
                } else {
                    // For other operators, add end state normally
                    const transition = `${taskId} --> [*]`;
                    if (!processedTransitions.has(transition)) {
                        lines.push(transition);
                        processedTransitions.add(transition);
                    }
                }
            }
        }

        return lines.join('\n');
    }

    static fromJSON(jsonStr) {
        const data = JSON.parse(jsonStr);
        return new Workflow(data.name, data.version, data.description, data.tasks, data.variables, data.start_task, data.schedule, data.start_date, data.catchup, data.is_paused, data.tags, data.max_active_runs, data.default_retry_policy);
    }
}

class WorkflowBuilder {
    constructor(name, existingWorkflow = null, parent = null) {
        if (existingWorkflow) {
            this.workflow = existingWorkflow;
        } else {
            this.workflow = new Workflow(name);
        }
        this._currentTask = null;
        this.parent = parent;
    }

    _addTask(task, kwargs = {}) {
        const dependencies = kwargs.dependencies || [];

        // Check if this task is intended to be a handler for another task
        let isHandlerTask = false;
        for (const otherTask of Object.values(this.workflow.tasks)) {
            if ((otherTask.on_failure_task_id === task.task_id) ||
                (otherTask.on_success_task_id === task.task_id)) {
                isHandlerTask = true;
                break;
            }
        }

        // Only add the current task as dependency if:
        // 1. There IS a current task (not the first task)
        // 2. No explicit dependencies were provided
        // 3. This is NOT a handler task
        if (this._currentTask && !dependencies.length && !isHandlerTask) {
            dependencies.push(this._currentTask);
        }

        task.dependencies = [...new Set(dependencies)].sort();
        this.workflow.addTask(task);
        this._currentTask = task.task_id;
    }

    task(taskId, functionName, kwargs = {}) {
        const task = new TaskOperator(taskId, functionName, kwargs.args || [], kwargs.kwargs || {}, kwargs.resultKey, ...Object.values(kwargs));
        this._addTask(task, kwargs);
        return this;
    }

    condition(taskId, condition, ifTrue, ifFalse, kwargs = {}) {
        const trueBuilder = ifTrue(new WorkflowBuilder(`${taskId}_true`, null, this));
        const falseBuilder = ifFalse(new WorkflowBuilder(`${taskId}_false`, null, this));

        const trueTasks = Object.keys(trueBuilder.workflow.tasks);
        const falseTasks = Object.keys(falseBuilder.workflow.tasks);

        const task = new ConditionOperator(
            taskId,
            condition,
            trueTasks[0] || null,
            falseTasks[0] || null,
            ...Object.values(kwargs)
        );

        this._addTask(task, kwargs);

        // Add true branch tasks
        for (const taskObj of Object.values(trueBuilder.workflow.tasks)) {
            if (!taskObj.dependencies.includes(taskId)) {
                taskObj.dependencies.push(taskId);
            }
            this.workflow.addTask(taskObj);
        }

        // Add false branch tasks
        for (const taskObj of Object.values(falseBuilder.workflow.tasks)) {
            if (!taskObj.dependencies.includes(taskId)) {
                taskObj.dependencies.push(taskId);
            }
            this.workflow.addTask(taskObj);
        }

        this._currentTask = taskId;
        return this;
    }

    wait(taskId, waitFor, kwargs = {}) {
        const task = new WaitOperator(taskId, waitFor, ...Object.values(kwargs));
        this._addTask(task, kwargs);
        return this;
    }

    parallel(taskId, branches, kwargs = {}) {
        const branchBuilders = {};
        for (const [name, branchFunc] of Object.entries(branches)) {
            const branchBuilder = branchFunc(new WorkflowBuilder(`${taskId}_${name}`, null, this));
            branchBuilders[name] = branchBuilder;
        }

        const branchTasks = {};
        for (const [name, builder] of Object.entries(branchBuilders)) {
            branchTasks[name] = Object.keys(builder.workflow.tasks);
        }

        const task = new ParallelOperator(taskId, branchTasks, kwargs.timeout, ...Object.values(kwargs));
        this._addTask(task, kwargs);

        // Add branch tasks
        for (const builder of Object.values(branchBuilders)) {
            for (const taskObj of Object.values(builder.workflow.tasks)) {
                if (!taskObj.is_internal_loop_task && !taskObj.dependencies.includes(taskId)) {
                    taskObj.dependencies.push(taskId);
                }
                this.workflow.addTask(taskObj);
            }
        }

        this._currentTask = taskId;
        return this;
    }

    foreach(taskId, items, loopBody, kwargs = {}) {
        const tempBuilder = new WorkflowBuilder(`${taskId}_loop`, null, this);
        const loopBuilder = loopBody(tempBuilder);
        const loopTasks = Object.values(loopBuilder.workflow.tasks);

        // Mark all loop body tasks as internal
        for (const taskObj of loopTasks) {
            taskObj.is_internal_loop_task = true;
        }

        const task = new ForEachOperator(
            taskId,
            items,
            loopTasks,
            ...Object.values(kwargs)
        );

        this._addTask(task, kwargs);

        // Add foreach task as dependency to first loop task
        if (loopTasks.length > 0) {
            const firstTask = loopTasks[0];
            if (!firstTask.dependencies.includes(taskId)) {
                firstTask.dependencies.push(taskId);
            }

            // Add all loop tasks
            for (const taskObj of loopTasks) {
                this.workflow.addTask(taskObj);
            }
        }

        this._currentTask = taskId;
        return this;
    }

    whileLoop(taskId, condition, loopBody, kwargs = {}) {
        const loopBuilder = loopBody(new WorkflowBuilder(`${taskId}_loop`, null, this));
        const loopTasks = Object.values(loopBuilder.workflow.tasks);

        // Mark all loop body tasks as internal
        for (const taskObj of loopTasks) {
            taskObj.is_internal_loop_task = true;
        }

        const task = new WhileOperator(
            taskId,
            condition,
            loopTasks,
            ...Object.values(kwargs)
        );

        this._addTask(task, kwargs);

        // Add while task as dependency to first loop task
        if (loopTasks.length > 0) {
            const firstTask = loopTasks[0];
            if (!firstTask.dependencies.includes(taskId)) {
                firstTask.dependencies.push(taskId);
            }

            // Add all loop tasks
            for (const taskObj of loopTasks) {
                this.workflow.addTask(taskObj);
            }
        }

        this._currentTask = taskId;
        return this;
    }

    retry(maxRetries = 3, delay = { seconds: 5 }, backoffFactor = 2.0) {
        if (this._currentTask && this.workflow.tasks[this._currentTask] instanceof TaskOperator) {
            this.workflow.tasks[this._currentTask].retry_policy = new RetryPolicy(maxRetries, delay, backoffFactor);
        }
        return this;
    }

    timeout(timeout, killOnTimeout = true) {
        if (this._currentTask && this.workflow.tasks[this._currentTask] instanceof TaskOperator) {
            this.workflow.tasks[this._currentTask].timeout_policy = new TimeoutPolicy(timeout, killOnTimeout);
        }
        return this;
    }

    emitEvent(taskId, eventName, kwargs = {}) {
        const task = new EmitEventOperator(taskId, eventName, kwargs.payload || {}, ...Object.values(kwargs));
        this._addTask(task, kwargs);
        return this;
    }

    waitForEvent(taskId, eventName, timeoutSeconds = null, kwargs = {}) {
        const task = new WaitForEventOperator(taskId, eventName, timeoutSeconds, ...Object.values(kwargs));
        this._addTask(task, kwargs);
        return this;
    }

    switch(taskId, switchOn, cases, defaultCase = null, kwargs = {}) {
        const task = new SwitchOperator(taskId, switchOn, cases, defaultCase, ...Object.values(kwargs));
        this._addTask(task, kwargs);
        return this;
    }

    onSuccess(taskId) {
        if (this._currentTask) {
            this.workflow.tasks[this._currentTask].on_success_task_id = taskId;
        }
        return this;
    }

    onFailure(taskId) {
        if (this._currentTask) {
            this.workflow.tasks[this._currentTask].on_failure_task_id = taskId;
        }
        return this;
    }

    build() {
        return this.workflow;
    }
}

// Export for use in web pages
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        Workflow,
        WorkflowBuilder,
        OperatorType,
        RetryPolicy,
        TimeoutPolicy,
        BaseOperator,
        TaskOperator,
        ConditionOperator,
        WaitOperator,
        ParallelOperator,
        ForEachOperator,
        WhileOperator,
        EmitEventOperator,
        WaitForEventOperator,
        SwitchOperator
    };
} else {
    window.HighwayDSL = {
        Workflow,
        WorkflowBuilder,
        OperatorType,
        RetryPolicy,
        TimeoutPolicy,
        BaseOperator,
        TaskOperator,
        ConditionOperator,
        WaitOperator,
        ParallelOperator,
        ForEachOperator,
        WhileOperator,
        EmitEventOperator,
        WaitForEventOperator,
        SwitchOperator
    };
}