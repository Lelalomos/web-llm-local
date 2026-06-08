const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {
    TASK_MODE_OPTIONS,
    getDefaultTaskMode,
    getTaskModeDetectionStatusMessage,
    inferTaskModeFromPrompt,
    inferTaskModeForPrompt,
} = require("./task_modes");

const indexJs = fs.readFileSync(path.join(__dirname, "index.js"), "utf8");
const indexHtml = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");

assert.equal(getDefaultTaskMode(), "general");
assert.equal(TASK_MODE_OPTIONS.some(option => option.value === "code_writer"), true);
assert.equal(TASK_MODE_OPTIONS.some(option => option.value === "bug_fixer"), true);
assert.equal(inferTaskModeFromPrompt("i want to you write rust language for api?", "general"), "code_writer");
assert.equal(inferTaskModeFromPrompt("can you explain what an API is?", "general"), "general");
assert.equal(inferTaskModeFromPrompt("write python function to add numbers", "code_reviewer"), "code_writer");
assert.equal(inferTaskModeFromPrompt("if i fall in love with someone how should i do with who i love?", "code_writer"), "general");
assert.equal(inferTaskModeFromPrompt("", "code_writer"), "code_writer");
assert.equal(getTaskModeDetectionStatusMessage(0), "Ollama: Detecting task mode...");
assert.equal(getTaskModeDetectionStatusMessage(8), "Ollama: Still detecting task mode...");
assert.equal(getTaskModeDetectionStatusMessage(20), "Ollama: Still detecting task mode. The small model may be loading...");
assert.match(indexJs, /function startTaskModeDetectionStatus\(\)/);
assert.match(indexJs, /setInterval\(renderStatus, 1000\)/);
assert.match(indexJs, /stopTaskModeDetectionStatus\(\);/);
assert.match(indexHtml, /task_modes\.js\?v=20260609-2/);
assert.match(indexHtml, /index\.js\?v=20260609-4/);

async function runAsyncTests() {
    const modelSelectedMode = await inferTaskModeForPrompt("review this function", "general", async () => ({
        ok: true,
        json: async () => ({ task_mode: "code_reviewer" })
    }));
    assert.equal(modelSelectedMode, "code_reviewer");

    const fallbackMode = await inferTaskModeForPrompt("write python function to add numbers", "general", async () => ({
        ok: false,
        json: async () => ({})
    }));
    assert.equal(fallbackMode, "code_writer");

    const invalidMode = await inferTaskModeForPrompt("hello", "code_writer", async () => ({
        ok: true,
        json: async () => ({ task_mode: "bad_mode" })
    }));
    assert.equal(invalidMode, "general");
}

runAsyncTests()
    .then(() => console.log("task_modes tests passed"))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
