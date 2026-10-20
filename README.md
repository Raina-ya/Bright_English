# Bright English

> 一個用 AI 驅動、資料存在本地的英文學習網頁應用。每天自動抓取新聞、生成聽力與閱讀測驗、追蹤單字與錯題，還有一隻會陪你學習的寵物。

![status](https://img.shields.io/badge/status-active-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)

---

## 這是什麼

Bright English 是一個單機運行的英文學習工具，目標是讓「每天練英文」變成一件不用意志力的事。它把閱讀、聽力、單字、測驗和遊戲化激勵放在同一個介面裡，題目由 AI 即時生成，學習紀錄全部存在你自己的電腦上。

這個專案是用 **Claude Code / Codex** 等 AI coding agent 協作開發而成。README 後段有「開發過程與設計決策」一節，記錄了我在這個過程中做的判斷、遇到的問題、以及哪些地方我沒有照 AI 的建議走。

## 功能

- **今日閱讀**：從 BBC、CNN、The Guardian、NPR、Reuters 等公開 RSS 抓取新聞，附中文翻譯與語音朗讀。
- **閱讀測驗**：針對新聞主題生成 600 字以上的長文與 5–8 道題，題型涵蓋主旨、細節、推論、詞彙、作者態度。
- **聽力測驗**：比照多益題型（看圖描述、應答、短對話、獨白），每段材料 120 字以上，支援重播與語速調整。
- **單字學習**：每日 15–20 個新詞，含音標、詞性、中英釋義、例句；支援收藏與分類。
- **單字測驗**：英選中、中選英、語境填空、同義反義輪換，答錯自動進錯題本。
- **四級難度**：★ 到 ★★★★，對標 CEFR B2 到 C2，閱讀、聽力、單字、測驗共用設定。
- **寵物系統**：會呼吸、眨眼、回應滑鼠的虛擬寵物，可聊天、餵食、用學習金幣購買配件。
- **資料本地化**：所有學習紀錄存在瀏覽器 localStorage，不上傳雲端。

## 技術棧

- 前端：原生 HTML / CSS / JavaScript（無框架）
- 後端：Python 輕量本地伺服器（處理 RSS 代理與 AI API 呼叫，避開 CORS）
- 語音：瀏覽器原生 SpeechSynthesis API
- AI 出題：支援多供應商 fallback（Groq / OpenRouter / Google AI Studio / OpenAI）
- 資料儲存：localStorage + 本地 JSON 快取

## 快速開始

### 需求

- Python 3.9+
- 現代瀏覽器（Chrome / Edge / Firefox）
- 至少一個 AI API Key（見下方設定）

### 啟動

```bash
git clone https://github.com/你的帳號/bright-english.git
cd bright-english
python server.py
