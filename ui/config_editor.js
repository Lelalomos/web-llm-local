function formatConfigForEditor(config) {
    return `${JSON.stringify(config || {}, null, 2)}\n`;
}

function parseConfigEditorValue(rawValue) {
    let parsed;
    try {
        parsed = JSON.parse(String(rawValue || "").trim() || "{}");
    } catch (error) {
        throw new Error("Config must be valid JSON.");
    }

    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("Config must be a JSON object.");
    }

    return parsed;
}

if (typeof module !== "undefined") {
    module.exports = { formatConfigForEditor, parseConfigEditorValue };
}

if (typeof window !== "undefined") {
    window.formatConfigForEditor = formatConfigForEditor;
    window.parseConfigEditorValue = parseConfigEditorValue;
}
