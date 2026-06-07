const TASK_MODE_OPTIONS = [
    { value: "general", label: "General Chat" },
    { value: "code_writer", label: "Write Code" },
    { value: "code_reviewer", label: "Review Code" },
    { value: "code_editor", label: "Edit Code" },
    { value: "bug_fixer", label: "Fix Bug" },
];

function getDefaultTaskMode() {
    return "general";
}

if (typeof window !== "undefined") {
    window.TASK_MODE_OPTIONS = TASK_MODE_OPTIONS;
    window.getDefaultTaskMode = getDefaultTaskMode;
}

if (typeof module !== "undefined") {
    module.exports = { TASK_MODE_OPTIONS, getDefaultTaskMode };
}
