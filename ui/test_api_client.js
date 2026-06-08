const assert = require("node:assert/strict");
const {
    buildApiBaseCandidates,
    DEFAULT_API_BASE,
    fetchApi,
    getPreferredApiBase,
    normalizeApiPath,
    setPreferredApiBase,
    shouldRetryApiResponse,
} = require("./api_client");

assert.equal(normalizeApiPath("/api/chat"), "/api/chat");
assert.equal(normalizeApiPath("api/chat"), "/api/chat");
assert.deepEqual(buildApiBaseCandidates(""), ["", DEFAULT_API_BASE]);
assert.deepEqual(buildApiBaseCandidates(DEFAULT_API_BASE), [DEFAULT_API_BASE, ""]);
assert.equal(shouldRetryApiResponse({ status: 503 }), true);
assert.equal(shouldRetryApiResponse({ status: 400 }), false);

async function testFallbackOnNotFound() {
    setPreferredApiBase("");
    const calls = [];
    const response = await fetchApi("/api/config", {}, async (url) => {
        calls.push(url);
        if (url === "/api/config") {
            return { ok: false, status: 404 };
        }
        if (url === `${DEFAULT_API_BASE}/api/config`) {
            return { ok: true, status: 200 };
        }
        throw new Error(`Unexpected url ${url}`);
    });
    assert.equal(response.ok, true);
    assert.deepEqual(calls, ["/api/config", `${DEFAULT_API_BASE}/api/config`]);
    assert.equal(getPreferredApiBase(), DEFAULT_API_BASE);
}

async function testFallbackOnNetworkError() {
    setPreferredApiBase("");
    const calls = [];
    const response = await fetchApi("/api/tags", {}, async (url) => {
        calls.push(url);
        if (url === "/api/tags") {
            throw new Error("proxy unavailable");
        }
        return { ok: true, status: 200 };
    });
    assert.equal(response.ok, true);
    assert.deepEqual(calls, ["/api/tags", `${DEFAULT_API_BASE}/api/tags`]);
}

Promise.resolve()
    .then(testFallbackOnNotFound)
    .then(testFallbackOnNetworkError)
    .then(() => {
        console.log("api_client tests passed");
    });
