/* Bright English client: one state flow, one renderer, no runtime overrides. */
const $ = (selector, root = document) => root.querySelector(selector);
const app = $('#app');
const SETTINGS_KEY = 'bright-settings-v3';
const FAVORITES_KEY = 'bright-favorites-v2';

const defaults = () => ({
  version: 1, settings: {}, days: {}, mistakes: [], learned_words: [],
  stats: { answers: 0, correct: 0, study_dates: [] },
  pet: { mood: 65, food: 0, chat: [] }
});

const levels = {
  one: { stars: '★', label: 'B2', rate: 0.82, pool: 'basic' },
  two: { stars: '★★', label: 'C1', rate: 0.98, pool: 'business' },
  three: { stars: '★★★', label: 'C1+/C2', rate: 1.08, pool: 'academic' },
  four: { stars: '★★★★', label: 'C2 / GRE', rate: 1.18, pool: 'advanced' }
};

const wordBank = {
  basic: [
    ['achieve','/əˈtʃiːv/','v.','to successfully reach a goal','達成','She worked steadily to <mark>achieve</mark> her goal.'],
    ['benefit','/ˈbenɪfɪt/','n.','an advantage or helpful result','益處','Regular practice is a lasting <mark>benefit</mark>.'],
    ['challenge','/ˈtʃælɪndʒ/','n.','a difficult task that tests ability','挑戰','The course presents a useful <mark>challenge</mark>.'],
    ['compare','/kəmˈpeər/','v.','to examine similarities and differences','比較','Please <mark>compare</mark> the two proposals carefully.'],
    ['require','/rɪˈkwaɪər/','v.','to need something as necessary','需要','The role will <mark>require</mark> clear communication.'],
    ['method','/ˈmeθəd/','n.','a way of doing something','方法','The teacher explained a practical <mark>method</mark>.']
  ],
  business: [
    ['agenda','/əˈdʒendə/','n.','a list of topics for a meeting','議程','Please read the <mark>agenda</mark> before the meeting.'],
    ['budget','/ˈbʌdʒɪt/','n.','a plan for spending money','預算','The team approved the annual <mark>budget</mark>.'],
    ['contract','/ˈkɒntrækt/','n.','a legal business agreement','合約','Both companies signed the <mark>contract</mark>.'],
    ['deadline','/ˈdedlaɪn/','n.','the latest time for completing work','截止日期','The report is due before the <mark>deadline</mark>.'],
    ['negotiate','/nɪˈɡəʊʃieɪt/','v.','to discuss in order to reach agreement','協商','The partners will <mark>negotiate</mark> the price.'],
    ['revenue','/ˈrevənjuː/','n.','income received by a business','營收','Online sales increased quarterly <mark>revenue</mark>.']
  ],
  academic: [
    ['allocate','/ˈæləkeɪt/','v.','to distribute resources for a purpose','分配','The council will <mark>allocate</mark> funds to research.'],
    ['assess','/əˈses/','v.','to judge or evaluate carefully','評估','Researchers <mark>assess</mark> the evidence before publishing.'],
    ['coherent','/kəʊˈhɪərənt/','adj.','logical, clear, and well organized','連貫的','Her argument was <mark>coherent</mark> and well supported.'],
    ['empirical','/ɪmˈpɪrɪkəl/','adj.','based on observation or experiment','實證的','The claim needs <mark>empirical</mark> evidence.'],
    ['hypothesis','/haɪˈpɒθəsɪs/','n.','an idea that can be tested','假設','The experiment tested a clear <mark>hypothesis</mark>.'],
    ['sustainable','/səˈsteɪnəbəl/','adj.','able to continue without causing harm','永續的','The city needs a <mark>sustainable</mark> transport plan.']
  ],
  advanced: [
    ['aberration','/ˌæbəˈreɪʃən/','n.','a departure from what is normal','反常現象','The result was treated as an <mark>aberration</mark>, not a trend.'],
    ['circumscribe','/ˈsɜːkəmskraɪb/','v.','to restrict within limits','限制','Strict rules may <mark>circumscribe</mark> academic inquiry.'],
    ['deleterious','/ˌdeləˈtɪəriəs/','adj.','causing harm or damage','有害的','The policy had a <mark>deleterious</mark> effect on trust.'],
    ['inchoate','/ɪnˈkəʊeɪt/','adj.','only partly formed or developed','初具雛形的','The proposal remained <mark>inchoate</mark> for months.'],
    ['perspicacious','/ˌpɜːspɪˈkeɪʃəs/','adj.','having keen insight and judgment','有洞見的','Her <mark>perspicacious</mark> analysis changed the discussion.'],
    ['trenchant','/ˈtrentʃənt/','adj.','clear, forceful, and effective','尖銳有力的','The essay offered a <mark>trenchant</mark> critique.']
  ]
};

let data = defaults();
let tab = 'dashboard';
let wordPane = 'learn';
let settings = { level: 'two', listenMode: 'practice', speed: 'normal' };

function today() { return new Date().toISOString().slice(0, 10); }
function escapeHtml(value = '') { return String(value).replace(/[&<>'"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;' }[c])); }
function day() {
  data.days ||= {};
  return data.days[today()] ||= { words: [], readingDone: false, listeningDone: false, wordDone: false, vocabDone: false, reviewDone: false };
}
function currentLevel() { return levels[settings.level] || levels.two; }
function loadSettings() { try { settings = { ...settings, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') }; } catch {} }
function saveSettings() { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); }
function lookupWord(term) {
  return Object.values(wordBank).flat().find(word => word[0] === term) || [term, '', '', '', '尚未提供中文釋義', ''];
}
function favorites() {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]').map(item => {
      const term = item.term || item.word;
      return { ...item, term, word: Array.isArray(item.word) ? item.word : lookupWord(term) };
    }).filter(item => item.term);
  } catch { return []; }
}
function saveFavorites(items) { localStorage.setItem(FAVORITES_KEY, JSON.stringify(items)); }
function api(path, body) {
  return fetch(path, { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
    .then(r => r.json().then(payload => r.ok ? payload : Promise.reject(new Error(payload.error || `HTTP ${r.status}`))));
}
async function save() { try { await api('/api/data', data); } catch { toast('本機伺服器暫時無法儲存資料。'); } }
function toast(message) { const el = $('#toast'); if (!el) return; el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 2200); }
function speak(text) {
  if (!('speechSynthesis' in window)) return toast('此瀏覽器不支援語音朗讀。');
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-US'; utterance.rate = currentLevel().rate;
  speechSynthesis.cancel(); speechSynthesis.speak(utterance);
}
function recordAnswer(ok, mistake) {
  const stats = data.stats ||= { answers: 0, correct: 0, study_dates: [] };
  stats.answers++; if (ok) stats.correct++;
  if (!stats.study_dates.includes(today())) stats.study_dates.push(today());
  if (!ok && mistake && !(data.mistakes || []).some(item => item.id === mistake.id)) (data.mistakes ||= []).push(mistake);
  data.pet ||= { mood: 65, food: 0, chat: [] };
  data.pet.mood = Math.max(0, Math.min(100, data.pet.mood + (ok ? 2 : -1)));
  save();
}

function difficultySelect() {
  return `<label class="difficulty">難度 <select class="globalLevel">${Object.entries(levels).map(([key, value]) => `<option value="${key}" ${settings.level === key ? 'selected' : ''}>${value.stars} ${value.label}</option>`).join('')}</select></label>`;
}
function dashboard() {
  const d = day(), done = ['readingDone','listeningDone','wordDone','vocabDone','reviewDone'].filter(key => d[key]).length;
  const stats = data.stats || {}, accuracy = stats.answers ? Math.round(stats.correct / stats.answers * 100) : 0;
  return `<section class="card hero"><div><p class="quote">Small steps, bright results.</p><h1>Bright English Dashboard</h1><p>今日完成度 ${done}/5 · 正確率 ${accuracy}% · 錯題 ${(data.mistakes || []).length} 題</p><div class="progress"><b style="width:${done * 20}%"></b></div></div><button class="dashPetButton" data-go="pet"><span class="dashFox">🦊</span><span>Foxy</span></button></section>
  <section class="card"><h2>快速入口</h2><div class="quickLinks"><button data-go="reading">閱讀</button><button data-go="listening">聽力</button><button data-go="words">單字</button><button id="exportMarkdown">匯出 Markdown</button></div></section>`;
}

function reading() {
  const d = day(), articles = d.rssArticles || [];
  if (!articles.length && !d.rssLoading) setTimeout(loadRss, 0);
  if (!articles.length) return `<section class="card"><div class="row"><h2 class="grow">今日閱讀</h2>${difficultySelect()}</div><p>正在載入 RSS 新聞來源與本機文章池…</p></section>`;
  const index = d.readIndex || 0, article = articles[index], key = `reading-${settings.level}-${article.id}`, result = d[key];
  if (!result && !d.readingLoading) setTimeout(() => generateReading(article, key), 0);
  return `<section class="card"><div class="row"><h2 class="grow">今日閱讀 ${index + 1}/${articles.length}</h2>${difficultySelect()}</div><span class="tag">${escapeHtml(article.source)}</span><h3>${escapeHtml(article.title)}</h3><p class="small">${escapeHtml(article.published || '')}</p><p class="passage">${escapeHtml(article.en)}</p><p class="translation">${escapeHtml(article.zh || '尚未提供中文摘要。')}</p><div class="row"><button id="readSpeak">朗讀摘要</button><button id="nextArticle">下一篇</button>${article.link ? `<a class="sourceLink" href="${escapeHtml(article.link)}" target="_blank" rel="noopener">原文連結 ↗</a>` : ''}</div></section>
  <section class="card"><h2>閱讀測驗</h2>${d.readingLoading === key ? '<p>正在生成並驗證長文與題組…</p>' : ''}${result ? readingResult(result) : '<p class="small">材料準備中；若沒有 AI key，會顯示原因而不會重複出題。</p>'}</section>`;
}
function readingResult(result) {
  if (result.error) return `<p class="feedback qualityWarn">未能產生測驗：${escapeHtml(result.error)}</p>`;
  return `<p class="small">${result.validation?.word_count || 0} 詞 · ${currentLevel().stars}</p><p class="passage">${escapeHtml(result.en)}</p><details><summary>中文翻譯</summary><p class="translation">${escapeHtml(result.zh)}</p></details>${questionCards(result.questions, 'reading')}`;
}
async function loadRss() {
  const d = day(); d.rssLoading = true; render();
  try {
    const history = (await api('/api/history')).questions || [];
    const response = await api('/api/rss', { seen: history });
    d.rssArticles = (response.articles || []).slice(0, 3);
    if (!d.rssArticles.length) throw new Error('暫無可用 RSS 文章');
  } catch (error) { d.rssError = error.message; d.rssArticles = []; }
  d.rssLoading = false; await save(); render();
}
async function generateReading(article, key) {
  const d = day(); d.readingLoading = key; render();
  try { d[key] = (await api('/api/longread', { article, difficulty: settings.level })).result; }
  catch (error) { d[key] = { error: error.message }; }
  d.readingLoading = ''; await save(); render();
}

function listening() {
  const d = day(), key = `listening-${settings.level}`, item = d[key];
  if (!item && !d.listeningLoading) setTimeout(() => generateListening(key), 0);
  return `<section class="card"><div class="row"><h2 class="grow">聽力測驗</h2>${difficultySelect()}</div>${d.listeningLoading ? '<p>正在生成並驗證聽力材料…</p>' : ''}${!item ? '<p>材料準備中。</p>' : item.error ? `<p class="feedback qualityWarn">${escapeHtml(item.error)}</p>` : `<p class="small">${item.validation?.word_count || 0} 詞 · ${currentLevel().stars}</p><button id="listenSpeak">播放英文</button><p class="passage">${escapeHtml(item.text)}</p>${questionCards(item.questions, 'listening')}</section>`}`;
}
async function generateListening(key) {
  const d = day(); d.listeningLoading = true; render();
  try { d[key] = (await api('/api/listening', { difficulty: settings.level })).result; }
  catch (error) { d[key] = { error: error.message }; }
  d.listeningLoading = false; await save(); render();
}
function questionCards(questions = [], type) {
  return questions.map((question, index) => `<div class="aiQuestion"><h3>${index + 1}. ${escapeHtml(question.stem)}</h3>${(question.o || []).map((option, optionIndex) => `<button class="option answer" data-type="${type}" data-question="${index}" data-ok="${optionIndex === question.ans}" data-stem="${escapeHtml(question.stem)}" data-answer="${escapeHtml(question.o?.[question.ans] || '')}">${'ABCD'[optionIndex]}. ${escapeHtml(option)}</button>`).join('')}<div class="feedback" hidden>${escapeHtml(question.why || '')}</div></div>`).join('');
}

function ensureWords() {
  const d = day(), pool = wordBank[currentLevel().pool];
  if (!Array.isArray(d.words) || !d.words.length || d.wordLevel !== settings.level) {
    d.words = [...pool].sort(() => Math.random() - 0.5).slice(0, 6); d.wordLevel = settings.level;
    for (const word of d.words) if (!(data.learned_words || []).includes(word[0])) (data.learned_words ||= []).push(word[0]);
    save();
  }
  return d.words;
}
function wordCard(word) {
  const [term, ipa, pos, en, zh, example] = word;
  const saved = favorites().some(item => item.term === term);
  return `<article class="word wordCard"><button class="favorite ${saved ? 'saved' : ''}" data-favorite="${escapeHtml(term)}" title="收藏">★</button><h3>${escapeHtml(term)}</h3><span class="ipa">${escapeHtml(ipa)}</span><button class="wordSpeak" data-word="${escapeHtml(term)}">🔊</button><p><b>${escapeHtml(pos)}</b> · ${escapeHtml(en)}<br><b>中文：</b>${escapeHtml(zh)}</p><p>${example}</p></article>`;
}
function words() {
  const current = ensureWords(), saved = favorites();
  const body = wordPane === 'learn' ? `<div class="wordGrid">${current.map(wordCard).join('')}</div><button id="finishWords">完成今日單字</button>`
    : wordPane === 'quiz' ? vocabularyQuiz(current)
    : wordPane === 'favorites' ? `<div class="wordGrid">${saved.length ? saved.map(item => wordCard(item.word)).join('') : '<p>尚未收藏單字。</p>'}</div>`
    : favoriteReview(saved);
  return `<section class="card wordShell"><div class="row"><h2 class="grow">單字</h2>${difficultySelect()}</div><div class="subtabs">${[['learn','今日單字'],['quiz','單字測驗'],['favorites',`我的收藏 (${saved.length})`],['review','收藏複習']].map(([id,label]) => `<button data-pane="${id}" class="${wordPane === id ? 'active' : ''}">${label}</button>`).join('')}</div><div class="wordContent">${body}</div></section>`;
}
function vocabularyQuiz(current) {
  const word = current[0], distractors = current.slice(1, 4).map(item => item[4]);
  const options = [word[4], ...distractors].sort(() => Math.random() - 0.5);
  return `<article class="word"><h3>「${escapeHtml(word[0])}」最適合的中文意思是？</h3>${options.map(option => `<button class="option vocabAnswer" data-ok="${option === word[4]}" data-term="${escapeHtml(word[0])}" data-answer="${escapeHtml(word[4])}">${escapeHtml(option)}</button>`).join('')}<div class="feedback" hidden>${escapeHtml(word[1])} · ${escapeHtml(word[2])}<br>${word[5]}</div></article>`;
}
function favoriteReview(saved) {
  if (!saved.length) return '<p>先在今日單字中收藏至少一個單字。</p>';
  const item = saved[0], other = saved.slice(1, 4).map(x => x.term), options = [item.term, ...other].sort(() => Math.random() - 0.5);
  return `<article class="word"><h3>Which word means「${escapeHtml(item.word[4])}」?</h3>${options.map(option => `<button class="option vocabAnswer" data-ok="${option === item.term}" data-term="${escapeHtml(item.term)}" data-answer="${escapeHtml(item.term)}">${escapeHtml(option)}</button>`).join('')}<div class="feedback" hidden>${escapeHtml(item.word[5])}</div></article>`;
}
function addFavorite(term) {
  const word = ensureWords().find(item => item[0] === term) || favorites().find(item => item.term === term)?.word;
  if (!word) return; const list = favorites().filter(item => item.term !== term);
  list.push({ term, word, category: '待複習', date: today() }); saveFavorites(list); toast(`已收藏 ${term}`); render();
}

function petPage() {
  const pet = data.pet || { mood: 65, food: 0 };
  return `<section class="card petPage"><div id="petStageFox" class="petStage" role="button" tabindex="0"><svg class="foxSvg" viewBox="0 0 300 340" aria-label="Foxy"><g class="foxTailSvg"><path d="M222 245c62-20 68 44 20 57-30 9-53-7-69-27 22 4 36-9 49-30z" fill="#e9874d" stroke="#9d4d32" stroke-width="7"/><path d="M238 272c21-6 29 12 9 18-14 4-27-1-36-9 12 1 20-2 27-9z" fill="#fff4df"/></g><g class="foxBodySvg"><path d="M91 165c-21 34-17 112 18 135 22 15 61 15 83 0 35-23 39-101 17-135z" fill="#e9874d" stroke="#9d4d32" stroke-width="7"/><path d="M117 193c4 53 14 83 33 89 19-6 29-36 33-89-19 9-46 9-66 0z" fill="#fff4df"/></g><g><path d="M81 119 73 38l57 42c13-5 28-5 41 0l56-42-8 81c9 16 11 43 3 62-12 29-52 48-102 42-39-5-65-30-66-61-1-17 3-31 8-43z" fill="#e9874d" stroke="#9d4d32" stroke-width="7"/><ellipse class="foxEye leftEye" cx="116" cy="137" rx="8" ry="11" fill="#263451"/><ellipse class="foxEye rightEye" cx="184" cy="137" rx="8" ry="11" fill="#263451"/><path d="m145 154 10 0-5 6z" fill="#263451"/></g></svg><p id="stagePetSpeech" class="stagePetSpeech">今天的一小題，也算進步。</p></div></section><section class="card petInfo"><h2>Foxy 的狀態</h2><p>心情：${pet.mood || 65}/100 · 飼料：${pet.food || 0}</p><button id="openPetChat">和 Foxy 聊聊天</button></section>`;
}
async function sendChat() {
  const input = $('#chatText'), text = input?.value.trim(); if (!text) return;
  const pet = data.pet ||= { mood: 65, food: 0, chat: [] }; pet.chat ||= [];
  pet.chat.push({ role: 'user', content: text }); input.value = ''; renderChat();
  const messages = [{ role: 'system', content: 'You are Foxy, a kind and witty English-learning fox. Reply briefly in Traditional Chinese and include English examples when helpful.' }, ...pet.chat.slice(-10)];
  try { const response = await api('/api/chat', { messages }); pet.chat.push({ role: 'assistant', content: response.reply }); }
  catch { pet.chat.push({ role: 'assistant', content: '我現在連不上 AI，但我們可以先從一個單字或一句英文開始。' }); }
  await save(); renderChat();
}
function renderChat() { const log = $('#chatLog'); if (!log) return; const messages = data.pet?.chat || []; log.innerHTML = messages.map(m => `<p class="${m.role}"><b>${m.role === 'user' ? '你' : 'Foxy'}：</b>${escapeHtml(m.content)}</p>`).join('') || '<p class="assistant">Foxy：今天想練什麼？</p>'; log.scrollTop = log.scrollHeight; }
function exportMarkdown() {
  const mistakes = data.mistakes || [], words = [...new Set(data.learned_words || [])];
  const text = `# Bright English 匯出\n\n## 待複習錯題\n${mistakes.map(m => `- [ ] ${m.q || m.stem || ''}\n  - 答案：${m.answer || ''}`).join('\n') || '無'}\n\n## 已學單字\n${words.map(w => `- [ ] ${w}`).join('\n') || '無'}\n`;
  const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([text], { type: 'text/markdown' })); link.download = `Bright-English-${today()}.md`; link.click(); URL.revokeObjectURL(link.href);
}
function render() {
  const views = { dashboard, reading, listening, words, pet: petPage };
  try { app.innerHTML = (views[tab] || dashboard)(); }
  catch (error) { console.error(error); app.innerHTML = '<section class="card"><h2>載入發生問題</h2><p>本機資料已保留；請重新整理後再試。</p></section>'; }
  document.querySelectorAll('[data-tab]').forEach(button => button.classList.toggle('active', button.dataset.tab === tab)); bind();
}
function bind() {
  document.querySelectorAll('[data-tab],[data-go]').forEach(button => button.onclick = () => { tab = button.dataset.tab || button.dataset.go; render(); });
  $('#brandHome')?.addEventListener('click', () => { tab = 'dashboard'; render(); });
  document.querySelectorAll('.globalLevel').forEach(select => select.onchange = () => { settings.level = select.value; saveSettings(); render(); });
  $('#readSpeak')?.addEventListener('click', () => speak(day().rssArticles?.[day().readIndex || 0]?.en || ''));
  $('#nextArticle')?.addEventListener('click', () => { const d = day(); d.readIndex = ((d.readIndex || 0) + 1) % d.rssArticles.length; save(); render(); });
  $('#listenSpeak')?.addEventListener('click', () => speak(day()[`listening-${settings.level}`]?.text || ''));
  document.querySelectorAll('.wordSpeak').forEach(button => button.onclick = () => speak(button.dataset.word));
  document.querySelectorAll('[data-favorite]').forEach(button => button.onclick = () => addFavorite(button.dataset.favorite));
  document.querySelectorAll('[data-pane]').forEach(button => button.onclick = () => { wordPane = button.dataset.pane; render(); });
  $('#finishWords')?.addEventListener('click', () => { day().wordDone = true; save(); toast('今日單字已完成。'); });
  $('#exportMarkdown')?.addEventListener('click', exportMarkdown);
  document.querySelectorAll('.answer,.vocabAnswer').forEach(button => button.onclick = () => {
    const card = button.parentElement; if (card.dataset.done) return; card.dataset.done = '1'; const ok = button.dataset.ok === 'true';
    button.classList.add(ok ? 'right' : 'wrong'); const feedback = $('.feedback', card); if (feedback) feedback.hidden = false;
    recordAnswer(ok, ok ? null : { id: `${button.dataset.type || 'vocab'}-${Date.now()}`, q: button.dataset.stem || button.dataset.term, answer: button.dataset.answer, hits: 0 });
  });
  const pet = $('#petStageFox'); if (pet) pet.onclick = () => { pet.classList.remove('petCelebrate'); void pet.offsetWidth; pet.classList.add('petCelebrate'); $('#stagePetSpeech').textContent = '你做得很好，繼續前進！'; };
  $('#openPetChat')?.addEventListener('click', () => { $('#chat').hidden = false; renderChat(); });
  $('#pet')?.addEventListener('click', () => { $('#chat').hidden = false; renderChat(); });
  $('#closeChat')?.addEventListener('click', () => $('#chat').hidden = true);
  $('#sendChat')?.addEventListener('click', sendChat);
  $('#chatText')?.addEventListener('keydown', event => { if (event.key === 'Enter') sendChat(); });
}
async function init() { loadSettings(); try { data = await api('/api/data'); } catch { data = defaults(); toast('本機伺服器未連線，使用暫存資料。'); } render(); }
init();
