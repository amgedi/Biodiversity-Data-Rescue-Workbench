import {experienceCopy,helpCopy} from '../web/experience-copy.mjs';
// AST audit of interface literals. Scientific vocabularies and data are not auto-translated.
import fs from 'node:fs';import path from 'node:path';import * as acorn from 'acorn';
import {catalogs,localeInfo} from '../web/locales.mjs';import {catalogProblems} from '../web/i18n.mjs';
import {workstationCopy} from '../web/workstation-copy.mjs';import {structuralCopy} from '../web/structural-copy.mjs';
const root=new URL('../',import.meta.url),entries=[];
for(const filename of fs.readdirSync(new URL('web/',root)).filter(name=>name.endsWith('.mjs')&&name!=='locales.mjs')){
 const source=fs.readFileSync(new URL('web/'+filename,root),'utf8'),tree=acorn.parse(source,{ecmaVersion:'latest',sourceType:'module',locations:true});
 function add(node,text,kind){if(typeof text==='string'&&/[A-Za-z]{2}/.test(text))entries.push({file:'web/'+filename,line:node.loc.start.line,kind,text});}
 function walk(node,parent){if(!node||typeof node!=='object')return;
  if(node.type==='TemplateElement'){for(const match of node.value.raw.matchAll(/>([A-Za-z][^<>$]+)</g))add(node,match[1],'static HTML text');}
  if(node.type==='Literal'&&typeof node.value==='string'){
   if(parent?.type==='Property'&&['title','body','label','placeholder'].includes(parent.key.name||parent.key.value))add(node,node.value,'display property');
   if(parent?.type==='CallExpression'&&['notice','alert','confirm','prompt'].includes(parent.callee.name)&&parent.arguments[0]===node)add(node,node.value,'notice or dialog');
   if(parent?.type==='NewExpression'&&parent.callee.name==='Error')add(node,node.value,'error message');
   if(parent?.type==='CallExpression'&&parent.callee.name==='select'&&parent.arguments[1]===node)add(node,node.value,'selection label');
  }
  for(const [key,value]of Object.entries(node)){if(['loc','start','end'].includes(key))continue;if(Array.isArray(value))value.forEach(item=>walk(item,node));else if(value&&typeof value==='object')walk(value,node);}
 }
 walk(tree,null);
}
// Stable identifiers are compatibility contracts, not prose to translate. Keep
// every exception visible in the report instead of quietly dropping candidates.
const stableCodes=entries.filter(row=>row.kind==='error message'&&/^[A-Z][A-Z0-9_]+:?(?: )?$/.test(row.text));
const candidates=entries.filter(row=>!stableCodes.includes(row));
const total=Object.keys(catalogs.en).length,addedKeys=Object.keys({...workstationCopy,...structuralCopy,...experienceCopy,...helpCopy});
const report={catalogKeys:total,addedEnglishFallbackKeys:addedKeys.length,localeCoverage:Object.fromEntries(Object.entries(localeInfo).map(([code,info])=>[code,{name:info.name,availableKeys:Object.keys(catalogs[code]).length,englishIdenticalKeys:code==='en'?0:Object.keys(catalogs.en).filter(key=>catalogs[code][key]===catalogs.en[key]).length,newEnglishFallbackKeys:code==='en'?0:addedKeys.length,applicationComplete:info.applicationComplete,problems:catalogProblems(code),review:info.review}])),rawCandidateCount:entries.length,stableCodeExceptions:stableCodes,hardcodedCandidates:candidates.length,candidates,wholeApplicationCoverage:'This AST audit covers static HTML text, display properties, selection labels and notices/errors. Dynamic prose, tutorial arrays, HTML attributes and backend messages still require a broader review. Available keys do not imply translated keys.',productionLanguages:['en'],previewLanguages:Object.keys(localeInfo).filter(code=>code!=='en'),structuralAuditGate:candidates.length||catalogProblems('en').length?'FAIL':'PASS within the stated AST scope',fullApplicationLocalizationAudit:'PENDING'};
fs.mkdirSync(new URL('artifacts/qa/',root),{recursive:true});fs.writeFileSync(new URL('artifacts/qa/localization.json',root),JSON.stringify(report,null,2));console.log(JSON.stringify({catalogKeys:total,rawCandidateCount:entries.length,stableCodeExceptions:stableCodes.length,hardcodedCandidates:candidates.length,productionLanguages:report.productionLanguages,structuralAuditGate:report.structuralAuditGate,fullApplicationLocalizationAudit:report.fullApplicationLocalizationAudit},null,2));
if(process.argv.includes('--strict')&&(candidates.length||catalogProblems('en').length))process.exitCode=1;
