const assert = require("node:assert/strict");
const { TASK_MODE_OPTIONS, getDefaultTaskMode } = require("./task_modes");

assert.equal(getDefaultTaskMode(), "general");
assert.equal(TASK_MODE_OPTIONS.some(option => option.value === "code_writer"), true);
assert.equal(TASK_MODE_OPTIONS.some(option => option.value === "bug_fixer"), true);
