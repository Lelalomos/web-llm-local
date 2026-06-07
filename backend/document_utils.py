import io
import os

import openpyxl
import pymupdf
import pytesseract
import xlrd
from docx import Document
from PIL import Image
from pypdf import PdfReader


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv"}
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls"} | SUPPORTED_TEXT_EXTENSIONS
DEFAULT_SUMMARY_PROMPT = "Summarize this document and highlight the key points."
MAX_DOCUMENT_PROMPT_CHARS = 5000
PDF_OCR_LANGUAGE = os.getenv("PDF_OCR_LANGUAGE", "eng")
PDF_OCR_DPI = int(os.getenv("PDF_OCR_DPI", "200"))


def extract_document_text(filename: str, content: bytes) -> tuple[str, int]:
    _, ext = os.path.splitext(filename.lower())

    if ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise ValueError(f"Unsupported file format '{ext}'")

    if ext == ".pdf":
        extracted_text = _extract_pdf_text(content)
    elif ext == ".docx":
        extracted_text = _extract_docx_text(content)
    elif ext == ".xlsx":
        extracted_text = _extract_xlsx_text(content)
    elif ext == ".xls":
        extracted_text = _extract_xls_text(content)
    else:
        extracted_text = content.decode("utf-8", errors="ignore")

    cleaned_text = extracted_text.strip()
    return cleaned_text, len(extracted_text)


def build_document_prompt(file_name: str, file_text: str, user_prompt: str) -> str:
    prompt = (user_prompt or "").strip() or DEFAULT_SUMMARY_PROMPT
    document_body = _truncate_document_text(file_text)
    return (
        f'Context from uploaded file "{file_name}":\n\n'
        "--- START OF FILE CONTENT ---\n"
        f"{document_body}\n"
        "--- END OF FILE CONTENT ---\n\n"
        f"Use the file content above to answer this prompt: {prompt}"
    )


def _extract_pdf_text(content: bytes) -> str:
    pdf_file = io.BytesIO(content)
    reader = PdfReader(pdf_file)
    text_parts = []
    with pymupdf.open(stream=content, filetype="pdf") as ocr_document:
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                text = _ocr_pdf_page(ocr_document.load_page(index - 1)).strip()
            if text:
                text_parts.append(f"Page {index}\n{text}")
    return "\n\n".join(text_parts)


def _ocr_pdf_page(page) -> str:
    pixmap = page.get_pixmap(dpi=PDF_OCR_DPI, alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        return pytesseract.image_to_string(image, lang=PDF_OCR_LANGUAGE)
    finally:
        image.close()


def _extract_docx_text(content: bytes) -> str:
    docx_file = io.BytesIO(content)
    doc = Document(docx_file)
    return "\n".join(para.text for para in doc.paragraphs if para.text)


def _extract_xlsx_text(content: bytes) -> str:
    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    return _render_workbook_sheets(workbook.sheetnames, lambda name: workbook[name].iter_rows(values_only=True))


def _extract_xls_text(content: bytes) -> str:
    workbook = xlrd.open_workbook(file_contents=content)

    def iter_rows(sheet_name: str):
        sheet = workbook.sheet_by_name(sheet_name)
        for row_index in range(sheet.nrows):
            yield sheet.row_values(row_index)

    return _render_workbook_sheets(workbook.sheet_names(), iter_rows)


def _render_workbook_sheets(sheet_names, row_provider) -> str:
    parts = []
    for sheet_name in sheet_names:
        parts.append(f"Sheet: {sheet_name}")
        for row in row_provider(sheet_name):
            row_text = ", ".join(str(value) if value is not None else "" for value in row).strip(", ")
            if row_text:
                parts.append(row_text)
        parts.append("")
    return "\n".join(parts).strip()


def _truncate_document_text(file_text: str) -> str:
    if len(file_text) <= MAX_DOCUMENT_PROMPT_CHARS:
        return file_text

    return (
        file_text[:MAX_DOCUMENT_PROMPT_CHARS].rstrip() +
        f"\n\n[Content truncated to the first {MAX_DOCUMENT_PROMPT_CHARS} characters to fit the model context window.]"
    )
