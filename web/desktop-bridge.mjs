import {t} from './i18n.mjs';
import {applyPreferences} from './preferences.mjs';
import {checkImportSelection} from './import-discovery.mjs';
const native=()=>window.__TAURI_INTERNALS__?.invoke;
export async function nativeSave(data,name){
 const bytes=new Uint8Array(await new Blob([data]).arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=16384)binary+=String.fromCharCode(...bytes.subarray(i,i+16384));
 return native()('native_save',{name,base64:btoa(binary)});
}
export async function newWindow(projectId){return native()('open_workbench',{route:projectId?new URLSearchParams({view:'Project',project:projectId}).toString():''});}
export function setupDesktopBridge({notice}){
 if(!native())return;
 const refreshAccessibility=async()=>{try{const flags=await native()('native_accessibility');window.__biorescueNativeReducedTransparency=flags.reducedTransparency===true;applyPreferences();}catch{/* Older desktop shells continue with media and user preferences. */}};refreshAccessibility();window.addEventListener('focus',refreshAccessibility);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshAccessibility();});
 document.body.dataset.desktop='true';document.querySelectorAll('[data-desktop-new-window]').forEach(button=>{button.hidden=false;button.onclick=()=>newWindow().catch(error=>notice(String(error),true));});
 document.addEventListener('keydown',event=>{if(event.ctrlKey&&event.shiftKey&&event.key.toLowerCase()==='n'){event.preventDefault();newWindow().catch(error=>notice(String(error),true));}});
 const accept=entries=>{if(!entries.length)return;const files=entries.map(entry=>{const bytes=Uint8Array.from(atob(entry.base64),character=>character.charCodeAt(0));const file=new File([bytes],entry.name.split('/').pop());Object.defineProperty(file,'webkitRelativePath',{value:entry.name});return file;});checkImportSelection(files);const transfer=new DataTransfer();files.forEach(file=>transfer.items.add(file));const dialog=document.querySelector('#import-dialog');if(!dialog.open)dialog.showModal();const target=document.querySelector('#batch-files');target.files=transfer.files;target.dispatchEvent(new Event('change',{bubbles:true}));};
 window.__TAURI__.event.listen('workbench-native-drop',event=>{try{accept(event.payload);}catch(error){notice(String(error),true);}});window.__TAURI__.event.listen('workbench-native-drop-error',event=>notice(String(event.payload),true));
 const select=async(folder=false)=>{try{const entries=await native()('native_intake',{folder});accept(entries);}catch(error){notice(String(error),true);}};
 const replace=()=>{for(const [selector,folder]of [['[data-choose-many]',false],['[data-choose-folder]',true]]){const button=document.querySelector(selector);if(button&&!button.dataset.native){button.dataset.native='true';button.onclick=()=>select(folder);}}};
 replace();new MutationObserver(replace).observe(document.querySelector('#import-dialog'),{childList:true,subtree:true});
}
