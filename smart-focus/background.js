// Background service worker for Productivity Guard
const API_BASE = 'http://127.0.0.1:5000/api';
const USER_ID  = 'default_user';

let activeTabId            = null;
let sessionStartTime       = null;
let currentUrl             = '';
let userInteractionData    = { clicks: 0, keystrokes: 0, mouseMovements: 0, scrolls: 0 };
let sessionGlobalStartTime = Date.now();
let tabSwitchCount         = 0;
let trackingInterval       = null;
let autoUploadInterval     = null;  // BUG FIX: was anonymous setInterval, now tracked

// ─── Init ─────────────────────────────────────────────────────────────────────
chrome.runtime.onStartup.addListener(initializeExtension);
chrome.runtime.onInstalled.addListener(initializeExtension);

async function initializeExtension() {
    console.log('Productivity Guard initialized');
    await resetDailyStatsIfNeeded();
    sessionGlobalStartTime = Date.now();
    tabSwitchCount = 0;
    startTracking();
    startAutoUpload();

    chrome.alarms.create('dailyReset', {
        when: getNextMidnight(),
        periodInMinutes: 24 * 60
    });
}

// ─── Tab listeners ────────────────────────────────────────────────────────────
chrome.tabs.onActivated.addListener(async (activeInfo) => {
    tabSwitchCount++;
    updateSessionData();
    await handleTabChange(activeInfo.tabId);
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.active) {
        await handleTabChange(tabId);
        if (tab.url) updateVisitFrequency(tab.url);
    }
});

// ─── Tab change handler ───────────────────────────────────────────────────────
async function handleTabChange(tabId) {
    if (activeTabId && sessionStartTime) await saveSessionData();

    const tab = await chrome.tabs.get(tabId).catch(() => null);
    if (tab && tab.url) {
        activeTabId      = tabId;
        currentUrl       = tab.url;
        sessionStartTime = Date.now();
        userInteractionData = { clicks: 0, keystrokes: 0, mouseMovements: 0, scrolls: 0 };

        await sendTabInfoToBackend(tab);
        await checkUrlLimits(tab.url);
    }
}

// ─── Session data ─────────────────────────────────────────────────────────────
function updateSessionData() {
    const sessionTime = Math.floor((Date.now() - sessionGlobalStartTime) / 1000);
    const data = { sessionTime, tabSwitchCount, timestamp: new Date().toISOString() };
    chrome.storage.local.set({ sessionData: data });
}

function updateVisitFrequency(url) {
    try {
        const domain = new URL(url).hostname;
        chrome.storage.local.get(['visitFrequency'], (result) => {
            const vf = result.visitFrequency || {};
            vf[domain] = (vf[domain] || 0) + 1;
            chrome.storage.local.set({ visitFrequency: vf });
        });
    } catch (e) { console.error('updateVisitFrequency error:', e); }
}

async function saveSessionData() {
    if (!sessionStartTime || !currentUrl) return;
    const sessionDuration = Math.floor((Date.now() - sessionStartTime) / 1000);
    if (sessionDuration < 5) return;

    const result = await chrome.storage.local.get([
        'todayStats', 'distractionUrls', 'productiveUrls', 'urlTimeSpent'
    ]);

    const todayStats      = result.todayStats    || { activeTime: 0, distractionTime: 0, productiveTime: 0 };
    const distractionUrls = result.distractionUrls || [];
    const productiveUrls  = result.productiveUrls  || [];
    const urlTimeSpent    = result.urlTimeSpent    || {};
    const domain          = extractDomain(currentUrl);

    todayStats.activeTime += sessionDuration;

    // BUG FIX: support both string and object URL formats in the arrays
    const isDistraction = distractionUrls.some(d =>
        extractDomain(typeof d === 'string' ? d : d.url) === domain);
    const isProductive = productiveUrls.some(p =>
        extractDomain(typeof p === 'string' ? p : p.url) === domain);

    if (isDistraction)     todayStats.distractionTime += sessionDuration;
    else if (isProductive) todayStats.productiveTime  += sessionDuration;

    urlTimeSpent[domain] = (urlTimeSpent[domain] || 0) + sessionDuration;
    await chrome.storage.local.set({ todayStats, urlTimeSpent });

    await sendUsageDataToBackend({
        user_id:      USER_ID,   // BUG FIX: was missing user_id
        url:          currentUrl,
        domain:       domain,
        duration:     sessionDuration,
        interactions: userInteractionData,
        timestamp:    new Date().toISOString(),  // BUG FIX: backend expects ISO string not unix ms
        is_distraction: isDistraction,           // BUG FIX: backend expects snake_case
        is_productive:  isProductive
    });

    chrome.runtime.sendMessage({ action: 'updateStats' }).catch(() => {});
}

// ─── URL limit checking ───────────────────────────────────────────────────────
async function checkUrlLimits(url) {
    const result = await chrome.storage.local.get([
        'distractionUrls', 'urlTimeSpent', 'strictMode', 'notificationsEnabled'
    ]);

    const distractionUrls    = result.distractionUrls    || [];
    const urlTimeSpent       = result.urlTimeSpent       || {};
    const strictMode         = result.strictMode         || false;
    const notificationsEnabled = result.notificationsEnabled !== false;

    const domain    = extractDomain(url);
    const timeSpent = urlTimeSpent[domain] || 0;

    // BUG FIX: support both string and object URL formats
    const distractionUrl = distractionUrls.find(d =>
        extractDomain(typeof d === 'string' ? d : d.url) === domain);

    if (distractionUrl && timeSpent >= (distractionUrl.timeLimit || 0)) {
        const excessTime = timeSpent - (distractionUrl.timeLimit || 0);
        const question   = await getQuestionFromBackend(domain, excessTime);

        if (strictMode && excessTime > 300) {
            await showBlockingPopup(domain, question);
        } else if (notificationsEnabled) {
            await showFloatingNotification(domain, question);
        }
    }
}

// ─── Backend API calls ────────────────────────────────────────────────────────
async function getQuestionFromBackend(domain, excessTime) {
    try {
        const response = await fetch(`${API_BASE}/get-question`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ user_id: USER_ID, domain, excessTime })
        });
        if (response.ok) {
            const data = await response.json();
            return data.question || 'You have exceeded your time limit. Continue?';
        }
    } catch (e) { console.error('getQuestionFromBackend error:', e); }
    return 'You have exceeded your time limit. Continue?';
}

async function sendTabInfoToBackend(tab) {
    try {
        await fetch(`${API_BASE}/tab-activity`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                user_id:    USER_ID,   // BUG FIX: was missing
                url:        tab.url,
                title:      tab.title,
                timestamp:  new Date().toISOString(),
                timeOfDay:  new Date().getHours()
            })
        });
    } catch (e) { console.error('sendTabInfoToBackend error:', e); }
}

async function sendUsageDataToBackend(data) {
    try {
        await fetch(`${API_BASE}/usage-data`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(data)
        });
    } catch (e) { console.error('sendUsageDataToBackend error:', e); }
}

async function handleQuestionAnswer(answer, domain) {
    try {
        const response = await fetch(`${API_BASE}/question-answer`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                user_id:   USER_ID,   // BUG FIX: was missing
                answer,
                domain,
                timestamp: new Date().toISOString()
            })
        });
        if (response.ok) {
            const data = await response.json();
            if (data.rewardPoints) {
                const r = await chrome.storage.local.get(['rewardPoints']);
                await chrome.storage.local.set({ rewardPoints: (r.rewardPoints || 0) + data.rewardPoints });
            }
            // BUG FIX: don't overwrite entire distractionUrls with updatedLimits — it's just limit data
            // Only update limits if the response explicitly contains them
            if (data.updatedLimits && Array.isArray(data.updatedLimits)) {
                await chrome.storage.local.set({ distractionUrls: data.updatedLimits });
            }
        }
    } catch (e) { console.error('handleQuestionAnswer error:', e); }
}

// ─── Scripting helpers ────────────────────────────────────────────────────────
async function showFloatingNotification(domain, question) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func:   createFloatingNotification,
            args:   [domain, question]
        }).catch(e => console.error('showFloatingNotification error:', e));
    }
}

async function showBlockingPopup(domain, question) {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func:   createBlockingPopup,
            args:   [domain, question]
        }).catch(e => console.error('showBlockingPopup error:', e));
    }
}

// ─── Export ───────────────────────────────────────────────────────────────────
function exportAllData() {
    chrome.storage.local.get(null, (data) => {
        const exportData = {
            sessionData:    data.sessionData    || {},
            visitFrequency: data.visitFrequency || {},
            behaviorData:   data.behaviorData   || {},
            todayStats:     data.todayStats     || {},
            urlTimeSpent:   data.urlTimeSpent   || {},
            exportTime:     new Date().toISOString()
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url  = URL.createObjectURL(blob);
        chrome.downloads.download({ url, filename: `productivity_guard_data_${Date.now()}.json` },
            () => URL.revokeObjectURL(url));
    });
}

// ─── Auto-upload to backend ───────────────────────────────────────────────────
function getLatestBehaviorEntries(behaviorData, limit = 20) {
    const all = [];
    for (const [domain, sessions] of Object.entries(behaviorData || {})) {
        sessions.forEach(s => all.push({ domain, ...s }));
    }
    all.sort((a, b) =>
        new Date(b.lastUpdated || b.timeOfDay || 0).getTime() -
        new Date(a.lastUpdated || a.timeOfDay || 0).getTime()
    );
    return all.slice(0, limit);
}

async function autoUploadLatestBehavior() {
    try {
        const result  = await chrome.storage.local.get(['behaviorData']);
        const entries = getLatestBehaviorEntries(result.behaviorData, 20);
        if (entries.length === 0) return;  // BUG FIX: skip empty uploads

        const response = await fetch(`${API_BASE}/behavior-upload`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ behavior: entries, uploadedAt: new Date().toISOString() })
        });
        if (response.ok) console.log('Auto-upload success:', await response.json());
        else console.error('Auto-upload failed:', response.status);
    } catch (e) { console.warn('Auto-upload error (backend offline):', e.message); }
}

function startAutoUpload() {
    if (autoUploadInterval) clearInterval(autoUploadInterval); // prevent duplicates
    autoUploadInterval = setInterval(autoUploadLatestBehavior, 60000); // BUG FIX: was 10000ms
}

// ─── Message handling ─────────────────────────────────────────────────────────
// BUG FIX: original called sendResponse multiple times (once per if-block + once at end)
// which throws "message channel closed". Now uses a single return path.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'updateInteractionData') {
        userInteractionData.clicks         += message.data.clicks         || 0;
        userInteractionData.keystrokes     += message.data.keystrokes     || 0;
        userInteractionData.mouseMovements += message.data.mouseMovements || 0;
        userInteractionData.scrolls        += message.data.scrolls        || 0;
        sendResponse({ success: true });

    } else if (message.action === 'toggleFocusMode') {
        // handled via storage in popup
        sendResponse({ success: true });

    } else if (message.action === 'answerQuestion') {
        handleQuestionAnswer(message.answer, message.domain);
        sendResponse({ success: true });

    } else if (message.type === 'UPDATE_BEHAVIOR_DATA') {
        updateSessionData();
        sendResponse({ success: true });

    } else if (message.type === 'EXPORT_DATA') {
        exportAllData();
        sendResponse({ success: true });

    } else {
        sendResponse({ success: true });
    }
});

// ─── Alarms ───────────────────────────────────────────────────────────────────
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'dailyReset') resetDailyStatsIfNeeded();
});

async function resetDailyStatsIfNeeded() {
    const result = await chrome.storage.local.get(['lastResetDate']);
    const today  = new Date().toDateString();
    if (result.lastResetDate !== today) {
        await chrome.storage.local.set({
            todayStats:    { activeTime: 0, distractionTime: 0, productiveTime: 0 },
            urlTimeSpent:  {},
            lastResetDate: today
        });
        console.log('Daily stats reset');
    }
}

// ─── Tracking interval ────────────────────────────────────────────────────────
function startTracking() {
    if (trackingInterval) clearInterval(trackingInterval);
    trackingInterval = setInterval(async () => {
        const result = await chrome.storage.local.get(['trackingPaused']);
        if (!result.trackingPaused && activeTabId && sessionStartTime) {
            await saveSessionData();
            sessionStartTime = Date.now();
        }
    }, 30000);
}

setInterval(updateSessionData, 60000);

// ─── Window focus ─────────────────────────────────────────────────────────────
chrome.windows.onFocusChanged.addListener(async (windowId) => {
    if (windowId === chrome.windows.WINDOW_ID_NONE) {
        if (activeTabId && sessionStartTime) {
            await saveSessionData();
            sessionStartTime = null;
        }
    } else {
        const [tab] = await chrome.tabs.query({ active: true, windowId });
        if (tab) await handleTabChange(tab.id);
    }
});

// ─── Utilities ────────────────────────────────────────────────────────────────
function extractDomain(url) {
    try { return new URL(url).hostname; } catch { return url; }
}

function getNextMidnight() {
    const now = new Date();
    const midnight = new Date(now);
    midnight.setHours(24, 0, 0, 0);
    return midnight.getTime();
}
