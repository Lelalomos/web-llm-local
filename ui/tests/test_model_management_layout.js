const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "..", "index.css"), "utf8");

assert.match(
    html,
    /<div class="model-pull-row model-control-group">[\s\S]*id="model-pull-input"[\s\S]*id="pull-model-button"/,
);
assert.match(
    html,
    /<div class="model-delete-row model-control-group">[\s\S]*id="model-delete-select"[\s\S]*id="delete-model-button"/,
);
assert.doesNotMatch(html, /id="installed-model-list"/);
assert.match(
    css,
    /\.model-control-group\s*\{[\s\S]*flex-direction:\s*column;[\s\S]*\}/,
);
assert.doesNotMatch(css, /\.installed-model-list\s*\{/);

console.log("model_management_layout tests passed");
