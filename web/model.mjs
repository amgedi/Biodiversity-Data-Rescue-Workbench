import {t as structuralText,htmlMessage as structuralHtml} from './i18n.mjs';
export const TERMS = ['', 'occurrenceID', 'scientificName', 'eventDate', 'decimalLatitude', 'decimalLongitude', 'individualCount', 'samplingProtocol', 'samplingEffort', 'occurrenceStatus', 'locality', 'basisOfRecord', 'recordedBy'];
export const METADATA = [['title', 'Dataset title'], ['description', 'Description & purpose'], ['creator', 'Creator / custodian'], ['contact', 'Contact or persistent identifier'], ['license', 'License / permissions'], ['methods', 'Sampling methods & effort'], ['spatialCoverage', 'Spatial coverage & coordinate reference system'], ['temporalCoverage', 'Temporal coverage'], ['sensitivity', 'Sensitive data & sharing restrictions']];
export function typeOf(value) {
  const v = value.trim();
  if (!v) return 'empty';
  if (/^[+-]?\d+$/.test(v)) return 'integer';
  if (/^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$/.test(v)) return 'number';
  if (/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(v)) return 'date-like';
  if (/^(true|false)$/i.test(v)) return 'boolean';
  return 'text';
}
export function profile(project) {
  return project.headers.map((name, c) => {
    const values = project.rows.map(row => row[c]);
    const nonempty = values.filter(v => v.trim() !== '');
    const types = {};
    for (const value of nonempty) { const t = typeOf(value); types[t] = (types[t] || 0) + 1; }
    if (types.integer && types.number) { types.number += types.integer; delete types.integer; }
    const ranked = Object.entries(types).sort((a, b) => b[1] - a[1]);
    return {name, missing: values.length - nonempty.length, unique: new Set(nonempty).size, type: ranked[0]?.[0] || 'empty', types, examples: [...new Set(nonempty)].slice(0, 3), whitespace: values.filter(v => v !== v.trim()).length};
  });
}
export function issues(project) {
  const result = [];
  const add = (severity, title, detail, column = null, rows = []) => result.push({severity, title, detail, column, rows});
  const profiles = profile(project);
  for (const key of ['title', 'creator', 'license', 'methods', 'spatialCoverage', 'temporalCoverage']) {
    if (!project.metadata[key]?.trim()) add('context', `Missing ${METADATA.find(m => m[0] === key)[1].toLowerCase()}`, 'Document this context, or explicitly explain why it is unknown.');
  }
  const seen = new Set(), duplicateRows = [];
  project.rows.forEach((row, i) => { const key = JSON.stringify(row); if (seen.has(key)) duplicateRows.push(i); seen.add(key); });
  if (duplicateRows.length) add('review', 'Exact duplicate rows', `${duplicateRows.length} repeated rows. Repeated observations can be valid; confirm before removing.`, null, duplicateRows);
  const ragged = project.rowWidths?.filter(w => w !== project.originalHeaders.length).length || 0;
  if (ragged) add('review', 'Source row widths differ', `${ragged} source rows differ from the header width. Extra fields were retained and shorter rows padded with blanks. This import finding remains after repairs.`);
  for (const [c, p] of profiles.entries()) {
    const values = project.rows.map(r => r[c]);
    const rowsWhere = predicate => values.flatMap((v, i) => predicate(v) ? [i] : []);
    if (!project.columns[c]?.description?.trim()) add('context', `Define “${p.name}”`, 'Record what this field means, including collection conventions.', c);
    if (p.missing) add('info', `Blank values in ${p.name}`, `${p.missing} of ${values.length} values are blank or whitespace. Blank does not mean zero or absence.`, c, rowsWhere(v => !v.trim()));
    if (p.whitespace) add('review', `Whitespace in ${p.name}`, `${p.whitespace} values have leading or trailing whitespace.`, c, rowsWhere(v => v !== v.trim()));
    if (Object.keys(p.types).length > 1 && (p.types.integer || p.types.number || p.types['date-like'])) add('review', `Mixed types in ${p.name}`, `Observed types: ${Object.entries(p.types).map(([k, n]) => `${k} (${n})`).join(', ')}. Values are preserved as strings.`, c);
    const tokens = rowsWhere(v => /^(NA|N\/A|NULL|NONE|-9999|\?)$/i.test(v.trim()));
    if (tokens.length) add('review', `Possible missing tokens in ${p.name}`, `${tokens.length} values use a common missing-value marker. Confirm the convention before normalizing.`, c, tokens);
    const dates = rowsWhere(v => /^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}$/.test(v.trim()));
    if (dates.length) add('review', `Ambiguous dates in ${p.name}`, `${dates.length} dates need a documented day/month convention. No dates have been converted.`, c, dates);
    const garbled = rowsWhere(v => /\uFFFD|Ã.|Â./.test(v));
    if (garbled.length) add('review', `Possible encoding damage in ${p.name}`, 'Review unusual characters against the original. Detection can produce false positives.', c, garbled);
    const formulas = rowsWhere(v => /^[=+@]|^-(?!\d+(?:\.\d*)?(?:[eE][+-]?\d+)?$)/.test(v));
    if (formulas.length) add('review', `Spreadsheet formula-like text in ${p.name}`, 'Export preserves these values. Import the CSV as text in spreadsheet software.', c, formulas);
    const term = project.columns[c]?.term;
    const axis = term === 'decimalLatitude' || /^(latitude|lat|decimalLatitude)$/i.test(p.name) ? 'latitude' : term === 'decimalLongitude' || /^(longitude|lon|lng|decimalLongitude)$/i.test(p.name) ? 'longitude' : null;
    if (axis) {
      const limit = axis === 'latitude' ? 90 : 180;
      const invalid = rowsWhere(v => v.trim() && (!Number.isFinite(Number(v)) || Math.abs(Number(v)) > limit));
      if (invalid.length) add('review', `Invalid ${axis} range`, `${invalid.length} values fall outside ±${limit} or are not numeric. Confirm units and coordinate reference system.`, c, invalid);
    }
    if (term === 'individualCount' || /^count$/i.test(p.name)) {
      const invalid = rowsWhere(v => v.trim() && (!/^\d+$/.test(v.trim())));
      if (invalid.length) add('review', `Review counts in ${p.name}`, `${invalid.length} nonblank values are not nonnegative integers; confirm missing tokens or measurement conventions.`, c, invalid);
    }
    if (values.some(v => /^0\d+$/.test(v))) add('info', `Leading zeros in ${p.name}`, 'Keep these values as text when opening exports to preserve identifiers.', c);
  }
  return result;
}
export function createProject(source, imported) {
  const now = new Date().toISOString();
  return {version: 1, id: crypto.randomUUID(), createdAt: now, updatedAt: now, source: {...source, sha256: imported.sha256, bytes: imported.bytes}, headers: imported.headers, rows: imported.rows, rowWidths: imported.rowWidths, originalHeaders: imported.originalHeaders, parsing: imported.parsing, notes: imported.notes, metadata: Object.fromEntries(METADATA.map(([key]) => [key, ''])), columns: imported.headers.map(() => ({description: '', unit: '', term: '', missingToken: ''})), audit: [{id: crypto.randomUUID(), at: now, action: 'import', reason: 'Imported source with explicit parsing settings.', sourceHash: imported.sha256, parsing: imported.parsing, rowCount: imported.rows.length}]};
}
const snapshot = project => structuredClone({headers: project.headers, rows: project.rows, metadata: project.metadata, columns: project.columns});
export function commit(project, action, reason, change) {
  if (!reason.trim()) throw new Error(structuralText('v07.migrated.32f943889f3b'));
  const next = structuredClone(project), before = snapshot(project);
  change(next);
  const after = snapshot(next);
  if (JSON.stringify(before) === JSON.stringify(after)) throw new Error(structuralText('v07.migrated.327206371846'));
  const now = new Date().toISOString();
  next.updatedAt = now;
  next.audit.push({id: crypto.randomUUID(), at: now, action, reason: reason.trim(), before, after});
  return next;
}
export function undo(project) {
  const undone = new Set(project.audit.filter(e => e.action === 'undo').map(e => e.target));
  const event = [...project.audit].reverse().find(e => e.before && e.action !== 'undo' && !undone.has(e.id));
  if (!event) throw new Error(structuralText('v07.migrated.8c0d4dd30ecd'));
  const next = commit(project, 'undo', `Reverted: ${event.action}`, p => Object.assign(p, structuredClone(event.before)));
  next.audit.at(-1).target = event.id;
  return next;
}
export function repair(project, operation, column, value, reason) {
  return commit(project, operation, reason, p => {
    if (operation === 'trim whitespace') p.rows.forEach(r => {r[column] = r[column].trim();});
    else if (operation === 'normalize missing token') {
      if (!value) throw new Error(structuralText('v07.migrated.091a71c07436'));
      p.rows.forEach(r => {if (r[column] === value) r[column] = '';});
      p.columns[column].missingToken = value;
    } else if (operation === 'rename column') {
      if (!value.trim() || p.headers.some((h, i) => i !== column && h === value.trim())) throw new Error(structuralText('v07.migrated.e61f7f362a99'));
      p.headers[column] = value.trim();
    } else if (operation === 'remove duplicate rows') {
      const seen = new Set();
      p.rows = p.rows.filter(r => {const k = JSON.stringify(r); if (seen.has(k)) return false; seen.add(k); return true;});
    } else throw new Error(structuralText('v07.migrated.2df8d31e8c0b'));
  });
}
export function validateProject(p) {
  if (!p || p.version !== 1 || typeof p.id !== 'string' || !Array.isArray(p.headers) || !p.headers.length || p.headers.length > 250 || !p.headers.every(h => typeof h === 'string' && h.trim()) || new Set(p.headers).size !== p.headers.length || !Array.isArray(p.rows) || p.rows.length > 100000 || !p.rows.every(r => Array.isArray(r) && r.length === p.headers.length && r.every(v => typeof v === 'string')) || !p.source || typeof p.source.base64 !== 'string' || !/^[a-f0-9]{64}$/.test(p.source.sha256) || !Array.isArray(p.audit) || !Array.isArray(p.columns) || p.columns.length !== p.headers.length || !p.columns.every(c => c && ['description', 'unit', 'term', 'missingToken'].every(k => typeof c[k] === 'string')) || !p.metadata || !METADATA.every(([k]) => typeof p.metadata[k] === 'string') || !Array.isArray(p.originalHeaders) || !Array.isArray(p.rowWidths) || !Array.isArray(p.notes) || !p.parsing) throw new Error(structuralText('v07.migrated.0d13372bd7f4'));
  // Imported audit snapshots are untrusted; malformed ones must never drive undo.
  for (const e of p.audit) {
    if (!e || typeof e.action !== 'string' || typeof e.reason !== 'string' || typeof e.at !== 'string') throw new Error(structuralText('v07.migrated.785fe1c7eb7b'));
    for (const s of [e.before, e.after].filter(Boolean)) {
      validateProject({...p, ...s, audit: []});
    }
  }
  return p;
}
