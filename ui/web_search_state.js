const AUTO_SEARCH_HINTS = [
    "latest", "recent", "today", "yesterday", "tomorrow", "current", "news",
    "price", "stock", "market", "finance", "weather", "forecast", "release",
    "update", "earnings", "schedule", "score", "ข่าว", "ล่าสุด", "วันนี้",
    "ราคา", "หุ้น", "ตลาด", "การเงิน", "อากาศ", "อัปเดต",
];

const NO_SEARCH_HINTS = [
    "write code",
    "python script",
    "summarize this file",
    "explain this code",
    "use the file content above",
];

function shouldLikelySearch(query, autoSearchEnabled) {
    if (!autoSearchEnabled) {
        return false;
    }

    const normalized = String(query || "").trim().toLowerCase();
    if (!normalized) {
        return false;
    }

    if (NO_SEARCH_HINTS.some(hint => normalized.includes(hint))) {
        return false;
    }

    return AUTO_SEARCH_HINTS.some(hint => normalized.includes(hint));
}

if (typeof window !== "undefined") {
    window.shouldLikelySearch = shouldLikelySearch;
}

if (typeof module !== "undefined") {
    module.exports = { shouldLikelySearch };
}
