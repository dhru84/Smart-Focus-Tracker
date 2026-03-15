// Content script for tracking user interactions and showing notifications
let interactionData = { clicks: 0, keystrokes: 0, mouseMovements: 0, scrolls: 0 };

let behaviorData = {
    url:           window.location.href,
    clicks:        0,
    scrolls:       0,
    keystrokes:    0,
    mouseMovements: 0,
    typingSpeed: { totalKeys: 0, totalTime: 0, sessions: [] },
    timeOfDay:   new Date().toISOString(),
    pageLoadTime: Date.now()
};

let lastMouseMove    = 0;
let typingSpeed      = [];
let lastKeyTime      = 0;
let typingSession    = { startTime: null, keyCount: 0 };
let scrollThrottle   = false;   // BUG FIX: was declared inside the scroll handler (reset every call)
const MOUSE_THROTTLE = 100;

// ─── Click tracking ───────────────────────────────────────────────────────────
document.addEventListener('click', () => {
    interactionData.clicks++;
    behaviorData.clicks++;
    saveBehaviorData();
}, true);

// ─── Mouse movement tracking ──────────────────────────────────────────────────
// BUG FIX: original had TWO checks both resetting lastMouseMove, so the second
// check (behaviorData.mouseMovements++) never fired because lastMouseMove was
// already updated by the first check. Merged into one throttled handler.
document.addEventListener('mousemove', () => {
    const now = Date.now();
    if (now - lastMouseMove > MOUSE_THROTTLE) {
        interactionData.mouseMovements++;
        behaviorData.mouseMovements++;
        lastMouseMove = now;
        saveBehaviorData();
    }
}, true);

// ─── Keystroke / typing speed tracking ───────────────────────────────────────
document.addEventListener('keydown', (e) => {
    const now = Date.now();
    interactionData.keystrokes++;

    // Existing typing interval tracking
    if (lastKeyTime > 0) {
        typingSpeed.push(now - lastKeyTime);
        if (typingSpeed.length > 10) typingSpeed.shift();
    }
    lastKeyTime = now;

    // Enhanced behavior tracking
    if (e.key.length === 1 || e.key === 'Backspace' || e.key === 'Delete') {
        behaviorData.keystrokes++;

        if (!typingSession.startTime) {
            typingSession.startTime = now;
            typingSession.keyCount  = 1;
        } else {
            typingSession.keyCount++;
            clearTimeout(typingSession.timeout);
            typingSession.timeout = setTimeout(() => {
                if (typingSession.keyCount > 5) {
                    const sessionDuration = (now - typingSession.startTime) / 1000;
                    const wpm = (typingSession.keyCount / 5) / (sessionDuration / 60);
                    behaviorData.typingSpeed.sessions.push({
                        wpm:       Math.round(wpm),
                        duration:  sessionDuration,
                        keyCount:  typingSession.keyCount,
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
}, true);

// ─── Scroll tracking ─────────────────────────────────────────────────────────
document.addEventListener('scroll', () => {
    interactionData.scrolls++;
    // BUG FIX: scrollThrottle is now a module-level var (not re-declared here)
    if (!scrollThrottle) {
        behaviorData.scrolls++;
        saveBehaviorData();
        scrollThrottle = true;
        setTimeout(() => { scrollThrottle = false; }, 100);
    }
}, true);

// ─── Visibility / unload ──────────────────────────────────────────────────────
document.addEventListener('visibilitychange', () => {
    if (document.hidden) saveBehaviorData();
    else behaviorData.timeOfDay = new Date().toISOString();
});

window.addEventListener('beforeunload', saveBehaviorData);

// ─── Save behavior data ───────────────────────────────────────────────────────
function saveBehaviorData() {
    // BUG FIX: guard against invalid URLs (e.g. chrome:// pages)
    let urlKey;
    try { urlKey = new URL(window.location.href).hostname; }
    catch (e) { return; }

    const dataToSave = {
        ...behaviorData,
        sessionDuration: Date.now() - behaviorData.pageLoadTime,
        lastUpdated:     new Date().toISOString()
    };

    chrome.storage.local.get(['behaviorData'], (result) => {
        if (chrome.runtime.lastError) return;
        const all = result.behaviorData || {};
        if (!all[urlKey]) all[urlKey] = [];

        const idx = all[urlKey].findIndex(e => e.pageLoadTime === behaviorData.pageLoadTime);
        if (idx >= 0) all[urlKey][idx] = dataToSave;
        else          all[urlKey].push(dataToSave);

        chrome.storage.local.set({ behaviorData: all });
    });

    chrome.runtime.sendMessage({ type: 'UPDATE_BEHAVIOR_DATA' }).catch(() => {});
}

// ─── Periodic interaction flush to background ─────────────────────────────────
setInterval(() => {
    if (Object.values(interactionData).some(v => v > 0)) {
        const avgTypingSpeed = typingSpeed.length > 0
            ? typingSpeed.reduce((a, b) => a + b, 0) / typingSpeed.length
            : 0;
        chrome.runtime.sendMessage({
            action: 'updateInteractionData',
            data:   { ...interactionData, avgTypingSpeed }
        }).catch(() => {});
        interactionData = { clicks: 0, keystrokes: 0, mouseMovements: 0, scrolls: 0 };
    }
}, 10000);

// ─── Initial + periodic save ──────────────────────────────────────────────────
saveBehaviorData();
setInterval(saveBehaviorData, 30000);

// ─── Floating notification (injected by background) ───────────────────────────
function createFloatingNotification(domain, question) {
    const existing = document.getElementById('productivity-guard-notification');
    if (existing) existing.remove();

    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes pulse   { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
    `;
    document.head.appendChild(style);

    const notification = document.createElement('div');
    notification.id = 'productivity-guard-notification';
    notification.style.cssText = `
        position:fixed;top:20px;right:20px;width:300px;
        background:linear-gradient(135deg,#ff6b6b,#feca57);
        color:white;padding:20px;border-radius:12px;
        box-shadow:0 8px 32px rgba(0,0,0,0.3);z-index:999999;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        font-size:14px;animation:slideIn 0.3s ease-out;
        border:1px solid rgba(255,255,255,0.2);`;
    notification.innerHTML = `
        <div style="margin-bottom:15px;">
            <div style="font-weight:bold;margin-bottom:8px;">⚠️ Time Limit Exceeded</div>
            <div style="font-size:12px;opacity:0.9;">Domain: ${domain}</div>
        </div>
        <div style="margin-bottom:15px;line-height:1.4;">${question}</div>
        <div style="display:flex;gap:10px;">
            <button id="pg-yes-btn" style="flex:1;padding:8px 16px;background:rgba(255,255,255,0.2);color:white;border:1px solid rgba(255,255,255,0.3);border-radius:6px;cursor:pointer;font-size:12px;">Yes</button>
            <button id="pg-no-btn"  style="flex:1;padding:8px 16px;background:rgba(255,255,255,0.2);color:white;border:1px solid rgba(255,255,255,0.3);border-radius:6px;cursor:pointer;font-size:12px;">No</button>
        </div>`;
    document.body.appendChild(notification);

    notification.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('mouseenter', () => { btn.style.background = 'rgba(255,255,255,0.3)'; });
        btn.addEventListener('mouseleave', () => { btn.style.background = 'rgba(255,255,255,0.2)'; });
    });

    document.getElementById('pg-yes-btn').addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'answerQuestion', answer: 'yes', domain });
        notification.remove();
    });
    document.getElementById('pg-no-btn').addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'answerQuestion', answer: 'no', domain });
        notification.remove();
    });

    setTimeout(() => { if (notification.parentNode) notification.remove(); }, 10000);
}

// ─── Blocking popup (injected by background) ──────────────────────────────────
function createBlockingPopup(domain, question) {
    const existing = document.getElementById('productivity-guard-blocking');
    if (existing) existing.remove();

    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
        @keyframes shake  { 0%,100%{transform:translateX(0);} 25%{transform:translateX(-10px);} 75%{transform:translateX(10px);} }
    `;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.id = 'productivity-guard-blocking';
    overlay.style.cssText = `
        position:fixed;top:0;left:0;width:100vw;height:100vh;
        background:rgba(0,0,0,0.9);z-index:9999999;
        display:flex;align-items:center;justify-content:center;
        backdrop-filter:blur(5px);animation:fadeIn 0.3s ease-out;`;

    const popup = document.createElement('div');
    popup.style.cssText = `
        background:linear-gradient(135deg,#667eea,#764ba2);padding:40px;
        border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,0.5);
        color:white;text-align:center;max-width:500px;width:90%;
        animation:shake 0.5s ease-in-out;`;
    popup.innerHTML = `
        <div style="font-size:48px;margin-bottom:20px;">🚫</div>
        <h2 style="margin:0 0 20px 0;font-size:24px;">Access Restricted</h2>
        <p style="margin:0 0 10px 0;opacity:0.8;">Domain: ${domain}</p>
        <p style="margin:0 0 30px 0;font-size:16px;line-height:1.5;">${question}</p>
        <div style="display:flex;gap:20px;justify-content:center;">
            <button id="pg-block-yes" style="padding:15px 30px;background:#ff6b6b;color:white;border:none;border-radius:8px;cursor:pointer;font-size:16px;font-weight:bold;">Yes, Continue</button>
            <button id="pg-block-no"  style="padding:15px 30px;background:#51cf66;color:white;border:none;border-radius:8px;cursor:pointer;font-size:16px;font-weight:bold;">No, Go Back</button>
        </div>`;
    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    popup.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('mouseenter', () => { btn.style.transform = 'scale(1.05)'; });
        btn.addEventListener('mouseleave', () => { btn.style.transform = 'scale(1)'; });
    });

    document.getElementById('pg-block-yes').addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'answerQuestion', answer: 'yes', domain });
        overlay.remove();
    });
    document.getElementById('pg-block-no').addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'answerQuestion', answer: 'no', domain });
        overlay.remove();
        window.history.back();
    });

    overlay.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); });

    const blockKeyboard = e => { e.preventDefault(); e.stopPropagation(); return false; };
    document.addEventListener('keydown', blockKeyboard, true);

    const observer = new MutationObserver(mutations => {
        mutations.forEach(m => m.removedNodes.forEach(node => {
            if (node === overlay) {
                document.removeEventListener('keydown', blockKeyboard, true);
                observer.disconnect();
            }
        }));
    });
    observer.observe(document.body, { childList: true });
}

// ─── Message listener ─────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'showNotification')  createFloatingNotification(message.domain, message.question);
    if (message.action === 'showBlockingPopup') createBlockingPopup(message.domain, message.question);
    sendResponse({ success: true });
});