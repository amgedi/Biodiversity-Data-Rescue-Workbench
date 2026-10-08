// Windows file drops arrive through Tauri, not the DOM DataTransfer API.
export async function mountNativeDrop({listen,dialog,intake,open,notice}) {
 const target=()=>{const d=dialog();if(d.open&&!d.querySelector('#intake'))return null;if(!d.open)open();return dialog();};
 const highlight=(d,active)=>{d?.querySelector('#source-drop-zone')?.classList.toggle('drag-over',active);const heading=d?.querySelector('#drop-heading');if(heading)heading.textContent=active?'Release to add files':'Drop files here';};
 const fail=problem=>{const d=target();highlight(d,false);const error=d?.querySelector('#intake-error');if(error){error.hidden=false;error.textContent=String(problem);}notice(String(problem),true);};
 const stops=[];
 try {
 stops.push(await listen('workbench-native-drag',event=>{highlight(event.payload===true?target():dialog(),event.payload===true);}));
 stops.push(await listen('workbench-native-drop',event=>{if(!event.payload?.length)return;const d=target();if(!d){notice('Close the current dialog, then drop the files again.',true);return;}highlight(d,false);if(intake().entries(event.payload))notice('Files added. Inspect extraction before importing.');}));
 stops.push(await listen('workbench-native-drop-error',event=>fail(event.payload)));
 } catch(error){stops.forEach(stop=>stop());throw error;}
 return ()=>stops.forEach(stop=>stop());
}
