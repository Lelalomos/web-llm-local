const TASK_MODE_OPTIONS = [
    { value: "general", label: "General Chat" },
    { value: "code_writer", label: "Write Code" },
    { value: "code_reviewer", label: "Review Code" },
    { value: "code_editor", label: "Edit Code" },
    { value: "bug_fixer", label: "Fix Bug" },
];

const CODE_WRITER_PATTERNS = [
    /\bwrite\b.*\b(code|api|endpoint|function|script|program|rust|python|javascript|typescript|go|java|c\+\+|sql)\b/i,
    /\b(create|build|implement|generate)\b.*\b(api|endpoint|function|script|program|service|server|client|code)\b/i,
    /\b(rust|python|javascript|typescript|go|java|c\+\+|sql)\b.*\b(api|endpoint|function|script|program|code)\b/i,
    /\bclass\b|\bfunction\b|\bendpoint\b|\bapi route\b|\bfastapi\b|\bexpress\b|\bactix\b|\baxum\b/i,
];

function getDefaultTaskMode() {
    return "general";
}

function inferTaskModeFromPrompt(prompt, currentTaskMode = "general") {
    const text = String(prompt || "").trim();
    if (!text) {
        return String(currentTaskMode || "general");
    }

    return CODE_WRITER_PATTERNS.some((pattern) => pattern.test(text)) ? "code_writer" : "general";
}

async function inferTaskModeForPrompt(prompt, currentTaskMode = "general", fetchApiImpl = null) {
    const fallbackTaskMode = inferTaskModeFromPrompt(prompt, currentTaskMode);
    const apiFetch = fetchApiImpl || (typeof window !== "undefined" ? window.fetchApi : null);
    if (!apiFetch) {
        return fallbackTaskMode;
    }

    try {
        const response = await apiFetch("/api/task-mode/infer", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                prompt: String(prompt || ""),
                current_task_mode: String(currentTaskMode || "general")
            })
        });
        if (!response.ok) {
            return fallbackTaskMode;
        }

        const data = await response.json();
        const taskMode = String(data.task_mode || "");
        return TASK_MODE_OPTIONS.some((option) => option.value === taskMode) ? taskMode : fallbackTaskMode;
    } catch (error) {
        return fallbackTaskMode;
    }
}

if (typeof window !== "undefined") {
    window.TASK_MODE_OPTIONS = TASK_MODE_OPTIONS;
    window.getDefaultTaskMode = getDefaultTaskMode;
    window.inferTaskModeFromPrompt = inferTaskModeFromPrompt;
    window.inferTaskModeForPrompt = inferTaskModeForPrompt;
}

if (typeof module !== "undefined") {
    module.exports = { TASK_MODE_OPTIONS, getDefaultTaskMode, inferTaskModeFromPrompt, inferTaskModeForPrompt };
}
