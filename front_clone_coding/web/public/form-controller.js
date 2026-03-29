export function createFormController(elements) {
  const {
    form,
    startButton,
    startButtonText,
    loader,
    cancelButton,
    restoreButton,
    footnote,
    summaryError,
    fieldErrors,
    setupState,
    workspaceMode,
  } = elements;

  function readSubmission() {
    clearErrors();

    const values = {
      url: form.elements.url.value.trim(),
      maxDepth: form.elements.maxDepth.value,
      maxPages: form.elements.maxPages.value,
      concurrency: form.elements.concurrency.value,
      recursive: form.elements.recursive.checked,
      scaffold: form.elements.scaffold.checked,
      cookieFile: form.elements.cookieFile.value.trim(),
    };

    const errors = [];
    if (!values.url) {
      errors.push({ field: 'url', message: 'URL을 입력하세요.' });
    }

    validateNumberField(values.maxDepth, 'maxDepth', 0, '최대 깊이는 0 이상이어야 합니다.', errors);
    validateNumberField(values.maxPages, 'maxPages', 1, '최대 페이지는 1 이상이어야 합니다.', errors);
    validateNumberField(values.concurrency, 'concurrency', 1, '동시 작업은 1 이상이어야 합니다.', errors);

    if (errors.length > 0) {
      showErrors(errors);
      return null;
    }

    return {
      url: values.url,
      options: {
        maxDepth: values.maxDepth,
        maxPages: values.maxPages,
        concurrency: values.concurrency,
        recursive: values.recursive,
        scaffold: values.scaffold,
        cookieFile: values.cookieFile || undefined,
      },
    };
  }

  function setBusyState({ busy, canCancel, submitLabel, footnoteText, showRestore = true }) {
    startButton.disabled = busy;
    startButtonText.textContent = submitLabel;
    loader.classList.toggle('hidden', !busy);
    cancelButton.classList.toggle('hidden', !canCancel);
    restoreButton.classList.toggle('hidden', !showRestore);
    if (footnoteText) footnote.textContent = footnoteText;
  }

  function setWorkspaceMode(text) {
    workspaceMode.textContent = text;
  }

  function setSetupState(text) {
    setupState.textContent = text;
  }

  function showErrors(errors) {
    summaryError.textContent = errors.map((error) => error.message).join(' ');
    summaryError.classList.remove('hidden');

    for (const error of errors) {
      const fieldError = fieldErrors[error.field];
      if (!fieldError) continue;
      fieldError.textContent = error.message;
      fieldError.classList.remove('hidden');
    }
  }

  function clearErrors() {
    summaryError.textContent = '';
    summaryError.classList.add('hidden');
    for (const fieldError of Object.values(fieldErrors)) {
      fieldError.textContent = '';
      fieldError.classList.add('hidden');
    }
  }

  return {
    readSubmission,
    setBusyState,
    setWorkspaceMode,
    setSetupState,
    clearErrors,
  };
}

function validateNumberField(rawValue, field, minimum, message, errors) {
  const numeric = Number.parseInt(rawValue, 10);
  if (Number.isNaN(numeric) || numeric < minimum) {
    errors.push({ field, message });
  }
}
