const QUALITY_SUMMARY_FIELDS = [
  ['pagesCaptured', '캡처 페이지'],
  ['pagesFailed', '실패 페이지'],
  ['skippedPages', '건너뜀'],
  ['missingCriticalAssets', '누락 자산'],
  ['replayWarnings', '리플레이 경고'],
  ['graphqlEndpoints', 'GraphQL'],
];

const STATUS_COPY = {
  idle: {
    label: '대기',
    tone: 'idle',
    headline: '실행 준비',
    detail: 'URL을 입력하고 실행하세요.',
  },
  queued: {
    label: '대기열',
    tone: 'queued',
    headline: '대기 중',
    detail: '곧 시작합니다.',
  },
  running: {
    label: '실행 중',
    tone: 'running',
    headline: '크롤 중',
    detail: '로그를 확인하세요.',
  },
  completed: {
    label: '완료',
    tone: 'completed',
    headline: '완료',
    detail: '결과를 확인하세요.',
  },
  failed: {
    label: '실패',
    tone: 'failed',
    headline: '실패',
    detail: '오류를 확인하세요.',
  },
  cancelled: {
    label: '중지됨',
    tone: 'cancelled',
    headline: '중지됨',
    detail: '부분 결과가 남아 있을 수 있습니다.',
  },
};

const STAGE_LABELS = [
  { key: 'setup', label: '실행' },
  { key: 'live', label: '진행' },
  { key: 'results', label: '결과' },
];

export function buildJobStatusModel(job = {}) {
  const statusCode = normalizeStatus(job.status);
  const summaryItems = buildQualitySummaryItems(job.qualitySummary);
  const warningItems = buildVerificationWarningItems(job.verificationWarnings);
  const artifactItems = buildArtifactItems(job.artifacts);
  const outputRoot = toOutputRelativePath(job.outputDir);

  return {
    status: {
      code: statusCode,
      ...STATUS_COPY[statusCode],
    },
    stageItems: buildStageItems(statusCode),
    summaryItems,
    primarySummary: summaryItems.filter((item) => item.value !== '—').slice(0, 4),
    warningItems,
    warningGroups: buildWarningGroups(warningItems),
    artifactItems,
    artifactLinks: buildArtifactLinks(artifactItems, outputRoot),
    outputShortcuts: buildOutputShortcutItems({
      artifacts: artifactItems,
      outputRoot,
    }),
    replayOutcome: buildReplayOutcome({
      statusCode,
      summary: job.qualitySummary,
      outputDir: job.outputDir,
    }),
  };
}

export function buildQualitySummaryItems(summary) {
  const source = summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : null;
  if (!source) return [];

  return QUALITY_SUMMARY_FIELDS.map(([key, label]) => ({
    key,
    label,
    value: formatJobValue(source[key]),
  }));
}

export function buildVerificationWarningItems(warnings) {
  if (!Array.isArray(warnings)) return [];

  return warnings
    .map((warning) => formatJobValue(warning))
    .filter(Boolean)
    .map((text, index) => ({
      key: `warning-${index}`,
      text,
    }));
}

export function buildArtifactItems(artifacts) {
  if (!artifacts || typeof artifacts !== 'object' || Array.isArray(artifacts)) return [];

  return Object.entries(artifacts)
    .map(([key, value]) => ({
      key,
      label: humanizeLabel(key),
      value: formatArtifactValue(value),
    }))
    .filter((item) => item.value);
}

export function formatJobValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'boolean') return value ? '예' : '아니오';
  if (typeof value === 'string') return value;

  if (Array.isArray(value)) {
    const items = value.map((item) => formatJobValue(item)).filter((item) => item !== '—');
    return items.length > 0 ? items.join(', ') : '—';
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value)
      .map(([key, item]) => `${humanizeLabel(key)}: ${formatJobValue(item)}`)
      .filter((entry) => !entry.endsWith(': —'));

    if (entries.length > 0) {
      return entries.join(' | ');
    }

    try {
      return JSON.stringify(value);
    } catch {
      return '—';
    }
  }

  return String(value);
}

export function toOutputRelativePath(value) {
  if (!value) return '';
  const normalized = String(value).replaceAll('\\', '/').trim();
  if (!normalized) return '';

  const withoutDot = normalized.replace(/^\.\//, '');
  if (withoutDot === 'output') return '';
  if (withoutDot.startsWith('output/')) {
    return withoutDot.slice('output/'.length);
  }

  const absoluteIndex = withoutDot.lastIndexOf('/output/');
  if (absoluteIndex >= 0) {
    return withoutDot.slice(absoluteIndex + '/output/'.length);
  }

  return withoutDot.replace(/^\/+/, '');
}

export function buildArtifactLinks(items, outputRoot = '') {
  return items.map((item) => ({
    ...item,
    href: buildOutputHref(resolveOutputPath(item.value, outputRoot)),
  }));
}

function buildReplayOutcome({ statusCode, summary, outputDir }) {
  const replayWarnings = toFiniteNumber(summary?.replayWarnings);
  const missingAssets = toFiniteNumber(summary?.missingCriticalAssets);
  const pagesCaptured = toFiniteNumber(summary?.pagesCaptured);

  if (statusCode === 'completed') {
    if (replayWarnings === 0 && missingAssets === 0) {
      return {
        tone: 'success',
        headline: '정상',
        detail: pagesCaptured > 0
          ? `${pagesCaptured}개 페이지를 캡처했고 큰 문제가 없습니다.`
          : '큰 문제가 없습니다.',
        meta: outputDir ? `출력: ${outputDir}` : '출력 생성 완료',
      };
    }

    return {
      tone: 'warning',
      headline: '확인 필요',
      detail: `경고 ${replayWarnings ?? '—'} | 누락 자산 ${missingAssets ?? '—'}`,
      meta: outputDir ? `출력: ${outputDir}` : '아래 내용을 확인하세요.',
    };
  }

  if (statusCode === 'failed') {
    return {
      tone: 'error',
      headline: '실패',
      detail: '실행 중 오류가 발생했습니다.',
      meta: '리플레이 결과가 완성되지 않았습니다.',
    };
  }

  if (statusCode === 'cancelled') {
    return {
      tone: 'muted',
      headline: '중지됨',
      detail: '부분 결과만 남았을 수 있습니다.',
      meta: '최종 결과가 없습니다.',
    };
  }

  if (statusCode === 'running' || statusCode === 'queued') {
    return {
      tone: 'info',
      headline: '생성 중',
      detail: '작업이 끝나면 결과가 표시됩니다.',
      meta: '실행 중',
    };
  }

  return {
    tone: 'muted',
    headline: '결과 없음',
    detail: '실행 후 결과가 표시됩니다.',
    meta: '대기 중',
  };
}

function buildStageItems(statusCode) {
  const stageStateByStatus = {
    idle: ['current', 'pending', 'pending'],
    queued: ['complete', 'current', 'pending'],
    running: ['complete', 'current', 'pending'],
    completed: ['complete', 'complete', 'current'],
    failed: ['complete', 'attention', 'current'],
    cancelled: ['complete', 'attention', 'current'],
  };

  const states = stageStateByStatus[statusCode] || stageStateByStatus.idle;
  return STAGE_LABELS.map((stage, index) => ({
    ...stage,
    state: states[index],
  }));
}

function buildWarningGroups(items) {
  if (!Array.isArray(items) || items.length === 0) return [];

  const groups = new Map();
  for (const item of items) {
    const descriptor = classifyWarningGroup(item.text);
    if (!groups.has(descriptor.key)) {
      groups.set(descriptor.key, {
        ...descriptor,
        items: [],
      });
    }
    groups.get(descriptor.key).items.push(item);
  }

  return Array.from(groups.values());
}

function classifyWarningGroup(text) {
  const normalized = String(text || '').toLowerCase();

  if (/(font|image|stylesheet|script|asset|missing critical asset|hero|first-paint)/i.test(normalized)) {
    return {
      key: 'missing-assets',
      title: '누락 자산',
      tone: 'warning',
      description: '화면 표시나 리플레이에 영향이 있습니다.',
    };
  }

  if (/(external|recaptcha|tracking|telemetry|analytics|adtech|runtime|third-party)/i.test(normalized)) {
    return {
      key: 'external-runtime',
      title: '외부 런타임',
      tone: 'info',
      description: '검증 중 외부 호출이 남아 있습니다.',
    };
  }

  return {
    key: 'replay-warnings',
    title: '리플레이 경고',
    tone: 'warning',
    description: '리플레이 확인이 필요합니다.',
  };
}

function buildOutputShortcutItems({ artifacts, outputRoot }) {
  const shortcuts = [];
  const seen = new Set();

  const pushShortcut = (shortcut) => {
    if (!shortcut?.path) return;
    const relativePath = toOutputRelativePath(shortcut.path);
    if (!relativePath || seen.has(relativePath)) return;
    seen.add(relativePath);
    shortcuts.push({
      ...shortcut,
      path: relativePath,
      href: buildOutputHref(relativePath),
    });
  };

  if (outputRoot) {
    pushShortcut({
      key: 'output-root',
      label: '출력 폴더',
      description: '생성된 결과 폴더를 엽니다.',
      path: outputRoot,
    });
    pushShortcut({
      key: 'generated-readme',
      label: 'README',
      description: '생성된 README를 엽니다.',
      path: `${outputRoot}/README.md`,
    });
    pushShortcut({
      key: 'crawl-manifest',
      label: '크롤 매니페스트',
      description: '캡처 결과를 확인합니다.',
      path: `${outputRoot}/server/spec/manifest/crawl-manifest.json`,
    });
    pushShortcut({
      key: 'replay-verification',
      label: '리플레이 검증',
      description: '검증 결과를 확인합니다.',
      path: `${outputRoot}/server/spec/replay-verification.json`,
    });
  }

  for (const artifact of artifacts) {
    pushShortcut({
      key: artifact.key,
      label: artifact.label,
      description: '생성된 파일을 엽니다.',
      path: resolveOutputPath(artifact.value, outputRoot),
    });
  }

  return shortcuts;
}

function formatArtifactValue(value) {
  if (value === null || value === undefined || value === '') return '';
  if (typeof value === 'string') return value;

  if (Array.isArray(value)) {
    return value.map((item) => formatArtifactValue(item)).filter(Boolean).join(', ');
  }

  if (typeof value === 'object') {
    if (typeof value.path === 'string' || typeof value.url === 'string' || typeof value.href === 'string') {
      return value.path || value.url || value.href;
    }

    const entries = Object.entries(value)
      .map(([key, item]) => `${humanizeLabel(key)}: ${formatJobValue(item)}`)
      .filter(Boolean);

    if (entries.length > 0) {
      return entries.join(' | ');
    }

    try {
      return JSON.stringify(value);
    } catch {
      return '';
    }
  }

  return String(value);
}

function buildOutputHref(pathValue) {
  const relativePath = toOutputRelativePath(pathValue);
  if (!relativePath) return '';
  return `/api/output?path=${encodeURIComponent(relativePath)}`;
}

function resolveOutputPath(pathValue, outputRoot) {
  const relativePath = toOutputRelativePath(pathValue);
  if (!relativePath) return '';
  if (outputRoot && relativePath !== outputRoot && !relativePath.startsWith(`${outputRoot}/`)) {
    return `${outputRoot}/${relativePath}`;
  }
  return relativePath;
}

function normalizeStatus(status) {
  return STATUS_COPY[status] ? status : 'idle';
}

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function humanizeLabel(value) {
  return String(value || '')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
