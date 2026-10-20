# Bright English

Bright English 是供以閱讀、聽力與單字練習為主的英語學習者使用的本機網頁工具，將每日題目、錯題與單字紀錄保存在本機。

## 功能

- Dashboard 顯示每日任務、金幣、收藏數與錯題數。
- 閱讀模組透過本機 RSS proxy 取得新聞來源，並可交由已設定的 AI provider 改寫與出題。
- 聽力模組使用瀏覽器 `SpeechSynthesis` 朗讀材料，提供練習與模考播放模式。
- 單字模組提供每日單字、發音、收藏分類與收藏複習。
- 錯題會儲存於本機；答對紀錄與題目 history 用於複習與避免重複。
- 可將錯題與已學單字匯出為 Obsidian 可用的 Markdown。
- Foxy 寵物提供 SVG 互動、情緒數值與 AI 聊天入口；無法使用 AI 時仍保留本機介面。
- `widget.py` 提供 Tkinter 桌面小工具，顯示諺語與今日單字。
- `mobile/` 內含 Expo/React Native 實驗性行動版專案。

## Tech stack

- Frontend: HTML、CSS、vanilla JavaScript
- Local server: Python 3 standard library (`http.server`、`urllib`、`xml.etree`)
- Storage: JSON 檔案與 browser `localStorage`
- Speech: browser `SpeechSynthesis API`
- AI providers: Groq、OpenRouter、Google Gemini、OpenAI
- Mobile: Expo SDK 54、React Native、AsyncStorage、Expo Speech

## Quick start

### Requirements

- Python 3.10 以上
- 現代瀏覽器
- 選用：任一 AI provider 的 API key；未設定時，AI 改寫、生成與聊天會失敗或使用既有內容

### Run the web app

```powershell
git clone https://github.com/Raina-ya/Bright_English.git
cd Bright_English
Copy-Item .env.example .env
```

在 `.env` 填入想使用的 provider；未使用的欄位維持空白即可。

```dotenv
GROQ_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=
```

啟動本機伺服器：

```powershell
py -3 server.py
```

再開啟 [http://localhost:8765](http://localhost:8765)。Windows 也可直接執行 `啟動英文遊戲.bat`；它會偵測 8765 port 是否已被使用，再開啟瀏覽器。

AI provider 會依 `config.json` 的 `order` 順序嘗試。`.env` 中的值優先於 `config.json` 內對應的 `key` 欄位；不要把實際 key 寫入或提交 `config.json`。

### Run the desktop widget

先啟動 `server.py` 一次以建立本機資料檔，再執行：

```powershell
py -3 widget.py
```

### Run the mobile experiment

```powershell
cd mobile
npm install
npm run start
```

使用 Expo Go 掃描 Expo CLI 顯示的 QR code。

## Project structure

```text
.
├── index.html             # Web app HTML shell and main navigation
├── style.css              # Web layout, cards, animation, and pet styles
├── app.js                 # Web UI, local state, speech, quizzes, and pet interaction
├── server.py              # Local API, RSS proxy, AI fallback, validation, and JSON persistence
├── config.json            # Provider models and fallback order; keep API keys empty
├── .env.example           # API key variable template
├── 啟動英文遊戲.bat        # Windows launcher for the local server and browser
├── widget.py              # Tkinter desktop widget
└── mobile/
    ├── App.js             # Expo mobile interface
    ├── package.json       # Mobile scripts and dependencies
    └── app.json           # Expo application configuration
```

## Design decisions and pitfalls

### RSS proxy

Problem → Browsers may block direct cross-origin RSS requests through CORS, and individual RSS feeds can fail.

Solution → `server.py` fetches RSS feeds concurrently, parses them locally, tracks source health, removes duplicate items, and returns a normalized `/api/rss` response.

Reason → The frontend can use one same-origin endpoint while retaining source metadata and a controlled fallback path.

### Length and difficulty validation

Problem → AI output can be shorter than requested, use unsuitable sentence complexity, or return unusable options.

Solution → `validate_reading`、`validate_listening`、`validate_news_rewrite` and `valid_generated` in `server.py` count words, inspect sentence length and clauses, check question-option integrity, and retry generation up to three times.

Reason → Failed validation is surfaced to the UI instead of silently accepting material that misses the stated constraints.

### Vocabulary sub-tabs

Problem → Rebuilding the vocabulary page when switching among today’s words, quiz, favorites, and review can discard the visible state.

Solution → The current `words()` rendering uses independent `.wordSection` regions and `hidden` state, with `switchWordPane` changing visibility.

Reason → The four views remain part of one vocabulary page rather than becoming separate routes.

### Pet rendering

Problem → CSS-only mascot shapes can deform when animated or resized.

Solution → The pet page uses an inline SVG fox with separate tail, body, head, and eye elements; CSS classes apply breathing, blinking, hover, jump, and heart effects.

Reason → SVG `viewBox` keeps the pet’s proportions while animations target individual parts.

### AI fallback and degradation

Problem → A single provider can be unavailable, rate-limited, or reject a request.

Solution → `call_ai` reads the ordered providers from `config.json`, uses `.env` keys first, and attempts each configured provider in sequence. RSS-derived content is cached locally; when a provider fails, endpoints return an error or existing seed/fallback material where the relevant flow implements it.

Reason → The app continues to present locally available study data without embedding credentials in frontend code.

## Known limitations

- AI-generated output quality and availability depend on the selected provider and its quota.
- RSS feeds can be unavailable, delayed, duplicated across publishers, or changed without notice.
- Data is local to the browser and project directory; there is no multi-device sync or account system.
- Browser voices and available accents depend on the operating system and browser.
- The mobile Expo project is separate from the web app’s JSON storage and does not automatically sync its progress.
- The web code contains several legacy UI paths; test the relevant page after changing its associated functions.

## License

MIT
