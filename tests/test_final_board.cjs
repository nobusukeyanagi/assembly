'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {verifiedFinals,nextFinalIndex}=require('../app.js');
const day='2026-11-03';
const card=(sport,venue,race,time)=>({
  sport,venue,race,startTime:time,event:'SG日本選手権オートレース',
  raceName:sport==='keirin'?'S級決勝':'優勝戦',
  riders:Array.from({length:sport==='keirin'?9:8},(_,i)=>({number:i+1,name:'選手'+(i+1)})),
});
const finals={date:day,finals:{status:'ok',items:[
  card('auto','浜松',12,'16:10'),
  card('keirin','防府',12,'16:26'),
]}};
assert.equal(verifiedFinals(finals,day).length,2);
assert.equal(verifiedFinals(finals,'2026-11-04').length,0);
assert.equal(verifiedFinals({date:day,finals:{items:[]}},day).length,0);
assert.equal(verifiedFinals({date:day,finals:{items:[
  {...card('auto','浜松',12,'16:10'),raceName:'最終予選'}]}},day).length,0);
assert.deepEqual([-1,0,1,2,3].map(i=>nextFinalIndex(i,3)),[0,1,2,-1,-1]);
assert.equal(nextFinalIndex(-1,0),-1);

const css=fs.readFileSync(path.join(__dirname,'..','styles.css'),'utf8');
const sizes=[...css.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px\b/g)].map(m=>Number(m[1]));
assert.ok(sizes.length>15);
assert.ok(sizes.every(n=>n%10===0),'all font sizes must be multiples of 10px: '+sizes);
assert.match(css,/\.final-screen\s*\{[^}]*width:\s*1920px;[^}]*height:\s*980px;/s);
assert.match(css,/\.final-riders\s*\{[^}]*grid-template-rows:\s*repeat\(9,/s);
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
assert.match(html,/id="final-screen"[^>]*hidden/);
console.log('Final board tests passed: cycle, date, 8/9 riders, fonts in 10px steps and 1920×980px viewport');
