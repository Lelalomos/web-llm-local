const assert = require("node:assert/strict");
const { encodeBase64, looksLikeCodeBlock, renderMarkdown } = require("./markdown_renderer");

const headingHtml = renderMarkdown("### Title");
assert.equal(headingHtml.includes('class="markdown-heading level-3"'), true);
assert.equal(headingHtml.includes(">Title<"), true);

const listHtml = renderMarkdown("- one\n- two");
assert.equal(listHtml.includes('<ul class="markdown-list">'), true);
assert.equal(listHtml.includes("<li>one</li>"), true);

const codeHtml = renderMarkdown("```python\nprint('hi')\n```");
assert.equal(codeHtml.includes('class="code-container"'), true);
assert.equal(codeHtml.includes("Copy code"), true);

const openFenceHtml = renderMarkdown("```python\nprint('hi')");
assert.equal(openFenceHtml.includes('class="code-container"'), true);

assert.equal(encodeBase64("print('hi')").length > 0, true);

assert.equal(looksLikeCodeBlock("def add(a, b):\n    return a + b\nprint(add(1, 2))"), true);
assert.equal(looksLikeCodeBlock("This is normal text.\nThis is another sentence."), false);

const heuristicCodeHtml = renderMarkdown("def add(a, b):\n    return a + b\nprint(add(1, 2))");
assert.equal(heuristicCodeHtml.includes('class="code-container"'), true);
