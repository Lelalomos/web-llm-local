import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw, ImageFont

from document_utils import DEFAULT_SUMMARY_PROMPT, MAX_DOCUMENT_PROMPT_CHARS, build_document_prompt, extract_document_text


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = PROJECT_ROOT / "test"


class DocumentUtilsTests(unittest.TestCase):
    def test_extract_pdf_text_from_live_test_file(self):
        pdf_path = TEST_DIR / "DeepSeek_V3_2.pdf"
        text, character_count = extract_document_text(pdf_path.name, pdf_path.read_bytes())

        self.assertGreater(character_count, 0)
        self.assertIn("Page", text)

    def test_extract_excel_text_from_live_test_file(self):
        excel_path = TEST_DIR / "Transfer's Mos.xlsx"
        text, character_count = extract_document_text(excel_path.name, excel_path.read_bytes())

        self.assertGreater(character_count, 0)
        self.assertIn("Sheet:", text)

    def test_build_document_prompt_uses_default_summary_prompt(self):
        prompt = build_document_prompt("example.pdf", "hello world", "")

        self.assertIn(DEFAULT_SUMMARY_PROMPT, prompt)
        self.assertIn("hello world", prompt)

    def test_build_document_prompt_truncates_large_documents(self):
        large_text = "a" * (MAX_DOCUMENT_PROMPT_CHARS + 250)
        prompt = build_document_prompt("example.pdf", large_text, "Summarize this")

        self.assertIn("Content truncated", prompt)
        self.assertLess(len(prompt), len(large_text) + 200)

    def test_unsupported_extension_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported file format"):
            extract_document_text("archive.zip", b"123")

    def test_extract_pdf_text_uses_ocr_for_empty_pages(self):
        fake_reader = MagicMock()
        fake_reader.pages = [MagicMock(extract_text=MagicMock(return_value="")), MagicMock(extract_text=MagicMock(return_value="Embedded text"))]
        fake_ocr_doc = MagicMock()
        fake_ocr_doc.__enter__.return_value = fake_ocr_doc
        fake_ocr_doc.load_page.return_value = object()

        with patch("document_utils.PdfReader", return_value=fake_reader), patch("document_utils.pymupdf.open", return_value=fake_ocr_doc), patch("document_utils._ocr_pdf_page", return_value="OCR page text"):
            text, character_count = extract_document_text("scan.pdf", b"%PDF-1.4")

        self.assertIn("Page 1\nOCR page text", text)
        self.assertIn("Page 2\nEmbedded text", text)
        self.assertGreater(character_count, 0)

    def test_extract_pdf_text_reads_image_only_pdf_with_ocr(self):
        pdf_bytes = _build_image_only_pdf("OCR TEST 123")

        text, character_count = extract_document_text("ocr.pdf", pdf_bytes)

        normalized_text = " ".join(text.upper().split())
        self.assertGreater(character_count, 0)
        self.assertIn("PAGE 1", normalized_text)
        self.assertRegex(normalized_text, r"(OCR|TEST|123)")


def _build_image_only_pdf(text: str) -> bytes:
    image = Image.new("RGB", (1800, 900), "white")
    drawer = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 120)
    drawer.text((120, 180), text, fill="black", font=font, spacing=40)
    drawer.text((120, 380), text, fill="black", font=font, spacing=40)

    buffer = io.BytesIO()
    try:
        image.save(buffer, format="PDF", resolution=300.0)
        return buffer.getvalue()
    finally:
        image.close()


if __name__ == "__main__":
    unittest.main()
