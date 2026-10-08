import test from 'node:test';import assert from 'node:assert/strict';
import {choicePlacement,typeaheadIndex} from '../web/combobox.mjs';
test('select opens above at lower edge and remains inside viewport',()=>{const p=choicePlacement({left:450,top:450,bottom:494,width:200},{width:600,height:520});assert.equal(p.up,true);assert.ok(p.left+p.width<=592);assert.ok(p.top>=8);assert.ok(p.top+p.maxHeight<450);});
test('select opens below with room and handles narrow viewport',()=>{const p=choicePlacement({left:20,top:40,bottom:84,width:200},{width:150,height:500});assert.equal(p.up,false);assert.equal(p.width,134);assert.equal(p.left,8);assert.equal(p.top,88);});
test('repeated typeahead cycles matching options and full prefixes match literally',()=>{const labels=['Apple','Apricot','Banana'];assert.equal(typeaheadIndex(labels,0,'aa'),1);assert.equal(typeaheadIndex(labels,1,'aaa'),0);assert.equal(typeaheadIndex(labels,0,'ban'),2);assert.equal(typeaheadIndex(labels,2,'missing'),2);});
