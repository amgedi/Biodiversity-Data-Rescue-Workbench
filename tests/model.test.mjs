import test from 'node:test';
import assert from 'node:assert/strict';
import {createProject, profile, issues, commit, repair, undo, validateProject} from '../web/model.mjs';
function project() {
  return createProject({name: 'test.csv', base64: 'YQ=='}, {sha256: 'a'.repeat(64), bytes: 1, headers: ['id', 'latitude', 'count'], originalHeaders: ['id', 'latitude', 'count'], rowWidths: [3, 3, 3], rows: [['001', ' 53 ', '0'], ['002', '153', 'NA'], ['002', '153', 'NA']], parsing: {format: 'delimited'}, notes: []});
}
test('flags coordinates, missing tokens, duplicates and context without modifying data', () => {
  const p = project(), before = structuredClone(p);
  const flags = issues(p);
  assert.ok(flags.some(i => i.title === 'Invalid latitude range' && i.rows.length === 2));
  assert.ok(flags.some(i => i.title === 'Exact duplicate rows'));
  assert.ok(flags.some(i => i.title.includes('Possible missing tokens')));
  assert.equal(profile(p)[2].missing, 0);
  assert.deepEqual(p, before);
});
test('repairs preserve original, blanks differ from zero, and sequential undo appends history', () => {
  const initial = project();
  let p = repair(initial, 'trim whitespace', 1, '', 'Reviewed source notes');
  p = repair(p, 'normalize missing token', 2, 'NA', 'Protocol defines NA as missing');
  assert.equal(p.rows[0][2], '0'); assert.equal(p.rows[1][2], '');
  assert.deepEqual(p.source, initial.source);
  p = undo(p); assert.equal(p.rows[1][2], 'NA');
  p = undo(p); assert.deepEqual(p.rows, initial.rows);
  assert.equal(p.audit.length, 5);
  assert.throws(() => undo(p), /no changes/);
  assert.deepEqual(initial.rows[0], ['001', ' 53 ', '0']);
});
test('duplicate removal is explicit, reversible, and no-op changes rejected', () => {
  const initial = project();
  const p = repair(initial, 'remove duplicate rows', 0, '', 'Verified duplicate import');
  assert.equal(p.rows.length, 2); assert.deepEqual(undo(p).rows, initial.rows);
  assert.throws(() => repair(initial, 'rename column', 0, 'count', 'Rename'), /unique/);
  assert.throws(() => repair(initial, 'trim whitespace', 0, '', 'Trim'), /No values/);
  assert.throws(() => repair(initial, 'normalize missing token', 2, '', 'Normalize'), /nonempty/);
});
test('metadata changes and undo preserve the dictionary and source', () => {
  const initial = project();
  const p = commit(initial, 'update metadata', 'Recovered protocol', next => {next.metadata.methods = 'Point counts, 30 minutes'; next.columns[2].description = 'Individuals observed';});
  assert.equal(validateProject(p), p);
  assert.deepEqual(undo(p).metadata, initial.metadata);
  const bad = structuredClone(p); bad.audit[1].before.rows = [['broken']];
  assert.throws(() => validateProject(bad), /supported/);
});
