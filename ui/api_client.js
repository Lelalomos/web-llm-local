const DEFAULT_API_BASE = "http://127.0.0.1:8001";
const RETRYABLE_API_STATUSES = new Set([404, 502, 503, 504]);

let preferredApiBase = "";

function normalizeApiPath(path) {
    const normalized = String(path || "").trim();
    if (!normalized) {
        return "/";
    }
    return normalized.startsWith("/") ? normalized : `/${normalized}`;
}

function buildApiBaseCandidates(currentBase = preferredApiBase) {
    const orderedBases = [currentBase, "", DEFAULT_API_BASE];
    return orderedBases.filter((base, index) => orderedBases.indexOf(base) === index);
}

function shouldRetryApiResponse(response) {
    return Boolean(response) && RETRYABLE_API_STATUSES.has(response.status);
}

async function fetchApi(path, options = {}, fetchImpl = fetch) {
    const normalizedPath = normalizeApiPath(path);
    const candidates = buildApiBaseCandidates();
    let lastResponse = null;
    let lastError = null;

    for (const base of candidates) {
        try {
            const response = await fetchImpl(`${base}${normalizedPath}`, options);
            if (!shouldRetryApiResponse(response)) {
                preferredApiBase = base;
                return response;
            }
            lastResponse = response;
        } catch (error) {
            lastError = error;
        }
    }

    if (lastResponse) {
        return lastResponse;
    }

    throw lastError || new Error(`API request failed for ${normalizedPath}`);
}

function getPreferredApiBase() {
    return preferredApiBase;
}

function setPreferredApiBase(base) {
    preferredApiBase = String(base || "");
}

if (typeof module !== "undefined") {
    module.exports = {
        DEFAULT_API_BASE,
        buildApiBaseCandidates,
        fetchApi,
        getPreferredApiBase,
        normalizeApiPath,
        setPreferredApiBase,
        shouldRetryApiResponse,
    };
}

if (typeof window !== "undefined") {
    window.DEFAULT_API_BASE = DEFAULT_API_BASE;
    window.buildApiBaseCandidates = buildApiBaseCandidates;
    window.fetchApi = fetchApi;
    window.getPreferredApiBase = getPreferredApiBase;
    window.normalizeApiPath = normalizeApiPath;
    window.setPreferredApiBase = setPreferredApiBase;
    window.shouldRetryApiResponse = shouldRetryApiResponse;
}
