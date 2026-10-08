import test from 'node:test';
import assert from 'node:assert/strict';
import {createRescueSession} from '../web/rescue-assistant.mjs';
import {newProject} from '../web/project.mjs';

test('cancelling analysis aborts its detached worker and cannot publish a late result',async()=>{
 const p=newProject('Disposable cancellation test');
 p.resources.push({id:'fictional',name:'fictional.csv',sha256:'synthetic',base64:'',bytes:0});
 let signal,started;
 const ready=new Promise(resolve=>started=resolve);
 const session=createRescueSession({yieldStep:()=>Promise.resolve(),analyzer:(_snapshot,options)=>new Promise((resolve,reject)=>{
  signal=options.signal;started();signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});
 })});
 const before=JSON.stringify(p),run=session.run(p);await ready;session.cancel();await run;
 assert.equal(signal.aborted,true);assert.equal(session.state.status,'idle');assert.equal(session.state.result,null);assert.equal(JSON.stringify(p),before);
});

