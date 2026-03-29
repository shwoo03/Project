import { buildJobStatusModel, formatJobValue } from './job-status-utils.js';
import { createOutputHref, truncateMiddle } from './ui-formatters.js';

export function createJobView(elements) {
  const {
    statusBadge,
    stageRail,
    jobMeta,
    statusHeadline,
    statusReadout,
    resultsState,
    resultsTopline,
    outcomeMeta,
    replayOutcome,
    jobInsights,
    artifactShortcuts,
    workspaceMode,
  } = elements;

  function render(job = {}) {
    const model = buildJobStatusModel(job);
    renderStatus(model);
    renderStages(model.stageItems);
    renderReadout(model);
    renderOutcome(model);
    renderWarningsAndArtifacts(model);
    renderShortcuts(model.outputShortcuts);
    workspaceMode.textContent = model.status.headline;
    return model;
  }

  return { render };

  function renderStatus(model) {
    statusBadge.textContent = model.status.label;
    statusBadge.dataset.state = model.status.code;
    jobMeta.textContent = buildMetaLine(model.status.detail, model.replayOutcome.meta);
    statusHeadline.textContent = model.status.headline;
    resultsState.textContent = model.status.code === 'completed' ? '확인 가능' : humanizeResultsState(model.status.code);
    resultsTopline.textContent = model.replayOutcome.detail;
    outcomeMeta.textContent = model.replayOutcome.meta;
  }

  function renderStages(items) {
    stageRail.replaceChildren();
    for (const item of items) {
      const node = document.createElement('div');
      node.className = `stage-item ${item.state}`;

      const marker = document.createElement('span');
      marker.className = 'stage-marker';
      marker.textContent = item.state === 'complete' ? '✓' : item.state === 'attention' ? '!' : '';

      const label = document.createElement('span');
      label.className = 'stage-label';
      label.textContent = item.label;

      node.append(marker, label);
      stageRail.appendChild(node);
    }
  }

  function renderReadout(model) {
    statusReadout.replaceChildren();
    const rows = [];

    if (model.primarySummary.length > 0) {
      rows.push(...model.primarySummary.map((item) => ({
        label: item.label,
        value: item.value,
      })));
    }

    if (model.artifactLinks.length > 0) {
      rows.push({
        label: '대표 파일',
        value: truncateMiddle(model.artifactLinks[0].value, 58),
      });
    }

    if (rows.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state compact';
      empty.textContent = '실행 후 정보가 표시됩니다.';
      statusReadout.appendChild(empty);
      return;
    }

    const list = document.createElement('dl');
    list.className = 'status-readout-list';
    for (const row of rows) {
      const term = document.createElement('dt');
      term.textContent = row.label;
      const value = document.createElement('dd');
      value.textContent = formatJobValue(row.value);
      list.append(term, value);
    }
    statusReadout.appendChild(list);
  }

  function renderOutcome(model) {
    replayOutcome.replaceChildren();

    const card = document.createElement('article');
    card.className = `outcome-shell ${model.replayOutcome.tone}`;

    const headline = document.createElement('h4');
    headline.textContent = model.replayOutcome.headline;

    const detail = document.createElement('p');
    detail.textContent = model.replayOutcome.detail;

    const meta = document.createElement('p');
    meta.className = 'outcome-note';
    meta.textContent = model.replayOutcome.meta;

    card.append(headline, detail, meta);
    replayOutcome.appendChild(card);
  }

  function renderWarningsAndArtifacts(model) {
    jobInsights.replaceChildren();

    const cards = [];
    if (model.warningGroups.length > 0) {
      for (const group of model.warningGroups) {
        cards.push(buildWarningCard(group));
      }
    }

    if (model.summaryItems.some((item) => item.value !== '—')) {
      cards.push(buildSummaryCard(model.summaryItems));
    }

    if (model.artifactLinks.length > 0) {
      cards.push(buildArtifactCard(model.artifactLinks));
    }

    if (cards.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'job-insights-empty';
      empty.textContent = '완료 후 요약이 표시됩니다.';
      jobInsights.appendChild(empty);
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'job-insights-grid';
    cards.forEach((card) => grid.appendChild(card));
    jobInsights.appendChild(grid);
  }

  function renderShortcuts(shortcuts) {
    artifactShortcuts.replaceChildren();

    if (!shortcuts.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state compact';
      empty.textContent = '주요 파일이 여기에 표시됩니다.';
      artifactShortcuts.appendChild(empty);
      return;
    }

    for (const shortcut of shortcuts) {
      const link = document.createElement('a');
      link.className = 'shortcut-card';
      link.href = shortcut.href || createOutputHref(shortcut.path);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';

      const label = document.createElement('span');
      label.className = 'shortcut-label';
      label.textContent = shortcut.label;

      const description = document.createElement('span');
      description.className = 'shortcut-description';
      description.textContent = shortcut.description;

      const path = document.createElement('span');
      path.className = 'shortcut-path';
      path.textContent = truncateMiddle(shortcut.path, 56);

      link.append(label, description, path);
      artifactShortcuts.appendChild(link);
    }
  }
}

function buildMetaLine(detail, replayMeta) {
  return replayMeta ? `${detail} ${replayMeta}` : detail;
}

function buildWarningCard(group) {
  const card = createInsightCard(group.title, group.tone);
  const description = document.createElement('p');
  description.className = 'insight-card-description';
  description.textContent = group.description;
  card.appendChild(description);

  const list = document.createElement('ul');
  list.className = 'insight-list';
  for (const item of group.items) {
    const entry = document.createElement('li');
    entry.textContent = item.text;
    list.appendChild(entry);
  }
  card.appendChild(list);
  return card;
}

function buildSummaryCard(items) {
  const card = createInsightCard('요약', 'summary');
  const list = document.createElement('dl');
  list.className = 'insight-summary-list';

  for (const item of items) {
    const term = document.createElement('dt');
    term.textContent = item.label;
    const value = document.createElement('dd');
    value.textContent = formatJobValue(item.value);
    list.append(term, value);
  }

  card.appendChild(list);
  return card;
}

function buildArtifactCard(items) {
  const card = createInsightCard('생성 파일', 'artifact');
  const list = document.createElement('ul');
  list.className = 'insight-list';

  for (const item of items) {
    const entry = document.createElement('li');
    const label = document.createElement('span');
    label.className = 'insight-list-label';
    label.textContent = item.label;
    const link = document.createElement('a');
    link.className = 'artifact-link';
    link.href = item.href || createOutputHref(item.value);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = truncateMiddle(item.value, 56);
    entry.append(label, link);
    list.appendChild(entry);
  }

  card.appendChild(list);
  return card;
}

function createInsightCard(title, tone) {
  const card = document.createElement('article');
  card.className = `job-insight-card ${tone}`;

  const header = document.createElement('div');
  header.className = 'job-insight-card-header';
  header.textContent = title;
  card.appendChild(header);

  return card;
}

function humanizeResultsState(statusCode) {
  if (statusCode === 'running' || statusCode === 'queued') return '생성 중';
  if (statusCode === 'failed') return '확인 필요';
  if (statusCode === 'cancelled') return '부분 결과';
  return '대기';
}
