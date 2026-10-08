import test from 'node:test';
import assert from 'node:assert/strict';
import {newProject,addImport} from '../web/project.mjs';
import {projectFacts,nextStep,stageContext} from '../web/v7/domain/journey.mjs';
import {iconNames,icon} from '../web/v7/design-system/icons.mjs';
import {settingCategories} from '../web/v7/workspaces/screens.mjs';
test('V7 journey preserves unknown meanings and has no automatic scientific effect',()=>{const p=newProject('Fictional rescue'),before=JSON.stringify(p),facts=projectFacts(p);assert.equal(nextStep(facts)[0],'Sources');assert.equal(facts.integrity,null);assert.equal(JSON.stringify(p),before);assert.equal(stageContext(facts).length,7);});
test('V7 settings and primary concepts all have distinct semantic icons',()=>{const names=settingCategories.map(x=>x[1]);for(const name of names)assert(iconNames.includes(name));const concepts=['home','library','overview','sources','understand','review','repair','standardize','validate','package'];assert.equal(new Set(concepts.map(icon)).size,concepts.length);});
