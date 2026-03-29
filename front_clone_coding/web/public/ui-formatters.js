export function normalizeText(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (value instanceof Error) return value.message || String(value);

  if (typeof value === 'object') {
    const preferred = [
      value.message,
      typeof value.error === 'string' ? value.error : null,
      typeof value.code === 'string' ? value.code : null,
      value.hint,
    ].filter(Boolean);

    if (preferred.length > 0) {
      return preferred.map((item) => normalizeText(item)).filter(Boolean).join(' | ');
    }

    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
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
  if (withoutDot.startsWith('output/')) return withoutDot.slice('output/'.length);

  const absoluteIndex = withoutDot.lastIndexOf('/output/');
  if (absoluteIndex >= 0) {
    return withoutDot.slice(absoluteIndex + '/output/'.length);
  }

  return withoutDot.replace(/^\/+/, '');
}

export function createOutputHref(pathValue) {
  const relativePath = toOutputRelativePath(pathValue);
  if (!relativePath) return '';
  return `/api/output?path=${encodeURIComponent(relativePath)}`;
}

export function formatTimestamp(timestamp) {
  if (!timestamp) return '방금 전';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '방금 전';

  return new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

export function truncateMiddle(value, maxLength = 76) {
  const text = String(value || '');
  if (text.length <= maxLength) return text;
  const side = Math.max(10, Math.floor((maxLength - 1) / 2));
  return `${text.slice(0, side)}…${text.slice(-side)}`;
}
