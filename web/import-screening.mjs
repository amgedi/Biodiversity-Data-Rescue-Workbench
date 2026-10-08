import {sanitize} from './preferences.mjs';
import {htmlMessage as h,t} from './i18n.mjs';
export const SCREEN_LIMITS=Object.freeze({rowsPerTable:1000,cells:50000,examples:5});
const normalize=value=>String(value).toLowerCase().replace(/[^a-z0-9]/g,'');
export function screenImport(imported,settings){
 const p=sanitize(settings),enabled={dates:p.importCheckDates,coordinates:p.importCheckCoordinates,identifiers:p.importCheckIdentifiers},tables=[];let remaining=SCREEN_LIMITS.cells;
 for(const [tableIndex,table] of imported.tables.entries()){
  const count=Math.min(table.rows.length,SCREEN_LIMITS.rowsPerTable,Math.floor(remaining/Math.max(1,table.headers.length))),rows=table.rows.slice(0,count);remaining-=count*table.headers.length;
  const findings=[];const add=(kind,column,indices)=>{if(indices.length)findings.push({kind,column,field:table.headers[column],candidateOnly:true,affectedSampleRecords:indices.length,examples:indices.slice(0,SCREEN_LIMITS.examples).map(i=>({dataRecord:i+1,literalValue:rows[i][column]}))});};
  for(const [column,name] of table.headers.entries()){
   const values=rows.map(row=>row[column]);
   if(enabled.dates){const ambiguous=[];values.forEach((value,i)=>{const m=/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})$/.exec(value);if(m&&+m[1]<=12&&+m[2]<=12&&+m[1]!==+m[2])ambiguous.push(i);});add('ambiguousDate',column,ambiguous);}
   const field=normalize(name);
   if(enabled.coordinates&&['lat','latitude','decimallatitude','lon','lng','longitude','decimallongitude'].includes(field)){
    const bound=['lat','latitude','decimallatitude'].includes(field)?90:180;add('coordinateRange',column,values.flatMap((value,i)=>value.trim()&&(!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(value.trim())||!Number.isFinite(Number(value))||Math.abs(Number(value))>bound)?[i]:[]));
   }
   if(enabled.identifiers&&(/id$|identifier$|^id$/.test(field))){const seen=new Set(),duplicates=[],blank=[];values.forEach((value,i)=>{if(value===''){blank.push(i);return;}if(seen.has(value))duplicates.push(i);seen.add(value);});add('identifierRepeat',column,duplicates);add('identifierBlank',column,blank);}
  }
  tables.push({tableIndex,sampledRecords:count,totalRecords:table.rows.length,coverageComplete:count===table.rows.length,findings});
 }
 return {version:1,sourceSha256:imported.resource.sha256,enabled,limits:{...SCREEN_LIMITS},tables,scientificInterpretation:'unconfirmed; header and value patterns are candidates only',settingsScope:'Supplemental import screening only; full validation and source-preservation checks remain available.'};
}
export async function verifyImportRoundTrip(imported,source){
 if(imported.resource.base64!==source.base64||imported.resource.name!==source.name)throw new Error(t('v0610.integrityBlocked'));
 const binary=atob(source.base64),bytes=Uint8Array.from(binary,c=>c.charCodeAt(0)),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
 if(hash!==imported.resource.sha256||bytes.length!==imported.resource.bytes)throw new Error(t('v0610.integrityBlocked'));
 return {algorithm:'SHA-256',sourceSha256:hash,byteLength:bytes.length,exactSourceRoundTrip:true};
}
export async function prepareImportReview(imported,source,settings){const integrity=await verifyImportRoundTrip(imported,source),review=screenImport(imported,settings);imported.resource.archaeology??={};imported.resource.archaeology.importScreening={...review,integrity};return imported;}
export function importScreeningHtml(imported){const review=imported.resource.archaeology?.importScreening;if(!review)return '';return `<section class="callout import-screening"><h3>${h('v0610.screenTitle')}</h3><p>${h('v0610.screenSafety')}</p><p>${h('v0610.integrityVerified')}</p><ul>${['dates','coordinates','identifiers'].map(key=>`<li>${h('v0610.check.'+key)}: ${h(review.enabled[key]?'v0610.enabled':'v0610.disabled')}</li>`).join('')}</ul>${review.tables.map(table=>`<p>${h('v0610.coverage',{sampled:table.sampledRecords,total:table.totalRecords})}</p><ul>${table.findings.map(f=>`<li><bdi>${String(f.field).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</bdi>: ${h('v0610.finding.'+f.kind,{count:f.affectedSampleRecords})}</li>`).join('')}</ul>`).join('')}</section>`;}
