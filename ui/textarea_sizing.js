const CHAT_INPUT_MAX_HEIGHT = 200;

function getTextareaHeight(scrollHeight, maxHeight = CHAT_INPUT_MAX_HEIGHT) {
    const safeScrollHeight = Math.max(Number(scrollHeight) || 0, 0);
    return Math.min(safeScrollHeight, maxHeight);
}

if (typeof window !== "undefined") {
    window.getTextareaHeight = getTextareaHeight;
    window.CHAT_INPUT_MAX_HEIGHT = CHAT_INPUT_MAX_HEIGHT;
}

if (typeof module !== "undefined") {
    module.exports = { CHAT_INPUT_MAX_HEIGHT, getTextareaHeight };
}
