function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function encodeBase64(text) {
    if (typeof btoa === "function") {
        return btoa(unescape(encodeURIComponent(text)));
    }
    if (typeof Buffer !== "undefined") {
        return Buffer.from(text, "utf-8").toString("base64");
    }
    throw new Error("No base64 encoder available");
}

function createCodeBlockHtml(lang, code, codeBlockIndex) {
    const cleanedCode = code.trim();
    const base64Code = encodeBase64(cleanedCode);
    const btnId = `copy-btn-${codeBlockIndex}`;
    const displayLang = lang || "code";

    return `
        <div class="code-container">
            <div class="code-header">
                <span class="code-lang">${displayLang}</span>
                <button class="code-copy-btn" id="${btnId}" onclick="copyCodeBlock('${btnId}', '${base64Code}')">Copy code</button>
            </div>
            <pre><code class="language-${displayLang}">${cleanedCode}</code></pre>
        </div>
    `;
}

function looksLikeCodeBlock(block) {
    const trimmedBlock = String(block || "").trim();
    if (!trimmedBlock) {
        return false;
    }

    const lines = trimmedBlock.split("\n").map(line => line.trimEnd()).filter(Boolean);
    if (lines.length < 2) {
        return false;
    }

    const codePattern = /(^\s{2,}\S)|(^def\s+\w+\()|(^class\s+\w+)|(^import\s+\w+)|(^from\s+\w+\s+import\s+)|(^if\s+__name__\s*==)|(^return\b)|(^print\()|(^for\s+\w+\s+in\s+)|(^while\s+.+:)|(^try:)|(^except\b)|(^with\s+.+:)|(^const\s+\w+)|(^let\s+\w+)|(^function\s+\w+\()|(^app\s*=\s*FastAPI)|(^@\w+)/;
    const punctuationPattern = /[:{}()[\]=,]|\bNone\b|\bTrue\b|\bFalse\b/;

    let codeLikeLines = 0;
    for (const line of lines) {
        if (codePattern.test(line) || punctuationPattern.test(line)) {
            codeLikeLines += 1;
        }
    }

    return codeLikeLines >= 2 && codeLikeLines >= Math.ceil(lines.length / 2);
}

function renderInlineMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return html;
}

function renderTextBlock(block) {
    if (looksLikeCodeBlock(block)) {
        return createCodeBlockHtml("", escapeHtml(block), `heuristic-${Math.random().toString(36).slice(2, 8)}`);
    }

    const lines = block.split("\n");
    const rendered = [];
    let listItems = [];
    const codePlaceholderPattern = /^@@CODE_BLOCK_\d+@@$/;

    function flushList() {
        if (!listItems.length) {
            return;
        }
        rendered.push(`<ul class="markdown-list">${listItems.join("")}</ul>`);
        listItems = [];
    }

    for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        const trimmed = line.trim();

        if (!trimmed) {
            flushList();
            continue;
        }

        if (codePlaceholderPattern.test(trimmed)) {
            flushList();
            rendered.push(trimmed);
            continue;
        }

        const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
        if (headingMatch) {
            flushList();
            const level = headingMatch[1].length;
            rendered.push(`<h${level + 1} class="markdown-heading level-${level}">${renderInlineMarkdown(headingMatch[2])}</h${level + 1}>`);
            continue;
        }

        if (/^[-*]\s+/.test(trimmed)) {
            const itemText = trimmed.replace(/^[-*]\s+/, "");
            listItems.push(`<li>${renderInlineMarkdown(itemText)}</li>`);
            continue;
        }

        if (/^\d+\.\s+/.test(trimmed)) {
            const itemText = trimmed.replace(/^\d+\.\s+/, "");
            listItems.push(`<li>${renderInlineMarkdown(itemText)}</li>`);
            continue;
        }

        flushList();
        rendered.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
    }

    flushList();
    return rendered.join("");
}

function renderMarkdown(text) {
    if (!text) {
        return "";
    }

    const sourceText = String(text);
    const codeBlocks = [];
    let codeBlockIndex = 0;
    let workingText = sourceText.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
        codeBlockIndex += 1;
        const placeholder = `@@CODE_BLOCK_${codeBlockIndex}@@`;
        codeBlocks.push({ placeholder, html: createCodeBlockHtml(lang, escapeHtml(code), codeBlockIndex) });
        return placeholder;
    });

    const openFenceMatch = workingText.match(/```(\w*)\n([\s\S]*)$/);
    if (openFenceMatch) {
        codeBlockIndex += 1;
        const placeholder = `@@CODE_BLOCK_${codeBlockIndex}@@`;
        codeBlocks.push({ placeholder, html: createCodeBlockHtml(openFenceMatch[1], escapeHtml(openFenceMatch[2]), codeBlockIndex) });
        workingText = workingText.replace(/```(\w*)\n([\s\S]*)$/, placeholder);
    }

    const blocks = workingText.split(/\n{2,}/);
    let html = blocks
        .map(block => block.trim())
        .filter(Boolean)
        .map(renderTextBlock)
        .join("");

    for (const codeBlock of codeBlocks) {
        html = html.replace(codeBlock.placeholder, codeBlock.html);
    }

    return html;
}

if (typeof window !== "undefined") {
    window.renderMarkdown = renderMarkdown;
}

if (typeof module !== "undefined") {
    module.exports = { encodeBase64, escapeHtml, looksLikeCodeBlock, renderMarkdown };
}
