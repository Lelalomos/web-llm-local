const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const js = fs.readFileSync(path.join(__dirname, "index.js"), "utf8");

assert.doesNotMatch(html, /id="reload-config-button"/);
assert.match(html, /id="open-config-button"/);
assert.match(html, /id="config-modal"/);
assert.match(html, /id="close-config-button"/);
assert.match(html, /id="save-config-button"/);
assert.match(html, /href="index\.css\?v=20260609-2"/);
assert.match(html, /src="index\.js\?v=20260609-4"/);
assert.doesNotMatch(
    html,
    /<div class="sidebar-section">[\s\S]*<label for="config-editor">Config<\/label>[\s\S]*id="config-editor"[\s\S]*<\/div>/,
);
assert.doesNotMatch(js, /reloadConfigButton/);
assert.match(js, /function openConfigModal\(\)/);
assert.match(js, /function closeConfigModal\(\)/);
assert.match(js, /function setupConfigModalEventListeners\(\)/);
assert.match(js, /setupConfigModalEventListeners\(\);\n\s+setupEventListeners\(\);/);
assert.match(js, /openConfigButton\.addEventListener\("click", openConfigModal\)/);
assert.match(js, /configModalBackdrop\.addEventListener\("click", closeConfigModal\)/);

console.log("config_button_layout tests passed");
