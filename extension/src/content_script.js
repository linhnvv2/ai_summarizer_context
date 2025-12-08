// content_script.js - Injected into web pages to access DOM content

// Command execution functions
const executeCommand = (command) => {
    const { action, selector, text } = command;

    try {
        switch (action) {
            case 'scroll_down':
                window.scrollBy(0, window.innerHeight * 0.8);
                return { success: true, message: 'Scrolled down' };

            case 'scroll_up':
                window.scrollBy(0, -window.innerHeight * 0.8);
                return { success: true, message: 'Scrolled up' };

            case 'scroll_to_top':
                window.scrollTo(0, 0);
                return { success: true, message: 'Scrolled to top' };

            case 'scroll_to_bottom':
                window.scrollTo(0, document.body.scrollHeight);
                return { success: true, message: 'Scrolled to bottom' };

            case 'click':
                if (!selector) {
                    return { success: false, message: 'No selector provided' };
                }
                const clickElement = document.querySelector(selector);
                if (!clickElement) {
                    return { success: false, message: `Element not found: ${selector}` };
                }
                clickElement.click();
                return { success: true, message: `Clicked element: ${selector}` };

            case 'type':
                if (!selector || !text) {
                    return { success: false, message: 'Selector and text required' };
                }
                const inputElement = document.querySelector(selector);
                if (!inputElement) {
                    return { success: false, message: `Element not found: ${selector}` };
                }
                inputElement.value = text;
                inputElement.dispatchEvent(new Event('input', { bubbles: true }));
                return { success: true, message: `Typed "${text}" into ${selector}` };

            case 'read_element':
                if (!selector) {
                    return { success: false, message: 'No selector provided' };
                }
                const readElement = document.querySelector(selector);
                if (!readElement) {
                    return { success: false, message: `Element not found: ${selector}` };
                }
                const content = readElement.innerText || readElement.textContent;
                return { success: true, message: 'Element read', data: content };

            case 'get_page_structure':
                const structure = {
                    title: document.title,
                    headings: Array.from(document.querySelectorAll('h1, h2, h3')).map(h => ({
                        tag: h.tagName.toLowerCase(),
                        text: h.innerText.trim()
                    })).slice(0, 10),
                    links: Array.from(document.querySelectorAll('a[href]')).map(a => ({
                        text: a.innerText.trim(),
                        href: a.href
                    })).slice(0, 10),
                    buttons: Array.from(document.querySelectorAll('button, input[type="submit"]')).map(b => ({
                        text: b.innerText || b.value,
                        id: b.id,
                        class: b.className
                    })).slice(0, 10)
                };
                return { success: true, message: 'Page structure retrieved', data: structure };

            default:
                return { success: false, message: `Unknown action: ${action}` };
        }
    } catch (error) {
        return { success: false, message: `Error: ${error.message}` };
    }
};

// Listen for messages from background script and sidepanel
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getSelectedText') {
        const selectedText = window.getSelection().toString();
        sendResponse({ text: selectedText });
    } else if (request.action === 'getPageContent') {
        // Get readable content from the page
        const pageContent = document.body.innerText;
        const pageTitle = document.title;
        sendResponse({
            title: pageTitle,
            content: pageContent
        });
    } else if (request.action === 'executeCommand') {
        // Execute automation command
        const result = executeCommand(request.command);
        sendResponse(result);
    }
    return true; // Keep the message channel open for async response
});
