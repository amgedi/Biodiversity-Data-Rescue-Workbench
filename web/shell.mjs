import {nativePreferencesReady} from './desktop-client-state.mjs';
await nativePreferencesReady;
import {htmlMessage as uiText,t as uiValue} from './i18n.mjs';
const $=s=>document.querySelector(s);
import {applyPreferences,getPreferences,setPreferences} from './preferences.mjs';
import {enhanceUploads} from './uploads.mjs';
try{if(!localStorage.getItem('biorescue-preferences')){const old=localStorage.getItem('biorescue-theme');if(old)setPreferences({...getPreferences(),theme:old});}}catch{}
applyPreferences();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>applyPreferences());
const control=document.createElement('button');control.className='nav';control.dataset.section='Settings';control.dataset.tourId='settings';control.innerHTML=`<span class="nav-icon" aria-hidden="true">⚙</span><span data-i18n="settings">${uiText("settings")}</span>`;$('.rail-bottom').insertBefore(control,$('.local-note'));
enhanceUploads();new MutationObserver(()=>enhanceUploads()).observe(document.body,{childList:true,subtree:true});
document.addEventListener('click',e=>{if(e.target.closest('[data-section]')&&$('#command-dialog').open)$('#command-dialog').close();});
if('serviceWorker' in navigator&&!window.__WORKBENCH_DESKTOP__){navigator.serviceWorker.register('/sw.js').then(reg=>{const show=()=>{if(!navigator.serviceWorker.controller||!reg.waiting||document.querySelector('.update-banner'))return;const banner=document.createElement('div');banner.className='update-banner';banner.innerHTML=`<p data-i18n="ui.9c52040446da">${uiText("ui.9c52040446da")}</p><button class="button secondary" data-i18n="ui.202cc47f5144">${uiText("ui.202cc47f5144")}</button>`;banner.querySelector('button').onclick=()=>{const event=new CustomEvent('biorescue-request-update',{cancelable:true});if(document.dispatchEvent(event))reg.waiting?.postMessage({type:'ACTIVATE_SAVED_UPDATE'});};document.body.append(banner);};show();reg.addEventListener('updatefound',()=>reg.installing?.addEventListener('statechange',show));}).catch(()=>{});navigator.serviceWorker.addEventListener('controllerchange',()=>location.reload());}

document.addEventListener('click',e=>{if(e.target.closest('[data-close-large-edit]'))document.querySelector('#large-edit-dialog').close();});

matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',()=>applyPreferences());
