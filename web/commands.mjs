import {analyzeProject} from './smart-analysis.mjs';
import {knowledge} from './knowledge.mjs';
import {selectHelpArticle} from './help-center.mjs';
import {toolLabel,TOOLS} from './workspace-profile.mjs';
import {uiLabel} from './i18n.mjs';
import {t,htmlMessage as tr} from './i18n.mjs';
import {esc} from './components.mjs';
export function setupCommands({projects,navigate,openProject,getProject}){
 const dialog=document.querySelector('#command-dialog');dialog.innerHTML=`<h2 data-i18n="ui.50ee31174b2e">${tr("ui.50ee31174b2e")}</h2><p data-i18n="ui.a21bd89b6098">${tr("ui.a21bd89b6098")}</p><label>${tr("ui.00ff7398c308")}<input id="command-search" type="search" autocomplete="off"></label><div class="command-results"></div><form method="dialog"><button class="button secondary" data-i18n="ui.7d9eb7acb13e">${tr("ui.7d9eb7acb13e")}</button></form>`;
 const sections=[...new Set(['Projects','Settings','Help',...TOOLS])];
 const input=dialog.querySelector('input'),results=dialog.querySelector('.command-results');
 function draw(){const term=input.value.toLocaleLowerCase();const items=[{name:t('studio.assistant'),route:'Project',kind:'Tool'},...sections.map(name=>({name:name==='Projects'?uiLabel(name):toolLabel(name),route:name,kind:'Tool'})),...knowledge.map(article=>({name:t('knowledge.'+article.id+'.title'),keywords:(article.keywords||[]).join(' '),route:'Help',article:article.id,kind:'Help'})),...(getProject?.()?.tables||[]).flatMap(table=>table.headers.map((name,column)=>({name:table.name+' · '+name,route:'Metadata',tableId:table.id,column,kind:'Field'}))),...(getProject?.()?analyzeProject(getProject()).items.slice(0,200).map(item=>({name:t('v06.kind.'+item.kind,{field:item.field||item.metadataField||''}),route:'Review queue',finding:item.id,tableId:item.tableId,column:item.column,kind:'Finding'})):[]),...projects().filter(p=>p.state==='active').map(p=>({name:p.title,id:p.id,kind:'Project'}))].filter(x=>(x.name+' '+(x.keywords||'')).toLocaleLowerCase().includes(term)).slice(0,100);results.innerHTML=items.map((x,i)=>`<button class="button secondary" data-command="${i}"><span>${esc(x.name)}</span><small>${esc(uiLabel(x.kind))}</small></button>`).join('')||`<p data-i18n="ui.a25ca99e32a5">${tr("ui.a25ca99e32a5")}</p>`;for(const b of results.querySelectorAll('button'))b.onclick=async()=>{const item=items[+b.dataset.command];dialog.close();if(item.id)await openProject(item.id);else{if(item.article)selectHelpArticle(item.article);await navigate(item.route,item.column,item.tableId);if(item.finding)window.dispatchEvent(new CustomEvent('biorescue-inspect',{detail:{kind:'finding',id:item.finding,tableId:item.tableId}}))};};}
 input.oninput=draw;input.onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();results.querySelector('button')?.focus();}};
 results.onkeydown=e=>{const buttons=[...results.querySelectorAll('button')],i=buttons.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const index=e.key==='Home'?0:e.key==='End'?buttons.length-1:Math.max(0,Math.min(buttons.length-1,i+(e.key==='ArrowDown'?1:-1)));buttons[index]?.focus();}};
 window.addEventListener('biorescue-language',()=>{if(dialog.open)draw();});
 return ()=>{input.value='';draw();dialog.showModal();input.focus();};
}
