import fs from 'node:fs/promises';import {newProject,addImport,interpretation,validateProject} from '../../web/project.mjs';
const imports=JSON.parse(await fs.readFile(new URL('../../examples/practice/imports.json',import.meta.url),'utf8'));
const titles={amphibian:'Simple amphibian survey',museum:'Museum specimen collection',camera:'Camera-trap collection'};
for(const [kind,items]of Object.entries(imports)){let p=newProject(titles[kind]+' · fictional practice');for(const imported of items)p=addImport(p,imported);p.metadata.description={...interpretation('Authored fictional training collection. Inspect literals, uncertainty, evidence and package purpose. No real research records.','Confirmed'),rationale:'Authored exclusively for local practice.'};validateProject(p);await fs.writeFile(new URL('../../examples/practice/'+kind+'.biorescue.json',import.meta.url),JSON.stringify(p,null,2));}
console.log('Created three fictional projects through the actual import and project constructors.');
