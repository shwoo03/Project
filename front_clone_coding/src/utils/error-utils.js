export function stringifyErrorLike(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;

  if (value instanceof Error) {
    return value.message || String(value);
  }

  if (typeof value === 'object') {
    const preferred = [
      value.message,
      typeof value.error === 'string' ? value.error : null,
      typeof value.code === 'string' ? value.code : null,
      value.details,
      value.hint,
    ].filter(Boolean);

    if (preferred.length > 0) {
      return preferred
        .map((item) => stringifyErrorLike(item))
        .filter(Boolean)
        .join(' | ');
    }

    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);
}

export function serializeJobError(error) {
  if (!error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: 'Unknown error',
      hint: null,
    };
  }

  if (typeof error === 'string') {
    return {
      code: 'UNKNOWN_ERROR',
      message: error,
      hint: null,
    };
  }

  return {
    code: error.code || 'UNKNOWN_ERROR',
    message: stringifyErrorLike(error.message || error) || 'Unknown error',
    hint: stringifyErrorLike(error.hint) || null,
  };
}
