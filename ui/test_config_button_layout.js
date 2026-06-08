const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const js = fs.readFileSync(path.join(__dirname, "index.js"), "utf8");

assert.doesNotMatch(html, /id="reload-config-button"/);
assert.match(html, /id="save-config-button"/);
assert.doesNotMatch(js, /reloadConfigButton/);

console.log("config_button_layout tests passed");
