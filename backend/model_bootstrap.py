import os
import threading
from typing import Any

import requests


DEFAULT_OLLAMA_MODEL = os.getenv("DEFAULT_OLLAMA_MODEL", "gemma2:2b")
BOOTSTRAP_PULL_TIMEOUT_SECONDS = int(os.getenv("BOOTSTRAP_PULL_TIMEOUT_SECONDS", "1800"))

_bootstrap_lock = threading.Lock()


def extract_model_names(tags_payload: dict[str, Any]) -> list[str]:
    models = tags_payload.get("models", [])
    if not isinstance(models, list):
        return []
    return [str(model.get("name", "")).strip() for model in models if model.get("name")]


def should_pull_default_model(tags_payload: dict[str, Any]) -> bool:
    return len(extract_model_names(tags_payload)) == 0


def ensure_default_model_available(ollama_url: str, default_model: str = DEFAULT_OLLAMA_MODEL) -> dict[str, Any]:
    with _bootstrap_lock:
        tags_response = requests.get(f"{ollama_url}/api/tags", timeout=30)
        tags_response.raise_for_status()
        tags_payload = tags_response.json()

        if not should_pull_default_model(tags_payload):
            return {"status": "skipped", "model": default_model}

        pull_response = requests.post(
            f"{ollama_url}/api/pull",
            json={"model": default_model, "stream": False},
            timeout=BOOTSTRAP_PULL_TIMEOUT_SECONDS,
        )
        pull_response.raise_for_status()
        response_text = pull_response.text.strip()
        if not response_text:
            return {"status": "success", "model": default_model}

        try:
            payload = pull_response.json()
        except requests.exceptions.JSONDecodeError:
            payload = {"status": response_text}

        payload["model"] = default_model
        return payload
