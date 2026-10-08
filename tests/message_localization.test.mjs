import test from 'node:test';import assert from 'node:assert/strict';
import {messageFor,resolveLocale} from '../web/i18n.mjs';
test('dynamic messages escape punctuation and preserve scientific interpolation literally',()=>{
 assert.notEqual(messageFor('fr','Active (17)'),'Active (17)');assert.match(messageFor('fr','Active (17)'),/\(17\)/);
 const literal='Rana temporaria.001 NA حدث';const result=messageFor('fr','Unconfirmed mapping: '+literal);assert.ok(result.endsWith(literal));assert.notEqual(result,'Unconfirmed mapping: '+literal);
});
test('unrecognized evidence prose is retained rather than guessed or rewritten',()=>{const text='Protocol XYZ: 001 means observed; NA remains unknown.';assert.equal(messageFor('ar',text),text);});
test('system language resolution uses exact region then available base language',()=>{
 const available=['en','fr','pt-BR','zh-CN','ar'];assert.equal(resolveLocale(['pt-PT','fr'],available),'pt-BR');assert.equal(resolveLocale(['zh-Hans-CN'],available),'zh-CN');assert.equal(resolveLocale(['zz','fr-CA'],available),'fr');assert.equal(resolveLocale(['zz'],available),'en');
});
