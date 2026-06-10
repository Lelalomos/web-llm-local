import json
import re
from pathlib import Path

from fastapi import HTTPException


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "app_config.json"
ALLOWED_WEB_SEARCH_MODES = {"auto", "on", "off"}
ALLOWED_SEARCH_PROVIDERS = {"auto", "searxng", "legacy"}
ALLOWED_OCR_ENGINES = {"auto", "tesseract", "qwen_vl", "surya_docling"}
ALLOWED_PDF_EXTRACTION_MODES = {"auto", "surya_docling", "legacy", "qwen_vl", "page_image_ocr"}
ALLOWED_TASK_MODES = {"general", "code_writer", "code_reviewer", "code_editor", "bug_fixer"}
ALLOWED_MEMORY_USED_KEYS = ALLOWED_TASK_MODES | {"upload_file"}

DEFAULT_APP_CONFIG = {
    "default_model": "gemma4:e2b",
    "default_system_prompt": "",
    "default_web_search_mode": "auto",
    "skill_markdown_enabled": True,
    "skill_prompt_max_chars": 12000,
    "web_search_context_max_chars": 2500,
    "chat_memory_prompt_max_chars": 2000,
    "search_provider": "auto",
    "searxng_enabled": True,
    "searxng_url": "http://searxng:8080",
    "searxng_timeout_seconds": 8,
    "meilisearch_enabled": True,
    "meilisearch_url": "http://meilisearch:7700",
    "meilisearch_index": "web_search_results",
    "meilisearch_timeout_seconds": 3,
    "chat_max_continuations": 4,
    "memory_used": {
        "general": True,
        "code_writer": True,
        "code_reviewer": True,
        "code_editor": False,
        "bug_fixer": False,
        "upload_file": False,
    },
    "chat_summary_prompt": (
        "You are creating persistent memory notes about the user. "
        "Write a detailed markdown summary with these sections exactly: "
        "## Session Goal, ## Important Facts, ## User Preferences, ## Personal Style, ## Open Questions, ## Useful Follow-ups. "
        "Keep it factual. Do not invent details. Include concrete details that would help future chats understand the user better. "
        "Do not include session ids, model names, task mode names, timestamps, or backend metadata."
    ),
    "task_mode_interpreter_enabled": True,
    "task_mode_interpreter_model": "gemma2:2b",
    "task_mode_interpreter_timeout_seconds": 30,
    "search_context_enhancer_enabled": True,
    "search_context_enhancer_model": "qwen2.5:0.5b",
    "search_context_enhancer_timeout_seconds": 45,
    "search_context_enhancer_max_chars": 6000,
    "ocr_engine": "auto",
    "pdf_extraction_mode": "page_image_ocr",
    "vision_ocr_model": "qwen3-vl:latest",
    "vision_ocr_timeout_seconds": 120,
    "vision_ocr_prompt": (
        "Extract all visible text from this image. Preserve line breaks and table structure. "
        "Return only the extracted text. If the text is Thai, return Thai text exactly."
    ),
    "default_options": {
        "num_predict": 1200,
    },
}
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]*$")


def _copy_default_config() -> dict:
    return json.loads(json.dumps(DEFAULT_APP_CONFIG))


def _ensure_config_file() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_APP_CONFIG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_int(config: dict, key: str, minimum: int = 0, maximum: int | None = None) -> None:
    value = config.get(key)
    if not isinstance(value, int):
        raise HTTPException(status_code=400, detail=f"{key} must be an integer")
    if value < minimum:
        raise HTTPException(status_code=400, detail=f"{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise HTTPException(status_code=400, detail=f"{key} must be <= {maximum}")


def _validate_default_options(default_options: dict) -> None:
    if not isinstance(default_options, dict):
        raise HTTPException(status_code=400, detail="default_options must be an object")

    for key, value in default_options.items():
        if not isinstance(key, str) or not key.strip():
            raise HTTPException(status_code=400, detail="default_options keys must be non-empty strings")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise HTTPException(status_code=400, detail=f"default_options.{key} has an unsupported value type")


def _validate_memory_used(memory_used: dict) -> None:
    if not isinstance(memory_used, dict):
        raise HTTPException(status_code=400, detail="memory_used must be an object")

    unknown_modes = sorted(set(memory_used.keys()) - ALLOWED_MEMORY_USED_KEYS)
    if unknown_modes:
        raise HTTPException(status_code=400, detail=f"memory_used has unknown task modes: {', '.join(unknown_modes)}")

    for task_mode, enabled in memory_used.items():
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=400, detail=f"memory_used.{task_mode} must be a boolean")


def validate_app_config(candidate: dict) -> dict:
    if not isinstance(candidate, dict):
        raise HTTPException(status_code=400, detail="config payload must be a JSON object")

    normalized = _copy_default_config()
    normalized.update(candidate)

    unknown_keys = sorted(set(normalized.keys()) - set(DEFAULT_APP_CONFIG.keys()))
    if unknown_keys:
        raise HTTPException(status_code=400, detail=f"unknown config keys: {', '.join(unknown_keys)}")

    if not isinstance(normalized.get("default_model"), str):
        raise HTTPException(status_code=400, detail="default_model must be a string")
    if not MODEL_NAME_PATTERN.fullmatch(normalized.get("default_model", "")):
        raise HTTPException(status_code=400, detail="default_model contains invalid characters")
    if not isinstance(normalized.get("default_system_prompt"), str):
        raise HTTPException(status_code=400, detail="default_system_prompt must be a string")

    default_web_search_mode = normalized.get("default_web_search_mode")
    if default_web_search_mode not in ALLOWED_WEB_SEARCH_MODES:
        raise HTTPException(status_code=400, detail="default_web_search_mode must be auto, on, or off")
    if normalized.get("search_provider") not in ALLOWED_SEARCH_PROVIDERS:
        raise HTTPException(status_code=400, detail="search_provider must be auto, searxng, or legacy")
    if not isinstance(normalized.get("searxng_enabled"), bool):
        raise HTTPException(status_code=400, detail="searxng_enabled must be a boolean")
    if not isinstance(normalized.get("searxng_url"), str):
        raise HTTPException(status_code=400, detail="searxng_url must be a string")
    _require_int(normalized, "searxng_timeout_seconds", minimum=1, maximum=60)
    if not isinstance(normalized.get("meilisearch_enabled"), bool):
        raise HTTPException(status_code=400, detail="meilisearch_enabled must be a boolean")
    if not isinstance(normalized.get("meilisearch_url"), str):
        raise HTTPException(status_code=400, detail="meilisearch_url must be a string")
    if not isinstance(normalized.get("meilisearch_index"), str) or not normalized.get("meilisearch_index").strip():
        raise HTTPException(status_code=400, detail="meilisearch_index must be a non-empty string")
    _require_int(normalized, "meilisearch_timeout_seconds", minimum=1, maximum=30)

    if not isinstance(normalized.get("skill_markdown_enabled"), bool):
        raise HTTPException(status_code=400, detail="skill_markdown_enabled must be a boolean")

    _require_int(normalized, "skill_prompt_max_chars", minimum=0, maximum=50000)
    _require_int(normalized, "web_search_context_max_chars", minimum=0, maximum=50000)
    _require_int(normalized, "chat_memory_prompt_max_chars", minimum=0, maximum=12000)
    _require_int(normalized, "chat_max_continuations", minimum=0, maximum=5)
    _validate_memory_used(normalized.get("memory_used"))
    if not isinstance(normalized.get("chat_summary_prompt"), str) or not normalized.get("chat_summary_prompt").strip():
        raise HTTPException(status_code=400, detail="chat_summary_prompt must be a non-empty string")
    if not isinstance(normalized.get("task_mode_interpreter_enabled"), bool):
        raise HTTPException(status_code=400, detail="task_mode_interpreter_enabled must be a boolean")
    if not isinstance(normalized.get("task_mode_interpreter_model"), str):
        raise HTTPException(status_code=400, detail="task_mode_interpreter_model must be a string")
    if not MODEL_NAME_PATTERN.fullmatch(normalized.get("task_mode_interpreter_model", "")):
        raise HTTPException(status_code=400, detail="task_mode_interpreter_model contains invalid characters")
    _require_int(normalized, "task_mode_interpreter_timeout_seconds", minimum=1, maximum=60)
    if not isinstance(normalized.get("search_context_enhancer_enabled"), bool):
        raise HTTPException(status_code=400, detail="search_context_enhancer_enabled must be a boolean")
    if not isinstance(normalized.get("search_context_enhancer_model"), str):
        raise HTTPException(status_code=400, detail="search_context_enhancer_model must be a string")
    if not MODEL_NAME_PATTERN.fullmatch(normalized.get("search_context_enhancer_model", "")):
        raise HTTPException(status_code=400, detail="search_context_enhancer_model contains invalid characters")
    _require_int(normalized, "search_context_enhancer_timeout_seconds", minimum=1, maximum=120)
    _require_int(normalized, "search_context_enhancer_max_chars", minimum=500, maximum=20000)
    if normalized.get("ocr_engine") not in ALLOWED_OCR_ENGINES:
        raise HTTPException(status_code=400, detail="ocr_engine must be auto, tesseract, qwen_vl, or surya_docling")
    if normalized.get("pdf_extraction_mode") not in ALLOWED_PDF_EXTRACTION_MODES:
        raise HTTPException(status_code=400, detail="pdf_extraction_mode must be auto, surya_docling, legacy, qwen_vl, or page_image_ocr")
    if not isinstance(normalized.get("vision_ocr_model"), str):
        raise HTTPException(status_code=400, detail="vision_ocr_model must be a string")
    if not MODEL_NAME_PATTERN.fullmatch(normalized.get("vision_ocr_model", "")):
        raise HTTPException(status_code=400, detail="vision_ocr_model contains invalid characters")
    _require_int(normalized, "vision_ocr_timeout_seconds", minimum=1, maximum=300)
    if not isinstance(normalized.get("vision_ocr_prompt"), str) or not normalized.get("vision_ocr_prompt").strip():
        raise HTTPException(status_code=400, detail="vision_ocr_prompt must be a non-empty string")
    _validate_default_options(normalized.get("default_options"))
    return normalized


def load_app_config() -> dict:
    _ensure_config_file()
    try:
        raw_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid config file: {exc}") from exc

    return validate_app_config(raw_config)


def save_app_config(candidate: dict) -> dict:
    _ensure_config_file()
    normalized = validate_app_config(candidate)
    CONFIG_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized
