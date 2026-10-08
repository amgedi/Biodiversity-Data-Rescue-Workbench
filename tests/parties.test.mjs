import test from 'node:test';import assert from 'node:assert/strict';import {newProject,change,undoRedo,validateProject} from '../web/project.mjs';
test('typed creator metadata is audited and survives undo/redo without changing source text',()=>{
 const original=newProject('Party metadata fixture');original.metadata.creator.value='Literal Creator';
 const changed=change(original,'recover project metadata','Explicit source evidence',p=>Object.assign(p.metadata.creator,{partyType:'Person',identifier:'https://example.invalid/person/001',status:'Confirmed'}));
 assert.equal(changed.metadata.creator.value,'Literal Creator');assert.equal(changed.audit[0].after.metadata.creator.partyType,'Person');const undone=undoRedo(changed);assert.equal(undone.metadata.creator.partyType,undefined);assert.equal(undone.metadata.creator.value,'Literal Creator');assert.equal(undoRedo(undone,true).metadata.creator.identifier,'https://example.invalid/person/001');assert.equal(validateProject(changed),changed);
});
test('typed parties reject unknown types and relative or malformed identifiers',()=>{
 for(const attrs of [{partyType:'Guess'},{identifier:'../someone'},{identifier:'https://example.invalid/has whitespace'},{identifier:45}]){const p=newProject();Object.assign(p.metadata.creator,attrs);assert.throws(()=>validateProject(p));}
});
