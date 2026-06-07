const assert = require("node:assert/strict");
const { DEFAULT_DOCUMENT_PROMPT, MAX_DOCUMENT_PROMPT_CHARS, buildFinalPrompt, truncateDocumentText } = require("./document_prompt");

assert.equal(buildFinalPrompt("hello", "", ""), "hello");
assert.equal(
    buildFinalPrompt("", "report.pdf", "example body").includes(DEFAULT_DOCUMENT_PROMPT),
    true,
);
assert.equal(
    buildFinalPrompt("Summarize this", "report.pdf", "example body").includes("Use the file content above to answer this prompt: Summarize this"),
    true,
);
assert.equal(truncateDocumentText("a".repeat(MAX_DOCUMENT_PROMPT_CHARS + 10)).includes("Content truncated"), true);
