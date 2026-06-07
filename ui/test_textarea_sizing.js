const assert = require("node:assert/strict");
const { CHAT_INPUT_MAX_HEIGHT, getTextareaHeight } = require("./textarea_sizing");

assert.equal(getTextareaHeight(0), 0);
assert.equal(getTextareaHeight(48), 48);
assert.equal(getTextareaHeight(240), CHAT_INPUT_MAX_HEIGHT);
assert.equal(getTextareaHeight("72"), 72);
