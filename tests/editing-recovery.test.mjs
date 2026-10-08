import test from 'node:test';
import assert from 'node:assert/strict';
import {EditingSession} from '../web/edit-sessions.mjs';
test('losing edit authority immediately disables writes and retains a recovery copy',async()=>{
 const changed=[],notices=[];let retained=0;
 // Test the transition without constructing a browser session or opening dialogs.
 const session=Object.create(EditingSession.prototype);
 Object.assign(session,{timer:null,authority:{token:'old'},changed:value=>changed.push(value),notice:message=>notices.push(message),prepare:async()=>{retained++;}});
 const pending=session.lose('another window took over');assert.equal(session.authority,null);assert.deepEqual(changed,[true]);await pending;assert.equal(retained,1);assert.deepEqual(changed,[true,true]);
});
test('failed local recovery retention keeps the window read-only and reports keep-open guidance',async()=>{
 const notices=[],changed=[];const session=Object.create(EditingSession.prototype);
 Object.assign(session,{timer:null,authority:{token:'old'},changed:value=>changed.push(value),notice:message=>notices.push(message),prepare:async()=>{throw new Error('storage unavailable');}});
 await session.lose('revoked');assert.equal(session.authority,null);assert.deepEqual(changed,[true]);assert.ok(notices.some(message=>message.includes('keep this window open')));
});
