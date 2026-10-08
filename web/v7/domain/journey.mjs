import {analyzeProject} from '../../smart-analysis.mjs';
import {validation} from '../../project.mjs';
export const journey=['Preserve','Understand','Review','Repair','Standardize','Validate','Package'];
export const routes=['Overview','Sources','Understand','Review','Repair','Standardize','Validate','Package'];
export function projectFacts(project,workspace={reviews:{}},integrity=null){
 const analysis=analyzeProject(project),issues=validation(project),pending=analysis.items.filter(item=>!['Reviewed','Accepted','Rejected','Intentionally unresolved'].includes(workspace.reviews?.[item.id]?.state));
 const unknown=analysis.fields.filter(f=>f.status!=='Confirmed'&&f.status!=='Not Applicable').length;
 const mechanical=analysis.items.filter(i=>i.mechanical),blockers=issues.filter(i=>i.severity==='Error');
 return {analysis,issues,pending,unknown,mechanical,blockers,sources:project.resources.length,tables:project.tables.length,rows:project.tables.reduce((n,t)=>n+t.rows.length,0),integrity};
}
export function nextStep(facts){if(!facts.sources)return ['Sources','Bring in your original files','Preserve the files before interpreting their contents.'];if(facts.pending.length)return ['Review',`Review ${facts.pending[0].field||facts.pending[0].metadataField||'the next finding'}`,'A candidate needs your evidence and decision.'];if(facts.blockers.length)return ['Validate','Resolve validation blockers','Structural checks found issues that need attention.'];return ['Package','Review your package preflight','Check privacy and standards before creating an export.'];}
export function stageContext(f){return [`${f.sources} originals`,`${f.tables} tables · ${f.analysis.items.length} findings`,`${f.pending.length} decisions pending`,`${f.mechanical.length} mechanical candidates`,`${f.analysis.fields.filter(x=>x.term).length} mapped fields`,`${f.blockers.length} structural blockers`,'Privacy review required'];}
