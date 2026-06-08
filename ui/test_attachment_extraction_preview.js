const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const js = fs.readFileSync(path.join(__dirname, "index.js"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "index.css"), "utf8");

assert.match(html, /accept="[^"]*\.jpg[^"]*\.jpeg[^"]*\.png[^"]*"/);
assert.match(html, /Attach File \(PDF, Office, Image, TXT, CSV\.\.\.\)/);

assert.match(js, /function renderExtractionPreview\(file, mode = "input"\)/);
assert.match(js, /function getExtractionLabel\(file\)/);
assert.match(js, /Qwen-VL: \$\{model\}/);
assert.match(js, /Tesseract fallback from \$\{fallbackFrom\}/);
assert.match(js, /function startUploadStatus\(fileName\)/);
assert.match(js, /function isImageUpload\(file\)/);
assert.match(js, /function renderOriginalImagePreview\(file, mode = "input"\)/);
assert.match(js, /URL\.createObjectURL\(file\)/);
assert.match(js, /URL\.revokeObjectURL\(file\.imagePreviewUrl\)/);
assert.match(js, /onload="URL\.revokeObjectURL\(this\.src\)"/);
assert.match(js, /Still working\. OCR\/model extraction can take a while/);
assert.match(js, /Original extraction/);
assert.match(js, /renderAttachmentChip\(attachedFile\)/);
assert.match(js, /appendMessage\("user", userVisiblePrompt, activeFileName, activeFile\)/);
assert.match(js, /if \(!activeFile\) \{\s*chatHistory\.forEach\(msg => apiMessages\.push\(msg\)\);/s);
assert.match(js, /renderOriginalImagePreview\(fileExtraction, "message"\)/);
assert.match(js, /file\?\.isImage \? "🖼️" : "📄"/);

assert.match(css, /\.upload-progress/);
assert.match(css, /\.upload-spinner/);
assert.match(css, /\.original-image-preview/);
assert.match(css, /object-fit: contain;/);
assert.match(css, /\.extraction-preview/);
assert.match(css, /max-height: 220px;/);
assert.match(css, /white-space: pre-wrap;/);

console.log("attachment extraction preview checks passed");
