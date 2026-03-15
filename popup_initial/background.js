// background.js
let activeTabId = null;
let timerId = null;

function resetTimer(tabId) {
  // Clear any existing timer
  if (timerId) {
    clearTimeout(timerId);
    timerId = null;
  }

  // Remember which tab is active
  activeTabId = tabId;

  // Get the tab’s URL
  chrome.tabs.get(tabId, (tab) => {
    const url = tab.url || '';
    // Only proceed if it’s a regular web page
    if (!/^https?:/.test(url)) {
      return; // skip tabs like chrome://, file://, webstore, etc.
    }

    // After 30 s, tell the content script to show the floating box
    timerId = setTimeout(() => {
      chrome.tabs.sendMessage(
        activeTabId,
        { action: "showFloatingBox" },
        (response) => {
          // If there's no listener (e.g. content script didn’t load), swallow the error
          if (chrome.runtime.lastError) {
            // console.log("No content script on this tab—skipping.");
          }
        }
      );
    }, 30000);
  });
}

// When the user switches to a different tab
chrome.tabs.onActivated.addListener(({ tabId }) => {
  resetTimer(tabId);
});

// When the active tab reloads or finishes loading
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (tab.active && changeInfo.status === "complete") {
    resetTimer(tabId);
  }
});

// When the window loses focus (e.g. user Alt‑Tabs away), clear the timer
chrome.windows.onFocusChanged.addListener((winId) => {
  if (winId === chrome.windows.WINDOW_ID_NONE && timerId) {
    clearTimeout(timerId);
    timerId = null;
  }
});

// If the active tab is closed, clear the timer
chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeTabId && timerId) {
    clearTimeout(timerId);
    timerId = null;
  }
});
