window.createChatSessionId = function createChatSessionId() {
    const timestamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
    const randomPart = Math.random().toString(36).slice(2, 8);
    return `chat-${timestamp}-${randomPart}`;
};

window.shouldPersistChatSession = function shouldPersistChatSession(chatHistory) {
    return Array.isArray(chatHistory) && chatHistory.length > 0;
};
