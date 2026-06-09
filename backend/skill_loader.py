import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", BASE_DIR.parent))
SKILL_DIR = Path(os.getenv("SKILL_DIR", PROJECT_ROOT / "skill"))


def ensure_skill_dir() -> Path:
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    return SKILL_DIR


def load_skill_markdown(max_chars: int) -> str:
    ensure_skill_dir()
    if max_chars <= 0:
        return ""

    collected_blocks = []
    remaining_chars = max_chars

    for path in sorted(SKILL_DIR.rglob("*.md")):
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue

        if not content:
            continue

        relative_path = path.relative_to(SKILL_DIR)
        block = f"## Skill File: {relative_path}\n\n{content}"
        if len(block) > remaining_chars:
            block = block[:remaining_chars].rstrip()
        if not block:
            break

        collected_blocks.append(block)
        remaining_chars -= len(block)
        if remaining_chars <= 0:
            break

    return "\n\n".join(collected_blocks).strip()


def inject_skill_context(payload: dict, max_chars: int) -> bool:
    skill_markdown = load_skill_markdown(max_chars)
    if not skill_markdown:
        return False

    skill_prompt = (
        "Read and follow the following skill markdown before answering. "
        "Treat it as project-specific guidance.\n\n"
        f"{skill_markdown}"
    )

    for message in payload.get("messages", []):
        if message.get("role") == "system":
            message["content"] = f"{skill_prompt}\n\n{message.get('content', '')}".strip()
            return True

    payload.setdefault("messages", []).insert(0, {"role": "system", "content": skill_prompt})
    return True
