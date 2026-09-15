'use strict';

const {LatestRequest, isFormEmpty, copyPayload} = window.CitationState;
const STYLES = ['APA', 'MLA', 'Chicago'];
const TYPES = ['book', 'article', 'chapter', 'website'];
const inputs = [...document.querySelectorAll('.field input, .field textarea, .field select')];
const fieldBlocks = [...document.querySelectorAll('.field')];
const typeButtons = [...document.querySelectorAll('.type-option')];
const styleButtons = [...document.querySelectorAll('.style-option')];
const fieldGroups = [...document.querySelectorAll('.field-group')];
const navLinks = [...document.querySelectorAll('.nav-link')];
const statusLine = document.getElementById('status');
const librarySection = document.getElementById('library');
const libraryFilter = document.getElementById('library-filter');
const themeToggle = document.getElementById('theme-toggle');
const formRequests = new LatestRequest();
const libraryRequests = new LatestRequest();
const DRAFT_KEY = 'citation-formatter-draft-v2';
const UNDO_KEY = 'citation-formatter-undo-v2';
const THEME_KEY = 'citation-formatter-theme-v1';
let currentType = 'book';
let libraryStyle = 'APA';
let editingId = null;
let corrections = {};
let formatTimer = null;
let formVersion = 0;
let formatted = null;
let libraryPayload = null;
let libraryLoading = true;
let mutationBusy = false;
let lookupFields = null;
let lookupBusy = false;
let removedIds = [];
const copyTimers = new WeakMap();

function themeLabel(theme) {
  return theme === 'dark' ? 'Dark' : theme === 'light' ? 'Light' : 'System';
}
function applyTheme(theme, persist = true) {
  const selected = ['system', 'light', 'dark'].includes(theme) ? theme : 'system';
  document.documentElement.dataset.theme = selected;
  if (themeToggle) {
    const label = themeLabel(selected);
    const labelNode = themeToggle.querySelector('[data-theme-label]');
    if (labelNode) labelNode.textContent = label;
    themeToggle.setAttribute('aria-label', `Color theme: ${label}. Activate to change.`);
    themeToggle.title = `Color theme: ${label}. Activate to change.`;
  }
  if (persist) {
    try { localStorage.setItem(THEME_KEY, selected); } catch (error) { /* Optional. */ }
  }
}
function storedTheme() {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return ['system', 'light', 'dark'].includes(value) ? value : 'system';
  } catch (error) { return 'system'; }
}
applyTheme(storedTheme(), false);

function escapeHtml(text) {
  const holder = document.createElement('div');
  holder.textContent = String(text);
  return holder.innerHTML;
}
function setStatus(message, problem = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle('is-problem', problem);
}
function setLibraryStatus(message, problem = false) {
  const target = document.getElementById('library-status');
  target.textContent = message;
  target.classList.toggle('is-problem', problem);
}
function setLookupStatus(message, problem = false) {
  const target = document.getElementById('lookup-status');
  target.textContent = message;
  target.classList.toggle('is-problem', problem);
}
function showEditingState() {
  document.getElementById('editing-status').textContent = editingId ? 'Editing a saved source' : 'New source';
  document.getElementById('save-label').textContent = editingId ? 'Save changes' : 'Save to list';
  document.getElementById('new-source').hidden = !editingId;
}
function syncButtons() {
  document.querySelectorAll('.copy, #copy-all').forEach(button => { button.disabled = !formatted; });
  document.getElementById('save').disabled = mutationBusy || !formatted;
  const unavailable = libraryLoading || mutationBusy || !libraryPayload || !libraryPayload.count;
  ['copy-library', 'print-library', 'clear-library'].forEach(id => { document.getElementById(id).disabled = unavailable; });
  document.querySelectorAll('.remove, .edit-source').forEach(button => { button.disabled = mutationBusy || libraryLoading; });
  const exportLink = document.getElementById('export-library');
  exportLink.setAttribute('aria-disabled', String(unavailable));
  exportLink.tabIndex = unavailable ? -1 : 0;
  document.getElementById('undo-remove').disabled = mutationBusy || !removedIds.length;
  libraryFilter.disabled = libraryLoading || !libraryPayload || !libraryPayload.count;
}
function applySourceType(type) {
  currentType = TYPES.includes(type) ? type : 'book';
  typeButtons.forEach(button => {
    const selected = button.dataset.type === currentType;
    button.classList.toggle('is-selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  fieldBlocks.forEach(block => {
    block.hidden = !(block.dataset.for || '').split(' ').includes(currentType);
    const label = block.querySelector('.label-text');
    const alternative = label && label.dataset['label' + currentType[0].toUpperCase() + currentType.slice(1)];
    if (alternative) label.textContent = alternative;
  });
  fieldGroups.forEach(group => { group.hidden = !group.querySelector('.field:not([hidden])'); });
  requestFormatting();
}
function collectFields() {
  const fields = {source_type: currentType, case_overrides: {...corrections}};
  inputs.forEach(input => {
    if (!input.closest('.field').hidden) fields[input.name] = input.value;
  });
  if (fields.author_mode === 'unknown') fields.authors = '';
  return fields;
}
function persistDraft() {
  try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify({fields: collectFields(), editingId})); } catch (error) { /* Storage may be unavailable. */ }
}
function clearFields() {
  inputs.forEach(input => { input.value = input.tagName === 'SELECT' ? input.options[0].value : ''; });
  corrections = {};
}
function fillFields(fields, id = null) {
  clearFields();
  editingId = id;
  corrections = fields.case_overrides && typeof fields.case_overrides === 'object' ? {...fields.case_overrides} : {};
  inputs.forEach(input => { if (typeof fields[input.name] === 'string') input.value = fields[input.name]; });
  // Import a draft created by the previous release.
  if (!fields.published_date && fields.access_date) document.getElementById('published_date').value = fields.access_date;
  applySourceType(fields.source_type);
  showEditingState();
  requestFormatting();
}
function clearErrors() {
  document.querySelectorAll('.field-error').forEach(node => { node.textContent = ''; });
  inputs.forEach(input => input.removeAttribute('aria-invalid'));
}
function showErrors(errors) {
  clearErrors();
  Object.entries(errors || {}).forEach(([name, message]) => {
    const input = inputs.find(item => item.name === name);
    if (!input) return;
    input.setAttribute('aria-invalid', 'true');
    const target = document.getElementById(name + '-error');
    if (target) target.textContent = message;
  });
}
function flagMissingFields(missing) {
  const names = new Set(missing || []);
  fieldBlocks.forEach(block => {
    const input = block.querySelector('input, textarea, select');
    const flag = block.querySelector('.flag');
    if (flag && input) flag.hidden = block.hidden || !names.has(input.name);
  });
}
async function api(url, method = 'GET', body, signal) {
  const response = await fetch(url, {
    method, signal, headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let payload;
  try { payload = await response.json(); } catch (error) { throw new Error('The server returned an unreadable response.'); }
  if (!response.ok) {
    const error = new Error(payload.error || 'The request could not be completed.');
    error.fields = payload.fields;
    error.duplicateId = payload.duplicate_id;
    throw error;
  }
  return payload;
}
function clearResults() {
  STYLES.forEach(style => {
    document.getElementById('out-' + style).replaceChildren();
    document.getElementById('intext-' + style).replaceChildren();
  });
  flagMissingFields([]);
  document.getElementById('parsed-authors').textContent = '';
  document.getElementById('learned').hidden = true;
}
function requestFormatting() {
  // Invalidate immediately, before the debounce. A late response is never current.
  formVersion += 1;
  formRequests.invalidate();
  clearTimeout(formatTimer);
  formatted = null;
  persistDraft();
  clearErrors();
  document.getElementById('authors').disabled = document.getElementById('author_mode').value === 'unknown';
  syncButtons();
  if (isFormEmpty(collectFields())) {
    clearResults();
    setStatus('Enter a source or load an example to begin.');
    document.getElementById('results').classList.remove('is-stale');
    return;
  }
  setStatus('Updating citation…');
  document.getElementById('results').classList.add('is-stale');
  formatTimer = setTimeout(formatNow, 250);
}
async function formatNow() {
  const request = formRequests.begin();
  try {
    const payload = await api('/api/format', 'POST', collectFields(), request.signal);
    if (!request.isCurrent()) return;
    formatted = payload.styles;
    STYLES.forEach(style => {
      document.getElementById('out-' + style).innerHTML = formatted[style].interactive_html;
      document.getElementById('intext-' + style).innerHTML = formatted[style].intext.map((item, index) =>
        `<dt>${escapeHtml(item.label)}</dt><dd><span>${item.html}</span>` +
        `<button type="button" class="copy intext-copy" data-style="${style}" data-index="${index}" ` +
        `aria-label="Copy ${style} ${escapeHtml(item.label)}"><span>Copy</span></button></dd>`).join('');
    });
    flagMissingFields(payload.missing);
    setStatus(payload.warnings.length ? 'Recommended details missing: ' + payload.warnings.join(', ') + '.' : 'Ready to copy. Check the source details before submitting.');
    document.getElementById('parsed-authors').textContent = payload.parsed_authors ? 'Read as: ' + payload.parsed_authors : '';
    document.getElementById('learned').hidden = !payload.corrections;
    document.querySelector('.learned-count').textContent = `${payload.corrections} source-specific correction${payload.corrections === 1 ? '' : 's'}`;
    document.getElementById('word-hint').hidden = document.getElementById('capitalization').value === 'preserve';
    document.getElementById('results').classList.remove('is-stale');
  } catch (error) {
    if (!request.isCurrent() || error.name === 'AbortError') return;
    showErrors(error.fields);
    setStatus(error.fields ? error.message : 'Could not update the citation. ' + error.message, true);
  } finally {
    if (request.isCurrent()) syncButtons();
  }
}
async function copyCitation(button, value) {
  if (!value || !value.text) return;
  const plainOnly = document.getElementById('copy-mode').value === 'plain';
  try {
    const mode = await copyPayload(navigator.clipboard, window.ClipboardItem, value, plainOnly);
    const label = button.querySelector('span');
    if (!button.dataset.originalLabel) button.dataset.originalLabel = label ? label.textContent : 'Copy';
    if (label) label.textContent = 'Copied';
    button.classList.add('is-copied');
    clearTimeout(copyTimers.get(button));
    copyTimers.set(button, setTimeout(() => {
      if (label) label.textContent = button.dataset.originalLabel;
      button.classList.remove('is-copied');
    }, 1400));
    setStatus(mode === 'plain' && !plainOnly ? 'Copied plain text. Formatted copying is unavailable in this browser; HTML export preserves italics.' : 'Copied ' + mode + ' citation text.');
  } catch (error) {
    setStatus('Your browser blocked copying. Select the citation text manually, or use HTML export.', true);
  }
}
function matchesLibraryFilter(entry, query) {
  if (!query) return true;
  const fields = entry.fields || {};
  return ['title', 'authors', 'editors', 'container', 'publisher', 'year', 'doi', 'isbn']
    .some(key => String(fields[key] || '').toLocaleLowerCase().includes(query));
}
function buildLibraryItem(entry) {
  const item = document.createElement('li');
  item.className = 'library-item';

  // Citation HTML comes from the formatter. User text has already been escaped there.
  const citation = document.createElement('p');
  citation.className = 'citation';
  citation.innerHTML = entry.html;

  const tools = document.createElement('div');
  tools.className = 'library-item-tools';

  const edit = document.createElement('button');
  edit.type = 'button';
  edit.className = 'edit-source link-button';
  edit.dataset.id = entry.id;
  edit.textContent = 'Edit';

  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'remove';
  remove.dataset.id = entry.id;
  remove.setAttribute('aria-label', `Remove ${entry.fields.title || 'saved source'}`);
  remove.innerHTML = '<svg class="icon" aria-hidden="true"><use href="#i-trash"/></svg>';

  tools.append(edit, remove);
  item.append(citation, tools);
  return item;
}
function renderLibrary(payload) {
  libraryPayload = payload;
  document.getElementById('library-heading-text').textContent = payload.heading;
  document.getElementById('library-count').textContent = `${payload.count} source${payload.count === 1 ? '' : 's'}`;
  document.getElementById('list-link-count').textContent = payload.count;
  document.getElementById('empty-library').hidden = payload.count !== 0;
  document.querySelector('.library-filter-bar').hidden = payload.count === 0;

  const query = libraryFilter.value.trim().toLocaleLowerCase();
  const visibleEntries = payload.entries.filter(entry => matchesLibraryFilter(entry, query));
  document.getElementById('library-list').replaceChildren(...visibleEntries.map(buildLibraryItem));
  document.getElementById('filter-empty').hidden = payload.count === 0 || visibleEntries.length !== 0;
  document.getElementById('library-filter-status').textContent = query
    ? `Showing ${visibleEntries.length} of ${payload.count}`
    : '';
  document.getElementById('export-library').href = '/api/library/export?style=' + libraryStyle;
}
async function refreshLibrary() {
  const request = libraryRequests.begin();
  libraryLoading = true;
  syncButtons();
  try {
    const payload = await api('/api/library?style=' + libraryStyle, 'GET', undefined, request.signal);
    if (!request.isCurrent()) return;
    renderLibrary(payload);
  } catch (error) {
    if (request.isCurrent() && error.name !== 'AbortError') { libraryPayload = null; setLibraryStatus(error.message, true); }
  } finally {
    if (request.isCurrent()) { libraryLoading = false; syncButtons(); }
  }
}
function setLibraryStyle(style) {
  libraryStyle = style;
  styleButtons.forEach(button => {
    const selected = button.dataset.style === style;
    button.classList.toggle('is-selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  refreshLibrary();
}
async function mutateLibrary(method, body, path = '/api/library') {
  if (mutationBusy) return null;
  mutationBusy = true;
  libraryRequests.invalidate();
  syncButtons();
  try {
    const payload = await api(path + '?style=' + libraryStyle, method, body);
    setLibraryStatus(payload.message);
    if (payload.removed_ids) {
      removedIds = payload.removed_ids;
      try { sessionStorage.setItem(UNDO_KEY, JSON.stringify(removedIds)); } catch (error) { /* Optional. */ }
      document.getElementById('undo-bar').hidden = !removedIds.length;
    }
    return payload;
  } catch (error) {
    if (error.fields) showErrors(error.fields);
    setStatus(error.message, true);
    setLibraryStatus(error.message, true);
    return null;
  } finally {
    await refreshLibrary();
    mutationBusy = false;
    syncButtons();
  }
}
async function saveSource() {
  const version = formVersion;
  const payload = await mutateLibrary(editingId ? 'PUT' : 'POST', {id: editingId, fields: collectFields()});
  if (payload && version === formVersion) {
    editingId = payload.saved_id;
    showEditingState();
    persistDraft();
    setStatus(payload.message);
  }
}
function startNew() {
  editingId = null;
  clearFields();
  showEditingState();
  requestFormatting();
}
async function runLookup() {
  const identifier = document.getElementById('identifier').value.trim();
  const button = document.getElementById('lookup');
  const label = button.querySelector('span');
  if (lookupBusy) return;
  if (!identifier) {
    setLookupStatus('Enter a DOI or ISBN first.', true);
    document.getElementById('identifier').focus();
    return;
  }
  lookupBusy = true;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  label.textContent = 'Looking up…';
  setLookupStatus('Contacting the metadata service…');
  try {
    const payload = await api('/api/lookup', 'POST', {identifier});
    lookupFields = payload.fields;
    const populated = ['source_type', 'authors', 'title', 'container', 'publisher', 'year', 'edition', 'doi', 'isbn']
      .filter(key => lookupFields[key]);
    document.getElementById('lookup-preview-content').innerHTML = '<dl>' + populated.map(key =>
      `<dt>${escapeHtml(key.replaceAll('_', ' '))}</dt><dd>${escapeHtml(lookupFields[key])}</dd>`).join('') + '</dl>';
    document.getElementById('merge-lookup').disabled = lookupFields.source_type !== currentType;
    document.getElementById('lookup-preview').showModal();
    setLookupStatus('Review the imported details before applying them.');
  } catch (error) {
    setLookupStatus(error.message, true);
  } finally {
    lookupBusy = false;
    button.disabled = false;
    button.removeAttribute('aria-busy');
    label.textContent = 'Look up';
  }
}
const EXAMPLES = {
  book: {authors: 'Young, Hugh D.\nFreedman, Roger A.', title: 'University Physics with Modern Physics', publisher: 'Pearson', city: 'New York', year: '2026', edition: '16'},
  article: {authors: 'Shannon, C. E.', title: 'A Mathematical Theory of Communication', container: 'Bell System Technical Journal', year: '1948', volume: '27', issue: '3', pages: '379-423', doi: '10.1002/j.1538-7305.1948.tb01338.x'},
  chapter: {authors: 'Turing, Alan M.', editors: 'Copeland, B. Jack', title: 'Computing Machinery and Intelligence', container: 'The Essential Turing', publisher: 'Oxford University Press', city: 'Oxford', year: '2004', pages: '433-464'},
  website: {authors: 'Berners-Lee, Tim', title: 'Information Management: A Proposal', container: 'CERN', published_date: '1989-03-14', url: 'https://cds.cern.ch/record/369245'},
};
function loadExample() { fillFields({source_type: currentType, ...EXAMPLES[currentType]}); }

// Field errors and hint relationships are attached once, without inline scripts.
inputs.forEach(input => {
  const block = input.closest('.field');
  const hint = block.querySelector('.hint');
  if (hint) hint.id = input.id + '-hint';
  const error = document.createElement('p');
  error.id = input.id + '-error';
  error.className = 'field-error';
  block.append(error);
  input.setAttribute('aria-describedby', [hint && hint.id, error.id].filter(Boolean).join(' '));
  input.addEventListener('input', requestFormatting);
});
typeButtons.forEach(button => button.addEventListener('click', () => applySourceType(button.dataset.type)));
styleButtons.forEach(button => button.addEventListener('click', () => setLibraryStyle(button.dataset.style)));
navLinks.forEach(link => link.addEventListener('click', () => {
  navLinks.forEach(item => {
    const selected = item === link;
    item.classList.toggle('is-active', selected);
    if (selected) item.setAttribute('aria-current', 'page');
    else item.removeAttribute('aria-current');
  });
}));
libraryFilter.addEventListener('input', () => {
  if (libraryPayload) renderLibrary(libraryPayload);
});
document.getElementById('results').addEventListener('click', event => {
  const copy = event.target.closest('.copy');
  if (copy && formatted) {
    const citation = formatted[copy.dataset.style];
    copyCitation(copy, copy.dataset.index === undefined ? citation : citation.intext[Number(copy.dataset.index)]);
  }
  const word = event.target.closest('.word');
  if (word && formatted) {
    const text = word.textContent;
    const key = text.replaceAll('’', "'").split("'")[0].replace(/[^\p{L}-]/gu, '').replace(/^-+|-+$/g, '').toLocaleLowerCase();
    const first = [...text].find(char => /\p{L}/u.test(char));
    if (key && first) {
      corrections[key] = first === first.toLocaleUpperCase() ? 'common' : 'proper';
      requestFormatting();
    }
  }
});
document.getElementById('forget').addEventListener('click', () => { corrections = {}; requestFormatting(); });
document.getElementById('clear').addEventListener('click', startNew);
document.getElementById('new-source').addEventListener('click', startNew);
document.getElementById('example').addEventListener('click', loadExample);
document.getElementById('save').addEventListener('click', saveSource);
document.getElementById('lookup').addEventListener('click', runLookup);
document.getElementById('identifier').addEventListener('keydown', event => { if (event.key === 'Enter') runLookup(); });
if (themeToggle) themeToggle.addEventListener('click', () => {
  const order = ['system', 'light', 'dark'];
  const current = document.documentElement.dataset.theme || 'system';
  applyTheme(order[(order.indexOf(current) + 1) % order.length]);
});
document.getElementById('cancel-lookup').addEventListener('click', () => document.getElementById('lookup-preview').close());
document.getElementById('replace-lookup').addEventListener('click', () => {
  if (lookupFields) fillFields(lookupFields);
  document.getElementById('lookup-preview').close();
});
document.getElementById('merge-lookup').addEventListener('click', () => {
  if (!lookupFields || lookupFields.source_type !== currentType) return;
  inputs.forEach(input => { if (!input.value && typeof lookupFields[input.name] === 'string') input.value = lookupFields[input.name]; });
  requestFormatting();
  document.getElementById('lookup-preview').close();
});
document.getElementById('copy-all').addEventListener('click', event => {
  if (formatted) copyCitation(event.currentTarget, {
    text: STYLES.map(style => style + '\n' + formatted[style].text).join('\n\n'),
    html: STYLES.map(style => '<p><strong>' + style + '</strong></p><p>' + formatted[style].html + '</p>').join(''),
  });
});
document.getElementById('copy-library').addEventListener('click', event => {
  if (libraryPayload) copyCitation(event.currentTarget, {text: libraryPayload.plain, html: libraryPayload.html});
});
document.getElementById('clear-library').addEventListener('click', async () => {
  const payload = await mutateLibrary('DELETE', {id: '*'});
  if (payload) { editingId = null; showEditingState(); persistDraft(); }
});
document.getElementById('undo-remove').addEventListener('click', async () => {
  const payload = await mutateLibrary('POST', {ids: removedIds}, '/api/library/restore');
  if (payload) {
    removedIds = [];
    document.getElementById('undo-bar').hidden = true;
    try { sessionStorage.removeItem(UNDO_KEY); } catch (error) { /* Optional. */ }
    syncButtons();
  }
});
document.getElementById('library-list').addEventListener('click', async event => {
  const edit = event.target.closest('.edit-source');
  if (edit && libraryPayload) {
    const entry = libraryPayload.entries.find(item => item.id === edit.dataset.id);
    if (entry) {
      fillFields(entry.fields, entry.id);
      document.getElementById('entry').scrollIntoView({block: 'start'});
      document.getElementById('title').focus({preventScroll: true});
    }
  }
  const remove = event.target.closest('.remove');
  if (remove) {
    const payload = await mutateLibrary('DELETE', {id: remove.dataset.id});
    if (payload && editingId === remove.dataset.id) { editingId = null; showEditingState(); persistDraft(); }
  }
});
document.getElementById('export-library').addEventListener('click', event => {
  if (event.currentTarget.getAttribute('aria-disabled') === 'true') event.preventDefault();
});
document.getElementById('print-library').addEventListener('click', () => {
  if (libraryPayload && libraryPayload.count) window.print();
});
document.addEventListener('keydown', event => {
  const save = document.getElementById('save');
  const dialogOpen = document.getElementById('lookup-preview').open;
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !save.disabled && !dialogOpen) {
    event.preventDefault();
    saveSource();
  }
});

// An explicitly empty draft stays empty. Older drafts can be restored once.
let draft = null;
try {
  const saved = sessionStorage.getItem(DRAFT_KEY);
  if (saved) draft = JSON.parse(saved);
  else {
    const previous = sessionStorage.getItem('citation-formatter-draft');
    if (previous) draft = {fields: JSON.parse(previous), editingId: null};
  }
  const savedUndo = JSON.parse(sessionStorage.getItem(UNDO_KEY) || '[]');
  if (Array.isArray(savedUndo) && savedUndo.every(id => typeof id === 'string')) removedIds = savedUndo;
} catch (error) { /* Ignore an unreadable browser draft. */ }
if (draft && draft.fields && typeof draft.fields === 'object') fillFields(draft.fields, draft.editingId || null);
else loadExample();
document.getElementById('undo-bar').hidden = !removedIds.length;
refreshLibrary();
