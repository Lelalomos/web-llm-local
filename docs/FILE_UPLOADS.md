# File Uploads

## Supported Formats

- PDF
- DOCX
- XLSX
- XLS
- TXT
- MD
- JSON
- CSV

## Current Behavior

- PDF text is extracted page by page.
- If a PDF page has no embedded text, the backend runs OCR on that page and merges the OCR result into the extracted document text.
- Excel files are converted into plain text with sheet names and row values.
- Uploaded file content is wrapped into the final prompt sent to the model.
- Large uploaded documents are truncated to the first `5000` characters before they are inserted into the chat prompt.
- If no prompt is typed after attaching a file, the default prompt is:
  - `Summarize this document and highlight the key points.`

## PDF OCR Notes

- OCR is a fallback, not the first path.
- Text-based PDFs stay faster because they skip OCR.
- Scanned PDFs are slower because each empty page must be rendered and read with Tesseract.
- OCR quality depends on page quality and language. The current default OCR language is `eng`.

## Live Test Files

Sample files for live verification are stored in `test/`:

- `test/DeepSeek_V3_2.pdf`
- `test/Transfer's Mos.xlsx`

## Recommended Manual Checks

1. Upload `test/DeepSeek_V3_2.pdf`.
2. Click send without typing.
3. Confirm the model returns a summary.
4. Upload `test/Transfer's Mos.xlsx`.
5. Click send without typing.
6. Confirm the model returns a summary with sheet-aware content.
