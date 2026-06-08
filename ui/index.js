// DOM Elements
const modelSelect = document.getElementById("model-select");
const systemPrompt = document.getElementById("system-prompt");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const refreshStatusBtn = document.getElementById("refresh-status");
const clearChatBtn = document.getElementById("clear-chat");
const messagesContainer = document.getElementById("messages-container");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");
const currentModelDisplay = document.getElementById("current-model-display");
const taskModeSelect = document.getElementById("task-mode-select");
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const sidebarToggleButton = document.getElementById("sidebar-toggle-button");
const sidebarCloseButton = document.getElementById("sidebar-close-button");
const modelPullInput = document.getElementById("model-pull-input");
const pullModelButton = document.getElementById("pull-model-button");
const modelDeleteSelect = document.getElementById("model-delete-select");
const deleteModelButton = document.getElementById("delete-model-button");
const modelManagementStatus = document.getElementById("model-management-status");
const configEditor = document.getElementById("config-editor");
const saveConfigButton = document.getElementById("save-config-button");
const configStatus = document.getElementById("config-status");

// New DOM Elements for Document Chat and Search
const attachButton = document.getElementById("attach-button");
const fileInput = document.getElementById("file-input");
const attachmentContainer = document.getElementById("attachment-container");
const webSearchToggle = document.getElementById("web-search-toggle");

let chatHistory = [];
let isGenerating = false;
let attachedFile = null; // Store { name: string, text: string, charCount: number }
let isWebSearchActive = true;
let currentModel = "";
let onlineModelCount = 0;
let currentSessionId = window.createChatSessionId();
let isManagingModels = false;
let statusRefreshTimer = null;
let appConfig = null;

// Auto-resize textarea
chatInput.addEventListener("input", function() {
    resizeChatInput(this);
});

// Init
window.addEventListener("DOMContentLoaded", async () => {
    setupEventListeners();
    taskModeSelect.value = window.getDefaultTaskMode();
    await loadConfigFromServer();
    await checkOllamaStatus();
    handleViewportChange();
});

async function readErrorMessage(response, fallbackMessage) {
    const fallback = fallbackMessage || `Request failed with status ${response?.status || "unknown"}`;
    if (!response) {
        return fallback;
    }

    const contentType = response.headers?.get?.("content-type") || "";
    if (contentType.includes("application/json")) {
        const payload = await response.json().catch(() => null);
        if (payload && typeof payload.detail === "string" && payload.detail.trim()) {
            return payload.detail.trim();
        }
    }

    const bodyText = await response.text().catch(() => "");
    const trimmed = String(bodyText || "").trim();
    return trimmed || fallback;
}

function setupEventListeners() {
    // Send button
    sendButton.addEventListener("click", handleSend);

    // Keyboard Enter to send
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Refresh status
    refreshStatusBtn.addEventListener("click", checkOllamaStatus);

    // Clear chat
    clearChatBtn.addEventListener("click", resetChatView);

    // Model selection changes UI display header and unloads the previous model from VRAM
    modelSelect.addEventListener("change", async (e) => {
        const newModel = e.target.value;
        updateHeaderDisplay(newModel);
        if (currentModel && currentModel !== newModel) {
            await unloadModel(currentModel);
        }
        currentModel = newModel;
        if (window.shouldCloseSidebarAfterAction(window.innerWidth)) {
            closeSidebar();
        }
    });

    // Handle suggestion chips
    document.querySelectorAll(".suggestion-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            chatInput.value = chip.textContent;
            chatInput.focus();
            chatInput.dispatchEvent(new Event('input'));
        });
    });

    // File upload trigger
    attachButton.addEventListener("click", () => {
        fileInput.click();
    });

    // File selection handler
    fileInput.addEventListener("change", handleFileUpload);

    // Web Search Toggle handler
    webSearchToggle.addEventListener("click", () => {
        isWebSearchActive = !isWebSearchActive;
        syncWebSearchToggle();
    });

    pullModelButton.addEventListener("click", handlePullModel);
    deleteModelButton.addEventListener("click", handleDeleteSelectedModel);
    modelDeleteSelect.addEventListener("change", syncDeleteButtonState);
    saveConfigButton.addEventListener("click", saveConfigToServer);
    modelPullInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handlePullModel();
        }
    });

    sidebarToggleButton.addEventListener("click", openSidebar);
    sidebarCloseButton.addEventListener("click", closeSidebar);
    sidebarBackdrop.addEventListener("click", closeSidebar);
    window.addEventListener("resize", handleViewportChange);
}

function syncWebSearchToggle() {
    if (isWebSearchActive) {
        webSearchToggle.classList.add("active");
        webSearchToggle.title = "Auto Web Search On";
    } else {
        webSearchToggle.classList.remove("active");
        webSearchToggle.title = "Auto Web Search Off";
    }
}

function renderOnlineStatus() {
    if (onlineModelCount > 0) {
        statusDot.className = "status-dot online";
        statusText.textContent = `Ollama: Online (${onlineModelCount} models)`;
        return;
    }

    statusDot.className = "status-dot loading";
    statusText.textContent = "Ollama: Bootstrapping default model...";
}

function setModelManagementStatus(message) {
    modelManagementStatus.textContent = message;
}

function setConfigStatus(message) {
    configStatus.textContent = message;
}

function applyConfigToUi(config) {
    appConfig = config;
    configEditor.value = window.formatConfigForEditor(config);
    systemPrompt.value = String(config.default_system_prompt || "");

    isWebSearchActive = config.default_web_search_mode !== "off";
    syncWebSearchToggle();
}

async function loadConfigFromServer() {
    setConfigStatus("Loading config...");
    saveConfigButton.disabled = true;

    try {
        const response = await window.fetchApi("/api/config");
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.detail || "Config load failed");
        }

        applyConfigToUi(payload);
        setConfigStatus("Config loaded.");
    } catch (error) {
        console.error(error);
        setConfigStatus(`Config load failed: ${error.message}`);
    } finally {
        saveConfigButton.disabled = false;
    }
}

async function saveConfigToServer() {
    let nextConfig;
    try {
        nextConfig = window.parseConfigEditorValue(configEditor.value);
    } catch (error) {
        setConfigStatus(error.message);
        alert(error.message);
        return;
    }

    setConfigStatus("Saving config...");
    saveConfigButton.disabled = true;

    try {
        const response = await window.fetchApi("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(nextConfig)
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.detail || "Config save failed");
        }

        applyConfigToUi(payload);
        setConfigStatus("Config saved.");
        await checkOllamaStatus();
    } catch (error) {
        console.error(error);
        setConfigStatus(`Config save failed: ${error.message}`);
        alert(`Error saving config: ${error.message}`);
    } finally {
        saveConfigButton.disabled = false;
    }
}

function renderInstalledModels(models) {
    modelDeleteSelect.innerHTML = "";

    const optionDefs = window.buildDeleteModelOptions(models);
    optionDefs.forEach((optionDef) => {
        const option = document.createElement("option");
        option.value = optionDef.value;
        option.textContent = optionDef.label;
        modelDeleteSelect.appendChild(option);
    });

    if (!models.length) {
        deleteModelButton.disabled = true;
        return;
    }

    syncDeleteButtonState();
}

function setModelManagementBusy(isBusy) {
    isManagingModels = isBusy;
    pullModelButton.disabled = isBusy;
    modelPullInput.disabled = isBusy;
    modelDeleteSelect.disabled = isBusy;
    deleteModelButton.disabled = isBusy || !modelDeleteSelect.value;
}

function syncDeleteButtonState() {
    deleteModelButton.disabled = isManagingModels || !modelDeleteSelect.value;
}

function isCompactViewport() {
    return window.isCompactLayout(window.innerWidth);
}

function openSidebar() {
    if (!isCompactViewport()) {
        return;
    }

    document.body.classList.add("sidebar-open");
    sidebarBackdrop.hidden = false;
}

function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    sidebarBackdrop.hidden = true;
}

function handleViewportChange() {
    if (!isCompactViewport()) {
        closeSidebar();
    }
}

function setSearchInProgressStatus(isSearching) {
    if (isSearching) {
        statusDot.className = "status-dot searching";
        statusText.textContent = "Web Search: Searching...";
        return;
    }

    renderOnlineStatus();
}

function setGeneratingStatus() {
    statusDot.className = "status-dot loading";
    statusText.textContent = "Ollama: Preparing...";
}

function resizeChatInput(element) {
    element.style.height = "auto";
    element.style.height = `${window.getTextareaHeight(element.scrollHeight)}px`;
    element.style.overflowY = element.scrollHeight > window.CHAT_INPUT_MAX_HEIGHT ? "auto" : "hidden";
}

// File Upload Handler
async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    // Check file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
        alert("File size exceeds 10MB limit.");
        fileInput.value = "";
        return;
    }
    
    // Visual upload state
    attachButton.disabled = true;
    attachButton.innerHTML = "⏳";
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await window.fetchApi("/api/upload", {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(await readErrorMessage(response, "Upload and parsing failed"));
        }
        
        const data = await response.json();
        
        attachedFile = {
            name: data.filename,
            text: data.text,
            charCount: data.character_count
        };
        
        renderAttachmentChip(file.name);
        if (window.shouldCloseSidebarAfterAction(window.innerWidth)) {
            closeSidebar();
        }
        
    } catch (err) {
        console.error(err);
        alert(`Error reading file: ${err.message}`);
    } finally {
        attachButton.disabled = false;
        attachButton.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        fileInput.value = "";
    }
}

function renderAttachmentChip(name) {
    attachmentContainer.innerHTML = `
        <div class="attachment-chip">
            <span class="attachment-icon">📄</span>
            <span class="attachment-name">${escapeHtml(name)}</span>
            <button class="remove-btn" onclick="removeAttachment()">&times;</button>
        </div>
    `;
    attachmentContainer.style.display = "flex";
}

window.removeAttachment = function() {
    attachedFile = null;
    attachmentContainer.innerHTML = "";
    attachmentContainer.style.display = "none";
};

function updateHeaderDisplay(modelName) {
    if (!modelName || modelName === "Connection error") {
        currentModelDisplay.textContent = "Offline";
        return;
    }
    if (modelName.startsWith("gemma4")) {
        currentModelDisplay.textContent = "Gemma 4";
    } else {
        currentModelDisplay.textContent = modelName;
    }
}

// Check Ollama server connectivity and fetch installed models
async function checkOllamaStatus() {
    if (statusRefreshTimer) {
        clearTimeout(statusRefreshTimer);
        statusRefreshTimer = null;
    }

    statusDot.className = "status-dot loading";
    statusText.textContent = "Ollama: Connecting...";
    syncWebSearchToggle();
    
    try {
        const response = await window.fetchApi("/api/tags");
        if (response.ok) {
            const data = await response.json();
            const models = data.models || [];
            
            // Populate select dropdown with available models
            modelSelect.innerHTML = "";
            if (models.length === 0) {
                onlineModelCount = 0;
                modelSelect.innerHTML = `<option value="">No models found</option>`;
                renderInstalledModels([]);
                renderOnlineStatus();
                sendButton.disabled = true;
                statusRefreshTimer = setTimeout(checkOllamaStatus, 5000);
            } else {
                onlineModelCount = models.length;
                models.forEach(model => {
                    const opt = document.createElement("option");
                    opt.value = model.name;
                    opt.textContent = `${model.name} (${(model.size / 1e9).toFixed(1)} GB)`;
                    modelSelect.appendChild(opt);
                });
                
                const configModel = String(appConfig?.default_model || "").trim();
                const preferredModel = (
                    models.some((model) => model.name === currentModel) ? currentModel :
                    models.some((model) => model.name === configModel) ? configModel :
                    window.pickPreferredModel(models)
                );
                modelSelect.value = preferredModel;
                updateHeaderDisplay(preferredModel);
                currentModel = modelSelect.value;
                renderInstalledModels(models);

                renderOnlineStatus();
                sendButton.disabled = false;
            }
            setModelManagementStatus("Ready.");
        } else {
            throw new Error(await readErrorMessage(response, "Unable to connect to Ollama."));
        }
    } catch (e) {
        onlineModelCount = 0;
        currentModel = "";
        statusDot.className = "status-dot";
        statusText.textContent = "Ollama: Offline";
        modelSelect.innerHTML = `<option value="">Connection error</option>`;
        renderInstalledModels([]);
        updateHeaderDisplay("Connection error");
        setModelManagementStatus("Unable to connect to Ollama.");
        sendButton.disabled = true;
        statusRefreshTimer = setTimeout(checkOllamaStatus, 5000);
    }
}

async function handlePullModel() {
    const modelName = window.normalizeModelName(modelPullInput.value);
    if (!window.isValidModelName(modelName)) {
        alert("Enter a valid model name.");
        return;
    }

    setModelManagementBusy(true);
    setModelManagementStatus(`Pulling ${modelName}...`);

    try {
        const response = await window.fetchApi("/api/models/pull", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model: modelName })
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.detail || "Model pull failed");
        }

        modelPullInput.value = "";
        setModelManagementStatus(`Pulled ${modelName}.`);
        await checkOllamaStatus();
    } catch (error) {
        console.error(error);
        setModelManagementStatus(`Pull failed: ${error.message}`);
        alert(`Error pulling model: ${error.message}`);
    } finally {
        setModelManagementBusy(false);
    }
}

async function handleDeleteModel(modelName) {
    if (!confirm(`Delete model "${modelName}" from Ollama?`)) {
        return;
    }

    setModelManagementBusy(true);
    setModelManagementStatus(`Deleting ${modelName}...`);

    try {
        const response = await window.fetchApi("/api/models/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model: modelName })
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.detail || "Model delete failed");
        }

        if (currentModel === modelName) {
            currentModel = "";
        }
        modelDeleteSelect.value = "";
        setModelManagementStatus(`Deleted ${modelName}.`);
        await checkOllamaStatus();
    } catch (error) {
        console.error(error);
        setModelManagementStatus(`Delete failed: ${error.message}`);
        alert(`Error deleting model: ${error.message}`);
    } finally {
        setModelManagementBusy(false);
    }
}

async function handleDeleteSelectedModel() {
    const modelName = modelDeleteSelect.value;
    if (!modelName) {
        alert("Select a model to delete.");
        return;
    }

    await handleDeleteModel(modelName);
}
// Append welcome card back if empty
function resetChatView() {
    chatHistory = [];
    currentSessionId = window.createChatSessionId();
    messagesContainer.innerHTML = `
        <div class="welcome-card">
            <div class="welcome-icon">✨</div>
            <h2>Welcome to Antigravity Studio</h2>
            <p>Chat with Gemma 4 or Qwen locally, directly on your machine. Your prompts never leave this computer.</p>
            <div class="suggestions">
                <div class="suggestion-chip">Explain quantum physics to a 10 year old</div>
                <div class="suggestion-chip">Write a quick python script for data sorting</div>
                <div class="suggestion-chip">Write a haiku about local artificial intelligence</div>
            </div>
        </div>
    `;
    
    // Re-attach listeners to new chips
    document.querySelectorAll(".suggestion-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            chatInput.value = chip.textContent;
            chatInput.focus();
            chatInput.dispatchEvent(new Event('input'));
        });
    });
}

// Copy to clipboard helper
function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.textContent;
        btn.textContent = "Copied!";
        btn.classList.add("copied");
        setTimeout(() => {
            btn.textContent = originalText;
            btn.classList.remove("copied");
        }, 2000);
    }).catch(err => {
        console.error("Failed to copy text: ", err);
    });
}

// Make copy code functions globally accessible
window.copyCodeBlock = function(btnId, base64Text) {
    const text = atob(base64Text);
    const btn = document.getElementById(btnId);
    copyToClipboard(text, btn);
};

// Dynamic syntax highlighting applying to new blocks
function highlightCodeBlocks(container) {
    if (typeof hljs === 'undefined') return;
    container.querySelectorAll('pre code').forEach((block) => {
        if (!block.dataset.highlighted) {
            hljs.highlightElement(block);
            block.dataset.highlighted = "true";
        }
    });
}

// Append message block to container with optional file name indicator
function appendMessage(role, content, attachedFileName = null) {
    // Remove welcome card if it's the first message
    const welcome = messagesContainer.querySelector(".welcome-card");
    if (welcome) {
        welcome.remove();
    }
    
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;
    
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = role === "user" ? "You" : modelSelect.value || "AI";
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    
    if (role === "user") {
        let innerHTML = "";
        if (attachedFileName) {
            innerHTML += `<div style="font-weight: 500; font-size: 0.8rem; padding: 6px 10px; background: rgba(255,255,255,0.15); border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; margin-bottom: 8px;">📄 ${escapeHtml(attachedFileName)}</div><br>`;
        }
        innerHTML += `<p>${escapeHtml(content).replace(/\n/g, "<br>")}</p>`;
        bubble.innerHTML = innerHTML;
    } else {
        bubble.innerHTML = renderMarkdown(content);
    }
    
    messageDiv.appendChild(label);
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    
    highlightCodeBlocks(bubble);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return bubble;
}

// Main sender handler
async function handleSend() {
    const text = chatInput.value.trim();
    if ((!text && !attachedFile) || isGenerating) return;

    // Reset input textarea
    chatInput.value = "";
    resizeChatInput(chatInput);
    
    // Block user input during generation
    isGenerating = true;
    sendButton.disabled = true;
    
    const activeFileName = attachedFile ? attachedFile.name : null;
    const activeFileText = attachedFile ? attachedFile.text : null;
    
    // Add user message to UI (with document badge if applicable)
    const userVisiblePrompt = text || window.DEFAULT_DOCUMENT_PROMPT;
    appendMessage("user", userVisiblePrompt, activeFileName);
    closeSidebar();
    
    // Prepare conversation messages payload
    const systemInstruction = systemPrompt.value.trim();
    const activeModel = modelSelect.value;
    
    const apiMessages = [];
    if (systemInstruction) {
        apiMessages.push({ role: "system", content: systemInstruction });
    }
    
    // Build from chat history
    chatHistory.forEach(msg => apiMessages.push(msg));
    
    // Construct final user prompt with file text if attached
    const finalPromptContent = window.buildFinalPrompt(text, activeFileName, activeFileText);
    
    // Add current user prompt to history payload
    apiMessages.push({ role: "user", content: finalPromptContent });
    
    // Add assistant bubble for streaming response
    const assistantBubble = appendMessage("assistant", "Preparing...");
    setGeneratingStatus();
    
    // Clear attachment chip immediately on send
    if (attachedFile) {
        removeAttachment();
    }
    
    try {
        const response = await window.fetchApi("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: activeModel,
                messages: apiMessages,
                stream: true,
                web_search_mode: isWebSearchActive ? "auto" : "off",
                task_mode: taskModeSelect.value,
                session_id: currentSessionId
            })
        });

        if (!response.ok) {
            throw new Error(await readErrorMessage(response, "Chat request failed"));
        }

        // Initialize streaming reader
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponseContent = "";
        let hasReceivedMetadata = false;
        let hasStartedAnswer = false;
        let streamBuffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunkText = decoder.decode(value, { stream: true });

            const parsedChunk = window.parseNdjsonChunk(streamBuffer, chunkText);
            streamBuffer = parsedChunk.buffer;

            for (const parsed of parsedChunk.messages) {
                if (parsed.type === "search_status") {
                    hasReceivedMetadata = true;
                    if (parsed.search_used) {
                        assistantBubble.innerHTML = renderMarkdown("Searching web...");
                        setSearchInProgressStatus(true);
                    } else {
                        assistantBubble.innerHTML = renderMarkdown("Thinking...");
                        setGeneratingStatus();
                    }
                    continue;
                }

                const word = parsed.message?.content || "";
                if (!hasStartedAnswer && word) {
                    hasStartedAnswer = true;
                    assistantBubble.innerHTML = "";
                    if (hasReceivedMetadata) {
                        statusText.textContent = "Ollama: Building answer...";
                    }
                }
                fullResponseContent += word;
                assistantBubble.innerHTML = renderMarkdown(fullResponseContent);
                highlightCodeBlocks(assistantBubble);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }

        if (streamBuffer.trim()) {
            try {
                const parsed = JSON.parse(streamBuffer);
                const word = parsed.message?.content || "";
                if (word) {
                    fullResponseContent += word;
                    assistantBubble.innerHTML = renderMarkdown(fullResponseContent);
                    highlightCodeBlocks(assistantBubble);
                }
            } catch (error) {
                // Ignore any trailing incomplete chunk.
            }
        }
        
        // Save to chat history
        chatHistory.push({ role: "user", content: finalPromptContent });
        chatHistory.push({ role: "assistant", content: fullResponseContent });

    } catch (e) {
        const errorMessage = e instanceof Error && e.message
            ? e.message
            : "Unable to receive response from local Ollama service.";
        assistantBubble.innerHTML = `<p style="color: #ff7675;">[Connection Error] ${escapeHtml(errorMessage)}</p>`;
        checkOllamaStatus().catch(() => {});
    } finally {
        isGenerating = false;
        sendButton.disabled = false;
        chatInput.focus();
        resizeChatInput(chatInput);
        setSearchInProgressStatus(false);
    }
}

async function unloadModel(modelName) {
    if (!modelName) return;
    try {
        console.log(`[UI] Unloading model from VRAM: ${modelName}`);
        await window.fetchApi("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: modelName,
                messages: [],
                keep_alive: 0
            })
        });
    } catch (e) {
        console.error(`[UI] Failed to unload model: ${modelName}`, e);
    }
}
