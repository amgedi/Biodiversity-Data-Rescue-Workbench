import {decorateSettingsV06} from './settings-v06.mjs';
export const decorateSettings=decorateSettingsV06;
export function startSettings(context={}){new MutationObserver(()=>decorateSettingsV06(context)).observe(document.querySelector('#main'),{childList:true,subtree:true});decorateSettingsV06(context);}
