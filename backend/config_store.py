import json
import re
from pathlib import Path

from fastapi import HTTPException


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "app_config.json"
ALLOWED_WEB_SEARCH_MODES = {"auto", "on", "off"}

DEFAULT_APP_CONFIG = {
    "default_model": "gemma4:e2b",
    "default_system_prompt": "",
    "default_web_search_mode": "auto",
    "skill_markdown_enabled": True,
    "skill_prompt_max_chars": 12000,
    "web_search_context_max_chars": 6000,
    "chat_max_continuations": 2,
    "default_options": {
        "num_predict": 900,
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

    if not isinstance(normalized.get("skill_markdown_enabled"), bool):
        raise HTTPException(status_code=400, detail="skill_markdown_enabled must be a boolean")

    _require_int(normalized, "skill_prompt_max_chars", minimum=0, maximum=50000)
    _require_int(normalized, "web_search_context_max_chars", minimum=0, maximum=50000)
    _require_int(normalized, "chat_max_continuations", minimum=0, maximum=5)
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
