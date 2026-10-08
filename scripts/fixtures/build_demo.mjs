import fs from 'node:fs/promises';
import {newProject,addImport,interpretation,validateProject} from '../../web/project.mjs';
const imports=JSON.parse(await fs.readFile(new URL('../../work/demo-imports.json',import.meta.url),'utf8'));
let p=newProject('Woodland 2008 · guided fictional rescue');
for(const imported of imports)p=addImport(p,imported);
p.metadata.description={...interpretation('Deliberately messy fictional biodiversity records. Not real field observations. Training data includes unknown dates, undocumented codes and questionable coordinates.','Confirmed'),rationale:'The example was authored explicitly for this tutorial.'};
p.metadata.license={...interpretation('CC0-1.0 (fictional tutorial files only)','Confirmed'),evidence:[p.resources.find(r=>r.name==='protocol_2008.txt').id],rationale:'Explicit license statement in the fictional training protocol.'};
// Do not pre-confirm any recovered scientific meaning: the tutorial requires evidence review.
validateProject(p);
await fs.writeFile(new URL('../../examples/relational-demo.biorescue.json',import.meta.url),JSON.stringify(p,null,2));
console.log('Fictional multi-resource project created: 3 tables, 4 sources, explicit unknowns.');
