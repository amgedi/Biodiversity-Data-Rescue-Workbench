import {build} from 'esbuild';
import fs from 'node:fs';
await build({entryPoints:['app/launcher/src/App.tsx'],outfile:'app/launcher/web/launcher.mjs',bundle:true,format:'esm',target:'es2022',define:{'process.env.NODE_ENV':'"production"'},loader:{'.mjs':'js'}});
fs.copyFileSync('web/branding/biodiversity-icon-master.png','app/launcher/web/biodiversity-icon.png');
fs.copyFileSync('app/launcher/src/launcher.css','app/launcher/web/launcher.css');
fs.writeFileSync('app/launcher/web/index.html','<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Launch Workbench</title><link rel="stylesheet" href="launcher.css"><script type="module" src="launcher.mjs"></script></head><body><div id="root"></div></body></html>');
console.log('Native launcher V2 React/TypeScript presentation built.');
