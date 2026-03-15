// Popup script to display current stats and handle export
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  
  document.getElementById('exportBtn').addEventListener('click', exportData);
  document.getElementById('clearBtn').addEventListener('click', clearData);
});

function loadStats() {
  // Check if extension context is valid
  if (!chrome || !chrome.tabs || !chrome.storage || !chrome.runtime) {
    console.error('Extension APIs not available');
    return;
  }

  // Get current tab info with error handling
  try {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        console.error('Tab query error:', chrome.runtime.lastError);
        document.getElementById('currentUrl').textContent = 'Error loading';
        return;
      }
      
      if (tabs[0] && tabs[0].url) {
        try {
          document.getElementById('currentUrl').textContent = 
            new URL(tabs[0].url).hostname;
        } catch (e) {
          document.getElementById('currentUrl').textContent = 'Invalid URL';
        }
      } else {
        document.getElementById('currentUrl').textContent = 'No active tab';
      }
    });
  } catch (error) {
    console.error('Failed to query tabs:', error);
    document.getElementById('currentUrl').textContent = 'Error';
  }
  
  // Load session data with error handling
  try {
    chrome.storage.local.get(['sessionData'], (result) => {
      if (chrome.runtime.lastError) {
        console.error('Session data error:', chrome.runtime.lastError);
        document.getElementById('sessionTime').textContent = 'Error';
        document.getElementById('tabSwitches').textContent = 'Error';
        return;
      }
      
      const sessionData = result.sessionData || {};
      document.getElementById('sessionTime').textContent = 
        formatTime(sessionData.sessionTime || 0);
      document.getElementById('tabSwitches').textContent = 
        sessionData.tabSwitchCount || 0;
    });
  } catch (error) {
    console.error('Failed to load session data:', error);
    document.getElementById('sessionTime').textContent = 'Error';
    document.getElementById('tabSwitches').textContent = 'Error';
  }
  
  // Load current page behavior data with error handling
  try {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError || !tabs[0]) {
        setDefaultBehaviorValues();
        return;
      }
      
      let hostname;
      try {
        hostname = new URL(tabs[0].url).hostname;
      } catch (e) {
        setDefaultBehaviorValues();
        return;
      }
      
      chrome.storage.local.get(['behaviorData'], (result) => {
        if (chrome.runtime.lastError) {
          console.error('Behavior data error:', chrome.runtime.lastError);
          setDefaultBehaviorValues();
          return;
        }
        
        const behaviorData = result.behaviorData || {};
        const siteData = behaviorData[hostname] || [];
        
        if (siteData.length > 0) {
          const currentSession = siteData[siteData.length - 1];
          document.getElementById('pageClicks').textContent = 
            currentSession.clicks || 0;
          document.getElementById('pageScrolls').textContent = 
            currentSession.scrolls || 0;
          document.getElementById('mouseMovements').textContent = 
            currentSession.mouseMovements || 0;
        } else {
          setDefaultBehaviorValues();
        }
      });
    });
  } catch (error) {
    console.error('Failed to load behavior data:', error);
    setDefaultBehaviorValues();
  }
}

function setDefaultBehaviorValues() {
  document.getElementById('pageClicks').textContent = '0';
  document.getElementById('pageScrolls').textContent = '0';
  document.getElementById('mouseMovements').textContent = '0';
}

function formatTime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}

function exportData() {
  if (!chrome || !chrome.runtime) {
    showError('Extension context not available');
    return;
  }

  try {
    chrome.runtime.sendMessage({ type: 'EXPORT_DATA' }, (response) => {
      if (chrome.runtime.lastError) {
        showError('Communication error: ' + chrome.runtime.lastError.message);
        return;
      }
      
      if (response && response.success) {
        showSuccess('Data Exported!');
      } else {
        showError('Export failed: ' + (response?.error || 'Unknown error'));
      }
    });
  } catch (error) {
    showError('Export failed: ' + error.message);
  }
}

function clearData() {
  if (!chrome || !chrome.storage) {
    showError('Extension context not available');
    return;
  }

  if (confirm('Are you sure you want to clear all tracked data?')) {
    try {
      chrome.storage.local.clear(() => {
        if (chrome.runtime.lastError) {
          showError('Clear failed: ' + chrome.runtime.lastError.message);
          return;
        }
        
        showSuccess('Data Cleared!', 'clearBtn');
        setTimeout(loadStats, 1000);
      });
    } catch (error) {
      showError('Clear failed: ' + error.message);
    }
  }
}

function showSuccess(message, buttonId = 'exportBtn') {
  const btn = document.getElementById(buttonId);
  const originalText = btn.textContent;
  btn.textContent = message;
  btn.style.background = '#34a853';
  
  setTimeout(() => {
    btn.textContent = originalText;
    btn.style.background = '#4285f4';
  }, 2000);
}

function showError(message) {
  const btn = document.getElementById('exportBtn');
  const originalText = btn.textContent;
  btn.textContent = 'Error!';
  btn.style.background = '#ea4335';
  console.error(message);
  
  setTimeout(() => {
    btn.textContent = originalText;
    btn.style.background = '#4285f4';
  }, 3000);
}