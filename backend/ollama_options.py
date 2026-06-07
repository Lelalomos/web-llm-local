import os
from typing import Any


def _parse_int_env(name: str) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return None

    try:
        return int(raw_value)
    except ValueError:
        return None


def _is_unload_request(payload: dict[str, Any]) -> bool:
    return payload.get("keep_alive") == 0 and not payload.get("messages")


def _set_default(options: dict[str, Any], key: str, value: int | None) -> None:
    if value is not None and key not in options:
        options[key] = value


def _apply_generic_defaults(options: dict[str, Any]) -> None:
    _set_default(options, "num_gpu", _parse_int_env("OLLAMA_FORCE_NUM_GPU") or 999)
    _set_default(options, "num_ctx", _parse_int_env("OLLAMA_DEFAULT_NUM_CTX"))
    _set_default(options, "num_batch", _parse_int_env("OLLAMA_DEFAULT_NUM_BATCH"))


def _apply_gemma_defaults(model_name: str, options: dict[str, Any]) -> None:
    if model_name == "gemma2:2b":
        _set_default(options, "num_gpu", _parse_int_env("OLLAMA_GEMMA2_2B_NUM_GPU") or 999)
        _set_default(options, "num_ctx", _parse_int_env("OLLAMA_GEMMA2_2B_NUM_CTX") or 2048)
        _set_default(options, "num_batch", _parse_int_env("OLLAMA_GEMMA2_2B_NUM_BATCH") or 256)
        return

    if model_name == "gemma4:e2b":
        _set_default(options, "num_gpu", _parse_int_env("OLLAMA_GEMMA4_E2B_NUM_GPU") or 999)
        _set_default(options, "num_ctx", _parse_int_env("OLLAMA_GEMMA4_E2B_NUM_CTX") or 2048)
        _set_default(options, "num_batch", _parse_int_env("OLLAMA_GEMMA4_E2B_NUM_BATCH") or 128)
        return

    if model_name in {"gemma4:12b", "gemma4:e4b"} or model_name.startswith("hf.co/unsloth/gemma-4-12b"):
        # Large Gemma models do not fit full GPU offload on 4 GB cards.
        _set_default(options, "num_ctx", _parse_int_env("OLLAMA_GEMMA_LARGE_NUM_CTX") or 1024)
        _set_default(options, "num_batch", _parse_int_env("OLLAMA_GEMMA_LARGE_NUM_BATCH") or 32)
        _set_default(options, "num_gpu", _parse_int_env("OLLAMA_GEMMA_LARGE_NUM_GPU"))
        return

    _apply_generic_defaults(options)


def apply_gpu_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    if _is_unload_request(payload):
        return payload

    options = payload.setdefault("options", {})
    model_name = str(payload.get("model", "")).lower()

    if model_name.startswith("gemma"):
        _apply_gemma_defaults(model_name, options)
    else:
        _apply_generic_defaults(options)

    return payload
