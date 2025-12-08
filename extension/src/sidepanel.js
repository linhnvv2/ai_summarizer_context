document.addEventListener('DOMContentLoaded', async () => {
    const messagesContainer = document.getElementById('messages');
    const inputArea = document.getElementById('prompt');
    const sendBtn = document.getElementById('send-btn');

    let config = {
        provider: "ollama",
        endpoint: "http://127.0.0.1:11434",
        model: "gemma:2b",
        language: "vi"
    };

    // Load config
    const loadConfig = async () => {
        const items = await chrome.storage.local.get(config);
        config = { ...config, ...items };
    };

    await loadConfig();

    // Markdown configuration
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true, // Enable line breaks
            gfm: true     // Enable GitHub Flavored Markdown
        });
    }

    const appendMessage = (role, text) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        if (role === 'assistant' && typeof marked !== 'undefined') {
            contentDiv.innerHTML = marked.parse(text);
        } else {
            contentDiv.textContent = text;
        }

        msgDiv.appendChild(contentDiv);
        messagesContainer.appendChild(msgDiv);

        // Auto scroll
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return contentDiv; // Return content div for streaming updates
    };

    const streamResponse = async (prompt, onChunk, onComplete) => {
        try {
            const apiEndpoint = config.endpoint.replace(/\/$/, ''); // Remove trailing slash
            let url = `${apiEndpoint}/api/generate`;
            let body = {
                model: config.model,
                prompt: prompt,
                stream: true
            };

            // LM Studio compatibility check (basic)
            if (config.provider === 'lmstudio') {
                // OpenAI compatible endpoint
                url = `${apiEndpoint}/chat/completions`;

                let systemPrompt = `You are a helpful assistant. Please answer in ${config.language}.`;

                // Add automation instructions if enabled
                if (config.automation_enabled) {
                    systemPrompt += `\n\nYou can control the browser by outputting JSON commands. Available commands:
- {"action": "scroll_down"} - Scroll down the page
- {"action": "scroll_up"} - Scroll up the page
- {"action": "scroll_to_top"} - Scroll to top
- {"action": "scroll_to_bottom"} - Scroll to bottom
- {"action": "click", "selector": "CSS_SELECTOR"} - Click an element
- {"action": "type", "selector": "CSS_SELECTOR", "text": "TEXT"} - Type into an input
- {"action": "read_element", "selector": "CSS_SELECTOR"} - Read element content
- {"action": "get_page_structure"} - Get page headings, links, buttons

Output commands on a separate line. Example:
{"action": "scroll_down"}`;
                }

                body = {
                    model: config.model,
                    messages: [
                        { role: "system", content: systemPrompt },
                        { role: "user", content: prompt }
                    ],
                    stream: true
                };
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        let textChunk = "";

                        // Handle Ollama format
                        if (config.provider === 'ollama') {
                            const json = JSON.parse(line);
                            if (json.done) continue;
                            textChunk = json.response;
                        }
                        // Handle LM Studio / OpenAI format
                        else if (line.startsWith('data: ')) {
                            const dataStr = line.slice(6);
                            if (dataStr === '[DONE]') continue;
                            const json = JSON.parse(dataStr);
                            const delta = json.choices[0].delta;
                            if (delta && delta.content) {
                                textChunk = delta.content;
                            }
                        }

                        if (textChunk) {
                            fullText += textChunk;
                            onChunk(fullText);
                        }
                    } catch (e) {
                        console.warn('Error parsing chunk', e);
                    }
                }
            }

            onComplete(fullText);

        } catch (error) {
            console.error(error);
            onChunk(`Error: ${error.message}. Please check your connection to ${config.provider}.`);
            onComplete();
        }
    };

    const handleSend = async () => {
        const text = inputArea.value.trim();
        if (!text) return;

        // Clear input
        inputArea.value = '';

        // Show User Message
        appendMessage('user', text);

        // Create Assistant Placeholder
        const assistantContentDiv = appendMessage('assistant', '...');

        // Stream Response
        await streamResponse(text, async (currentText) => {
            if (typeof marked !== 'undefined') {
                assistantContentDiv.innerHTML = marked.parse(currentText);
            } else {
                assistantContentDiv.textContent = currentText;
            }
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            // Detect and execute commands if automation is enabled
            if (config.automation_enabled) {
                const commandRegex = /\{[^}]*"action"\s*:\s*"[^"]+"/g;
                const matches = currentText.match(commandRegex);

                if (matches) {
                    for (const match of matches) {
                        try {
                            // Try to parse the command
                            const commandStr = match + (match.includes('}') ? '' : '}');
                            const command = JSON.parse(commandStr);

                            // Execute command via content script
                            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                            if (tab) {
                                const result = await chrome.tabs.sendMessage(tab.id, {
                                    action: 'executeCommand',
                                    command: command
                                });

                                // Show result in chat
                                const resultIcon = result.success ? '✅' : '❌';
                                const resultMsg = `${resultIcon} ${result.message}`;
                                appendMessage('assistant', resultMsg);

                                // If command returned data, show it
                                if (result.data) {
                                    appendMessage('assistant', `Data: ${JSON.stringify(result.data, null, 2)}`);
                                }
                            }
                        } catch (e) {
                            console.warn('Command parse error:', e);
                        }
                    }
                }
            }
        }, (finalText) => {
            console.log('Stream complete');
        });
    };

    sendBtn.addEventListener('click', handleSend);
    inputArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Check for pending actions from Context Menu
    const checkPendingAction = async () => {
        const data = await chrome.storage.local.get("pending_action");
        if (data.pending_action) {
            const { type, text } = data.pending_action;

            // Clear it immediately so it doesn't run again on reload
            await chrome.storage.local.remove("pending_action");

            let prompt = "";
            switch (type) {
                case "summary":
                    prompt = `Summarize the following text:\n\n"${text}"`;
                    break;
                case "explain":
                    prompt = `Explain the following text in simple terms:\n\n"${text}"`;
                    break;
                case "translate":
                    prompt = `Translate the following text to Vietnamese:\n\n"${text}"`;
                    break;
                case "rewrite":
                    prompt = `Rewrite the following text to be more professional:\n\n"${text}"`;
                    break;
                case "read_page":
                    const pageTitle = data.pending_action.title || "this page";
                    const content = text.length > 10000 ? text.substring(0, 10000) + "\n\n[Content truncated...]" : text;
                    prompt = `Analyze and summarize the following webpage (${pageTitle}):\n\n${content}`;
                    break;
                default: // 'ai_summarizer_root' or unknown
                    prompt = text;
                    break;
            }

            // Trigger send automatically
            inputArea.value = prompt; // Optional: show what we are asking
            handleSend();
        }
    };

    checkPendingAction();

    // Listen for storage changes (when panel is already open)
    chrome.storage.onChanged.addListener((changes, areaName) => {
        if (areaName === 'local' && changes.pending_action && changes.pending_action.newValue) {
            const { type, text } = changes.pending_action.newValue;

            // Clear it immediately
            chrome.storage.local.remove("pending_action");

            let prompt = "";
            switch (type) {
                case "summary":
                    prompt = `Summarize the following text:\n\n"${text}"`;
                    break;
                case "explain":
                    prompt = `Explain the following text in simple terms:\n\n"${text}"`;
                    break;
                case "translate":
                    prompt = `Translate the following text to Vietnamese:\n\n"${text}"`;
                    break;
                case "rewrite":
                    prompt = `Rewrite the following text to be more professional:\n\n"${text}"`;
                    break;
                case "read_page":
                    const pageTitle = changes.pending_action.newValue.title || "this page";
                    const content = text.length > 10000 ? text.substring(0, 10000) + "\n\n[Content truncated...]" : text;
                    prompt = `Analyze and summarize the following webpage (${pageTitle}):\n\n${content}`;
                    break;
                default:
                    prompt = text;
                    break;
            }

            // Trigger send automatically
            inputArea.value = prompt;
            handleSend();
        }
    });
});
