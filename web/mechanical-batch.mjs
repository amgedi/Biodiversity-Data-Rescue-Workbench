import {applyRepair,transform} from './project.mjs';
function plans(project,selection){
 if(!Array.isArray(selection)||!selection.length||selection.length>100)throw new Error('BATCH_SELECTION');
 const seen=new Set();return selection.map(item=>{if(!item||item.kind!=='trim'||item.mechanical!==true||!Number.isInteger(item.column))throw new Error('BATCH_MEANING');const table=project.tables.find(table=>table.id===item.tableId),key=JSON.stringify([item.tableId,item.column]);if(!table?.columns[item.column]||seen.has(key))throw new Error('BATCH_SELECTION');seen.add(key);const spec={op:'trim whitespace',column:item.column};return {tableId:table.id,field:table.headers[item.column],spec,...transform(table,spec)};});
}
export function previewMechanicalBatch(project,selection){return plans(project,selection).map(({tableId,field,affected,examples})=>({tableId,field,affected,examples}));}
export function applyMechanicalBatch(project,selection,reason){if(typeof reason!=='string'||!reason.trim()||reason.length>4000)throw new Error('BATCH_REASON');const prepared=plans(project,selection);let next=project;for(const plan of prepared)if(plan.affected)next=applyRepair(next,plan.tableId,plan.spec,reason.trim());return next;}
