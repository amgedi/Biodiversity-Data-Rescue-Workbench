import fs from 'node:fs';
import {themePalette,themeLights} from '../../web/studio-themes.mjs';
let css='\n/* BEGIN WORKSTATION V6 */\n';
for(const [key,[page,surface,accent,text]] of Object.entries(themePalette)){
 const light=['system','light','paper','sand','field-notes','mono-light'].includes(key),secondary=light?'#56645c':'#b8c8c1';
 const [a,b]=themeLights[key]||['#77777722','#88888811'];
 css+=`:root[data-theme="${key}"]{--page:${page};--surface:${surface};--inset:${page};--foreground:${text};--text:${text};--muted:${key==='high-contrast'?'#ffffff':secondary};--secondary-text:${key==='high-contrast'?'#ffffff':secondary};--accent:${accent};--accent-ink:${light?'#ffffff':page};--focus:${accent};--panel-border:color-mix(in srgb,${text} 15%,transparent);--selection-fill:color-mix(in srgb,${accent} 14%,${surface});--warning:${light?'#785321':'#e9be81'};--danger:${light?'#a33137':'#ffadad'};--v6-light-a:${a};--v6-light-b:${b};color-scheme:${light?'light':'dark'}}\n`;
}
css+=fs.readFileSync('web/design-v6.css','utf8')+'\n/* END WORKSTATION V6 */\n';
const path='web/workbench.css',before=fs.readFileSync(path,'utf8').split('/* BEGIN WORKSTATION V6 */')[0];
fs.writeFileSync(path,before+css);
console.log('V6 environments and composition compiled into canonical stylesheet.');
