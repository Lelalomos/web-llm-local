import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw, ImageFont

from document_utils import (
    DEFAULT_SUMMARY_PROMPT,
    MAX_DOCUMENT_PROMPT_CHARS,
    _extract_text_from_surya_results,
    _extract_pdf_with_surya,
    _extract_pdf_text_with_surya_docling,
    PDF_FAST_TEXT_MIN_CHARS,
    PDF_SURYA_MIN_DOCLING_CHARS,
    PDF_SURYA_TIMEOUT_SECONDS,
    build_document_prompt,
    extract_document_text,
    extract_document_text_with_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = PROJECT_ROOT / "test"


class DocumentUtilsTests(unittest.TestCase):
    def test_extract_pdf_text_from_live_test_file(self):
        pdf_path = TEST_DIR / "DeepSeek_V3_2.pdf"
        with patch("document_utils.PDF_EXTRACTION_MODE", "legacy"):
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

        with patch("document_utils.PDF_EXTRACTION_MODE", "legacy"), patch("document_utils.PdfReader", return_value=fake_reader), patch("document_utils.pymupdf.open", return_value=fake_ocr_doc), patch("document_utils._ocr_pdf_page", return_value="OCR page text"):
            text, character_count = extract_document_text("scan.pdf", b"%PDF-1.4")

        self.assertIn("Page 1\nOCR page text", text)
        self.assertIn("Page 2\nEmbedded text", text)
        self.assertGreater(character_count, 0)

    def test_surya_docling_pipeline_combines_results(self):
        with patch("document_utils._extract_pdf_with_docling", return_value="# Parsed heading"), patch("document_utils._extract_pdf_with_surya", return_value="OCR text"):
            text = _extract_pdf_text_with_surya_docling(b"%PDF-1.4", "report.pdf")

        self.assertIn("Document Parsing Result (Docling)", text)
        self.assertIn("# Parsed heading", text)
        self.assertIn("OCR Result (Surya)", text)
        self.assertIn("OCR text", text)

    def test_surya_docling_pipeline_skips_surya_when_docling_has_enough_text(self):
        parsed_text = "A" * PDF_SURYA_MIN_DOCLING_CHARS
        with patch("document_utils._extract_pdf_with_docling", return_value=parsed_text), patch("document_utils._extract_pdf_with_surya") as surya_mock:
            text = _extract_pdf_text_with_surya_docling(b"%PDF-1.4", "report.pdf")

        surya_mock.assert_not_called()
        self.assertIn("Document Parsing Result (Docling)", text)
        self.assertIn(parsed_text, text)
        self.assertNotIn("OCR Result (Surya)", text)

    def test_pdf_fast_embedded_text_skips_docling_for_text_pdf(self):
        embedded_text = "A" * PDF_FAST_TEXT_MIN_CHARS
        fake_page = MagicMock()
        fake_page.extract_text.return_value = embedded_text
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        with patch("document_utils.PDF_EXTRACTION_MODE", "surya_docling"), patch("document_utils.PdfReader", return_value=fake_reader), patch("document_utils._extract_pdf_text_with_surya_docling") as advanced_mock:
            text, character_count = extract_document_text("text.pdf", b"%PDF-1.4")

        advanced_mock.assert_not_called()
        self.assertIn(embedded_text, text)
        self.assertGreater(character_count, 0)

    def test_pdf_sparse_embedded_text_uses_advanced_pipeline(self):
        fake_page = MagicMock()
        fake_page.extract_text.return_value = "short"
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        with patch("document_utils.PDF_EXTRACTION_MODE", "surya_docling"), patch("document_utils.PdfReader", return_value=fake_reader), patch("document_utils._extract_pdf_text_with_surya_docling", return_value="advanced text") as advanced_mock:
            text, character_count = extract_document_text("scan.pdf", b"%PDF-1.4")

        advanced_mock.assert_called_once()
        self.assertEqual(text, "advanced text")
        self.assertGreater(character_count, 0)

    def test_surya_docling_failure_falls_back_to_legacy(self):
        with patch("document_utils.PDF_EXTRACTION_MODE", "surya_docling"), patch("document_utils._extract_pdf_text_with_surya_docling", side_effect=RuntimeError("advanced failed")), patch("document_utils._extract_pdf_text_legacy", return_value="legacy text"):
            text, character_count = extract_document_text("report.pdf", b"%PDF-1.4")

        self.assertEqual(text, "legacy text")
        self.assertGreater(character_count, 0)

    def test_extract_text_from_surya_results_collects_nested_text(self):
        text = _extract_text_from_surya_results(
            {
                "report": [
                    {"page": 0, "text_lines": [{"text": "First line"}, {"text": "Second line"}]},
                    {"page": 1, "text": "First line"},
                ]
            }
        )

        self.assertEqual(text, "First line\nSecond line")

    def test_extract_pdf_with_surya_uses_results_dir_cli(self):
        def fake_run(command, **kwargs):
            output_dir = Path(command[command.index("--results_dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "results.json").write_text('{"pages": [{"text": "OCR text"}]}', encoding="utf-8")
            return MagicMock(returncode=0, stderr="", stdout="")

        with patch("document_utils.subprocess.run", side_effect=fake_run) as run_mock:
            text = _extract_pdf_with_surya(b"%PDF-1.4", "report.pdf")

        command = run_mock.call_args.args[0]
        self.assertIn("--results_dir", command)
        self.assertNotIn("--output_dir", command)
        self.assertEqual(text, "OCR text")

    def test_extract_pdf_with_surya_retries_cpu_after_cuda_failure(self):
        def fake_run(command, **kwargs):
            if kwargs.get("env", {}).get("TORCH_DEVICE") == "cpu":
                output_dir = Path(command[command.index("--results_dir") + 1])
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "results.json").write_text('{"pages": [{"text": "CPU OCR text"}]}', encoding="utf-8")
                return MagicMock(returncode=0, stderr="", stdout="")
            return MagicMock(returncode=1, stderr="CUDA out of memory", stdout="")

        with patch("document_utils.subprocess.run", side_effect=fake_run) as run_mock:
            text = _extract_pdf_with_surya(b"%PDF-1.4", "report.pdf")

        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(run_mock.call_args.kwargs["env"]["TORCH_DEVICE"], "cpu")
        self.assertEqual(text, "CPU OCR text")

    def test_surya_timeout_default_is_short_for_uploads(self):
        self.assertEqual(PDF_SURYA_TIMEOUT_SECONDS, 60)

    def test_extract_pdf_text_reads_image_only_pdf_with_ocr(self):
        pdf_bytes = _build_image_only_pdf("OCR TEST 123")

        with patch("document_utils.PDF_EXTRACTION_MODE", "legacy"):
            text, character_count = extract_document_text("ocr.pdf", pdf_bytes)

        normalized_text = " ".join(text.upper().split())
        self.assertGreater(character_count, 0)
        self.assertIn("PAGE 1", normalized_text)
        self.assertRegex(normalized_text, r"(OCR|TEST|123)")

    def test_extract_jpg_routes_to_image_ocr(self):
        with patch("document_utils._extract_image_text_with_metadata", return_value=("image ocr text", {"ocr_engine_used": "qwen_vl"})) as image_ocr:
            text, character_count = extract_document_text("photo.jpg", b"image-bytes")

        image_ocr.assert_called_once_with(b"image-bytes", {}, None)
        self.assertEqual(text, "image ocr text")
        self.assertGreater(character_count, 0)

    def test_extract_image_uses_qwen_vl_when_configured(self):
        fake_response = MagicMock()
        fake_response.json.return_value = {"message": {"content": "สวัสดี"}}

        with patch("document_utils.requests.post", return_value=fake_response) as post_mock:
            text, character_count = extract_document_text(
                "thai.png",
                b"image-bytes",
                {
                    "ocr_engine": "qwen_vl",
                    "vision_ocr_model": "qwen3-vl:latest",
                    "vision_ocr_timeout_seconds": 120,
                    "vision_ocr_prompt": "Extract text",
                },
                "http://ollama:11434",
            )

        fake_response.raise_for_status.assert_called_once()
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen3-vl:latest")
        self.assertEqual(payload["messages"][0]["images"], ["aW1hZ2UtYnl0ZXM="])
        self.assertEqual(payload["options"]["num_gpu"], 999)
        self.assertEqual(text, "สวัสดี")
        self.assertGreater(character_count, 0)

    def test_extract_image_metadata_reports_qwen_vl(self):
        fake_response = MagicMock()
        fake_response.json.return_value = {"message": {"content": "ภาษาไทย"}}

        with patch("document_utils.requests.post", return_value=fake_response):
            text, character_count, metadata = extract_document_text_with_metadata(
                "thai.png",
                b"image-bytes",
                {
                    "ocr_engine": "qwen_vl",
                    "vision_ocr_model": "qwen3-vl:latest",
                    "vision_ocr_timeout_seconds": 120,
                    "vision_ocr_prompt": "Extract text",
                },
                "http://ollama:11434",
            )

        self.assertEqual(text, "ภาษาไทย")
        self.assertGreater(character_count, 0)
        self.assertEqual(metadata["ocr_engine_used"], "qwen_vl")
        self.assertEqual(metadata["ocr_model"], "qwen3-vl:latest")

    def test_extract_pdf_uses_qwen_vl_for_empty_pages_when_configured(self):
        fake_reader = MagicMock()
        fake_reader.pages = [MagicMock(extract_text=MagicMock(return_value="")), MagicMock(extract_text=MagicMock(return_value="Embedded text"))]
        fake_ocr_doc = MagicMock()
        fake_ocr_doc.__enter__.return_value = fake_ocr_doc
        fake_ocr_doc.load_page.return_value = object()

        with patch("document_utils.PdfReader", return_value=fake_reader), patch("document_utils.pymupdf.open", return_value=fake_ocr_doc), patch("document_utils._render_pdf_page_to_png", return_value=b"page-image"), patch("document_utils._extract_image_text_with_vision_model", return_value="ภาษาไทย"):
            text, character_count = extract_document_text(
                "scan.pdf",
                b"%PDF-1.4",
                {
                    "ocr_engine": "qwen_vl",
                    "vision_ocr_model": "qwen3-vl:latest",
                    "vision_ocr_timeout_seconds": 120,
                    "vision_ocr_prompt": "Extract text",
                },
                "http://ollama:11434",
            )

        self.assertIn("Page 1\nภาษาไทย", text)
        self.assertIn("Page 2\nEmbedded text", text)
        self.assertGreater(character_count, 0)

    def test_extract_png_image_with_ocr(self):
        image_bytes = _build_text_image("IMAGE OCR TEST")

        text, character_count = extract_document_text("receipt.png", image_bytes)

        normalized_text = " ".join(text.upper().split())
        self.assertGreater(character_count, 0)
        self.assertRegex(normalized_text, r"(IMAGE|OCR|TEST)")


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


def _build_text_image(text: str) -> bytes:
    image = Image.new("RGB", (1800, 700), "white")
    drawer = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 120)
    drawer.text((120, 160), text, fill="black", font=font, spacing=40)
    drawer.text((120, 360), text, fill="black", font=font, spacing=40)

    buffer = io.BytesIO()
    try:
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        image.close()


if __name__ == "__main__":
    unittest.main()
