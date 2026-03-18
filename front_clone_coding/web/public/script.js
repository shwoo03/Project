document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('clone-form');
  const startBtn = document.getElementById('start-btn');
  const btnText = startBtn.querySelector('.btn-text');
  const loader = startBtn.querySelector('.loader');
  const cancelBtn = document.getElementById('cancel-btn');
  const terminalBody = document.getElementById('terminal-output');
  const statusBadge = document.getElementById('job-status');
  const statusMeta = document.getElementById('job-meta');

  let eventSource = null;
  let statusTimer = null;
  let currentJobId = null;

  function appendLog(type, text) {
    if (type === 'update') {
      const lastLog = terminalBody.lastElementChild;
      if (lastLog && lastLog.classList.contains('update')) {
        lastLog.textContent = `[update] ${text}`;
        return;
      }
    }

    const line = document.createElement('div');
    line.className = `log line ${type}`;

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

    line.textContent = `${prefixMap[type] || ''}${text}`;
    terminalBody.appendChild(line);
    terminalBody.scrollTop = terminalBody.scrollHeight;
  }

  function setStatus(status, message = '') {
    statusBadge.textContent = status;
    statusBadge.dataset.state = status.toLowerCase();
    statusMeta.textContent = message;
  }

  function resetUI() {
    startBtn.disabled = false;
    btnText.textContent = 'Start Cloning';
    loader.classList.add('hidden');
    cancelBtn.classList.add('hidden');
    stopPolling();
  }

  function stopPolling() {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  }

  function closeSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function connectSSE(jobId) {
    closeSSE();
    eventSource = new EventSource(`/api/logs?jobId=${encodeURIComponent(jobId)}`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      appendLog(data.type, data.text);
    };

    eventSource.onerror = () => {
      closeSSE();
    };
  }

  async function fetchJobStatus(jobId) {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      throw new Error('Failed to fetch job status');
    }
    return response.json();
  }

  function startPolling(jobId) {
    stopPolling();
    statusTimer = setInterval(async () => {
      try {
        const job = await fetchJobStatus(jobId);
        setStatus(job.status, job.outputDir || job.error || '');

        if (job.status === 'completed') {
          appendLog('success', `Output ready at ${job.outputDir || '(unknown path)'}`);
          resetUI();
          closeSSE();
          browseOutput('');
        }

        if (job.status === 'failed') {
          appendLog('error', job.error || 'Clone failed');
          resetUI();
          closeSSE();
        }

        if (job.status === 'cancelled') {
          appendLog('warn', 'Job cancelled');
          resetUI();
          closeSSE();
        }
      } catch (error) {
        appendLog('error', error.message);
        resetUI();
        closeSSE();
      }
    }, 1000);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const url = document.getElementById('url').value;
    const maxDepth = document.getElementById('maxDepth').value;
    const maxPages = document.getElementById('maxPages').value;
    const concurrency = document.getElementById('concurrency').value;
    const recursive = document.getElementById('recursive').checked;
    const scaffold = document.getElementById('scaffold').checked;
    const cookieFile = document.getElementById('cookieFile').value;

    terminalBody.innerHTML = '';
    appendLog('info', `Initializing clone job for ${url}...`);
    setStatus('queued', 'Submitting job');

    startBtn.disabled = true;
    btnText.textContent = 'Processing...';
    loader.classList.remove('hidden');
    cancelBtn.classList.remove('hidden');

    try {
      const response = await fetch('/api/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          options: {
            maxDepth,
            maxPages,
            concurrency,
            recursive,
            scaffold,
            cookieFile: cookieFile || undefined,
          },
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        appendLog('error', payload.error || 'Failed to start job');
        setStatus('failed', payload.error || 'Unable to start');
        resetUI();
        return;
      }

      currentJobId = payload.jobId;
      appendLog('info', `Job ${currentJobId} accepted`);
      setStatus(payload.status, `Job ID: ${currentJobId}`);
      connectSSE(currentJobId);
      startPolling(currentJobId);
    } catch (error) {
      appendLog('error', `Network error: ${error.message}`);
      setStatus('failed', error.message);
      resetUI();
    }
  });

  // Output Browser
  const outputList = document.getElementById('output-list');
  const outputBreadcrumb = document.getElementById('output-breadcrumb');
  const refreshBtn = document.getElementById('refresh-output');

  async function browseOutput(dirPath) {
    try {
      const res = await fetch(`/api/output?path=${encodeURIComponent(dirPath || '')}`);
      if (!res.ok) {
        outputList.innerHTML = '<div class="output-empty">Could not load output directory.</div>';
        return;
      }
      const data = await res.json();
      renderBreadcrumb(data.path);
      if (data.entries.length === 0) {
        outputList.innerHTML = '<div class="output-empty">Empty directory.</div>';
        return;
      }
      outputList.innerHTML = '';
      for (const entry of data.entries) {
        const item = document.createElement('div');
        item.className = 'output-item';
        const icon = entry.type === 'directory' ? '\uD83D\uDCC1' : '\uD83D\uDCC4';
        item.innerHTML = `<span class="icon">${icon}</span><span class="name">${entry.name}</span>`;
        if (entry.type === 'directory') {
          item.addEventListener('click', () => browseOutput(entry.path));
        } else {
          item.addEventListener('click', () => {
            window.open(`/api/output?path=${encodeURIComponent(entry.path)}`, '_blank');
          });
        }
        outputList.appendChild(item);
      }
    } catch {
      outputList.innerHTML = '<div class="output-empty">Failed to load output.</div>';
    }
  }

  function renderBreadcrumb(currentPath) {
    outputBreadcrumb.innerHTML = '';
    const parts = (currentPath || '').split('/').filter(Boolean);
    const root = document.createElement('a');
    root.textContent = 'output';
    root.addEventListener('click', () => browseOutput(''));
    outputBreadcrumb.appendChild(root);

    let accumulated = '';
    for (const part of parts) {
      accumulated = accumulated ? `${accumulated}/${part}` : part;
      const sep = document.createTextNode(' / ');
      outputBreadcrumb.appendChild(sep);
      const link = document.createElement('a');
      link.textContent = part;
      const target = accumulated;
      link.addEventListener('click', () => browseOutput(target));
      outputBreadcrumb.appendChild(link);
    }
  }

  refreshBtn.addEventListener('click', () => browseOutput(''));
  browseOutput('');

  cancelBtn.addEventListener('click', async () => {
    if (!currentJobId) return;
    cancelBtn.disabled = true;
    try {
      await fetch(`/api/jobs/${encodeURIComponent(currentJobId)}/cancel`, { method: 'POST' });
    } catch (err) {
      appendLog('error', `Cancel request failed: ${err.message}`);
    } finally {
      cancelBtn.disabled = false;
    }
  });

  setStatus('idle', 'Awaiting a new clone job');
});
