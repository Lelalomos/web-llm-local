const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const sandbox = { window: {} };
vm.createContext(sandbox);

const script = fs.readFileSync(path.join(__dirname, "..", "layout_state.js"), "utf8");
vm.runInContext(script, sandbox);

assert.strictEqual(sandbox.window.isCompactLayout(900), true);
assert.strictEqual(sandbox.window.isCompactLayout(901), false);
assert.strictEqual(sandbox.window.shouldCloseSidebarAfterAction(640), true);
assert.strictEqual(sandbox.window.shouldCloseSidebarAfterAction(1280), false);

console.log("layout_state tests passed");
