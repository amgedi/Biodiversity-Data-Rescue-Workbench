const invoke=globalThis.window?.__TAURI_INTERNALS__?.invoke;
export const persistentKey=key=>['biorescue-grid-views','biorescue-preferences','biorescue-workspace-profile','biorescue-mode','biorescue-language','biorescue-local-templates','biorescue-theme','biorescue-help-read-v7','biorescue-support','biorescue-search-recent-v7'].includes(key)||key.startsWith('biorescue-product-tour-v');
let writes=Promise.resolve();
export const nativePreferencesReady=(async()=>{
 if(!invoke)return;
 try{const values=await invoke('native_client_state',{action:'load',key:null,value:null});for(const [key,value]of Object.entries(values))if(persistentKey(key))localStorage.setItem(key,value);}catch(error){window.__WORKBENCH_CLIENT_WARNING__=String(error);}
 const set=Storage.prototype.setItem,remove=Storage.prototype.removeItem;
 const persist=(key,value)=>{writes=writes.then(()=>invoke('native_client_state',{action:'save',key,value})).catch(error=>{window.__WORKBENCH_CLIENT_WARNING__=String(error);window.dispatchEvent(new CustomEvent('workbench-native-state-error',{detail:String(error)}));});};
 Storage.prototype.setItem=function(key,value){set.call(this,key,value);if(this===localStorage&&persistentKey(String(key)))persist(String(key),String(value));};
 Storage.prototype.removeItem=function(key){remove.call(this,key);if(this===localStorage&&persistentKey(String(key)))persist(String(key),null);};
})();
export const flushNativePreferences=()=>writes;

