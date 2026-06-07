const MODEL_NAME_PATTERN = /^[A-Za-z0-9._:/-]+$/;

function isValidModelName(modelName) {
    const normalized = String(modelName || "").trim();
    return normalized.length > 0 && MODEL_NAME_PATTERN.test(normalized);
}

function normalizeModelName(modelName) {
    return String(modelName || "").trim();
}

function buildDeleteModelOptions(models) {
    const options = [{ value: "", label: "Select installed model" }];
    for (const model of models || []) {
        if (!model || !model.name) {
            continue;
        }
        options.push({ value: model.name, label: model.name });
    }
    return options;
}

if (typeof module !== "undefined") {
    module.exports = { isValidModelName, normalizeModelName, buildDeleteModelOptions };
}

if (typeof window !== "undefined") {
    window.isValidModelName = isValidModelName;
    window.normalizeModelName = normalizeModelName;
    window.buildDeleteModelOptions = buildDeleteModelOptions;
}
