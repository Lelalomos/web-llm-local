const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const css = fs.readFileSync(path.join(__dirname, "..", "index.css"), "utf8");

assert.match(
    css,
    /\.sidebar\s*\{[\s\S]*overflow-y:\s*auto;[\s\S]*overflow-x:\s*hidden;[\s\S]*\}/,
);

assert.match(
    css,
    /\.config-editor\s*\{[\s\S]*max-height:\s*min\(62vh, 620px\);[\s\S]*overflow-y:\s*auto;[\s\S]*\}/,
);

assert.match(
    css,
    /\.config-modal-panel\s*\{[\s\S]*max-height:\s*min\(88vh, 780px\);[\s\S]*overflow:\s*hidden;[\s\S]*\}/,
);

assert.match(
    css,
    /\.config-editor-actions\s*\{[\s\S]*display:\s*flex;[\s\S]*min-width:\s*0;[\s\S]*\}/,
);

assert.match(
    css,
    /\.config-editor-actions \.model-action-btn\s*\{[\s\S]*flex:\s*1 1 auto;[\s\S]*min-width:\s*0;[\s\S]*\}/,
);

console.log("sidebar_scroll tests passed");
