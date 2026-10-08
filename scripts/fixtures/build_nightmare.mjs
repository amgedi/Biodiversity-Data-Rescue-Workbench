import fs from 'node:fs/promises';import {newProject,addImport,interpretation} from '../../web/project.mjs';
let p=newProject('Rocky Mountain Amphibian Survey 2003–2011 · fictional archaeology');
for(const item of JSON.parse(await fs.readFile(new URL('../../examples/nightmare/imports.json',import.meta.url),'utf8')))p=addImport(p,item);
p.metadata.description=interpretation('Fictional training project with conflicting protocol definitions, multiple workbook versions, unknown dates/datum, mixed units and orphan relationships. No real field locations or species occurrences.','Confirmed');
p.metadata.license=interpretation('CC0-1.0 — fictional demo artifacts only','Confirmed');
for(const t of p.tables){if(t.name==='sites')t.columns.forEach(c=>{if(/geometry|locality/i.test(c.workingName))c.sensitive=true;});if(t.name==='observations')t.columns.forEach(c=>{if(/lat|lon/i.test(c.workingName))c.sensitive=true;});}
await fs.writeFile(new URL('../../examples/nightmare.biorescue.json',import.meta.url),JSON.stringify(p,null,2));
console.log(`${p.resources.length} sources, ${p.tables.length} tables; scientific field meanings remain Unknown.`);
