// src/options.js

const DEFAULT_CONFIG = {
    provider: "ollama",
    endpoint: "http://127.0.0.1:11434",
    model: "gemma3:1b",
    language: "vi",
    automation_enabled: false
};

// Restores select box and checkbox state using the preferences
// stored in chrome.storage.
const restoreOptions = () => {
    chrome.storage.local.get(DEFAULT_CONFIG, (items) => {
        document.getElementById('provider').value = items.provider;
        document.getElementById('endpoint').value = items.endpoint;
        document.getElementById('model').value = items.model;
        document.getElementById('language').value = items.language;
        document.getElementById('automation_enabled').checked = items.automation_enabled;
    });
};

// Saves options to chrome.storage
const saveOptions = () => {
    const provider = document.getElementById('provider').value;
    const endpoint = document.getElementById('endpoint').value;
    const model = document.getElementById('model').value;
    const language = document.getElementById('language').value;
    const automation_enabled = document.getElementById('automation_enabled').checked;

    chrome.storage.local.set(
        { provider, endpoint, model, language, automation_enabled },
        () => {
            // Update status to let user know options were saved.
            const status = document.getElementById('status');
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 1000);
        }
    );
};

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);

// Dynamic default endpoint switching based on provider
document.getElementById('provider').addEventListener('change', (e) => {
    const endpointInput = document.getElementById('endpoint');
    if (e.target.value === 'lmstudio') {
        endpointInput.value = 'http://127.0.0.1:1234/v1';
    } else {
        endpointInput.value = 'http://127.0.0.1:11434';
    }
});
