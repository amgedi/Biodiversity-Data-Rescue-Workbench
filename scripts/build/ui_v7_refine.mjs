// Apply the V7 interaction refinements to its own source boundary.
import fs from 'node:fs';
const path='web/v7/app.mjs';let source=fs.readFileSync(path,'utf8');
if(!source.includes('intakeGeneration')){
 source=source.replace('selectedControl=null;','selectedControl=null,intakeGeneration=0;');
 source=source.replace('function importDialog(){selectedFile=null;','function importDialog(){intakeGeneration++;selectedFile=null;');
 source=source.replace("$('#intake').onchange=()=>{imported=null;","$('#intake').onchange=()=>{intakeGeneration++;imported=null;");
 source=source.replace('async function inspectImport(){const form=','async function inspectImport(){const intakeRevision=++intakeGeneration;const form=');
 source=source.replace("if(!$('#dialog').open||!$('#intake'))return;","if(intakeRevision!==intakeGeneration||!$('#dialog').open||!$('#intake'))return;");
 fs.writeFileSync(path,source);
}
