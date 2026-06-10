const assert = require("node:assert/strict");
const { encodeBase64, looksLikeCodeBlock, renderMarkdown } = require("../markdown_renderer");

const headingHtml = renderMarkdown("### Title");
assert.equal(headingHtml.includes('class="markdown-heading level-3"'), true);
assert.equal(headingHtml.includes(">Title<"), true);

const listHtml = renderMarkdown("- one\n- two");
assert.equal(listHtml.includes('<ul class="markdown-list">'), true);
assert.equal(listHtml.includes("<li>one</li>"), true);

const codeHtml = renderMarkdown("```python\nprint('hi')\n```");
assert.equal(codeHtml.includes('class="code-container"'), true);
assert.equal(codeHtml.includes("Copy code"), true);

const openFenceHtml = renderMarkdown("```python\nprint('hi')");
assert.equal(openFenceHtml.includes('class="code-container"'), true);

assert.equal(encodeBase64("print('hi')").length > 0, true);

assert.equal(looksLikeCodeBlock("def add(a, b):\n    return a + b\nprint(add(1, 2))"), true);
assert.equal(looksLikeCodeBlock("This is normal text.\nThis is another sentence."), false);

const heuristicCodeHtml = renderMarkdown("def add(a, b):\n    return a + b\nprint(add(1, 2))");
assert.equal(heuristicCodeHtml.includes('class="code-container"'), true);

const goCodeWithoutFence = renderMarkdown(`func fetchStock(ticker string) error {
    resp, err := http.Get("https://example.com")
    if err != nil {
        return fmt.Errorf("error making HTTP request: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("received non-200 status code: %d", resp.StatusCode)
    }

    var data StockResponse
    err = json.NewDecoder(resp.Body).Decode(&data)
    if err != nil {
        return fmt.Errorf("error decoding JSON response: %w", err)
    }

    fmt.Printf("Successfully fetched data for %s:\\n", ticker)
    return nil
}`);
assert.equal((goCodeWithoutFence.match(/class="code-container"/g) || []).length, 1);
assert.equal(goCodeWithoutFence.includes("resp.StatusCode"), true);
assert.equal(goCodeWithoutFence.includes("var data StockResponse"), true);

const tableHtml = renderMarkdown("| Description | Quantity | Unit Price | Amount |\n|---|---|---|---|\n| Subscription GLM Coding Pro | | $36.45 | $36.45 |");
assert.equal(tableHtml.includes('class="markdown-table-wrapper"'), true);
assert.equal(tableHtml.includes("<th>Description</th>"), true);
assert.equal(tableHtml.includes("<td>Subscription GLM Coding Pro</td>"), true);
assert.equal(tableHtml.includes("<td>$36.45</td>"), true);

const fencedTableHtml = renderMarkdown("```code\n| Section | Field/Description | Example Data (from template) |\n| :--- | :--- | :--- |\n| **Invoice Identification** | Invoice Number | (123456) |\n```");
assert.equal(fencedTableHtml.includes('class="markdown-table-wrapper"'), true);
assert.equal(fencedTableHtml.includes('class="code-container"'), false);
assert.equal(fencedTableHtml.includes("<th>Section</th>"), true);
assert.equal(fencedTableHtml.includes("<td><strong>Invoice Identification</strong></td>"), true);

const uppercaseFencedTableHtml = renderMarkdown("```CODE\n| Description | Quantity | Unit Price | Amount |\n|:---|:---|:---|:---|\n| Subscription GLM Coding Pro | | $36.45 | $36.45 |\n```");
assert.equal(uppercaseFencedTableHtml.includes('class="markdown-table-wrapper"'), true);
assert.equal(uppercaseFencedTableHtml.includes("Copy code"), false);
