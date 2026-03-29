import { formatTimestamp, normalizeText } from './ui-formatters.js';

export function createLogController(elements) {
  const { rawLogBody, importantEvents, importantMeta, rawLogMeta } = elements;
  const entries = [];

  function clear() {
    entries.length = 0;
    rawLogBody.replaceChildren();
    const line = document.createElement('div');
    line.className = 'log line info';
    line.textContent = '실행 대기 중...';
    rawLogBody.appendChild(line);
    renderImportant();
    updateMeta();
  }

  function append(type, text, timestamp = new Date().toISOString()) {
    const normalizedText = normalizeText(text);
    const normalizedEntry = { type, text: normalizedText, timestamp };
    entries.push(normalizedEntry);
    appendRawLine(normalizedEntry);
    renderImportant();
    updateMeta();
  }

  function renderImportant() {
    importantEvents.replaceChildren();
    const importantEntries = entries.filter(isImportantEntry).slice(-6).reverse();

    if (importantEntries.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state compact';
      empty.textContent = '주요 로그가 여기에 표시됩니다.';
      importantEvents.appendChild(empty);
      importantMeta.textContent = entries.length > 0 ? '변경 없음' : '로그 없음';
      return;
    }

    importantMeta.textContent = `${importantEntries.length}개`;
    for (const entry of importantEntries) {
      const card = document.createElement('article');
      card.className = `event-card ${normalizeTone(entry.type)}`;

      const badge = document.createElement('span');
      badge.className = 'event-badge';
      badge.textContent = normalizeEventLabel(entry.type);

      const body = document.createElement('p');
      body.className = 'event-text';
      body.textContent = entry.text;

      const meta = document.createElement('span');
      meta.className = 'event-meta';
      meta.textContent = formatTimestamp(entry.timestamp);

      card.append(badge, body, meta);
      importantEvents.appendChild(card);
    }
  }

  return {
    clear,
    append,
  };

  function appendRawLine(entry) {
    const line = document.createElement('div');
    line.className = `log line ${entry.type}`;

    const prefixMap = {
      succeed: '[ok] ',
      success: '[ok] ',
      fail: '[error] ',
      error: '[error] ',
      info: '[info] ',
      warn: '[warn] ',
      update: '[update] ',
      debug: '[debug] ',
      start: '[start] ',
    };

    line.textContent = `${prefixMap[entry.type] || ''}${entry.text}`;
    rawLogBody.appendChild(line);
    rawLogBody.scrollTop = rawLogBody.scrollHeight;
  }

  function updateMeta() {
    const count = entries.length + (entries.length === 0 ? 1 : 0);
    rawLogMeta.textContent = `${count}줄`;
  }
}

function isImportantEntry(entry) {
  if (['success', 'succeed', 'error', 'fail', 'warn', 'start'].includes(entry.type)) return true;
  if (entry.type === 'update') return true;
  if (entry.type !== 'info') return false;
  return /(queued|accepted|running|started|completed|cancelled|resume|failed|output ready|시작|복구|완료|중지|실패|출력)/i.test(entry.text);
}

function normalizeEventLabel(type) {
  switch (type) {
    case 'success':
    case 'succeed':
      return '성공';
    case 'error':
    case 'fail':
      return '실패';
    case 'warn':
      return '경고';
    case 'start':
      return '시작';
    case 'update':
      return '업데이트';
    default:
      return '정보';
  }
}

function normalizeTone(type) {
  if (['success', 'succeed'].includes(type)) return 'success';
  if (['error', 'fail'].includes(type)) return 'error';
  if (type === 'warn') return 'warning';
  return 'info';
}
