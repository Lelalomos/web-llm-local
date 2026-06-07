const assert = require("node:assert/strict");
const { shouldLikelySearch } = require("./web_search_state");

assert.equal(shouldLikelySearch("summarize about news of stock in today", true), true);
assert.equal(shouldLikelySearch("latest NVIDIA stock price", true), true);
assert.equal(shouldLikelySearch("write code to sort a list", true), false);
assert.equal(shouldLikelySearch("explain gravity", true), false);
assert.equal(shouldLikelySearch("latest NVIDIA stock price", false), false);
