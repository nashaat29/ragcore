const API_BASE = '';
let logStreamPaused = false;
let logEventSource = null;
let _uptimeRef = null;
function html(el, content) { document.getElementById(el).innerHTML = content; }
function val(el) { return document.getElementById(el).value; }

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatTime(seconds) {
  if (seconds == null || seconds < 0) return '-';
  if (seconds < 0.001) return (seconds * 1000).toFixed(2) + 'ms';
  if (seconds < 1) return (seconds * 1000).toFixed(0) + 'ms';
  return seconds.toFixed(2) + 's';
}

function animateCounter(elId, target, opts = {}) {
  const el = document.getElementById(elId);
  if (!el) return;
  const { isPercentage = false, emptyHint = null, duration = 800 } = opts;

  const rawText = el.textContent.replace(/[^0-9.-]/g, '');
  const current = parseInt(rawText) || 0;
  const diff = target - current;

  const card = el.closest('.metric-card');

  if (target === 0 && current === 0 && emptyHint) {
    el.textContent = '0' + (isPercentage ? '%' : '');
    el.style.color = '#d1d5db';
    if (card) card.classList.add('metric-empty');
    return;
  }

  if (target > 0 && card) {
    card.classList.remove('metric-empty');
    el.style.color = '';
  }

  if (diff === 0 && target !== 0) {
    el.textContent = target + (isPercentage ? '%' : '');
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
      if (card && target > 0) { card.classList.remove('pulse'); void card.offsetWidth; card.classList.add('pulse'); }
    }
  }

  requestAnimationFrame(step);
}

function latencyColor(seconds) {
  if (seconds == null) return 'dot-gray';
  if (seconds < 1) return 'dot-green';
  if (seconds < 5) return 'dot-yellow';
  return 'dot-red';
}

function setLatencyDot(elId, seconds) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.className = 'metric-dot ' + latencyColor(seconds);
}

async function fetchMetrics() {
  try {
    const res = await fetch(`${API_BASE}/monitoring/stats`);
    const data = await res.json();

    const counters = data.counters || {};
    const timings = data.timings || {};
    const pipeline = data.pipeline || {};

    animateCounter('cntQueries', counters.queries_total || 0, { emptyHint: 'no queries yet' });
    document.getElementById('sparkQueries')?.style.setProperty('width', Math.min((counters.queries_total || 0) / 100, 1) * 100 + '%');

    animateCounter('cntIngestion', counters.ingestions_total || 0, { emptyHint: 'no ingestions yet' });
    document.getElementById('sparkIngestion')?.style.setProperty('width', Math.min((counters.ingestions_total || 0) / 50, 1) * 100 + '%');

    animateCounter('cntCacheHits', counters.cache_hits || 0, { emptyHint: 'no cache hits' });
    document.getElementById('sparkHits')?.style.setProperty('width', Math.min((counters.cache_hits || 0) / 100, 1) * 100 + '%');

    animateCounter('cntCacheMisses', counters.cache_misses || 0, { emptyHint: 'no cache misses' });
    document.getElementById('sparkMisses')?.style.setProperty('width', Math.min((counters.cache_misses || 0) / 50, 1) * 100 + '%');

    animateCounter('cntErrors', counters.errors_total || 0, { emptyHint: 'no errors' });
    document.getElementById('sparkErrors')?.style.setProperty('width', Math.min((counters.errors_total || 0) / 20, 1) * 100 + '%');

    const hits = counters.cache_hits || 0;
    const misses = counters.cache_misses || 0;
    const total = hits + misses;
    const rate = total > 0 ? Math.round((hits / total) * 100) : 0;
    animateCounter('cntHitRate', rate, { isPercentage: true, emptyHint: 'no data yet' });
    document.getElementById('sparkHitRate')?.style.setProperty('width', rate + '%');

    const uptime = data.uptime_seconds;
    if (uptime != null) {
      _uptimeRef = { serverUptime: uptime, clientTime: Date.now() };
    }

    const qt = timings.query_latency;
    if (qt && qt.count > 0) {
      const latencies = [
        { id: 'latAvg', dotId: 'dotAvg', value: qt.avg },
        { id: 'latP50', dotId: 'dotP50', value: qt.p50 },
        { id: 'latP95', dotId: 'dotP95', value: qt.p95 },
        { id: 'latP99', dotId: 'dotP99', value: qt.p99 },
        { id: 'latMin', dotId: 'dotMin', value: qt.min },
        { id: 'latMax', dotId: 'dotMax', value: qt.max },
      ];
      latencies.forEach(({ id, dotId, value }) => {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = formatTime(value);
          el.style.color = '';
        }
        setLatencyDot(dotId, value);
      });
    } else {
      ['latAvg','latP50','latP95','latP99','latMin','latMax'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.textContent = '-'; el.style.color = '#d1d5db'; }
      });
      ['dotAvg','dotP50','dotP95','dotP99','dotMin','dotMax'].forEach(setLatencyDot);
    }

    html('plVectorCount', pipeline.vector_count != null ? pipeline.vector_count.toLocaleString() : '-');
    html('plActiveIndex', pipeline.active_index || 'none');
    html('plStrategy', pipeline.retrieval_strategy || 'none');
    html('monStrategy', pipeline.retrieval_strategy || '-');
    html('plIndexes', (pipeline.available_indexes || []).join(', ') || 'none');

    return data;
  } catch (e) {
    console.error('Metrics fetch failed:', e);
  }
}

async function fetchConfig() {
  try {
    const res = await fetch(`${API_BASE}/manage/config`);
    const data = await res.json();

    const keyFields = [
      { label: 'LLM Model', key: 'llm_model' },
      { label: 'Embedding', key: 'embedding_model' },
      { label: 'Top-K', key: 'retrieval_top_k' },
      { label: 'Strategy', key: 'retrieval_strategy' },
      { label: 'Host', key: 'server_host' },
      { label: 'Port', key: 'server_port' },
      { label: 'Cache', key: 'cache_enabled' },
      { label: 'Log Level', key: 'log_level' },
      { label: 'Max Tokens', key: 'llm_max_tokens' },
    ];
    let configHtml = '';
    keyFields.forEach(({ label, key }) => {
      const val = data[key] != null ? data[key] : '-';
      configHtml += `<tr><td>${label}</td><td class="val-mono">${escapeHtml(String(val))}</td></tr>`;
    });
    html('configTable', configHtml);
  } catch (e) {
    html('configTable', '<tr><td>Error</td><td>' + e.message + '</td></tr>');
  }
}

async function fetchLogs() {
  try {
    const res = await fetch(`${API_BASE}/monitoring/logs`);
    const lines = await res.json();
    if (!lines || lines.length === 0) {
      html('logViewer', '<div class="log-line" style="color:var(--gray-600);">No log entries yet.</div>');
      return;
    }
    renderLogs(lines);
  } catch (e) {
    html('logViewer', '<div class="log-line" style="color:var(--gray-600);">Failed to fetch logs.</div>');
  }
}

function parseLogLine(line) {
  try {
    const parsed = JSON.parse(line);
    const msg = parsed.record?.message || parsed.text || line;
    const level = parsed.record?.level?.name || 'INFO';
    return { message: msg, level: level };
  } catch {
    return { message: line, level: 'INFO' };
  }
}

function renderLogs(lines) {
  let htmlStr = lines.map(line => {
    const { message, level } = parseLogLine(line);
    const escaped = escapeHtml(message);
    let levelClass = 'level-INFO';
    if (level === 'WARNING' || level === 'WARN') levelClass = 'level-WARNING';
    else if (level === 'ERROR' || level === 'ERR') levelClass = 'level-ERROR';
    else if (level === 'DEBUG') levelClass = 'level-DEBUG';
    else if (level === 'CRITICAL') levelClass = 'level-CRITICAL';

    return `<div class="log-line"><span class="level-badge ${levelClass}">${level}</span><span class="${levelClass}">${escaped}</span></div>`;
  }).join('');

  html('logViewer', htmlStr);
  const viewer = document.getElementById('logViewer');
  if (viewer) viewer.scrollTop = viewer.scrollHeight;
}

function startLogStream() {
  if (logEventSource) logEventSource.close();
  logEventSource = new EventSource(`${API_BASE}/monitoring/logs/stream`);
  logEventSource.onmessage = event => {
    if (logStreamPaused) return;
    const viewer = document.getElementById('logViewer');
    const lines = JSON.parse(event.data);
    if (lines && lines.length > 0) {
      if (viewer.children.length <= 1 && viewer.children[0]?.textContent?.includes('Waiting')) {
        renderLogs(lines);
      } else {
        renderLogs(lines);
      }
    }
  };
  logEventSource.onerror = () => {
    console.log('Log stream disconnected, retrying...');
  };
}

function stopLogStream() {
  if (logEventSource) {
    logEventSource.close();
    logEventSource = null;
  }
}

function toggleLogStream() {
  logStreamPaused = !logStreamPaused;
  const btn = document.getElementById('logToggleText');
  const dot = document.getElementById('logStatusDot');
  if (logStreamPaused) {
    btn.textContent = 'Resume';
    dot.className = 'status-dot yellow';
  } else {
    btn.textContent = 'Pause';
    dot.className = 'status-dot green';
  }
}

function refreshMetrics() {
  fetchMetrics();
  fetchConfig();
}

async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    html('monStatus', `<span class="status-dot green"></span>Healthy`);
    html('monVersion', data.version || '-');
  } catch (e) {
    html('monStatus', `<span class="status-dot red"></span>Unreachable`);
  }
}

setInterval(() => {
  if (_uptimeRef) {
    const elapsed = _uptimeRef.serverUptime + (Date.now() - _uptimeRef.clientTime) / 1000;
    const h = Math.floor(elapsed / 3600);
    const m = Math.floor((elapsed % 3600) / 60);
    const s = Math.floor(elapsed % 60);
    const hh = String(h).padStart(2, '0');
    const mm = String(m).padStart(2, '0');
    const ss = String(s).padStart(2, '0');
    html('monUptime', `${hh}:${mm}:${ss}`);
  }
}, 1000);

setInterval(() => {
  if (!logStreamPaused) fetchMetrics();
  fetchHealth();
}, 3000);

fetchMetrics();
fetchConfig();
fetchLogs();
fetchHealth();
startLogStream();