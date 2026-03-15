// ─── Constants ────────────────────────────────────────────────────────────────
const API_BASE = 'http://127.0.0.1:5000';
const USER_ID  = 'default_user';

// ─── DOM references ───────────────────────────────────────────────────────────
const tabBtns           = document.querySelectorAll('.tab-btn');
const tabContents       = document.querySelectorAll('.tab-content');
const rewardPointsEl    = document.getElementById('rewardPoints');
const activeTimeEl      = document.getElementById('activeTime');
const distractionTimeEl = document.getElementById('distractionTime');
const productiveTimeEl  = document.getElementById('productiveTime');

let behaviorUpdateInterval = null;
let currentTabStartTime    = null;
let currentTabUrl          = null;
let autoUploadTimer        = null;

// ─── Sound ────────────────────────────────────────────────────────────────────
function playSound() {
    try {
        const audio = new Audio(chrome.runtime.getURL('sound.wav'));
        audio.volume = 0.3;
        audio.play().catch(() => {});
    } catch (e) {}
}

// ─── URL normalizer ───────────────────────────────────────────────────────────
function normalizeUrl(input) {
    input = String(input || '').trim().replace(/\s+/g, '');
    if (!input || input.length < 3) return null;
    if (!/^https?:\/\//i.test(input)) input = 'https://' + input;
    return input;
}

// ─── Tab switching ────────────────────────────────────────────────────────────
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        playSound();
        const tabId = btn.dataset.tab;
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        tabContents.forEach(c => {
            c.classList.remove('active');
            if (c.id === tabId) c.classList.add('active');
        });
        if (tabId === 'behavior') {
            loadBehaviorStats();
            startBehaviorStatsUpdate();
        } else {
            stopBehaviorStatsUpdate();
        }
    });
});

function startBehaviorStatsUpdate() {
    stopBehaviorStatsUpdate();
    behaviorUpdateInterval = setInterval(loadBehaviorStats, 500);
}
function stopBehaviorStatsUpdate() {
    if (behaviorUpdateInterval) { clearInterval(behaviorUpdateInterval); behaviorUpdateInterval = null; }
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
async function loadData() {
    try {
        const result = await chrome.storage.local.get([
            'rewardPoints', 'todayStats', 'distractionUrls', 'productiveUrls'
        ]);
        rewardPointsEl.textContent    = result.rewardPoints || 0;
        const stats = result.todayStats || {};
        activeTimeEl.textContent      = formatTime(stats.activeTime || 0);
        distractionTimeEl.textContent = formatTime(stats.distractionTime || 0);
        productiveTimeEl.textContent  = formatTime(stats.productiveTime || 0);
        displayUrlList('distraction', result.distractionUrls || []);
        displayUrlList('productive',  result.productiveUrls  || []);
    } catch (e) { console.error('loadData error:', e); }
}

// ─── Behavior stats ───────────────────────────────────────────────────────────
function loadBehaviorStats() {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0] || !tabs[0].url) return;
        let hostname;
        try { hostname = new URL(tabs[0].url).hostname; } catch (e) { return; }

        document.getElementById('currentUrl').textContent = hostname;

        if (currentTabUrl !== tabs[0].url) {
            currentTabUrl       = tabs[0].url;
            currentTabStartTime = Date.now();
        }
        if (currentTabStartTime) {
            document.getElementById('sessionTime').textContent =
                formatTimeDetailed(Math.floor((Date.now() - currentTabStartTime) / 1000));
        }

        chrome.storage.local.get(['sessionData'], r => {
            document.getElementById('tabSwitches').textContent =
                (r.sessionData || {}).tabSwitchCount || 0;
        });

        chrome.storage.local.get(['behaviorData'], r => {
            const siteData = (r.behaviorData || {})[hostname] || [];
            if (siteData.length > 0) {
                const latest = siteData[siteData.length - 1];
                const stale  = (Date.now() - new Date(latest.lastUpdated || 0).getTime()) > 30000;
                document.getElementById('pageClicks').textContent     = stale ? '0' : (latest.clicks         || 0);
                document.getElementById('pageScrolls').textContent    = stale ? '0' : (latest.scrolls        || 0);
                document.getElementById('mouseMovements').textContent = stale ? '0' : (latest.mouseMovements || 0);
            } else {
                document.getElementById('pageClicks').textContent     = '0';
                document.getElementById('pageScrolls').textContent    = '0';
                document.getElementById('mouseMovements').textContent = '0';
            }
        });
    });
}

// ─── Formatters ───────────────────────────────────────────────────────────────
function formatTime(seconds) { return `${Math.floor(seconds / 60)}m`; }
function formatTimeDetailed(seconds) {
    const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

// ─── Export ───────────────────────────────────────────────────────────────────
async function exportBehaviorData() {
    chrome.storage.local.get(null, async (data) => {
        const exportData = {
            sessionData:     data.sessionData    || {},
            visitFrequency:  data.visitFrequency || {},
            behaviorData:    data.behaviorData   || {},
            todayStats:      data.todayStats     || {},
            urlTimeSpent:    data.urlTimeSpent   || {},
            distractionUrls: data.distractionUrls || [],
            productiveUrls:  data.productiveUrls  || [],
            rewardPoints:    data.rewardPoints   || 0,
            exportTime:      new Date().toISOString(),
            exportedFrom:    'ProductivityGuard'
        };
        try {
            const entries = getLatestBehaviorEntries(exportData, 20);
            const resp = await fetch(`${API_BASE}/api/behavior-upload`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ behavior: entries, uploadedAt: new Date().toISOString() })
            });
            if (resp.ok) console.log('Backend analysis:', await resp.json());
        } catch (e) { console.warn('Backend offline:', e.message); }

        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url  = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url; link.download = `productivity_guard_data_${Date.now()}.json`;
        link.style.display = 'none';
        document.body.appendChild(link); link.click(); document.body.removeChild(link);
        URL.revokeObjectURL(url);

        const btn = document.getElementById('exportBtn'), orig = btn.textContent;
        btn.textContent = 'Exported! ✓'; btn.style.background = '#34a853';
        setTimeout(() => { btn.textContent = orig; btn.style.background = ''; }, 2000);
    });
}

// ─── Clear ────────────────────────────────────────────────────────────────────
function clearBehaviorData() {
    if (!confirm('Clear all tracked data?')) return;
    chrome.storage.local.clear(() => {
        currentTabStartTime = Date.now(); currentTabUrl = null;
        const btn = document.getElementById('clearBtn'), orig = btn.textContent;
        btn.textContent = 'Cleared!'; btn.style.background = '#ea4335';
        setTimeout(() => { btn.textContent = orig; btn.style.background = ''; loadBehaviorStats(); }, 2000);
    });
}

// ─── URL list display ─────────────────────────────────────────────────────────
function displayUrlList(type, urls) {
    const listEl = document.getElementById(`${type}List`);
    listEl.innerHTML = '';
    urls.forEach((urlData, index) => {
        const rawUrl  = typeof urlData === 'string' ? urlData : (urlData.url || '');
        const timeVal = typeof urlData === 'object' ? (urlData.timeLimit || urlData.targetTime || null) : null;
        let domain;
        try { domain = new URL(rawUrl).hostname; } catch (e) { domain = rawUrl; }
        const item = document.createElement('div');
        item.className = 'url-item';
        item.innerHTML = `
            <div class="url-info">
                <div class="url-domain">${domain}</div>
                <div class="url-time">${timeVal ? Math.round(timeVal / 60) + ' min' : '—'}</div>
            </div>
            <button class="remove-btn" data-type="${type}" data-index="${index}">×</button>`;
        listEl.appendChild(item);
    });
}

// ─── Add distraction URL ──────────────────────────────────────────────────────
document.getElementById('addDistraction').addEventListener('click', async () => {
    playSound();

    // Read values directly — no validation that can fail
    const rawUrl   = document.getElementById('distractionUrl').value;
    const rawTime = document.getElementById('distractionTimeInput').value;
    const url      = normalizeUrl(rawUrl);
    const timeLimit = parseInt(rawTime);

    console.log('Adding distraction:', rawUrl, '->', url, '| time:', rawTime, '->', timeLimit);

    if (!url || isNaN(timeLimit) || timeLimit < 1) {
        alert(`Got: url="${rawUrl}" time="${rawTime}". Please enter a site (e.g. youtube.com) and minutes (e.g. 30)`);
        return;
    }

    const result = await chrome.storage.local.get(['distractionUrls']);
    const distractionUrls = result.distractionUrls || [];
    distractionUrls.push({ url, timeLimit: timeLimit * 60 });
    await chrome.storage.local.set({ distractionUrls });

    await sendToBackend('/api/distraction-urls', {
        user_id: USER_ID,
        urls: distractionUrls.map(d => typeof d === 'string' ? d : d.url)
    });

    document.getElementById('distractionUrl').value  = '';
    document.getElementById('distractionTimeInput').value = '';
    displayUrlList('distraction', distractionUrls);
});

// ─── Add productive URL ───────────────────────────────────────────────────────
document.getElementById('addProductive').addEventListener('click', async () => {
    playSound();

    const rawUrl    = document.getElementById('productiveUrl').value;
    const rawTime = document.getElementById('productiveTimeInput').value;
    const url       = normalizeUrl(rawUrl);
    const targetTime = parseInt(rawTime);

    console.log('Adding productive:', rawUrl, '->', url, '| time:', rawTime, '->', targetTime);

    if (!url || isNaN(targetTime) || targetTime < 1) {
        alert(`Got: url="${rawUrl}" time="${rawTime}". Please enter a site (e.g. github.com) and minutes (e.g. 60)`);
        return;
    }

    const result = await chrome.storage.local.get(['productiveUrls']);
    const productiveUrls = result.productiveUrls || [];
    productiveUrls.push({ url, targetTime: targetTime * 60 });
    await chrome.storage.local.set({ productiveUrls });

    await sendToBackend('/api/productive-urls', {
        user_id: USER_ID,
        urls: productiveUrls.map(p => typeof p === 'string' ? p : p.url)
    });

    document.getElementById('productiveUrl').value  = '';
    document.getElementById('productiveTimeInput').value = '';
    displayUrlList('productive', productiveUrls);
});

// ─── Remove URL ───────────────────────────────────────────────────────────────
document.addEventListener('click', async (e) => {
    if (!e.target.classList.contains('remove-btn')) return;
    playSound();
    const type = e.target.dataset.type, index = parseInt(e.target.dataset.index);
    const storageKey = `${type}Urls`;
    const result = await chrome.storage.local.get([storageKey]);
    const urls = result[storageKey] || [];
    urls.splice(index, 1);
    await chrome.storage.local.set({ [storageKey]: urls });
    const endpoint = type === 'distraction' ? '/api/distraction-urls' : '/api/productive-urls';
    await sendToBackend(endpoint, { user_id: USER_ID, urls: urls.map(u => typeof u === 'string' ? u : u.url) });
    displayUrlList(type, urls);
});

// ─── Quick actions ────────────────────────────────────────────────────────────
document.getElementById('pauseTracking').addEventListener('click', async () => {
    playSound();
    const result = await chrome.storage.local.get(['trackingPaused']);
    const isPaused = !result.trackingPaused;
    await chrome.storage.local.set({ trackingPaused: isPaused });
    document.getElementById('pauseTracking').textContent = isPaused ? 'Resume Tracking' : 'Pause Tracking';
});

document.getElementById('focusMode').addEventListener('click', async () => {
    playSound();
    const result = await chrome.storage.local.get(['focusMode']);
    const isFocusMode = !result.focusMode;
    await chrome.storage.local.set({ focusMode: isFocusMode });
    document.getElementById('focusMode').textContent = isFocusMode ? 'Exit Focus Mode' : 'Focus Mode';
    chrome.runtime.sendMessage({ action: 'toggleFocusMode', enabled: isFocusMode });
});

document.getElementById('enableNotifications').addEventListener('change', async (e) => {
    await chrome.storage.local.set({ notificationsEnabled: e.target.checked });
});
document.getElementById('enableStrictMode').addEventListener('change', async (e) => {
    await chrome.storage.local.set({ strictMode: e.target.checked });
});

// ─── Backend helper ───────────────────────────────────────────────────────────
async function sendToBackend(endpoint, data) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) console.error('Backend error:', response.status);
        return response;
    } catch (e) { console.warn('Backend offline:', e.message); }
}

// ─── Auto-upload ──────────────────────────────────────────────────────────────
function getLatestBehaviorEntries(data, limit = 20) {
    const all = [];
    for (const [domain, sessions] of Object.entries(data.behaviorData || {}))
        sessions.forEach(s => all.push({ domain, ...s }));
    all.sort((a, b) =>
        new Date(b.lastUpdated || b.timeOfDay || 0) - new Date(a.lastUpdated || a.timeOfDay || 0));
    return all.slice(0, limit);
}

async function autoUploadLatestBehavior() {
    try {
        const result  = await chrome.storage.local.get(['behaviorData']);
        const entries = getLatestBehaviorEntries(result, 20);
        if (entries.length === 0) return;
        const resp = await fetch(`${API_BASE}/api/behavior-upload`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ behavior: entries, uploadedAt: new Date().toISOString() })
        });
        if (resp.ok) console.log('Auto-upload:', await resp.json());
    } catch (e) { console.warn('Auto-upload offline:', e.message); }
}

function startAutoUploadTimer() {
    if (autoUploadTimer) clearInterval(autoUploadTimer);
    autoUploadTimer = setInterval(autoUploadLatestBehavior, 60000);
}

// ─── Message listener ─────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'updateStats' || message.type === 'UPDATE_BEHAVIOR_DATA') {
        loadData(); loadBehaviorStats();
    }
    sendResponse({ success: true });
});

window.addEventListener('beforeunload', () => {
    stopBehaviorStatsUpdate();
    if (autoUploadTimer) clearInterval(autoUploadTimer);
});

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    loadBehaviorStats();
    document.getElementById('exportBtn').addEventListener('click', exportBehaviorData);
    document.getElementById('clearBtn').addEventListener('click', clearBehaviorData);

    chrome.storage.local.get(['trackingPaused', 'focusMode', 'notificationsEnabled', 'strictMode'])
        .then(result => {
            document.getElementById('pauseTracking').textContent =
                result.trackingPaused ? 'Resume Tracking' : 'Pause Tracking';
            document.getElementById('focusMode').textContent =
                result.focusMode ? 'Exit Focus Mode' : 'Focus Mode';
            document.getElementById('enableNotifications').checked = result.notificationsEnabled !== false;
            document.getElementById('enableStrictMode').checked    = result.strictMode || false;
        });

    startAutoUploadTimer();
});