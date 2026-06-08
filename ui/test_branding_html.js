const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const indexJs = fs.readFileSync(path.join(__dirname, "index.js"), "utf8");

assert.match(html, /<title>chat-personal - Gemma 4<\/title>/);
assert.doesNotMatch(html, /class="logo-icon"/);
assert.match(html, /<h2>chat-personal<\/h2>/);
assert.match(html, /id="current-model-display">Gemma 4<\/h1>/);
assert.match(html, /Chat with Gemma 4 or Qwen locally/);
assert.match(html, /placeholder="Ask Gemma 4 anything\.\.\./);
assert.doesNotMatch(html, /chat-personal-llm-llm/);
assert.doesNotMatch(html, /Ask  anything/);
assert.match(indexJs, /currentModelDisplay\.textContent = "Gemma 4"/);

console.log("branding html tests passed");
