import { createOutputHref, toOutputRelativePath } from './ui-formatters.js';

export function createOutputBrowser(elements) {
  const { outputList, outputBreadcrumb, outputShortcuts } = elements;
  let currentPath = '';

  async function browse(path = currentPath) {
    currentPath = path || '';
    try {
      const response = await fetch(`/api/output?path=${encodeURIComponent(currentPath)}`);
      if (!response.ok) {
        outputList.innerHTML = '<div class="output-empty">출력 폴더를 불러올 수 없습니다.</div>';
        return;
      }

      const data = await response.json();
      renderBreadcrumb(data.path);
      renderEntries(data.entries);
    } catch {
      outputList.innerHTML = '<div class="output-empty">출력을 불러올 수 없습니다.</div>';
    }
  }

  function setShortcuts(shortcuts = []) {
    outputShortcuts.replaceChildren();
    if (!shortcuts.length) return;

    for (const shortcut of shortcuts.slice(0, 4)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'output-shortcut-pill';
      button.textContent = shortcut.label;
      button.addEventListener('click', () => {
        if (shortcut.path) {
          const target = toOutputRelativePath(shortcut.path);
          const href = createOutputHref(target);
          if (href) window.open(href, '_blank');
        }
      });
      outputShortcuts.appendChild(button);
    }
  }

  return {
    browse,
    setShortcuts,
  };

  function renderEntries(entries) {
    if (!Array.isArray(entries) || entries.length === 0) {
      outputList.innerHTML = '<div class="output-empty">비어 있습니다.</div>';
      return;
    }

    outputList.innerHTML = '';
    for (const entry of entries) {
      const item = document.createElement('div');
      item.className = 'output-item';

      const icon = document.createElement('span');
      icon.className = 'icon';
      icon.textContent = entry.type === 'directory' ? '⌘' : '•';

      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = entry.name;

      const type = document.createElement('span');
      type.className = 'output-item-type';
      type.textContent = entry.type === 'directory' ? '폴더' : '파일';

      item.append(icon, name, type);
      item.addEventListener('click', () => {
        if (entry.type === 'directory') {
          browse(entry.path);
          return;
        }
        window.open(`/api/output?path=${encodeURIComponent(entry.path)}`, '_blank');
      });
      outputList.appendChild(item);
    }
  }

  function renderBreadcrumb(pathValue) {
    outputBreadcrumb.innerHTML = '';
    const parts = String(pathValue || '').split('/').filter(Boolean);

    const root = document.createElement('a');
    root.textContent = '출력';
    root.addEventListener('click', () => browse(''));
    outputBreadcrumb.appendChild(root);

    let accumulated = '';
    for (const part of parts) {
      accumulated = accumulated ? `${accumulated}/${part}` : part;
      const separator = document.createTextNode(' / ');
      outputBreadcrumb.appendChild(separator);

      const link = document.createElement('a');
      link.textContent = part;
      const target = accumulated;
      link.addEventListener('click', () => browse(target));
      outputBreadcrumb.appendChild(link);
    }
  }
}
