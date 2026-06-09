const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sandbox = {
    window: {},
    Math,
    Date,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "chat_session.js"), "utf8"), sandbox);

const sessionId = sandbox.window.createChatSessionId();

assert.match(sessionId, /^chat-\d{14}-[a-z0-9]{6}$/);
assert.equal(sandbox.window.shouldPersistChatSession([]), false);
assert.equal(sandbox.window.shouldPersistChatSession([{ role: "user", content: "hello" }]), true);

console.log("chat_session tests passed");
