import {homeV6} from './workflow-experience.mjs';
import {buildIdentity} from './build-identity.mjs';
import {practiceCases} from './practice-catalog.mjs';
import {icon,routeIcon} from './studio-icons.mjs';
import {htmlMessage as h,t,language} from './i18n.mjs';
import {esc} from './components.mjs';
import {getProfile,toolLabel,profileLabel,TOOLS,recommendedTools} from './workspace-profile.mjs';
import {getPreferences} from './preferences.mjs';
import {APP_VERSION} from './project.mjs';
import {primaryWorkflow,secondaryWorkflow,libraryRecommendation} from './workflow-experience.mjs';

const groups=[['rescue',['Project','Sources','Inspect','Review queue','Repair','Translate & standardize','Validate','Export']],['context',['Metadata','Evidence','Relationships']],['tools',['Map to Standards','Standards Center','Standards validation','DwC-DP preparation','Large CSV','Saved for later']],['history',['Audit / Report','Snapshots','Storage & Recovery']]];
const glyphs=['◉','▤','⌕','◇','⎘','⇄','✓','↗'];
let all=false;
export function workflowRail(project,section){
 const host=document.querySelector('#workflow-rail');if(!host)return;
 for(const [id,route]of [['workstation-home','Home'],['home-button','Projects']]){const button=document.getElementById(id);if(button){button.classList.toggle('active',section===route);button.classList.toggle('selected',section===route);if(section===route)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');}}
 const profile=getProfile(),advanced=profile.experience==='advanced',showAdvanced=all||secondaryWorkflow.includes(section);
 const link=(name,label)=>`<button class="rail-link ${section===name?'active':''}" title="${esc(label)}" aria-label="${esc(label)}" data-section="${name}" data-tour-id="section-${name.toLowerCase().replaceAll(/[^a-z]+/g,'-')}" ${section===name?'aria-current="page"':''}>${icon(routeIcon(name))}<span class="rail-label">${esc(label)}</span></button>`;
 host.innerHTML=project?`<section class="rail-group v6-primary"><h2>RESCUE WORKFLOW</h2>${primaryWorkflow.map(([name,label])=>link(name,advanced?toolLabel(name):label)).join('')}</section><section class="rail-group v6-project-tools"><button class="rail-disclosure" data-show-tools aria-expanded="${showAdvanced}">${icon('chevron')}<span class="rail-label">Project tools</span></button>${showAdvanced?secondaryWorkflow.map(name=>link(name,toolLabel(name))).join(''):''}</section>`:'';
 host.querySelector('[data-show-tools]')?.addEventListener('click',()=>{all=!showAdvanced;workflowRail(project,section);});
 document.querySelector('.sidebar').classList.toggle('has-project',!!project);
 const label=section==='Projects'?t('v07.library'):section==='Home'?t('v07.home'):toolLabel(section);
 const current=document.querySelector('#workstation-context');if(current)current.innerHTML=project?`<bdi>${esc(project.metadata.title.value)}</bdi><span aria-hidden="true">/</span><span>${esc(label)}</span>`:h(section==='Projects'?'v07.library':section==='Help'?'v07.helpTitle':'v07.home');
 const state=document.querySelector('#workstation-state');if(state){state.removeAttribute('data-i18n');state.textContent=project?t('v07.saved',{revision:project.revision}):t('v07.noProject');}
}
export function homeHtml(list){return homeV6(list);}
export function contextHtml(project,section){
 const label=primaryWorkflow.find(([route])=>route===section)?.[1]||toolLabel(section);
 return `<header class="project-heading v6-context-bar" data-tour-id="project-context"><div><strong><bdi>${esc(project.metadata.title.value||project.id)}</bdi></strong><span class="v6-context-stage">${esc(label)}</span><span class="v6-save-state">Saved revision ${project.revision}</span></div><div class="small-actions"><button class="icon-button" data-action="undo" ${project.undoStack?.length?'':'disabled'} aria-label="Undo last change" title="Undo">↶</button><button class="icon-button" data-action="redo" ${project.redoStack?.length?'':'disabled'} aria-label="Redo last change" title="Redo">↷</button><button class="button secondary" data-action="backup">Backup</button><button class="button primary" data-action="import">Add sources</button></div></header>${['Sources','Inspect','Repair','Translate & standardize'].includes(section)?`<div class="data-view-bar"><nav class="data-view-switch" aria-label="Data layers">${[['Sources','Source'],['Inspect','Working copy'],['Translate & standardize','Reviewed output']].map(([route,key])=>`<button data-section="${route}" ${section===route?'aria-current="page"':''}>${key}</button>`).join('')}</nav><details class="data-view-explainer"><summary>About these layers</summary><div class="data-lineage">${['source','working','reviewed'].map(key=>`<article><strong>${h('studio.'+key)}</strong><p>${h('studio.'+key+'Body')}</p></article>`).join('')}</div></details></div>`:''}`;
 /*
 return `<header class="project-heading ${section==='Project'?'':'compact-project-heading'}" data-tour-id="project-context"><div><div class="eyebrow">${h('v07.files',{count:project.resources.length})} · ${h('v07.tables',{count:project.tables.length})}</div><h1><bdi>${esc(project.metadata.title.value||project.id)}</bdi></h1><p class="muted">${esc(toolLabel(section))}</p></div><div class="small-actions"><button class="button secondary" data-action="backup">${h('ui.079e805754be')}</button><button class="button primary" data-action="import">${h('v07.chooseFiles')}</button><button class="icon-button" data-action="bookmark-workspace" aria-label="${h('v062.bookmarkWorkspace')}">◇</button></div></header>${['Sources','Inspect','Repair','Translate & standardize'].includes(section)?`<div class="data-view-bar"><strong>${h('studio.dataView')}</strong><nav class="data-view-switch" aria-label="${h('studio.dataView')}">${[['Sources','source'],['Inspect','working'],['Translate & standardize','reviewed']].map(([route,key])=>`<button data-section="${route}" ${section===route?'aria-current="page"':''}>${h('studio.'+key)}</button>`).join('')}</nav><details class="data-view-explainer"><summary>${h('studio.layers')}</summary><div class="data-lineage">${['source','working','reviewed'].map(key=>`<article><strong>${h('studio.'+key)}</strong><p>${h('studio.'+key+'Body')}</p></article>`).join('')}</div></details></div>`:''}`;
*/
}
export function setupWorkstation({home,navigate,getProject,getSection}){
 document.querySelector('#workstation-home').onclick=home;
 if(window.__TAURI_INTERNALS__){document.documentElement.dataset.nativeTitlebar='true';const bar=document.querySelector('.topbar'),controls=document.createElement('div');controls.className='v6-window-controls';controls.innerHTML='<button data-window-action="minimize" aria-label="Minimize window">−</button><button data-window-action="maximize" aria-label="Maximize or restore window">□</button><button data-window-action="close" aria-label="Close window">×</button>';bar.append(controls);const invoke=action=>window.__TAURI_INTERNALS__.invoke('native_window_action',{action});controls.querySelectorAll('button').forEach(button=>button.onclick=()=>invoke(button.dataset.windowAction));bar.addEventListener('pointerdown',event=>{if(event.button===0&&!event.target.closest('button,input,a'))invoke('drag');});bar.addEventListener('dblclick',event=>{if(!event.target.closest('button,input,a'))invoke('maximize');});}

 const menu=document.querySelector('#navigation-toggle'),sidebar=document.querySelector('.sidebar'),backdrop=document.querySelector('#navigation-backdrop');
 const close=()=>{document.body.classList.remove('navigation-open');menu.setAttribute('aria-expanded','false');};
 menu.onclick=()=>{const open=!document.body.classList.contains('navigation-open');document.body.classList.toggle('navigation-open',open);menu.setAttribute('aria-expanded',String(open));if(open)sidebar.querySelector('button')?.focus();};backdrop.onclick=close;
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('navigation-open')){close();menu.focus();}});
 document.addEventListener('click',event=>{if(event.target.closest('[data-section],[data-project]'))close();});
 window.addEventListener('biorescue-route',()=>workflowRail(getProject(),getSection()));
}

export function privacyDiagnostics(){const preferences=getPreferences();return {buildIdentity,applicationVersion:APP_VERSION,projectSchemaVersion:3,mode:window.__TAURI_INTERNALS__?'desktop':'web',theme:preferences.theme,language:language(),profile:profileLabel()};}
