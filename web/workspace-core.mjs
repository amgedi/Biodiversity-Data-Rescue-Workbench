// Presentation and bounded inspection only: never update a scientific project.
export function gridPresentation(saved={},count=0){
 const valid=n=>Number.isInteger(n)&&n>=0&&n<count;
 const order=[...new Set((Array.isArray(saved.order)?saved.order:[]).filter(valid))];
 for(let n=0;n<count;n++)if(!order.includes(n))order.push(n);
 const hidden=[...new Set((Array.isArray(saved.hidden)?saved.hidden:[]).filter(valid))].slice(0,Math.max(0,count-1));
 const pinned=[...new Set((Array.isArray(saved.pinned)?saved.pinned:[]).filter(valid))].slice(0,3);
 const widths=Object.fromEntries(Object.entries(saved.widths||{}).filter(([key,value])=>valid(Number(key))&&Number.isFinite(value)).map(([key,value])=>[key,Math.max(70,Math.min(600,value))]));
 return {order,hidden,pinned,widths};
}
export function moveColumn(view,column,direction,count){const next=gridPresentation(view,count),index=next.order.indexOf(column),target=Math.max(0,Math.min(count-1,index+direction));if(index>=0){next.order.splice(index,1);next.order.splice(target,0,column);}return next;}
export function originalCell(table,row,column){
 const origin=table.rowOrigins?.[row]??row,field=table.columns[column];
 const source=Object.hasOwn(field,'sourceIndex')?field.sourceIndex:column;
 if(!Number.isInteger(source)||!Number.isInteger(origin)||origin<0||source<0||table.rowWidths&&source>=table.rowWidths[origin])return null;
 return table.originalTable?.rows?.[origin]?.[source]??null;
}
export function fieldContext(project,table,column){
 if(!table?.columns[column])throw Error('WORKSPACE_FIELD');
 const field=table.columns[column],sample=table.rows.slice(0,1000),values=sample.map(row=>row[column]??''),counts=new Map();for(const v of values)counts.set(v,(counts.get(v)||0)+1);
 const assertions=(project.evidenceAssertions||[]).filter(a=>a.tableId===table.id&&a.field===table.headers[column]);
 return {kind:'field',tableId:table.id,column,name:table.headers[column],sourceName:field.originalName,status:field.status||'Unknown',definition:field,examples:[...counts].slice(0,12),sampled:sample.length,total:table.rows.length,blanks:values.filter(v=>v==='').length,unique:counts.size,assertions,resource:project.resources.find(r=>r.id===table.resourceId),history:(project.audit||[]).filter(a=>JSON.stringify(a).includes(table.headers[column])).slice(-10)};
}
export function rowContext(project,table,row){
 if(!Number.isInteger(row)||!table?.rows[row])throw Error('WORKSPACE_ROW');
 const origin=table.rowOrigins?.[row]??row;
 return {kind:'row',tableId:table.id,row,sourceRow:origin+1,resource:project.resources.find(r=>r.id===table.resourceId),values:table.headers.map((name,column)=>({name,column,original:originalCell(table,row,column),working:table.rows[row][column],derived:!!table.columns[column].derivation,status:table.columns[column].status||'Unknown',sensitive:!!table.columns[column].sensitive,definition:table.columns[column]}))};
}
export function cellLabel(table,row,column){const source=originalCell(table,row,column),value=table.rows[row]?.[column],field=table.columns[column];return {source,working:value,changed:source!==null&&source!==value,derived:!!field?.derivation,status:field?.status||'Unknown'};}
