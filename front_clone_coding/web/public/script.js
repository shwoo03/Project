import { createFormController } from './form-controller.js';
import { createJobView } from './job-view.js';
import { createLogController } from './log-controller.js';
import { createOutputBrowser } from './output-browser.js';
import { normalizeText } from './ui-formatters.js';

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('clone-form');
  const startButton = document.getElementById('start-btn');
  const startButtonText = startButton.querySelector('.btn-text');
  const loader = startButton.querySelector('.loader');
  const cancelButton = document.getElementById('cancel-btn');
  const restoreButton = document.getElementById('restore-btn');
  const workspaceMode = document.getElementById('workspace-mode');
  const setupState = document.getElementById('setup-state');
  const resultsState = document.getElementById('results-state');
  const formFootnote = document.getElementById('form-footnote');
  const outputRefreshButton = document.getElementById('refresh-output');

  const formController = createFormController({
    form,
    startButton,
    startButtonText,
    loader,
    cancelButton,
    restoreButton,
    footnote: formFootnote,
    summaryError: document.getElementById('form-error-summary'),
    fieldErrors: {
      url: document.getElementById('url-error'),
      maxDepth: document.getElementById('maxDepth-error'),
      maxPages: document.getElementById('maxPages-error'),
      concurrency: document.getElementById('concurrency-error'),
    },
    setupState,
    workspaceMode,
  });

  const logController = createLogController({
    rawLogBody: document.getElementById('terminal-output'),
    importantEvents: document.getElementById('important-events'),
    importantMeta: document.getElementById('important-events-meta'),
    rawLogMeta: document.getElementById('raw-log-meta'),
  });

  const jobView = createJobView({
    statusBadge: document.getElementById('job-status'),
    stageRail: document.getElementById('stage-rail'),
    jobMeta: document.getElementById('job-meta'),
    statusHeadline: document.getElementById('status-headline'),
    statusReadout: document.getElementById('status-readout'),
    resultsState,
    resultsTopline: document.getElementById('results-topline'),
    outcomeMeta: document.getElementById('outcome-meta'),
    replayOutcome: document.getElementById('replay-outcome'),
    jobInsights: document.getElementById('job-insights'),
    artifactShortcuts: document.getElementById('artifact-shortcuts'),
    workspaceMode,
  });

  const outputBrowser = createOutputBrowser({
    outputList: document.getElementById('output-list'),
    outputBreadcrumb: document.getElementById('output-breadcrumb'),
    outputShortcuts: document.getElementById('output-shortcuts'),
  });

  let eventSource = null;
  let statusTimer = null;
  let currentJobId = null;

  function setViewFromJob(job = {}) {
    const model = jobView.render(job);
    outputBrowser.setShortcuts(model.outputShortcuts);

    if (job.status === 'completed') {
      formController.setSetupState('재실행 가능');
      formController.setWorkspaceMode('결과 확인');
    } else if (job.status === 'running' || job.status === 'queued') {
      formController.setSetupState('실행 중');
      formController.setWorkspaceMode('크롤 진행 중');
    } else if (job.status === 'failed' || job.status === 'cancelled') {
      formController.setSetupState('다시 실행 가능');
      formController.setWorkspaceMode('확인 필요');
    } else {
      formController.setSetupState('대기');
      formController.setWorkspaceMode('대기 중');
    }
  }

  function formatJobError(error) {
    if (!error) return '';
    const message = normalizeText(error.message || error);
    const hint = normalizeText(error.hint);
    return hint ? `${message} (${hint.split('\n')[0]})` : message;
  }

  function closeSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function stopPolling() {
    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }
  }

  function resetToIdleView() {
    currentJobId = null;
    formController.setBusyState({
      busy: false,
      canCancel: false,
      submitLabel: '실행',
      footnoteText: '실행 준비가 되었습니다.',
      showRestore: true,
    });
  }

  function connectSSE(jobId) {
    closeSSE();
    eventSource = new EventSource(`/api/logs?jobId=${encodeURIComponent(jobId)}`);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      logController.append(data.type, data.text, data.timestamp);
    };

    eventSource.onerror = () => {
      closeSSE();
    };
  }

  async function fetchJobStatus(jobId) {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      throw new Error('작업 상태를 불러오지 못했습니다.');
    }
    return response.json();
  }

  async function fetchActiveJob() {
    const response = await fetch('/api/jobs/active/current');
    if (!response.ok) {
      throw new Error('활성 작업을 불러오지 못했습니다.');
    }
    return response.json();
  }

  function setRunningState(job) {
    currentJobId = job.id;
    formController.setBusyState({
      busy: true,
      canCancel: true,
      submitLabel: '실행 중',
      footnoteText: '현재 작업이 실행 중입니다.',
      showRestore: true,
    });
    setViewFromJob(job);
    connectSSE(job.id);
    startPolling(job.id);
  }

  function startPolling(jobId) {
    stopPolling();
    statusTimer = setInterval(async () => {
      try {
        const job = await fetchJobStatus(jobId);
        setViewFromJob(job);

        if (job.status === 'completed') {
          logController.append('success', `출력 준비 완료: ${job.outputDir || '(경로 없음)'}`);
          stopPolling();
          closeSSE();
          resetToIdleView();
          outputBrowser.browse('');
        }

        if (job.status === 'failed') {
          logController.append('error', formatJobError(job.error) || '실패');
          stopPolling();
          closeSSE();
          resetToIdleView();
        }

        if (job.status === 'cancelled') {
          logController.append('warn', '중지됨');
          stopPolling();
          closeSSE();
          resetToIdleView();
        }
      } catch (error) {
        logController.append('error', error.message);
        stopPolling();
        closeSSE();
        resetToIdleView();
      }
    }, 1000);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = formController.readSubmission();
    if (!payload) return;

    logController.clear();
    logController.append('info', `${payload.url} 실행 준비 중...`);
    formController.setBusyState({
      busy: true,
      canCancel: true,
      submitLabel: '요청 중',
      footnoteText: '실행 요청을 보내는 중입니다.',
      showRestore: true,
    });
    setViewFromJob({ status: 'queued' });

    try {
      const response = await fetch('/api/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      if (!response.ok) {
        logController.append('error', result.error || '실행 시작 실패');
        setViewFromJob({ status: 'failed' });
        resetToIdleView();
        return;
      }

      currentJobId = result.jobId;
      logController.append('info', `작업 ${currentJobId} 시작`);
      setRunningState({
        id: currentJobId,
        status: result.status,
        outputDir: '',
        error: null,
        verificationWarnings: [],
        qualitySummary: null,
        artifacts: null,
      });
    } catch (error) {
      logController.append('error', `네트워크 오류: ${error.message}`);
      setViewFromJob({ status: 'failed' });
      resetToIdleView();
    }
  });

  cancelButton.addEventListener('click', async () => {
    if (!currentJobId) return;
    cancelButton.disabled = true;
    try {
      await fetch(`/api/jobs/${encodeURIComponent(currentJobId)}/cancel`, { method: 'POST' });
    } catch (error) {
      logController.append('error', `중지 요청 실패: ${error.message}`);
    } finally {
      cancelButton.disabled = false;
    }
  });

  restoreButton.addEventListener('click', async () => {
    await restoreActiveJob();
  });

  outputRefreshButton.addEventListener('click', () => {
    outputBrowser.browse('');
  });

  async function restoreActiveJob() {
    try {
      const { job } = await fetchActiveJob();
      if (!job || (job.status !== 'queued' && job.status !== 'running')) {
        setViewFromJob({ status: 'idle' });
        resetToIdleView();
        return;
      }

      logController.append('info', `작업 ${job.id} 복구`);
      setRunningState(job);
    } catch (error) {
      logController.append('warn', `복구 실패: ${error.message}`);
      setViewFromJob({ status: 'idle' });
      resetToIdleView();
    }
  }

  setViewFromJob({ status: 'idle' });
  resetToIdleView();
  outputBrowser.browse('');
  restoreActiveJob();
});
