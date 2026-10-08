import {t as structuralText,htmlMessage as structuralHtml} from './i18n.mjs';
import {METADATA, TERMS, profile, issues, createProject, commit, undo, repair, validateProject} from './model.mjs';

const $ = selector => document.querySelector(selector);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
let db, projects = [], current = null, tab = 'overview', pending = null, source = null, page = 0, query = '', issueRows = null, editing = null, busy = false;
let dirty = false;
const date = value => new Date(value).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'});
const title = p => p.metadata.title || p.source.name;
const formatBytes = n => n > 1048576 ? `${(n / 1048576).toFixed(1)} MiB` : `${(n / 1024).toFixed(1)} KiB`;
function notify(message, error = false) { $('#notice').textContent = message; $('#notice').className = error ? 'visible error' : 'visible'; clearTimeout(notify.timer); notify.timer = setTimeout(() => {$('#notice').className = '';}, 6500); }
function request(store, mode, work) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode); const result = work(tx.objectStore(store));
    tx.oncomplete = () => resolve(result.result); tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error);
  });
}
async function init() {
  try {
    db = await new Promise((resolve, reject) => { const r = indexedDB.open('biodiversity-rescue', 1); r.onupgradeneeded = () => r.result.createObjectStore('projects', {keyPath: 'id'}); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
    projects = await request('projects', 'readonly', s => s.getAll());
  } catch { notify('Browser storage is unavailable. You can still work, but download project backups to preserve changes.', true); }
  renderSide(); renderHome();
}
async function save(next) {
  current = next; dirty = false;
  const index = projects.findIndex(p => p.id === next.id);
  if (index < 0) projects.push(next); else projects[index] = next;
  if (db) { try { await request('projects', 'readwrite', s => s.put(next)); notify('Saved on this computer.'); } catch { notify('Local save failed, possibly due to storage limits. Download a project backup now.', true); } }
  else notify('Working in memory. Download a project backup to keep this work.', true);
  renderSide();
}
async function api(path, body) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) { const result = await response.json(); throw new Error(result.error || 'Local request failed.'); }
  return response;
}
function download(bytes, name, mime) {
  const url = URL.createObjectURL(new Blob([bytes], {type: mime}));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
}
function safeName() {return title(current).replace(/[^\p{L}\p{N}_-]+/gu, '-').slice(0, 80) || 'biodiversity-rescue';}
function leave() {if (dirty && !confirm(structuralText('v07.migrated.df208af2a337'))) return false; dirty = false; return true;}
function renderSide() {
  $('#project-list').innerHTML = [...projects].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).map(p => `<button class="project-item ${current?.id === p.id ? 'selected' : ''}" data-project="${esc(p.id)}"><span>◌</span>${esc(title(p))}</button>`).join('');
  $('#home-button').classList.toggle('active', !current);
}
function renderHome() {
  current = null; renderSide();
  $('#main').innerHTML = `<section class="welcome"><div class="eyebrow">${structuralHtml('v07.migrated.e33125e2ace9')}</div><h1>${structuralHtml('v07.migrated.7449dc81f87c')}<br>${structuralHtml('v07.migrated.f5cb286bd2fa')}</h1><p>${structuralHtml('v07.migrated.4e22b4316be6')}</p><div class="welcome-actions"><button class="button primary" data-action="import">＋ Import a dataset</button><button class="button secondary" data-action="sample">${structuralHtml('v07.migrated.03a43f0b3708')}</button></div><div class="welcome-detail">${structuralHtml('v07.migrated.af11d3359ba0')}<span>•</span> ORIGINALS PRESERVED <span>•</span> OPEN FORMATS</div><div class="botanical" aria-hidden="true"><svg viewBox="0 0 300 310"><path d="M145 285 C130 220 170 160 143 48 M148 224 C88 225 59 192 52 154 C99 151 131 178 148 224 M149 185 C204 185 244 152 250 117 C203 119 162 140 149 185 M151 138 C102 133 84 104 83 70 C121 79 146 99 151 138 M145 92 C182 89 207 60 204 28 C172 38 151 59 145 92"/><path class="vein" d="M145 285 C130 220 170 160 143 48 M148 224 L72 171 M149 185 L229 133 M151 138 L96 88 M145 92 L194 45"/><circle cx="239" cy="239" r="31"/><path class="vein" d="M225 239 l10 10 19-23"/></svg></div></section><section class="workflow-grid"><article><span class="step-number">01</span><h3>${structuralHtml('v07.migrated.9660e9cedafb')}</h3><p>${structuralHtml('v07.migrated.e759a8aeb36f')}</p></article><article><span class="step-number">02</span><h3>${structuralHtml('v07.migrated.1e3ae080d1d3')}</h3><p>${structuralHtml('v07.migrated.d5dffabf7da7')}</p></article><article><span class="step-number">03</span><h3>${structuralHtml('v07.migrated.23112e0258f5')}</h3><p>${structuralHtml('v07.migrated.4083a4596c20')}</p></article></section><section class="recent-section"><div class="section-heading"><h2>${structuralHtml('v07.migrated.f35c3c1c573a')}</h2><span class="muted">${projects.length} saved locally</span></div>${projects.length ? `<div class="recent-grid">${projects.map(p => `<button class="recent-card" data-project="${esc(p.id)}"><span class="file-badge">${esc(p.parsing.format.toUpperCase())}</span><h3>${esc(title(p))}</h3><p>${p.rows.length.toLocaleString()} rows · ${p.headers.length} columns</p><small>Updated ${esc(date(p.updatedAt))} →</small></button>`).join('')}</div>` : '<div class="empty-projects"><span>◌</span><div><strong>A place for data worth rescuing</strong><p>Your projects will appear here. Start with a file or explore the woodland survey sample.</p></div></div>'}</section>`;
}
function shell(content) {
  const p = current;
  $('#main').innerHTML = `<div class="project-heading"><div><div class="eyebrow">${structuralHtml('v07.migrated.cc73d657f6ee')}<span class="source-tag">${esc(p.parsing.format.toUpperCase())}</span></div><h1>${esc(title(p))}</h1><p class="muted">${esc(p.source.name)} · ${formatBytes(p.source.bytes)} · Original preserved</p></div><button class="button secondary" data-action="backup">↓ Project backup</button></div><nav class="tabs" aria-label="Project sections">${[['overview', 'Overview'], ['data', 'Data & repairs'], ['metadata', 'Metadata'], ['history', 'History'], ['export', 'Export']].map(([key, name]) => `<button data-tab="${key}" class="${tab === key ? 'active' : ''}" ${tab === key ? 'aria-current="page"' : ''}>${name}</button>`).join('')}</nav>${content}`;
}
function renderProject() {
  if (!current) return renderHome();
  renderSide();
  if (tab === 'overview') renderOverview();
  else if (tab === 'data') renderData();
  else if (tab === 'metadata') renderMetadata();
  else if (tab === 'history') renderHistory();
  else renderExport();
}
function renderOverview() {
  const p = current, found = issues(p), review = found.filter(i => i.severity === 'review'), context = found.filter(i => i.severity === 'context');
  const blank = profile(p).reduce((sum, c) => sum + c.missing, 0);
  shell(`<div class="stats-grid"><article><span>${structuralHtml('v07.migrated.55a01b6f6f75')}</span><strong>${p.rows.length.toLocaleString()}<small>${structuralHtml('v07.migrated.bc51e9e65d79')}</small></strong><p>${p.headers.length} columns · literal values</p></article><article><span>${structuralHtml('v07.migrated.d83f48e8d0c5')}</span><strong>${review.length}<small>${structuralHtml('v07.migrated.2934fb49d6b3')}</small></strong><p>${structuralHtml('v07.migrated.631e4a4a0250')}</p></article><article><span>${structuralHtml('v07.migrated.b5e9fcf01aff')}</span><strong>${context.length}<small>${structuralHtml('v07.migrated.bfe5d697162d')}</small></strong><p>${structuralHtml('v07.migrated.cce073c0f0fd')}</p></article><article><span>${structuralHtml('v07.migrated.c6549aa3bbbe')}</span><strong>${blank.toLocaleString()}<small>${structuralHtml('v07.migrated.57104c57fbe0')}</small></strong><p>${structuralHtml('v07.migrated.1210bbb78fef')}</p></article></div><div class="overview-layout"><section class="panel"><div class="section-heading"><div><h2>${structuralHtml('v07.migrated.31bbad770444')}</h2><p class="muted">${structuralHtml('v07.migrated.610850285f5b')}</p></div><span class="count-pill">${found.length}</span></div><div class="issue-list">${found.length ? found.map((i, n) => `<article class="issue"><span class="issue-icon ${i.severity}">${i.severity === 'context' ? '◌' : i.severity === 'review' ? '!' : 'i'}</span><div><strong>${esc(i.title)}</strong><p>${esc(i.detail)}</p></div><button class="text-button" data-issue="${n}">${i.severity === 'context' ? 'Document' : i.rows.length ? 'Review rows' : 'Review'} →</button></article>`).join('') : '<p class="empty">No rule-based flags remain. Review the scientific context before sharing.</p>'}</div></section><aside class="panel provenance-panel"><div class="eyebrow">${structuralHtml('v07.migrated.142c12b0383a')}</div><h2>${structuralHtml('v07.migrated.2b0ddd8f8a9a')}</h2><p>${structuralHtml('v07.migrated.f4beb0290099')}</p><dl><dt>${structuralHtml('v07.migrated.98233428db30')}</dt><dd class="hash">${esc(p.source.sha256)}</dd><dt>${structuralHtml('v07.migrated.321f179c80ba')}</dt><dd>${esc(date(p.createdAt))}</dd><dt>${structuralHtml('v07.migrated.3bdead763923')}</dt><dd>${esc(p.parsing.encoding)}${p.parsing.delimiter ? ` · ${p.parsing.delimiter === '\t' ? 'Tab' : esc(p.parsing.delimiter)}` : ` · ${esc(p.parsing.sheet)}`}</dd><dt>${structuralHtml('v07.migrated.4d7cc7ed47a9')}</dt><dd>${p.parsing.headerRow}</dd></dl><button class="button secondary full" data-action="original">↓ Download original</button>${p.notes.length ? `<div class="import-notes"><strong>${structuralHtml('v07.migrated.7de8d0b3ebba')}</strong>${p.notes.map(n => `<p>${esc(n)}</p>`).join('')}</div>` : ''}</aside></div>`);
}
function selectedRows() {return current.rows.map((row, index) => ({row, index})).filter(({row, index}) => (!issueRows || issueRows.includes(index)) && (!query || row.some(v => v.toLowerCase().includes(query.toLowerCase()))));}
function renderData() {
  const profiles = profile(current), filtered = selectedRows(), pages = Math.max(1, Math.ceil(filtered.length / 50)); page = Math.min(page, pages - 1);
  shell(`<section class="panel data-panel"><div class="section-heading"><div><h2>${structuralHtml('v07.migrated.00738a2d006a')}</h2><p class="muted">${structuralHtml('v07.migrated.6e9c527f8b38')}</p></div><button class="button secondary" data-action="undo">↶ Undo last change</button></div><div class="table-toolbar"><label class="search-label">${structuralHtml('v07.migrated.c98c924dddbe')}<input id="search" type="search" placeholder="Find a taxon, site, identifier…" value="${esc(query)}"></label><span class="muted">${filtered.length.toLocaleString()} matching rows</span>${issueRows ? '<button class="text-button" data-action="clear-filter">Clear issue filter ×</button>' : ''}</div><div class="table-scroll" tabindex="0" aria-label="Working data table. Scroll horizontally for more columns."><table><caption class="sr-only">Working dataset, rows ${page * 50 + 1} through ${Math.min(filtered.length, (page + 1) * 50)}</caption><thead><tr><th scope="col">${structuralHtml('v07.row')}</th>${profiles.map(c => `<th scope="col"><strong>${esc(c.name)}</strong><span class="column-type">${esc(c.type)} · ${c.missing} blank</span></th>`).join('')}</tr></thead><tbody>${filtered.slice(page * 50, (page + 1) * 50).map(({row, index}) => `<tr><th scope="row">${index + 1}</th>${row.map((v, c) => `<td><button class="cell ${v === '' ? 'blank-cell' : ''}" data-cell="${index}:${c}" aria-label="Edit row ${index + 1}, ${esc(current.headers[c])}, ${esc(v || 'blank')}">${v === '' ? '<span>empty</span>' : esc(v)}</button></td>`).join('')}</tr>`).join('')}</tbody></table></div><details class="column-profiles"><summary>${structuralHtml('v07.migrated.1ba142460d3c')}</summary><div class="table-scroll"><table><thead><tr><th>${structuralHtml('v07.migrated.3fdc9a587693')}</th><th>${structuralHtml('v07.migrated.2581af463a8a')}</th><th>${structuralHtml('v07.migrated.2c3d371cbfd3')}</th><th>${structuralHtml('v07.migrated.b598ee7ee036')}</th><th>${structuralHtml('v07.migrated.e68ee04dff59')}</th></tr></thead><tbody>${profiles.map(c => `<tr><td>${esc(c.name)}</td><td>${esc(c.type)}</td><td>${c.missing}</td><td>${c.unique}</td><td>${c.examples.map(esc).join(" · ")}</td></tr>`).join("")}</tbody></table></div></details><div class="pagination"><button class="button secondary" data-action="prev" ${page === 0 ? 'disabled' : ''}>← Previous</button><span>Page ${page + 1} of ${pages} · 50 rows per page</span><button class="button secondary" data-action="next" ${page === pages - 1 ? 'disabled' : ''}>${structuralHtml('v07.migrated.bcf0489a7b45')}</button></div></section><section class="panel repair-panel"><div><div class="eyebrow">${structuralHtml('v07.migrated.67649f55ce50')}</div><h2>${structuralHtml('v07.migrated.544b0ce877c8')}</h2><p class="muted">${structuralHtml('v07.migrated.7b1cf10ed84e')}<br>${structuralHtml('v07.migrated.38e55062acc1')}</p></div><form id="repair-form"><div class="form-grid"><label>${structuralHtml('v07.migrated.3fdc9a587693')}<select id="repair-column">${current.headers.map((h, i) => `<option value="${i}">${esc(h)}</option>`).join('')}</select></label><label>${structuralHtml('v07.migrated.0f044feb6ca7')}<select id="repair-operation"><option>${structuralHtml('v07.migrated.2b1509ecb2ac')}</option><option>${structuralHtml('v07.migrated.34bbecceae34')}</option><option>${structuralHtml('v07.migrated.795770cc93d0')}</option><option>${structuralHtml('v07.migrated.cf852828e96f')}</option></select></label><label id="repair-value-label">${structuralHtml('v07.migrated.ee93178ad8b1')}<input id="repair-value" placeholder="Used for rename or missing-token repair"></label><label>${structuralHtml('v07.migrated.f81ab834de5f')}<input id="repair-reason" required placeholder="Document why this repair is justified"></label></div><p id="repair-preview" class="repair-preview"></p><button class="button primary">${structuralHtml('v07.migrated.4d0ab2d46cc2')}</button></form></section>`);
  $('#search').addEventListener('input', e => {query = e.target.value; page = 0; const caret = e.target.selectionStart; renderData(); $('#search').focus(); $('#search').setSelectionRange(caret, caret);});
  $('#repair-form').addEventListener('submit', async e => {e.preventDefault(); try {const next = repair(current, $('#repair-operation').value, Number($('#repair-column').value), $('#repair-value').value, $('#repair-reason').value); await save(next); issueRows = null; renderProject();} catch (error) {notify(error.message, true);}});
  const preview = () => {
    const op = $('#repair-operation').value, c = Number($('#repair-column').value), value = $('#repair-value').value;
    const count = op === 'trim whitespace' ? current.rows.filter(r => r[c] !== r[c].trim()).length : op === 'normalize missing token' ? current.rows.filter(r => r[c] === value).length : op === 'remove duplicate rows' ? current.rows.length - new Set(current.rows.map(r => JSON.stringify(r))).size : (value.trim() && value.trim() !== current.headers[c] ? 1 : 0);
    $('#repair-preview').textContent = `${count} ${op === 'rename column' ? 'column name' : op === 'remove duplicate rows' ? 'duplicate rows' : 'cells'} would change.${op === 'remove duplicate rows' ? ' Repeated observations can be valid. Check the records before applying.' : ''}`;
    $('#repair-value').disabled = !['normalize missing token', 'rename column'].includes(op); $('#repair-column').disabled = op === 'remove duplicate rows';
  };
  $('#repair-form').addEventListener('input', preview); preview();
}
function renderMetadata() {
  const columnProfiles = profile(current);
  shell(`<form id="metadata-form"><section class="panel"><div class="section-heading"><div><h2>${structuralHtml('v07.migrated.ad97a5794ed7')}</h2><p class="muted">${structuralHtml('v07.migrated.ff4324521d29')}</p></div><button class="button primary">${structuralHtml('v07.migrated.06d1ae6bcb25')}</button></div><div class="form-grid metadata-grid">${METADATA.map(([key, label]) => `<label>${esc(label)}${['description', 'methods', 'sensitivity', 'spatialCoverage'].includes(key) ? `<textarea name="${key}" rows="3" placeholder="Add context, or describe what remains unknown">${esc(current.metadata[key])}</textarea>` : `<input name="${key}" value="${esc(current.metadata[key])}" placeholder="Add context, or describe what remains unknown">`}</label>`).join('')}</div></section><section class="panel"><div class="section-heading"><div><h2>${structuralHtml('v07.migrated.b0b53d52a4cf')}</h2><p class="muted">${structuralHtml('v07.migrated.8ff165e78ec9')}</p></div></div><div class="dictionary">${current.headers.map((h, c) => `<article class="dictionary-row"><div><h3>${esc(h)}</h3><span class="column-type">${esc(columnProfiles[c].type)} · stored as text</span></div><label>${structuralHtml('v07.migrated.9813fafb098c')}<textarea name="column-${c}-description" rows="2" placeholder="What does this value represent?">${esc(current.columns[c].description)}</textarea></label><label>${structuralHtml('v07.migrated.9fb6669a77ea')}<input name="column-${c}-unit" value="${esc(current.columns[c].unit)}" placeholder="e.g. minutes"></label><label>${structuralHtml('v07.migrated.05c879475607')}<input name="column-${c}-missingToken" value="${esc(current.columns[c].missingToken)}" placeholder="e.g. NA"></label><label>${structuralHtml('v07.migrated.263cd7864913')}<select name="column-${c}-term">${[...new Set([...TERMS, current.columns[c].term])].map(t => `<option value="${esc(t)}" ${current.columns[c].term === t ? 'selected' : ''}>${esc(t || 'Not mapped')}</option>`).join('')}</select></label></article>`).join('')}</div></section><section class="panel save-panel"><label>${structuralHtml('v07.migrated.e2528333e0e7')}<input name="reason" required placeholder="e.g. Recovered methods from the 2023 survey protocol"></label><button class="button primary">${structuralHtml('v07.migrated.06d1ae6bcb25')}</button></section></form>`);
  $('#metadata-form').addEventListener('input', () => {dirty = true;});
  $('#metadata-form').addEventListener('submit', async e => {
    e.preventDefault(); const form = new FormData(e.target);
    try {await save(commit(current, 'update metadata', form.get('reason'), p => {METADATA.forEach(([k]) => {p.metadata[k] = form.get(k);}); p.columns.forEach((column, c) => {['description', 'unit', 'term', 'missingToken'].forEach(k => {column[k] = form.get(`column-${c}-${k}`);});});})); renderProject();} catch (error) {notify(error.message, true);}
  });
}
function renderHistory() {
  shell(`<section class="panel"><div class="section-heading"><div><h2>${structuralHtml('v07.migrated.99e56c8dd189')}</h2><p class="muted">${structuralHtml('v07.migrated.32328858b4bc')}</p></div><button class="button secondary" data-action="undo">↶ Undo last change</button></div><ol class="timeline">${[...current.audit].reverse().map((e, i) => `<li><span class="timeline-dot"></span><div class="timeline-heading"><h3>${esc(e.action)}</h3><time>${esc(date(e.at))}</time></div><p>${esc(e.reason)}</p>${e.before ? `<small>${e.before.rows.length} → ${e.after.rows.length} rows · Working table and metadata snapshots retained</small>` : `<small>${structuralHtml('v07.migrated.b384167eba1c')}<span class="hash">${esc(e.sourceHash)}</span></small>`}<span class="event-number">EVENT ${current.audit.length - i}</span></li>`).join('')}</ol></section>`);
}
function renderExport() {
  const found = issues(current);
  shell(`<div class="export-layout"><section class="panel export-main"><div class="eyebrow">${structuralHtml('v07.migrated.2129ecf3371c')}</div><h2>${structuralHtml('v07.migrated.f1be1fe65f1d')}</h2><p>${structuralHtml('v07.migrated.82bcbf8cec6a')}</p><div class="package-list">${[['cleaned.csv', 'Working data · UTF-8 · literal string values'], ['metadata.json', 'Dataset context, column dictionary & import settings'], ['datapackage.json', 'Open tabular data package descriptor'], ['quality-report.json', 'Unresolved review flags & column profiles'], ['audit.json', 'Changes, reasons & before/after snapshots'], ['original/', 'Immutable source file, byte for byte'], ['project.biorescue.json', 'Portable, reopenable project backup'], ['checksums.sha256 + README.txt', 'Integrity checks & safe reuse guidance']].map(([name, detail]) => `<div><span>✓</span><div><strong>${name}</strong><p>${detail}</p></div></div>`).join('')}</div><button class="button primary" data-action="export">↓ Download rescue package</button><button class="text-button" data-action="backup">${structuralHtml('v07.migrated.4785c5980ac2')}</button></section><aside class="panel"><h2>${structuralHtml('v07.migrated.6059764903b0')}</h2><p class="muted">${found.filter(i => i.severity === 'review').length} data review flags · ${found.filter(i => i.severity === 'context').length} missing context fields.</p><p>${structuralHtml('v07.migrated.46bd8e0ae2ae')}</p><p>${structuralHtml('v07.migrated.0176993cc875')}<strong>${structuralHtml('v07.migrated.982d9e3eb996')}</strong> to preserve IDs and prevent formula execution.</p><div class="callout">${structuralHtml('v07.migrated.f2178d7245da')}</div><button class="button secondary full" data-tab="metadata">${structuralHtml('v07.migrated.9b23baa4045c')}</button></aside></div>`);
}
function openImport() {
  $('#source-file').required = true;
  pending = null; source = null; $('#source-file').value = ''; $('#encoding').value = 'auto'; $('#delimiter').value = 'auto'; $('#header-row').value = '1'; $('#sheet').innerHTML = '<option value="">First worksheet</option>'; $('#import-preview').innerHTML = ''; $('#create-button').disabled = true; $('#import-dialog').showModal();
}
async function readSource(file) {
  if (file.size > 20 * 1024 * 1024) throw new Error(structuralText('v07.migrated.d7bf958554fa'));
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = ''; for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
  return {name: file.name, base64: btoa(binary)};
}
async function inspectSource() {
  if (busy) return;
  try {
    busy = true; $('#inspect-button').disabled = true; $('#create-button').disabled = true;
    for (const selector of ['#source-file', '#encoding', '#delimiter', '#header-row', '#sheet']) $(selector).disabled = true;
    if (!source) {if (!$('#source-file').files[0]) throw new Error(structuralText('v07.migrated.64a998bf9ae5')); source = await readSource($('#source-file').files[0]);}
    $('#import-preview').innerHTML = '<p class="muted">Reading file and checking its structure…</p>';
    const selectedSheet = $('#sheet').value;
    pending = await (await api('/api/inspect', {source, options: {encoding: $('#encoding').value, delimiter: $('#delimiter').value === 'tab' ? '\t' : $('#delimiter').value, headerRow: Number($('#header-row').value), sheet: selectedSheet}})).json();
    if (pending.parsing.sheets) $('#sheet').innerHTML = pending.parsing.sheets.map(s => `<option value="${esc(s)}" ${pending.parsing.sheet === s ? 'selected' : ''}>${esc(s)}</option>`).join('');
    $('#import-preview').innerHTML = `<div class="preview-summary"><strong>${esc(source.name)}</strong><span>${pending.rows.length.toLocaleString()} rows · ${pending.headers.length} columns · ${esc(pending.parsing.encoding)}${pending.parsing.delimiter ? ` · ${pending.parsing.delimiter === '\t' ? 'Tab' : esc(pending.parsing.delimiter)}` : ''}</span></div>${pending.notes.map(n => `<p class="callout">${esc(n)}</p>`).join('')}<div class="table-scroll"><table><thead><tr>${pending.headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${pending.rows.slice(0, 5).map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="muted">${structuralHtml('v07.migrated.75140137e42a')}<span class="hash">${pending.sha256}</span></p>`;
    $('#create-button').disabled = false;
  } catch (error) {pending = null; $('#import-preview').textContent = error.message; notify(error.message, true);}
  finally {busy = false; $('#inspect-button').disabled = false; for (const selector of ['#source-file', '#encoding', '#delimiter', '#header-row', '#sheet']) $(selector).disabled = false;}
}
$('#source-file').addEventListener('change', () => {source = null; pending = null; inspectSource();});
for (const selector of ['#encoding', '#delimiter', '#header-row', '#sheet']) $(selector).addEventListener('change', () => {pending = null; $('#create-button').disabled = true; $('#import-preview').innerHTML = '<p class="muted">Settings changed. Inspect the file again to update the preview.</p>';});
$('#inspect-button').addEventListener('click', inspectSource);
$('#close-import').addEventListener('click', () => {if (!busy) $('#import-dialog').close();});
$('#import-dialog').addEventListener('cancel', e => {if (busy) e.preventDefault();});
$('#import-form').addEventListener('submit', async e => {e.preventDefault(); if (!pending || busy) return; try {await save(createProject(source, pending)); tab = 'overview'; page = 0; query = ''; issueRows = null; $('#import-dialog').close(); renderProject();} catch (error) {notify(error.message, true);}});
$('#new-button').addEventListener('click', () => {if (leave()) openImport();});
$('#home-button').addEventListener('click', () => {if (leave()) renderHome();});
$('#restore-button').addEventListener('click', () => {if (leave()) $('#backup-file').click();});
$('#backup-file').addEventListener('change', async e => {
  try {
    const file = e.target.files[0]; if (!file) return; if (file.size > 150 * 1024 * 1024) throw new Error(structuralText('v07.migrated.13047ea34247'));
    const restored = validateProject(JSON.parse(await file.text()));
    const binary = atob(restored.source.base64); if (binary.length > 20 * 1024 * 1024) throw new Error(structuralText('v07.migrated.af975c8232fd'));
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', Uint8Array.from(binary, c => c.charCodeAt(0))))].map(b => b.toString(16).padStart(2, '0')).join('');
    if (hash !== restored.source.sha256) throw new Error(structuralText('v07.migrated.db3c2c4c9f10'));
    if (projects.some(p => p.id === restored.id)) restored.id = crypto.randomUUID();
    await save(restored); tab = 'overview'; page = 0; query = ''; issueRows = null; renderProject();
  } catch (error) {notify(error.message, true);} finally {e.target.value = '';}
});
$('#close-edit').addEventListener('click', () => $('#edit-dialog').close());
$('#edit-form').addEventListener('submit', async e => {e.preventDefault(); try {const [r, c] = editing; await save(commit(current, 'edit cell', $('#edit-reason').value, p => {p.rows[r][c] = $('#edit-value').value;})); $('#edit-dialog').close(); renderProject();} catch (error) {notify(error.message, true);}});
document.addEventListener('click', async e => {
  const button = e.target.closest('button'); if (!button) return;
  try {
    if (button.dataset.project) {if (!leave()) return; current = projects.find(p => p.id === button.dataset.project); tab = 'overview'; query = ''; page = 0; issueRows = null; renderProject();}
    if (button.dataset.tab) {if (!leave()) return; tab = button.dataset.tab; renderProject(); window.scrollTo(0, 0);}
    if (button.dataset.issue !== undefined) {const issue = issues(current)[Number(button.dataset.issue)]; tab = issue.severity === 'context' ? 'metadata' : 'data'; page = 0; query = ''; issueRows = issue.rows.length ? issue.rows : null; renderProject();}
    if (button.dataset.cell) {editing = button.dataset.cell.split(':').map(Number); const [r, c] = editing; $('#edit-context').textContent = `Working row ${r + 1} · ${current.headers[c]}`; $('#edit-value').value = current.rows[r][c]; $('#edit-reason').value = ''; $('#edit-dialog').showModal();}
    const action = button.dataset.action;
    if (action === 'import' && leave()) openImport();
    if (action === 'sample') {openImport(); const response = await fetch('/sample.csv'); const file = new File([await response.text()], 'woodland-survey.csv', {type: 'text/csv'}); source = await readSource(file); $('#source-file').required = false; await inspectSource();}
    if (action === 'backup') {download(JSON.stringify(current, null, 2), `${safeName()}.biorescue.json`, 'application/json'); notify('Project backup downloaded. Keep it somewhere safe.');}
    if (action === 'original') download(Uint8Array.from(atob(current.source.base64), c => c.charCodeAt(0)), current.source.name, 'application/octet-stream');
    if (action === 'undo') {await save(undo(current)); issueRows = null; renderProject();}
    if (action === 'clear-filter') {issueRows = null; page = 0; renderData();}
    if (action === 'prev' || action === 'next') {page += action === 'next' ? 1 : -1; renderData();}
    if (action === 'export') {button.disabled = true; button.textContent = 'Packaging source, data & metadata…'; try {download(await (await api('/api/export', {...current, qualityReview: issues(current), columnProfiles: profile(current)})).arrayBuffer(), `${safeName()}-rescue.zip`, 'application/zip'); notify('Rescue package downloaded.');} finally {renderExport();}}
  } catch (error) {notify(error.message, true);}
});
window.addEventListener('beforeunload', e => {if (dirty) {e.preventDefault(); e.returnValue = '';}});
init();
