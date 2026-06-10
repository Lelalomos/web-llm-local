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
- JPG
- JPEG
- PNG

## Current Behavior

- PDF extraction defaults to the `page_image_ocr` pipeline.
- In `page_image_ocr` mode, every PDF page is rendered to a JPG image first.
- The backend OCRs each rendered JPG page, combines the page text in page order, and sends that combined text to the model.
- The PDF OCR fallback priority is Qwen-VL page-image OCR, then Surya OCR, then Tesseract page-image OCR.
- Other PDF modes are still available for debugging or performance tuning.
- When `ocr_engine` is `qwen_vl`, scanned PDF pages and image uploads use the configured Ollama vision model for OCR.
- The backend combines Docling parsing output and Surya OCR output before sending document context to the model.
- If Docling or Surya fails or is unavailable, the backend falls back to the legacy PDF extractor.
- The legacy PDF extractor reads embedded text page by page and uses PyMuPDF + Tesseract OCR only for pages with no embedded text.
- Excel files are converted into plain text with sheet names and row values.
- JPG, JPEG, and PNG image files are converted into text before being sent to the model.
- Image uploads show the original image preview in the chat message after send.
- Image OCR uses Qwen-VL first when `ocr_engine` is `auto` or `qwen_vl`, then falls back to Tesseract if the vision model fails.
- Uploaded file content is wrapped into the final prompt sent to the model.
- Uploaded-file chats include previous chat turns. Stored summary memory is controlled by `memory_used.upload_file` in `backend/config/app_config.json` and defaults to off so the uploaded file remains the main context.
- The UI shows a collapsible `Original extraction` preview after upload and keeps that preview in the sent user message.
- The extraction preview uses the same `20000` character limit as the document prompt and shows detected PDF page markers in the preview metadata when present.
- While upload extraction is running, the UI shows a live `Still working` status with elapsed time so OCR/Docling work does not look frozen.
- When the user sends the uploaded file to chat, the attachment preview above the input is cleared.
- Large uploaded documents are truncated to the first `20000` characters before they are inserted into the chat prompt.
- Uploaded-file chat requests use a larger default model context window so multi-page OCR text has room to reach the model.
- If no prompt is typed after attaching a file, the default prompt is:
  - `Summarize this document and highlight the key points.`

## PDF OCR Notes

- The default pipeline is `page_image_ocr`, which converts every PDF page to JPG and OCRs each page image.
- `pdf_extraction_mode` can be set to `page_image_ocr`, `qwen_vl`, `surya_docling`, `legacy`, or `auto`.
- `page_image_ocr` tries Qwen-VL first, then Surya OCR, then Tesseract.
- The advanced `surya_docling` pipeline uses Docling for document parsing and Surya for OCR.
- Surya and Docling can be slower and heavier than the legacy extractor.
- First use can download model weights.
- Surya uses GPU when PyTorch can see a GPU in the backend container; CUDA/no-driver/out-of-memory failures retry on CPU before the legacy fallback.
- `PDF_SURYA_TIMEOUT_SECONDS` defaults to `60` so slow Surya runs fall back instead of blocking uploads for several minutes.
- `PDF_SURYA_MIN_DOCLING_CHARS` defaults to `1000`; when Docling extracts at least that much text, Surya is skipped for that PDF.
- `PDF_FAST_TEXT_MIN_CHARS` defaults to `1000`; when embedded PDF text reaches that threshold, Docling/Surya is skipped for faster uploads.
- The old Tesseract path remains as fallback.
- Set `pdf_extraction_mode` in `backend/config/app_config.json` to choose the app-level PDF pipeline.
- `PDF_EXTRACTION_MODE` is only the environment fallback when the app config does not choose a PDF mode.

## Image OCR Notes

- Image uploads can use Qwen-VL through Ollama or Tesseract OCR.
- The current app config uses `ocr_engine: qwen_vl` and `vision_ocr_model: qwen3-vl:latest`.
- `ocr_engine` can be `auto`, `tesseract`, `qwen_vl`, or `surya_docling`.
- `qwen_vl` uses the same configured vision model for image files and scanned PDF pages.
- `qwen_vl` sends Ollama `num_gpu: 999` by default so the vision OCR model uses GPU when the Ollama container can see an NVIDIA GPU.
- `surya_docling` is for PDF extraction only. Image files still fall back to Qwen-VL or Tesseract.
- `IMAGE_OCR_LANGUAGE` defaults to the same value as `PDF_OCR_LANGUAGE`.
- If `IMAGE_OCR_LANGUAGE` is not set, the default OCR language is `eng`.

## Vision OCR Config

Configure Qwen-VL OCR in `backend/config/app_config.json`:

```json
{
  "ocr_engine": "qwen_vl",
  "vision_ocr_model": "qwen3-vl:latest",
  "vision_ocr_timeout_seconds": 120,
  "vision_ocr_prompt": "Extract all visible text from this image. Preserve line breaks and table structure. Return only the extracted text. If the text is Thai, return Thai text exactly."
}
```

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
