import test from 'node:test';import assert from 'node:assert/strict';import {catalogs} from '../web/locales.mjs';
test('catalogs reject runaway repeated output and disproportionate expansion',()=>{
 const repetition=/(\p{L}+)(?:\s+\1){3,}/iu;
 for(const [locale,catalog]of Object.entries(catalogs))for(const [key,target]of Object.entries(catalog)){
  const source=catalogs.en[key];assert.ok(target.length<=Math.max(100,source.length*5),`${locale}:${key} disproportionate expansion`);
  assert.ok(!repetition.test(target)||repetition.test(source),`${locale}:${key} repeated translation output`);
 }
});
