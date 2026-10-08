import {htmlMessage as h} from './i18n.mjs';
export const helpWorkflows={
 Project:['overview1','overview2','overview3'],Sources:['source1','source2','source3'],Inspect:['inspect1','inspect2','inspect3'],Evidence:['evidence1','evidence2','evidence3'],
 'Review queue':['review1','review2','review3'],Repair:['repair1','repair2','repair3'],'Translate & standardize':['translate1','translate2','translate3'],
 'Standards Center':['standard1','standard2','standard3'],Validate:['validate1','validate2','validate3'],Export:['export1','export2','export3'],
 'Storage & Recovery':['recovery1','recovery2','recovery3'],'Large CSV':['large1','large2','large3'],Settings:['settings1','settings2','settings3']
};
export function workflowHelp(route){return `<h3>${h('v07x.help.steps')}</h3><ol class="help-workflow-steps">${(helpWorkflows[route]||[]).map(key=>`<li>${h('v07x.help.'+key)}</li>`).join('')}</ol><aside class="callout">${h('v07x.help.stop')}</aside>`;}
