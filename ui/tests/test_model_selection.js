const assert = require("node:assert/strict");
const { pickPreferredModel } = require("../model_selection");

assert.equal(
    pickPreferredModel([
        { name: "gemma2:2b" },
        { name: "gemma4:e2b" },
        { name: "qwen3:4b" },
    ]),
    "gemma4:e2b",
);

assert.equal(
    pickPreferredModel([
        { name: "gemma4:12b" },
        { name: "gemma2:2b" },
    ]),
    "gemma4:12b",
);

assert.equal(
    pickPreferredModel([
        { name: "gemma2:2b" },
        { name: "qwen3:4b" },
    ]),
    "gemma2:2b",
);

assert.equal(
    pickPreferredModel([
        { name: "qwen3:4b" },
        { name: "qwen2.5:0.5b" },
    ]),
    "qwen3:4b",
);

assert.equal(pickPreferredModel([]), "");
