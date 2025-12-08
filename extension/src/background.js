// src/background.js

// Setup context menus on installation
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "ai_summarizer_root",
        title: "AI Agent",
        contexts: ["selection", "page"]
    });

    const actions = [
        { id: "summary", title: "Summarize" },
        { id: "explain", title: "Explain" },
        { id: "translate", title: "Translate to Vietnamese" },
        { id: "rewrite", title: "Rewrite" }
    ];

    actions.forEach(action => {
        chrome.contextMenus.create({
            id: action.id,
            parentId: "ai_summarizer_root",
            title: action.title,
            contexts: ["selection"]
        });
    });

    // Add "Read Entire Page" option (available on all pages, not just selection)
    chrome.contextMenus.create({
        id: "read_page",
        parentId: "ai_summarizer_root",
        title: "Read Entire Page",
        contexts: ["page"]
    });

    // Set default side panel behavior
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId === "read_page") {
        // Request page content from content script
        try {
            const response = await chrome.tabs.sendMessage(tab.id, { action: 'getPageContent' });

            chrome.storage.local.set({
                "pending_action": {
                    type: "read_page",
                    text: response.content,
                    title: response.title
                }
            });

            // Open side panel
            chrome.sidePanel.open({ windowId: tab.windowId });
        } catch (error) {
            console.error('Error getting page content:', error);
        }
    } else if (info.menuItemId && info.selectionText) {
        // Open side panel to show result
        // Note: We need to pass the data to the side panel. 
        // We can use runtime.sendMessage or storage.
        chrome.storage.local.set({
            "pending_action": {
                type: info.menuItemId,
                text: info.selectionText
            }
        });

        // Open side panel
        chrome.sidePanel.open({ windowId: tab.windowId });
    }
});
