# 🛡️ Smart Focus Tracker

An AI-powered productivity Chrome extension that tracks your browsing behavior, enforces time limits on distracting websites, and uses Mistral AI to analyze your digital wellness and mental health patterns.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [How It Works](#how-it-works)

---

## 🧠 Overview

Smart Focus Tracker is a full-stack productivity tool that combines a Chrome Extension with a Flask backend powered by Mistral AI. It monitors your web browsing habits in real time, intervenes when you exceed time limits on distracting sites, and performs AI-driven mental health analysis based on your digital behavior patterns.

---

## ✨ Features

- 🔍 **Real-time behavior tracking** — clicks, scrolls, keystrokes, mouse movements, typing speed
- ⏱️ **Time limit enforcement** — set daily limits for distraction sites (YouTube, Instagram, etc.)
- 🤖 **AI intervention questions** — personalized prompts powered by Mistral AI when limits are exceeded
- 🚫 **Strict mode** — full-screen blocking popup for serious overuse
- 🧠 **Mental health analysis** — AI analyzes browsing patterns for stress, anxiety, and focus indicators
- 📊 **Dashboard** — live stats for active time, distraction time, and productive time
- 🏆 **Reward points** — earn points for making productive choices
- 📥 **Data export** — export behavior data as JSON and upload to backend for AI analysis
- 🔔 **Smart notifications** — floating alerts when time limits are exceeded
- 🌙 **Daily reset** — stats automatically reset at midnight

---

## 🛠️ Tech Stack

### Frontend (Chrome Extension)
- JavaScript (Manifest V3)
- Chrome Extension APIs (storage, tabs, scripting, alarms, downloads)
- HTML5 / CSS3

### Backend
- Python 3
- Flask + Flask-CORS
- SQLite
- LangChain (0.3.x)
- Mistral AI (`mistral-large-latest`, `mistral-small-latest`)
- NumPy, BeautifulSoup4

---

## 📁 Project Structure

```
Smart-Focus-Tracker/
│
├── .gitignore                          # Git ignore rules
├── productivity.db                     # Root-level SQLite DB (shared reference)
│
├── backend/                            # Flask backend server
│   ├── app.py                          # Main Flask app — defines all API routes and request handlers
│   ├── brain.py                        # Mental health analysis AI agent using Mistral LLM + LangChain
│   ├── checkUrl.py                     # URL productivity classifier — checks if a URL is productive or distracting
│   ├── db.py                           # Database manager — all SQLite read/write operations
│   ├── model.py                        # Productivity model — generates questions, insights, summaries, reward logic
│   ├── test.py                         # API test script — runs 8 endpoint tests to verify backend is working
│   ├── test_mistral.py                 # Quick Mistral AI connection test
│   ├── .env                            # Environment variables (MISTRAL_API_KEY) — not committed to Git
│   ├── packages.txt                    # List of installed Python packages for reference
│   ├── readme.md                       # Backend-specific notes
│   ├── latest_behavior_upload.json     # Last behavior data uploaded by extension (auto-generated)
│   ├── productivity.db                 # Main SQLite database — stores URLs, usage data, intervention responses
│   ├── user_behavior_history.db        # Historical behavior database — stores session analysis results
│   ├── __pycache__/                    # Python bytecode cache (auto-generated, not committed)
│   └── venv/                           # Python virtual environment (not committed)
│
├── smart-focus/                                # Main Chrome Extension — Productivity Guard
│   ├── manifest.json                   # Extension manifest (MV3) — permissions, service worker, content scripts
│   ├── background.js                   # Service worker — tracks tabs, sends usage data to backend, checks time limits
│   ├── content.js                      # Content script — runs on every page, tracks clicks/scrolls/keystrokes
│   ├── popup.html                      # Extension popup UI — Dashboard, Settings, and Behavior tabs
│   ├── popup.js                        # Popup logic — loads stats, handles URL add/remove, exports data to backend
│   ├── popup.css                       # Popup styles — gradient theme, tab layout, URL list styling
│   └── sound.wav                       # Click sound effect played on button interactions
│
├── popup_initial/                      # VisionEdge — standalone sidebar extension (no backend)
│   ├── manifest.json                   # Extension manifest for VisionEdge
│   ├── background.js                   # Shows floating tip box after 30 seconds on a page
│   ├── content.js                      # Injects sidebar and chat bubble into web pages
│   ├── popup.html                      # Simple popup with 3 buttons
│   ├── popup.js                        # Handles sidebar toggle, floating tip, and dark mode
│   ├── popup.css                       # Styles for VisionEdge popup
│   └── sound.wav                       # Click sound effect
│
└── projectX1/                          # User Behavior Tracker — standalone tracker (no backend)
    ├── manifest.json                   # Extension manifest for behavior tracker
    ├── background.js                   # Tracks tab switches, session time, visit frequency
    ├── content.js                      # Tracks clicks, scrolls, mouse movements, typing speed per page
    ├── data-manager.js                 # Manages saving/reading behavior data to extension storage
    ├── popup.html                      # Shows live session stats and export/clear buttons
    └── popup.js                        # Loads stats from storage, handles export and clear actions
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.10+
- Google Chrome browser
- Mistral AI API key — get one free at [console.mistral.ai](https://console.mistral.ai)

### 1. Clone the repository
```bash
git clone https://github.com/your-username/smart-focus-tracker.git
cd smart-focus-tracker
```

### 2. Set up the Python virtual environment
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies
```bash
# Remove conflicting packages if present
pip uninstall langchain-classic -y

# Install correct LangChain versions
pip install "langchain==0.3.25" "langchain-core==0.3.59" "langchain-community==0.3.24" "langchain-experimental==0.3.4"

# Install remaining packages
pip install flask flask-cors python-dotenv langchain-mistralai beautifulsoup4 numpy requests
```

### 4. Configure your API key
Create a `.env` file inside the `backend/` folder:
```
MISTRAL_API_KEY=your_mistral_api_key_here
```

### 5. Start the backend server
```bash
python app.py
```
You should see:
```
Database initialized successfully
Starting Flask server...
* Running on http://127.0.0.1:5000
```

### 6. Load the Chrome Extension
1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `smart-focus/` folder
5. Pin the 🛡️ **Productivity Guard** icon to your Chrome toolbar

### 7. Verify everything works
```bash
python test.py
```
Expected output:
```
🎉 Test Results: 8/8 tests passed
Your API is working correctly.
```

---

## 🚀 Usage

1. **Start the backend** — always run `python app.py` before using the extension
2. **Open the extension** — click the 🛡️ icon in your Chrome toolbar
3. **Settings tab** — add distraction URLs with time limits and productive URLs with targets

   | Example Distraction URLs | Time Limit |
   |--------------------------|-----------|
   | `youtube.com` | 30 min |
   | `instagram.com` | 20 min |
   | `twitter.com` | 15 min |

   | Example Productive URLs | Target Time |
   |-------------------------|------------|
   | `github.com` | 60 min |
   | `stackoverflow.com` | 45 min |

4. **Browse normally** — the extension tracks everything in the background automatically
5. **Get AI interventions** — when you exceed a time limit, a floating question appears asking if you want to continue
6. **Dashboard tab** — see your active time, distraction time, and productive time
7. **Behavior tab** — see live clicks, scrolls, mouse movements for the current page
8. **Export button** — uploads your behavior data to backend for Mistral AI mental health analysis

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check — confirms server and DB are running |
| POST | `/api/distraction-urls` | Save list of distraction URLs for a user |
| POST | `/api/productive-urls` | Save list of productive URLs for a user |
| POST | `/api/usage-data` | Record a URL visit with duration and interactions |
| POST | `/api/tab-activity` | Record a tab switch event |
| POST | `/api/get-question` | Get an AI-generated intervention question |
| POST | `/api/question-answer` | Submit user's answer, get reward points |
| POST | `/api/behavior-upload` | Upload behavior data for AI mental health analysis |
| GET | `/api/get-insights` | Get AI-generated productivity insights |
| GET | `/api/daily-summary` | Get today's productive vs distraction time summary |
| POST | `/api/adjust-limits` | Get AI recommendations for time limit adjustments |

---

## 🔬 How It Works

```
User browses the web
        │
        ▼
content.js (runs on every page)
tracks clicks, scrolls, keystrokes,
mouse movements, typing speed
        │
        ▼
background.js (service worker)
sends data to Flask backend every 30s
        │
        ├──▶ /api/usage-data ──▶ Saved to productivity.db
        │
        ├──▶ Time limit check ──▶ /api/get-question
        │                               │
        │                               ▼
        │                     Mistral AI generates
        │                     personalized question
        │                               │
        │                               ▼
        │                     Floating notification
        │                     shown on the page
        │
        └──▶ Export clicked ──▶ /api/behavior-upload
                                        │
                                        ▼
                               brain.py runs Mistral AI
                               mental health analysis
                                        │
                                        ▼
                               Stress score (0.0 - 1.0)
                               Intervention level (none/gentle/critical)
                               Wellness task recommendations
```

---
