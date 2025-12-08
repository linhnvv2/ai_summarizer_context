# Roadmap: Chrome Extension Clone & Automation Agent

## Goal
Create a Chrome Extension (`chrome-ai-agent`) that replicates the functionality of the existing Windows AI Summarizer App and enables browser automation capabilities for the AI Agent.

## Architecture
- **Manifest Version**: V3
- **UI Components**:
  - **Side Panel**: For the Chat Interface (persistent, parallel to browsing).
  - **Popup**: For quick settings or quick actions.
  - **Context Menu**: Replaces system tray/global hotkeys for triggering actions on selected text.
- **Backend**:
  - Direct communication with **Ollama** / **LM Studio** via `fetch` from Background Service Worker.
  - Optional: Communication with the Python native app (via Native Messaging) if OS-level features are strictly needed (but we will aim for standalone first).

## Roadmap Phases

### Phase 1: Foundation & LLM Connection
- **Setup**: Initialize `manifest.json`, directory structure (`extension/`).
- **Connection**: Implement the logic to connect to localhost Ollama/LM Studio endpoints from the extension.
- **Config UI**: Options page to set Model, Endpoint, System Prompt (mirroring `config.json`).

### Phase 2: Feature Parity (Summarizer & Chat)
- **Context Menu Integration**:
  - Add right-click options: "Summarize", "Explain", "Translate", "Rewrite".
- **Side Panel Chat**:
  - Port `chat_window.py` logic to a clean Web UI (HTML/CSS/JS).
  - Implement streaming response handling (UI update).
- **Result Handling**: Check if we should show results in a floating overlay (Content Script) or the Side Panel. *Decision: Side Panel is cleaner for Chrome.*

### Phase 3: "Smart Copy" & Page Context
- **Smart Selection**:
  - Instead of simulating `Ctrl+C`, use `window.getSelection().toString()`.
  - "Read Page": Feature to grab the entire readable content (`document.body.innerText` or Readability.js) and feed it to the Agent context.

### Phase 4: Agent Automation (The "Control" Feature)
- **Agent Commands**: enable the Agent to output structured commands e.g., `{"action": "scroll_down"}`, `{"action": "click", "selector": "..."}`.
- **Execution**: Content script listener that executes these commands on the active tab.
- **Use Case**: User asks "Find the pricing on this page", Agent (LLM) analyzes HTML, decides to scroll or click, extension executes it.

## Proposed Directory Structure
```
extension/
├── manifest.json
├── icons/
├── _locales/ (if multi-language support is kept)
├── src/
│   ├── background.js       # API calls to Ollama, Context Menu logic
│   ├── content_script.js   # Page interaction (reading text, executing actions)
│   ├── sidepanel.html      # Main Chat UI
│   ├── sidepanel.js        # Chat logic
│   ├── options.html        # Configuration
│   ├── options.js
│   └── styles.css
└── lib/
    └── marked.js (Markdown rendering)
```

## User Review Required
- [ ] **Native vs Standalone**: The current plan assumes the extension talks directly to Ollama/LM Studio. If you need it to share history *exactly* with the Python app, we need a Local Server in the Python app to sync data, or use `Native Messaging`. **Current Plan**: Standalone (Direct to LLM).
- [ ] **Automation Scope**: "Control agent automatically" is interpreted as the LLM sending commands to the page.
