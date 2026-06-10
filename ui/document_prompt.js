const DEFAULT_DOCUMENT_PROMPT = "Summarize this document and highlight the key points. Include important extracted values such as dates, IDs, names, line items, totals, and amounts when present.";
const MAX_DOCUMENT_PROMPT_CHARS = 20000;

function truncateDocumentText(fileText) {
    const normalizedText = String(fileText || "");
    if (normalizedText.length <= MAX_DOCUMENT_PROMPT_CHARS) {
        return normalizedText;
    }

    return (
        normalizedText.slice(0, MAX_DOCUMENT_PROMPT_CHARS).trimEnd() +
        `\n\n[Content truncated to the first ${MAX_DOCUMENT_PROMPT_CHARS} characters to fit the model context window.]`
    );
}

function buildFinalPrompt(userPrompt, attachedFileName, attachedFileText) {
    const prompt = String(userPrompt || "").trim();
    if (!attachedFileName || !attachedFileText) {
        return prompt;
    }

    const effectivePrompt = prompt || DEFAULT_DOCUMENT_PROMPT;
    const truncatedFileText = truncateDocumentText(attachedFileText);
    return (
        `Context from uploaded file "${attachedFileName}":\n\n` +
        "--- START OF FILE CONTENT ---\n" +
        `${truncatedFileText}\n` +
        "--- END OF FILE CONTENT ---\n\n" +
        `Use the file content above to answer this prompt: ${effectivePrompt}`
    );
}

if (typeof window !== "undefined") {
    window.DEFAULT_DOCUMENT_PROMPT = DEFAULT_DOCUMENT_PROMPT;
    window.MAX_DOCUMENT_PROMPT_CHARS = MAX_DOCUMENT_PROMPT_CHARS;
    window.buildFinalPrompt = buildFinalPrompt;
}

if (typeof module !== "undefined") {
    module.exports = { DEFAULT_DOCUMENT_PROMPT, MAX_DOCUMENT_PROMPT_CHARS, buildFinalPrompt, truncateDocumentText };
}
