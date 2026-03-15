// Background script to handle tab switches and session management
let sessionData = {};
let tabSwitchCount = 0;
let sessionStartTime = Date.now();

// Initialize session data
function initializeSession() {
  sessionStartTime = Date.now();
  tabSwitchCount = 0;
  updateSessionData();
}

chrome.runtime.onStartup.addListener(initializeSession);
chrome.runtime.onInstalled.addListener(initializeSession);

// Track tab switches
chrome.tabs.onActivated.addListener((activeInfo) => {
  tabSwitchCount++;
  updateSessionData();
});

// Track tab updates (URL changes)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab && tab.url && tab.url.startsWith('http')) {
    updateVisitFrequency(tab.url);
  }
});

function updateSessionData() {
  const currentTime = Date.now();
  const sessionTime = Math.floor((currentTime - sessionStartTime) / 1000);

  sessionData = {
    sessionTime: sessionTime,
    tabSwitchCount: tabSwitchCount,
    timestamp: new Date().toISOString()
  };

  chrome.storage.local.set({ sessionData: sessionData }, () => {
    if (chrome.runtime.lastError) {
      console.error('Failed to update session data:', chrome.runtime.lastError.message);
    }
  });
}

function updateVisitFrequency(url) {
  try {
    const domain = new URL(url).hostname;
    chrome.storage.local.get(['visitFrequency'], (result) => {
      if (chrome.runtime.lastError) {
        console.error('Get visitFrequency error:', chrome.runtime.lastError.message);
        return;
      }
      const visitFrequency = result.visitFrequency || {};
      visitFrequency[domain] = (visitFrequency[domain] || 0) + 1;
      chrome.storage.local.set({ visitFrequency: visitFrequency }, () => {
        if (chrome.runtime.lastError) {
          console.error('Set visitFrequency error:', chrome.runtime.lastError.message);
        }
      });
    });
  } catch (error) {
    console.error('Error processing URL for visit frequency:', error);
  }
}

async function exportAllData() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(null, (data) => {
      if (chrome.runtime.lastError) {
        return reject(chrome.runtime.lastError);
      }

      const exportData = {
        sessionData: data.sessionData || {},
        visitFrequency: data.visitFrequency || {},
        behaviorData: data.behaviorData || {},
        exportTime: new Date().toISOString()
      };

      const jsonString = JSON.stringify(exportData, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);

      chrome.downloads.download({
        url: url,
        filename: `user_behavior_data_${Date.now()}.json`,
        saveAs: true // Prompt user to choose a save location
      }, (downloadId) => {
        URL.revokeObjectURL(url); // Clean up the blob URL
        if (chrome.runtime.lastError) {
          return reject(new Error(chrome.runtime.lastError.message));
        }
        // If downloadId is undefined, the user cancelled the download.
        if (downloadId) {
          resolve();
        } else {
          reject(new Error("Download was cancelled by the user."));
        }
      });
    });
  });
}

// Listen for messages from other scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'UPDATE_BEHAVIOR_DATA') {
    updateSessionData();
    sendResponse({ success: true });
  } else if (message.type === 'EXPORT_DATA') {
    exportAllData()
      .then(() => {
        sendResponse({ success: true });
      })
      .catch(error => {
        console.error('Export failed:', error.message);
        sendResponse({ success: false, error: error.message });
      });
    return true; // Keep message channel open for async response
  }
  return false; // No async response
});


// Update session data every minute
setInterval(updateSessionData, 60000);
