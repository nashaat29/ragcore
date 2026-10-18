const API_BASE = '';
const STORAGE_KEY = 'ragcore_chat';

let messages = [];

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const parent = tab.closest('.card-body');
    parent.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    parent.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  });
});

function show(el) { document.getElementById(el).classList.remove('hidden'); }
function hide(el) { document.getElementById(el).classList.add('hidden'); }
function html(el, content) { document.getElementById(el).innerHTML = content; }
function text(el, content) { document.getElementById(el).textContent = content; }
function val(el) { return document.getElementById(el).value; }
function setVal(el, v) { document.getElementById(el).value = v; }

function escapeHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showToast(type, message, duration = 4000) {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function renderMarkdown(text) {
  if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
    return '<p>' + escapeHtml(text).replace(/\n/g, '<br>') + '</p>';
  }
  const html = marked.parse(text, { breaks: true, gfm: true });
  const clean = DOMPurify.sanitize(html);
  const div = document.createElement('div');
  div.innerHTML = clean;
  div.querySelectorAll('a').forEach(a => {
    if (!a.getAttribute('target')) {
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
    }
  });
  return div.innerHTML;
}

function formatTime(seconds) {
  if (seconds == null) return '';
  if (seconds < 0.01) return (seconds * 1000).toFixed(1) + 'ms';
  return seconds.toFixed(2) + 's';
}

function formatTimestamp(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function animateCounter(elId, target, opts = {}) {
  const el = document.getElementById(elId);
  if (!el) return;
  const { isPercentage = false, emptyHint = null, duration = 800 } = opts;

  const rawText = el.textContent.replace(/[^0-9.-]/g, '');
  const current = parseInt(rawText) || 0;
  const diff = target - current;

  const subEl = document.getElementById(elId + 'Sub');

  if (target === 0 && current === 0 && emptyHint) {
    if (diff === 0) {
      el.textContent = '0' + (isPercentage ? '%' : '');
      el.classList.add('stat-empty');
      if (subEl) {
        subEl.textContent = emptyHint;
        subEl.classList.add('stat-sub-empty');
      }
      return;
    }
  }

  if (target > 0) {
    el.classList.remove('stat-empty');
    if (subEl) subEl.classList.remove('stat-sub-empty');
  }

  if (diff === 0 && target !== 0) {
    el.textContent = target + (isPercentage ? '%' : '');
    const card = el.closest('.stat-card') || el.closest('.metric-card');
    if (card) { card.classList.remove('pulse'); void card.offsetWidth; card.classList.add('pulse'); }
    return;
  }

  if (diff === 0) return;

  const startTime = performance.now();
  const startValue = current;

  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
    const value = Math.round(startValue + diff * eased);
    el.textContent = value + (isPercentage ? '%' : '');

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      el.textContent = target + (isPercentage ? '%' : '');
      const card = el.closest('.stat-card') || el.closest('.metric-card');
      if (card && target > 0) { card.classList.remove('pulse'); void card.offsetWidth; card.classList.add('pulse'); }
    }
  }

  requestAnimationFrame(step);
}

function scrollToBottom() {
  const container = document.getElementById('chatMessages');
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });
}

function saveMessages() {
  try {
    const clean = messages.filter(m => !m.streaming).map(m => ({
      role: m.role, content: m.content, timestamp: m.timestamp,
      meta: m.meta, sources: m.sources,
    }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
  } catch (e) {}
}

function loadMessages() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (data) return JSON.parse(data);
  } catch (e) {}
  return [];
}

function clearChat() {
  if (messages.length === 0) return;
  messages = [];
  localStorage.removeItem(STORAGE_KEY);
  renderChat();
  showEmptyState();
  showToast('info', 'Conversation cleared');
}

function hideEmptyState() {
  const empty = document.getElementById('chatEmpty');
  if (empty) empty.style.display = 'none';
}

function showEmptyState() {
  if (messages.length === 0) {
    const empty = document.getElementById('chatEmpty');
    if (empty) empty.style.display = 'flex';
  }
}

function copyToClipboard(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(
      () => showToast('success', 'Copied to clipboard'),
      () => fallbackCopy(text)
    );
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast('success', 'Copied to clipboard');
  } catch (e) {
    showToast('error', 'Copy failed');
  }
  document.body.removeChild(ta);
}

function addMessage(role, content, metaStr = '', sources = null) {
  messages.push({ role, content, meta: metaStr, sources, timestamp: Date.now() });
  hideEmptyState();
  renderChat();
  scrollToBottom();
  saveMessages();
}

function renderChat() {
  const container = document.getElementById('chatMessages');
  let html = '';
  for (const msg of messages) {
    if (msg.role === 'user') {
      html += `<div class="message message-user">
        <div class="message-avatar">U</div>
        <div class="message-bubble">
          <div class="message-text">${escapeHtml(msg.content)}</div>
          <div class="message-meta">${formatTimestamp(msg.timestamp)}</div>
        </div>
      </div>`;
    } else if (msg.role === 'thinking') {
      continue;
    } else {
      const rendered = renderMarkdown(msg.content);
      const metaHtml = msg.meta ? `<div class="message-meta">${msg.meta}</div>` : '';
      const sourcesHtml = msg.sources ? `<div class="message-sources"><details><summary>Sources (${msg.sources.count})</summary>${msg.sources.html}</details></div>` : '';
      html += `<div class="message message-assistant">
        <div class="message-avatar">R</div>
        <div class="message-bubble">
          <div class="message-text markdown-body">${rendered}</div>
          <div class="message-actions">
            <button class="btn-copy" onclick="copyToClipboard(decodeURIComponent('${encodeURIComponent(msg.content)}'))" title="Copy to clipboard">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
          </div>
          ${metaHtml}
          ${sourcesHtml}
        </div>
      </div>`;
    }
  }
  container.innerHTML = html;
}

function showThinking() {
  hideEmptyState();
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'message message-assistant';
  div.id = 'thinkingMessage';
  div.innerHTML = `<div class="message-avatar">R</div>
    <div class="message-bubble">
      <div class="thinking-indicator">
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
      </div>
    </div>`;
  container.appendChild(div);
  scrollToBottom();
}

function hideThinking() {
  const el = document.getElementById('thinkingMessage');
  if (el) el.remove();
}

async function fetchStats() {
  try {
    const res = await fetch(`${API_BASE}/manage/index/stats`);
    const data = await res.json();
    const vstore = data.vectorstore || {};

    animateCounter('statChunks', vstore.total_vectors ?? 0, {
      emptyHint: 'no documents ingested yet'
    });
    const sparkChunks = document.getElementById('sparkChunks');
    if (sparkChunks) sparkChunks.style.width = Math.min((vstore.total_vectors ?? 0) / 100, 1) * 100 + '%';

    animateCounter('statIndexes', (data.available_indexes || []).length, {
      emptyHint: 'no saved indexes'
    });
    const sparkIdx = document.getElementById('sparkIndexes');
    if (sparkIdx) sparkIdx.style.width = Math.min((data.available_indexes || []).length * 25, 100) + '%';

    html('activeIndex', data.active_index || 'default');

    const strategy = data.retrieval_strategy || 'simple';
    html('queryStrategy', strategy);
    const sel = document.getElementById('strategySelect');
    if (sel) sel.value = strategy;

    const metricsRes = await fetch(`${API_BASE}/monitoring/stats`);
    const metrics = await metricsRes.json();
    const counters = metrics.counters || {};

    animateCounter('statQueries', counters.queries_total || 0, {
      emptyHint: 'no queries yet'
    });
    const sparkQ = document.getElementById('sparkQueries');
    if (sparkQ) sparkQ.style.width = Math.min((counters.queries_total || 0) / 100, 1) * 100 + '%';

    const qSub = document.getElementById('statQueriesSub');
    qSub.textContent = `${counters.queries_total || 0} queries, ${counters.ingestions_total || 0} ingestions`;
    if ((counters.queries_total || 0) === 0) {
      qSub.classList.add('stat-sub-empty');
    } else {
      qSub.classList.remove('stat-sub-empty');
    }

    const hits = counters.cache_hits || 0;
    const misses = counters.cache_misses || 0;
    const total = hits + misses;
    const rate = total > 0 ? Math.round((hits / total) * 100) : 0;

    animateCounter('statCache', rate, {
      isPercentage: true,
      emptyHint: 'no cache data yet'
    });
    const sparkC = document.getElementById('sparkCache');
    if (sparkC) sparkC.style.width = rate + '%';

    const cSub = document.getElementById('statCacheSub');
    cSub.textContent = `${hits} hits, ${misses} misses`;
    if (total === 0) {
      cSub.classList.add('stat-sub-empty');
    } else {
      cSub.classList.remove('stat-sub-empty');
    }

    return { counters };
  } catch (e) {
    console.error('Stats fetch failed:', e);
  }
}

async function fetchModelInfo() {
  try {
    const res = await fetch(`${API_BASE}/manage/config`);
    const config = await res.json();
    html('queryModel', config.llm_model || '');
  } catch (e) {}
}

fetchStats();
fetchModelInfo();
setInterval(fetchStats, 5000);

async function ingestText() {
  const text = val('ingestText').trim();
  if (!text) return showToast('warning', 'Please enter text to ingest.');

  let metadata = {};
  try {
    const metaStr = val('ingestTextMeta').trim();
    if (metaStr) metadata = JSON.parse(metaStr);
  } catch { return showToast('error', 'Invalid JSON metadata'); }

  const btn = document.querySelector('#tabText .btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Ingesting...';
  html('ingestStatus', 'Ingesting...');
  document.getElementById('ingestStatus').className = 'tag tag-yellow';

  try {
    const res = await fetch(`${API_BASE}/ingest/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, metadata })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ingestion failed');
    showToast('success', `✓ ${data.chunk_count} chunks ingested`);
    document.getElementById('ingestStatus').className = 'tag tag-green';
    html('ingestStatus', `${data.chunk_count} chunks`);
    fetchStats();
  } catch (e) {
    showToast('error', '✗ ' + e.message);
    document.getElementById('ingestStatus').className = 'tag tag-green';
    html('ingestStatus', 'Ready');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Ingest Text';
  }
}

async function ingestFile(input) {
  const file = input.files[0];
  if (!file) return;

  const info = document.getElementById('fileInfo');
  info.innerHTML = `<div class="alert alert-info">Uploading <strong>${file.name}</strong>...</div>`;
  show('fileInfo');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/ingest/file`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');
    info.innerHTML = `<div class="alert alert-success">✓ ${data.chunk_count} chunks from ${file.name}</div>`;
    document.getElementById('ingestStatus').className = 'tag tag-green';
    html('ingestStatus', `${data.chunk_count} chunks`);
    fetchStats();
  } catch (e) {
    info.innerHTML = `<div class="alert alert-error">✗ ${e.message}</div>`;
  }
}

async function ingestDirectory() {
  const path = val('ingestDir').trim();
  if (!path) return showToast('warning', 'Enter a directory path.');

  const recursive = document.getElementById('ingestRecursive').checked;
  const btn = document.querySelector('#tabDir .btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Ingesting...';

  try {
    const res = await fetch(`${API_BASE}/ingest/directory?path=${encodeURIComponent(path)}&recursive=${recursive}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    showToast('success', `✓ ${data.chunk_count} chunks ingested from directory`);
    fetchStats();
  } catch (e) {
    showToast('error', '✗ ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Ingest Directory';
  }
}

function renderSources(sources) {
  if (!sources || sources.length === 0) return '';
  let html = '';
  sources.forEach((s, i) => {
    const meta = Object.entries(s.metadata || {}).map(([k, v]) => `${k}: ${v}`).join(', ');
    const safeText = escapeHtml(s.text);
    html += `<div class="source-item">
      <div class="source-meta">
        <span>#${i + 1}</span>
        <span>Score: ${(s.score || 0).toFixed(3)}</span>
      </div>
      <div>${safeText}</div>
      ${meta ? `<div class="text-xs text-muted" style="margin-top:4px;">${escapeHtml(meta)}</div>` : ''}
    </div>`;
  });
  return html;
}

async function runQuery() {
  const question = val('queryInput').trim();
  if (!question) return;

  const k = parseInt(val('queryK')) || 4;

  addMessage('user', question);

  setVal('queryInput', '');
  autoResize(document.getElementById('queryInput'));

  const btn = document.getElementById('queryBtn');
  btn.disabled = true;

  showThinking();

  try {
    const msgEl = document.createElement('div');
    msgEl.className = 'message message-assistant';
    msgEl.id = 'streamingMsg';
    msgEl.innerHTML = `<div class="message-avatar">R</div>
      <div class="message-bubble">
        <div class="message-text" id="streamingText"></div>
      </div>`;
    document.getElementById('chatMessages').appendChild(msgEl);
    hideThinking();
    scrollToBottom();

    const res = await fetch(`${API_BASE}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, k })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Query failed');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let answer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;

        try {
          const data = JSON.parse(trimmed.slice(6));

          if (data.token) {
            answer += data.token;
            const stEl = document.getElementById('streamingText');
            if (stEl) stEl.textContent = answer;
            scrollToBottom();
          } else if (data.event === 'blocked') {
            const sEl = document.getElementById('streamingMsg');
            if (sEl) sEl.remove();
            addMessage('assistant', '**Blocked by safety guardrails.** This request was stopped before an answer was produced.');
            showToast('error', 'Blocked by safety guardrails');
          } else if (data.event === 'done') {
            const result = data.result || {};

            const sEl = document.getElementById('streamingMsg');
            if (sEl) sEl.remove();

            const metaStr = `${result.total_chunks || 0} chunks · ${formatTime(result.elapsed)}${result.cached ? ' · <span class="tag tag-green">cached</span>' : ''}`;
            const sourcesHtml = renderSources(result.sources);

            addMessage('assistant', answer, metaStr, sourcesHtml ? { html: sourcesHtml, count: (result.sources || []).length } : null);

            fetchStats();
          }
        } catch (e) {
          console.error('SSE parse error:', e);
        }
      }
    }
  } catch (e) {
    hideThinking();
    const sEl = document.getElementById('streamingMsg');
    if (sEl) sEl.remove();
    addMessage('assistant', '**Error:** ' + e.message);
    showToast('error', e.message);
  } finally {
    btn.disabled = false;
  }
}

async function retrieveOnly() {
  const question = val('queryInput').trim();
  if (!question) return;

  const k = parseInt(val('queryK')) || 4;

  addMessage('user', question + ' _(retrieve only)_');

  showThinking();

  try {
    const res = await fetch(`${API_BASE}/query/retrieve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, k })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');

    hideThinking();

    const header = `Retrieved ${data.total} chunks using "${data.retrieval_strategy}" strategy.`;
    const itemsHtml = data.results ? data.results.map((r, i) => {
      const safeText = escapeHtml(r.text);
      return `<div class="source-item">
        <div class="source-meta">
          <span>#${i + 1}</span>
          <span>Score: ${(r.score || 0).toFixed(3)}</span>
        </div>
        <div>${safeText}</div>
      </div>`;
    }).join('') : '';

    addMessage('assistant', header, '', data.results && data.results.length ? {
      html: itemsHtml,
      count: data.results.length
    } : null);
  } catch (e) {
    hideThinking();
    addMessage('assistant', '**Error:** ' + e.message);
    showToast('error', e.message);
  }
}

async function saveIndex() {
  const name = val('indexName').trim() || null;
  try {
    const res = await fetch(`${API_BASE}/manage/index/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    showToast('success', '✓ Index saved');
    fetchStats();
  } catch (e) {
    showToast('error', '✗ ' + e.message);
  }
}

async function loadIndex() {
  const name = val('indexName').trim();
  if (!name) return showToast('warning', 'Enter an index name to load.');
  await doLoadIndex(name);
}

async function loadIndexByName(name) {
  await doLoadIndex(name);
}

async function doLoadIndex(name) {
  try {
    const res = await fetch(`${API_BASE}/manage/index/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    showToast('success', `✓ Index "${name}" loaded`);
    fetchStats();
    listIndexes();
  } catch (e) {
    showToast('error', '✗ ' + e.message);
  }
}

async function deleteIndex(name) {
  if (!confirm(`Are you sure you want to delete the index "${name}"? This cannot be undone.`)) return;

  try {
    const res = await fetch(`${API_BASE}/manage/index/${encodeURIComponent(name)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Delete failed');
    showToast('success', `✓ Index "${name}" deleted`);
    fetchStats();
    listIndexes();
  } catch (e) {
    showToast('error', '✗ ' + e.message);
  }
}

async function listIndexes() {
  try {
    const res = await fetch(`${API_BASE}/manage/index/list`);
    const indexes = await res.json();
    if (!res.ok) throw new Error('Failed to fetch indexes');

    if (!indexes || indexes.length === 0) {
      html('indexList', '<tr><td colspan="4" style="text-align:center;color:var(--gray-400);padding:20px;">No saved indexes yet.</td></tr>');
      return;
    }

    let htmlStr = '';
    indexes.forEach(idx => {
      const sizeStr = idx.size_bytes ? (idx.size_bytes / 1024).toFixed(1) + ' KB' : '-';
      const activeTag = idx.active ? '<span class="status-pill pill-success" style="margin-left:4px;">active</span>' : '';
      htmlStr += `<tr>
        <td><strong style="font-size:13px;">${escapeHtml(idx.name)}</strong>${activeTag}</td>
        <td class="val-mono">${(idx.vector_count || 0).toLocaleString()}</td>
        <td class="val-mono" style="font-size:11px;color:var(--gray-500);">${sizeStr}</td>
        <td>
          <div class="flex gap-1">
            <button class="btn btn-secondary btn-sm" onclick="loadIndexByName('${escapeHtml(idx.name)}')" style="padding:2px 8px;font-size:11px;">Load</button>
            <button class="btn btn-secondary btn-sm" onclick="deleteIndex('${escapeHtml(idx.name)}')" style="padding:2px 8px;font-size:11px;color:var(--error);border-color:var(--red-200);">Delete</button>
          </div>
        </td>
      </tr>`;
    });
    html('indexList', htmlStr);
  } catch (e) {
    html('indexList', `<tr><td colspan="4" style="color:var(--error);padding:12px;">${e.message}</td></tr>`);
  }
}

async function changeStrategy(strategy) {
  try {
    const res = await fetch(`${API_BASE}/manage/retrieval/strategy?strategy=${strategy}`, { method: 'POST' });
    if (res.ok) {
      html('queryStrategy', strategy);
      showToast('info', `Strategy changed to ${strategy}`);
    }
  } catch (e) {
    console.error('Strategy change failed:', e);
  }
}

function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

const queryInput = document.getElementById('queryInput');
queryInput.addEventListener('input', () => autoResize(queryInput));

queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    runQuery();
  }
});

messages = loadMessages();
if (messages.length > 0) {
  renderChat();
  showEmptyState();
}

listIndexes();
