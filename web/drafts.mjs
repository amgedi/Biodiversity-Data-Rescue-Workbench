// One queue per immutable project ID. No delayed callback reads an active-project variable.
export class DraftQueue {
 constructor(send,{delay=()=>500,onError=()=>{},clientId='client'}={}){this.send=send;this.delay=delay;this.onError=onError;this.clientId=clientId;this.entries=new Map();}
 initialize(id,revision=0){const e=this.entries.get(id);if(!e||(e.paused&&!e.pending&&!e.running))this.entries.set(id,{revision,pending:null,running:null,timer:null,paused:false});}
 schedule(projectId,baseRevision,forms){this.initialize(projectId);const e=this.entries.get(projectId);e.pending={projectId,baseRevision,forms:structuredClone(forms)};clearTimeout(e.timer);if(e.paused)return;e.timer=setTimeout(()=>this.flush(projectId).catch(this.onError),this.delay());}
 pause(id){const e=this.entries.get(id);if(e){e.paused=true;clearTimeout(e.timer);}}
 retire(id){const e=this.entries.get(id);if(e?.running)throw Error('A draft write is still running.');if(e){clearTimeout(e.timer);e.pending=null;e.paused=true;}}
 async suspend(id){this.pause(id);const e=this.entries.get(id);if(!e)return null;clearTimeout(e.timer);if(e.running){try{await e.running;}catch{}}clearTimeout(e.timer);return structuredClone(e.pending);}
 rebase(id,revision=0){const e=this.entries.get(id);if(e?.running)throw Error('A draft write is still running.');if(e)clearTimeout(e.timer);this.entries.set(id,{revision,pending:null,running:null,timer:null,paused:false});}
 async flush(id){const e=this.entries.get(id);if(!e||e.paused)return;clearTimeout(e.timer);if(e.running){await e.running;return this.flush(id);}if(!e.pending)return;
  const value=e.pending;e.pending=null;
  e.running=this.send({...value,draftRevision:e.revision,clientId:this.clientId}).then(r=>{e.revision=r.draftRevision;}).catch(error=>{if(!e.pending)e.pending=value;throw error;}).finally(()=>{e.running=null;});
  await e.running;if(e.pending)await this.flush(id);
 }
 get pending(){return [...this.entries.values()].some(e=>e.pending||e.running);}
 async flushAll(){for(const id of this.entries.keys())await this.flush(id);}
}
// Committed operations include parsing and model updates, not merely fetch completion.
export class WriteBarrier {
 constructor(lock=()=>{}){this.lock=lock;this.pending=null;this.tasks=new Set();}
 run(operation){const previous=this.pending||Promise.resolve();if(!this.tasks.size)this.lock(true);const task=previous.then(operation);this.tasks.add(task);this.pending=task;return task.finally(()=>{this.tasks.delete(task);if(this.pending===task)this.pending=null;if(!this.tasks.size)this.lock(false);});}
 async flush(){const target=this.pending;if(target)await target;if(this.pending&&this.pending!==target)await this.flush();}
 get busy(){return this.tasks.size>0;}
}
