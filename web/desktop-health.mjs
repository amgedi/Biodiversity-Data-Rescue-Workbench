import {t,htmlMessage as h} from './i18n.mjs';
import {esc} from './components.mjs';
export function setupDesktopHealth({getProject,saveRecovery,notice}){
 const invoke=window.__TAURI_INTERNALS__?.invoke;if(!invoke)return;
 let panel=null,failed=false,lastStatus=null,busy=false;
 function show(status){lastStatus=status;if(panel)return;failed=true;panel=document.createElement('section');panel.className='engine-failure-panel';panel.setAttribute('role','alert');
  panel.innerHTML=`<h2>${h('v07x.engineStopped')}</h2><p data-engine-reason>${esc(status.message)}</p><p>${h('v07x.engineSafety')}</p><div class="small-actions"><button class="button secondary" data-engine-copy>${h('v07x.recoveryCopy')}</button><button class="button primary" data-engine-retry>${h('v07x.retry')}</button><button class="button secondary" data-engine-open disabled>${h('v07x.openRecovered')}</button><button class="button secondary" data-engine-logs>${h('v07x.openLogs')}</button><button class="button secondary" data-engine-diagnostics>${h('v07x.copyDiagnostics')}</button></div>`;
  document.querySelector('#main').before(panel);
  panel.querySelector('[data-engine-copy]').onclick=()=>saveRecovery();
  panel.querySelector('[data-engine-retry]').onclick=async()=>{try{await invoke('retry_engine');}catch(error){notice(String(error),true);}};
  panel.querySelector('[data-engine-open]').onclick=async()=>{try{const id=getProject()?.id;await invoke('open_workbench',{route:id?new URLSearchParams({view:'Project',project:id}).toString():''});}catch(error){notice(String(error),true);}};
  panel.querySelector('[data-engine-logs]').onclick=()=>invoke('open_logs').catch(error=>notice(String(error),true));
  panel.querySelector('[data-engine-diagnostics]').onclick=()=>navigator.clipboard.writeText(JSON.stringify({phase:lastStatus.phase,message:lastStatus.message},null,2)).catch(error=>notice(String(error),true));
 }
 async function check(){if(busy)return;busy=true;try{const status=await invoke('engine_status');lastStatus=status;if(status.failed)show(status);if(failed&&panel){panel.querySelector('[data-engine-reason]').textContent=status.message;panel.querySelector('[data-engine-open]').disabled=!status.ready;panel.querySelector('[data-engine-retry]').disabled=status.ready||status.phase==='Starting Workbench…';panel.querySelector('[data-engine-copy]').disabled=!getProject();}}catch(error){show({phase:'unavailable',message:String(error)});}finally{busy=false;}}
 setInterval(check,2000);check();
}
