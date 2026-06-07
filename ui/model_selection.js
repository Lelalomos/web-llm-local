function pickPreferredModel(models) {
    const modelNames = models.map(model => model.name);

    if (modelNames.includes("gemma4:e2b")) {
        return "gemma4:e2b";
    }

    const gemmaModel = models.find(model => model.name.startsWith("gemma4"));
    if (gemmaModel) {
        return gemmaModel.name;
    }

    const fallbackGemmaModel = models.find(model => model.name.startsWith("gemma"));
    if (fallbackGemmaModel) {
        return fallbackGemmaModel.name;
    }

    const qwenModel = models.find(model => model.name.startsWith("qwen"));
    if (qwenModel) {
        return qwenModel.name;
    }

    return models[0]?.name || "";
}

if (typeof window !== "undefined") {
    window.pickPreferredModel = pickPreferredModel;
}

if (typeof module !== "undefined") {
    module.exports = { pickPreferredModel };
}
