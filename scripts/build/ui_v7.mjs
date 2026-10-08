import {build} from 'esbuild';
import fs from 'node:fs';
await build({entryPoints:['web/v7/app.mjs'],outfile:'web/app.mjs',bundle:true,format:'esm',target:'es2022',external:['/project.mjs','/smart-analysis.mjs','/preferences.mjs','/i18n.mjs','/edit-sessions.mjs','/desktop-client-state.mjs','/source-integrity.mjs','/workspace-core.mjs','/desktop-bridge.mjs'],plugins:[{name:'trusted-domain',setup(b){b.onResolve({filter:/\.\.\/.*(project|smart-analysis|preferences|i18n|edit-sessions|desktop-client-state|source-integrity|workspace-core|desktop-bridge)\.mjs$/},args=>({path:'/'+args.path.split('/').pop(),external:true}));}}]});
fs.writeFileSync('web/styles.css',fs.readFileSync('web/v7/design-system/workstation.css','utf8')+'\n'+fs.readFileSync('web/v7/design-system/pre-release.css','utf8'));
console.log('V7 independent presentation compiled; trusted domain modules remain external.');
