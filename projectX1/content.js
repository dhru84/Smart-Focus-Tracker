// Content script to track user interactions on web pages
(function() {
  'use strict';

  // Early exit if extension context is already invalid
  if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.id) {
    console.log('Extension context not available, skipping tracking.');
    return;
  }

  let behaviorData = {
    url: window.location.href,
    clicks: 0,
    scrolls: 0,
    keystrokes: 0,
    mouseMovements: 0,
    typingSpeed: {
      totalKeys: 0,
      totalTime: 0,
      sessions: []
    },
    timeOfDay: new Date().toISOString(),
    pageLoadTime: Date.now()
  };

  let typingSession = {
    startTime: null,
    keyCount: 0
  };

  let lastMouseMove = Date.now();
  let mouseMoveThrottle = 100;
  let isActive = true;
  let eventListeners = [];

  // Robust extension validity check
  function isExtensionValid() {
    try {
      return !!(chrome && chrome.runtime && chrome.runtime.id);
    } catch (e) {
      return false;
    }
  }

  // Safe storage operation
  function safeSave(data, callback) {
    if (!isExtensionValid() || !isActive) {
      return;
    }

    try {
      chrome.storage.local.get(['behaviorData'], function(result) {
        // Check for disconnection during async operation
        if (chrome.runtime.lastError) {
          console.warn('Storage get error (context likely invalidated):', chrome.runtime.lastError.message);
          return;
        }

        const allBehaviorData = result.behaviorData || {};
        let urlKey;
        try {
          urlKey = new URL(window.location.href).hostname;
        } catch (e) {
          urlKey = 'unknown-domain';
        }

        if (!allBehaviorData[urlKey]) {
          allBehaviorData[urlKey] = [];
        }

        const existingIndex = allBehaviorData[urlKey].findIndex(
          entry => entry.pageLoadTime === data.pageLoadTime
        );

        if (existingIndex >= 0) {
          allBehaviorData[urlKey][existingIndex] = data;
        } else {
          allBehaviorData[urlKey].push(data);
        }

        chrome.storage.local.set({ behaviorData: allBehaviorData }, function() {
          if (chrome.runtime.lastError) {
            console.warn('Storage set error (context likely invalidated):', chrome.runtime.lastError.message);
            return;
          }
          if (callback) callback();
        });
      });
    } catch (error) {
      console.warn('Synchronous storage operation failed:', error.message);
    }
  }

  // Safe message sending
  function safeMessage(message) {
    try {
      if (!isExtensionValid() || !isActive) return;

      chrome.runtime.sendMessage(message, function(response) {
        if (chrome.runtime.lastError) {
          // This is expected during page unload. Just log it.
          console.log(`Ignoring sendMessage error: ${chrome.runtime.lastError.message}`);
        }
      });
    } catch (e) {
      // This catches errors if chrome.runtime is gone.
      console.log(`Ignoring synchronous sendMessage error: ${e.message}`);
    }
  }

  function saveBehaviorData() {
    if (!isActive) return;

    const dataToSave = {
      ...behaviorData,
      sessionDuration: Date.now() - behaviorData.pageLoadTime,
      lastUpdated: new Date().toISOString()
    };

    safeSave(dataToSave, function() {
      safeMessage({ type: 'UPDATE_BEHAVIOR_DATA' });
    });
  }

  // Enhanced event listener wrapper
  function addSafeEventListener(element, event, handler, options) {
    const safeHandler = (...args) => {
      if (!isActive || !isExtensionValid()) return;
      try {
        handler.apply(this, args);
      } catch (error) {
        console.warn('Event handler error:', error);
      }
    };
    element.addEventListener(event, safeHandler, options);
    eventListeners.push({ element, event, handler: safeHandler, options });
  }

  // Cleanup function
  function cleanup() {
    if (!isActive) return;
    console.log('Cleaning up extension tracking on this page.');
    isActive = false;

    eventListeners.forEach(({ element, event, handler, options }) => {
      try {
        element.removeEventListener(event, handler, options);
      } catch (e) {}
    });
    eventListeners = [];

    if (window.trackingInterval) clearInterval(window.trackingInterval);
    if (window.validityInterval) clearInterval(window.validityInterval);
    window.trackingInterval = null;
    window.validityInterval = null;
  }

  // Connection check
  function checkConnection() {
    if (!isExtensionValid()) {
      cleanup();
      return false;
    }
    return true;
  }

  if (!checkConnection()) {
    return;
  }

  // Track clicks
  addSafeEventListener(document, 'click', () => {
    behaviorData.clicks++;
    saveBehaviorData();
  });

  // Track scrolls
  let scrollThrottle = false;
  addSafeEventListener(document, 'scroll', () => {
    if (!scrollThrottle) {
      behaviorData.scrolls++;
      saveBehaviorData();
      scrollThrottle = true;
      setTimeout(() => { scrollThrottle = false; }, 100);
    }
  });

  // Track mouse movements
  addSafeEventListener(document, 'mousemove', () => {
    const now = Date.now();
    if (now - lastMouseMove > mouseMoveThrottle) {
      behaviorData.mouseMovements++;
      lastMouseMove = now;
      saveBehaviorData();
    }
  });

  // Track keystrokes and typing speed
  addSafeEventListener(document, 'keydown', (event) => {
    if (event.key.length === 1 || event.key === 'Backspace' || event.key === 'Delete') {
      behaviorData.keystrokes++;
      const now = Date.now();
      if (!typingSession.startTime) {
        typingSession.startTime = now;
        typingSession.keyCount = 1;
      } else {
        typingSession.keyCount++;
        clearTimeout(typingSession.timeout);
        typingSession.timeout = setTimeout(() => {
          if (typingSession.keyCount > 5) {
            const sessionDuration = (now - typingSession.startTime) / 1000;
            const wpm = (typingSession.keyCount / 5) / (sessionDuration / 60);
            behaviorData.typingSpeed.sessions.push({
              wpm: Math.round(wpm),
              duration: sessionDuration,
              keyCount: typingSession.keyCount,
              timestamp: new Date().toISOString()
            });
            behaviorData.typingSpeed.totalKeys += typingSession.keyCount;
            behaviorData.typingSpeed.totalTime += sessionDuration;
          }
          typingSession = { startTime: null, keyCount: 0 };
          saveBehaviorData();
        }, 2000);
      }
      saveBehaviorData();
    }
  });

  // Track page visibility changes
  addSafeEventListener(document, 'visibilitychange', () => {
    if (document.hidden) {
      saveBehaviorData();
    } else {
      behaviorData.timeOfDay = new Date().toISOString();
    }
  });

  // Track page unload
  addSafeEventListener(window, 'beforeunload', saveBehaviorData);

  // Initial save
  saveBehaviorData();

  // Periodic save
  window.trackingInterval = setInterval(saveBehaviorData, 30000);

  // Regular validity check
  window.validityInterval = setInterval(checkConnection, 5000);

  console.log('User behavior tracking initialized');
})();