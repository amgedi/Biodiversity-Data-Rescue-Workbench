import test from 'node:test';
import assert from 'node:assert/strict';
import {relationshipMetrics,packageWorkspace,translationStrip} from '../web/workflow-experience.mjs';
const relation={fromTable:'child',fromField:'key',toTable:'parent',toField:'key'};
test('relationship display preserves literal zero, blank and leading-zero distinctions',()=>{
 const project={tables:[{id:'child',headers:['key'],rows:[['0'],[''],['01'],['1'],['NA']]},{id:'parent',headers:['key'],rows:[['0'],['1'],['1'],['']]}]};
 const before=structuredClone(project);
 assert.deepEqual(relationshipMetrics(project,relation),{matched:2,orphans:2,blank:1,duplicates:1,total:4});
 assert.deepEqual(project,before);
});
test('missing relationship field is unavailable rather than a fabricated zero',()=>{
 assert.equal(relationshipMetrics({tables:[{id:'child',headers:['renamed'],rows:[]},{id:'parent',headers:['key'],rows:[]}]},relation),null);
});
test('duplicate display counts extra occurrences, excluding blank parent keys',()=>{
 assert.deepEqual(relationshipMetrics({tables:[{id:'child',headers:['key'],rows:[['a']]},{id:'parent',headers:['key'],rows:[['a'],['a'],['a'],[''],['']]}]},relation),{matched:1,orphans:0,blank:0,duplicates:2,total:1});
});
test('translation presentation uses preserved originals and escapes untrusted values',()=>{
 const table={columns:[{sourceIndex:0,originalName:'<original>',description:'<meaning>',status:'Unknown'}],originalTable:{headers:['<original>'],rows:[['6/7/08'],['0'],['']]},rows:[['changed']]};
 const project={tables:[table]};const before=structuredClone(project);const html=translationStrip(project,table,0);
 assert.match(html,/6\/7\/08/);assert.match(html,/&lt;meaning&gt;/);assert.doesNotMatch(html,/>changed</);assert.deepEqual(project,before);
});
