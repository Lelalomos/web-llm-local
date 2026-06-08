function parseNdjsonChunk(buffer, chunkText) {
    const combined = `${buffer || ""}${chunkText || ""}`;
    const lines = combined.split("\n");
    const nextBuffer = lines.pop() || "";
    const messages = [];

    for (const line of lines) {
        if (!line.trim()) {
            continue;
        }
        try {
            messages.push(JSON.parse(line));
        } catch (error) {
            // Keep ignoring malformed lines from the stream.
        }
    }

    return {
        buffer: nextBuffer,
        messages,
    };
}

if (typeof module !== "undefined") {
    module.exports = { parseNdjsonChunk };
}

if (typeof window !== "undefined") {
    window.parseNdjsonChunk = parseNdjsonChunk;
}
