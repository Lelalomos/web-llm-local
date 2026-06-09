const assert = require("node:assert/strict");
const { buildDeleteModelOptions, isValidModelName, normalizeModelName } = require("../model_management");

assert.equal(isValidModelName("qwen2.5:0.5b"), true);
assert.equal(isValidModelName(" hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M "), true);
assert.equal(isValidModelName("bad model name"), false);
assert.equal(isValidModelName(""), false);
assert.equal(normalizeModelName(" qwen3:4b "), "qwen3:4b");
assert.deepEqual(
    buildDeleteModelOptions([{ name: "gemma4:e2b" }, { name: "qwen2.5:0.5b" }]),
    [
        { value: "", label: "Select installed model" },
        { value: "gemma4:e2b", label: "gemma4:e2b" },
        { value: "qwen2.5:0.5b", label: "qwen2.5:0.5b" },
    ]
);

console.log("model_management tests passed");
