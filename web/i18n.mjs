import {practiceCopy} from './practice-catalog.mjs';
import {tutorialCopy} from './tutorial-registry.mjs';
import {workspaceCopy} from './workspace-copy.mjs';
import {knowledgeCopy} from './knowledge.mjs';
import {studioCopy} from './studio-copy.mjs';
import {catalogs,localeInfo} from './locales.mjs';
import {experienceCopy,helpCopy} from './experience-copy.mjs';
import {workstationCopy} from './workstation-copy.mjs';
import {structuralCopy} from './structural-copy.mjs';
for(const catalog of Object.values(catalogs))Object.assign(catalog,workstationCopy,structuralCopy,experienceCopy,helpCopy,studioCopy,knowledgeCopy,workspaceCopy,tutorialCopy,practiceCopy);
export const baseline='en';
let active=baseline,developer=false,preference='system';
const labels=new Map(Object.entries(catalogs.en).map(([key,text])=>[text,key]));
export const uiLabel=value=>labels.has(value)?t(labels.get(value)):String(value);
export function resolveLocale(requested,available=productionLocales()){for(const value of requested||[]){const exact=available.find(code=>code.toLowerCase()===value.toLowerCase());if(exact)return exact;const base=value.toLowerCase().split('-')[0],match=available.find(code=>code.toLowerCase().split('-')[0]===base);if(match)return match;}return baseline;}
export const languagePreference=()=>preference;
export const placeholders=text=>[...String(text).matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)].map(x=>x[1]).sort();
export function catalogProblems(locale){const en=catalogs.en,target=catalogs[locale]||{},problems=[];for(const key of Object.keys(en)){if(!Object.hasOwn(target,key))problems.push({key,code:'missing'});else if(JSON.stringify(placeholders(en[key]))!==JSON.stringify(placeholders(target[key])))problems.push({key,code:'arguments'});}for(const key of Object.keys(target))if(!Object.hasOwn(en,key))problems.push({key,code:'extra'});return problems;}
export function productionLocales(){return Object.keys(localeInfo).filter(code=>localeInfo[code].applicationComplete&&catalogProblems(code).length===0);}
export function translate(locale,key,args={}){if(!Object.hasOwn(catalogs.en,key))throw new Error('I18N_UNKNOWN_KEY: '+key);let text=catalogs[locale]?.[key]||catalogs.en[key];if(locale==='qps-ploc')text='⟦'+text.replace(/(\{[A-Za-z][A-Za-z0-9_]*\})|[aeiou]/g,(whole,arg)=>arg||({a:'åå',e:'ëë',i:'ïï',o:'öö',u:'üü'}[whole]))+'⟧';if(locale==='qps-rtl')text='⟦'+text+'⟧';for(const name of placeholders(catalogs.en[key]))if(!Object.hasOwn(args,name))throw new Error('I18N_MISSING_ARGUMENT: '+name);return text.replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g,(_,name)=>String(args[name]));}
export const t=(key,args)=>translate(active,key,args);
export const htmlMessage=(key,args)=>t(key,args).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export function pluralFor(locale,key,count,args={}){const region=locale.startsWith('qps')?'en':locale,category=new Intl.PluralRules(region).select(count);const chosen=Object.hasOwn(catalogs.en,key+'.'+category)?key+'.'+category:key+'.other';return translate(locale,chosen,{...args,count:new Intl.NumberFormat(region).format(count)});}
export const plural=(key,count,args)=>pluralFor(active,key,count,args);
export function language(){return active;}
export function setLanguage(locale,{persist=true,preview=false}={}){const requested=locale;if(locale==='system')locale=resolveLocale(navigator.languages||[navigator.language]);if(!productionLocales().includes(locale)&&!(developer&&preview&&(localeInfo[locale]||locale.startsWith('qps-'))))throw new Error('I18N_INCOMPLETE_LOCALE');active=locale;const root=document.documentElement;root.lang=locale.startsWith('qps')?'en':locale;root.dir=locale==='ar'||locale==='qps-rtl'?'rtl':'ltr';if(!preview)preference=requested;if(persist&&!preview)localStorage.setItem('biorescue-language',requested);applyTranslations();window.dispatchEvent(new CustomEvent('biorescue-language',{detail:{locale,preview}}));}
export function applyTranslations(root=document){for(const node of root.querySelectorAll('[data-i18n-attrs]'))for(const [attr,key]of Object.entries(JSON.parse(node.dataset.i18nAttrs))){if(!['aria-label','title','placeholder'].includes(attr))throw new Error('I18N_UNSAFE_ATTRIBUTE');node.setAttribute(attr,t(key));}for(const node of root.querySelectorAll('[data-i18n]')){const value=t(node.dataset.i18n,JSON.parse(node.dataset.i18nArgs||'{}'));if(node.dataset.i18nAttr){if(!['aria-label','title','placeholder'].includes(node.dataset.i18nAttr))throw new Error('I18N_UNSAFE_ATTRIBUTE');node.setAttribute(node.dataset.i18nAttr,value);}else if(node.textContent!==value)node.textContent=value;}}
export function startI18n(){developer=new URLSearchParams(location.search).get('i18nDebug')==='1';let saved;try{saved=localStorage.getItem('biorescue-language');}catch{}setLanguage(saved==='system'||productionLocales().includes(saved)?saved:'system',{persist:false});const observer=new MutationObserver(()=>applyTranslations());observer.observe(document.body,{childList:true,subtree:true});return observer;}

const escapePattern=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const messagePatterns=Object.entries(catalogs.en).filter(([,text])=>placeholders(text).length&&text.replace(/\{[^}]+\}/g,'').length>=4).map(([key,text])=>{
 const names=[];let pattern='',start=0;
 for(const match of text.matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)){pattern+=escapePattern(text.slice(start,match.index))+'([\\s\\S]*?)';names.push(match[1]);start=match.index+match[0].length;}
 return {key,names,length:text.length,pattern:new RegExp('^'+pattern+escapePattern(text.slice(start))+'$')};
}).sort((a,b)=>b.length-a.length);
export function messageFor(locale,value){if(typeof value!=='string')return value;const key=labels.get(value);if(key&&!placeholders(catalogs.en[key]).length)return translate(locale,key);for(const item of messagePatterns){const match=item.pattern.exec(value);if(match)return translate(locale,item.key,Object.fromEntries(item.names.map((name,i)=>[name,match[i+1]])));}return value;}
export const localizeMessage=value=>messageFor(active,value);

