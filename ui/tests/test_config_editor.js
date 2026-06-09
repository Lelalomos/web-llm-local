const assert = require("node:assert/strict");
const { formatConfigForEditor, parseConfigEditorValue } = require("../config_editor");

const configText = formatConfigForEditor({ default_model: "gemma4:e2b" });
assert.equal(configText.includes('"default_model": "gemma4:e2b"'), true);

assert.deepEqual(
    parseConfigEditorValue('{"default_web_search_mode":"off"}'),
    { default_web_search_mode: "off" }
);

assert.throws(() => parseConfigEditorValue("[]"), /JSON object/);
assert.throws(() => parseConfigEditorValue("{bad json"), /valid JSON/);

console.log("config_editor tests passed");
