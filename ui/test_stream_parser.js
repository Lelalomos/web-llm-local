const assert = require("node:assert/strict");
const { parseNdjsonChunk } = require("./stream_parser");

let state = parseNdjsonChunk("", '{"type":"search_status","search_used":true}\n{"message":{"content":"Hel');
assert.equal(state.messages.length, 1);
assert.equal(state.messages[0].type, "search_status");
assert.equal(state.buffer, '{"message":{"content":"Hel');

state = parseNdjsonChunk(state.buffer, 'lo"}}\n{"message":{"content":" world"}}\n');
assert.equal(state.messages.length, 2);
assert.equal(state.messages[0].message.content, "Hello");
assert.equal(state.messages[1].message.content, " world");
assert.equal(state.buffer, "");

console.log("stream_parser tests passed");
