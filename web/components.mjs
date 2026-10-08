import {htmlMessage as uiText,t as uiValue} from './i18n.mjs';
export const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const icon=(name='folder')=>`<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="${({folder:'M3 6h7l2 3h9v11H3z',more:'M5 12h.1M12 12h.1M19 12h.1',search:'M10 3a7 7 0 1 0 0 14a7 7 0 0 0 0-14M15 15l6 6',book:'M3 4h7l2 2 2-2h7v16h-7l-2 2-2-2H3z',check:'M4 12l5 5L20 6',trash:'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15',chevron:'m7 10 5 5 5-5'})[name]||'M3 6h7l2 3h9v11H3z'}"/></svg>`;
let sequence=0;
// One presentation component; native inputs/buttons retain their existing handlers.
export function SelectableSurface(element,{selected=false}={}){
 element.classList.add('selectable-surface');element.dataset.selected=String(selected);
 if(!element.querySelector(':scope > .selection-badge')){const badge=document.createElement('span');badge.className='selection-badge';badge.setAttribute('aria-hidden','true');badge.innerHTML=icon('check');element.append(badge);}
 return element;
}
export function refreshSelectableSurfaces(root=document){
 root.querySelectorAll('.icon-button[aria-label]:not([title])').forEach(button=>button.title=button.getAttribute('aria-label'));
 const selector='.review-card:has([data-select-review]),.profile-choice,.theme-card,[data-material],.journey-spine button,.settings-nav button,.review-filters button,[data-help-lesson],.help-home-grid>button,.help-question-list>button,.help-rail button,.command-grid button,[role=option],label:has(> input[type=checkbox]):not(.review-selection):not(.studio-setting-row):not(.review-focus-controls *)';
 root.querySelectorAll(selector).forEach(element=>SelectableSurface(element,{selected:element.querySelector('input')?.checked||element.getAttribute('aria-pressed')==='true'||element.getAttribute('aria-selected')==='true'||element.getAttribute('aria-current')==='page'}));
}
export function motionTiming(kind='panel'){
 const mode=document.documentElement.dataset.motion,style=getComputedStyle(document.documentElement),token=mode==='reduced'?'reduced':kind;
 return {duration:mode==='off'?0:parseFloat(style.getPropertyValue('--motion-'+token))||0,easing:style.getPropertyValue('--ease-standard').trim()||'linear'};
}
export async function acknowledgeReview(element){
 if(!element?.isConnected)return;
 element.dataset.recorded='true';
 const mode=document.documentElement.dataset.motion;
 if(mode==='off')return;
 const motion=element.animate(mode==='reduced'?[{opacity:.65},{opacity:1}]:[{transform:'scale(1)',opacity:1},{transform:'scale(1.008)',opacity:1},{transform:'scale(1)',opacity:1}],motionTiming('panel'));
 try{await motion.finished;}catch{/* Navigation may cancel presentation; the decision is already saved. */}
}
export function ask({title,body='',fields=[],choices=[{value:'ok',label:uiValue("ui.31fbef162594")},{value:null,label:uiValue("cancel")}]}){
 const focus=document.activeElement,id='dialog-'+(++sequence),dialog=document.createElement('dialog');dialog.className='workbench-dialog';dialog.setAttribute('aria-labelledby',id);dialog.innerHTML=`<form><header><h2 id="${id}">${esc(title)}</h2></header><p>${esc(body)}</p>${fields.map(f=>f.type==='checkbox'?`<label><input name="${esc(f.name)}" type="checkbox">${esc(f.label)}</label>`:f.type==='select'?`<label>${esc(f.label)}<select name="${esc(f.name)}">${f.options.map(option=>`<option value="${esc(option.value)}" ${String(f.value)===String(option.value)?'selected':''}>${esc(option.label)}</option>`).join('')}</select></label>`:f.type==='textarea'?`<label>${esc(f.label)}<textarea name="${esc(f.name)}" ${f.required?'required':''} maxlength="${f.max||4000}">${esc(f.value||'')}</textarea></label>`:`<label>${esc(f.label)}<input name="${esc(f.name)}" value="${esc(f.value||'')}" ${f.required?'required':''} maxlength="${f.max||200}"></label>`).join('')}<div class="dialog-actions">${choices.map((c,i)=>`<button type="${c.submit?'submit':'button'}" data-choice="${i}" class="button ${c.danger?'danger':i===0?'primary':'secondary'}">${esc(c.label)}</button>`).join('')}</div></form>`;
 document.body.append(dialog);
 return new Promise(resolve=>{
  const finish=value=>{if(dialog.open)dialog.close();dialog.remove();if(focus?.isConnected)focus.focus();resolve(value);};
  const choose=i=>{const c=choices[i];if(c.submit&&!dialog.querySelector('form').reportValidity())return;finish(c.value===null?null:{choice:c.value,...Object.fromEntries(new FormData(dialog.querySelector('form')))});};
  dialog.querySelector('form').onsubmit=e=>{e.preventDefault();choose(e.submitter?.dataset.choice!==undefined?+e.submitter.dataset.choice:choices.findIndex(c=>c.submit));};
  for(const b of dialog.querySelectorAll('[data-choice]'))if(b.type!=='submit')b.onclick=()=>choose(+b.dataset.choice);
  dialog.oncancel=e=>{e.preventDefault();finish(null);};dialog.showModal();
 });
}
