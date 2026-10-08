// English authoring catalog; visible practice labels resolve these keys via i18n.
export const practiceCopy={
 'practice.amphibian.title':'Simple amphibian survey',
 'practice.amphibian.focus':'Known zero, independent survey effort and exact identifiers.',
 'practice.messy.title':'Messy legacy spreadsheet',
 'practice.messy.focus':'Whitespace, orphan records, questionable coordinates and ambiguous dates.',
 'practice.museum.title':'Museum collection',
 'practice.museum.focus':'Distinct catalog literals and conflicting codebook editions.',
 'practice.camera.title':'Camera-trap collection',
 'practice.camera.focus':'Deployment/media/observation grain, orphan references and non-detection uncertainty.',
 'practice.nightmare.title':'Nightmare archive',
 'practice.nightmare.focus':'Conflicting final workbooks, field notes, undocumented codes and recovery.',
};
export const practiceCases=[
 {id:'amphibian',url:'/practice-amphibian.json'},
 {id:'messy',action:'demo'},
 {id:'museum',url:'/practice-museum.json'},
 {id:'camera',url:'/practice-camera.json'},
 {id:'nightmare',action:'nightmare'},
].map(item=>({...item,title:practiceCopy['practice.'+item.id+'.title'],focus:practiceCopy['practice.'+item.id+'.focus']}));
