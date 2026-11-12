'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {verifiedFinals,nextFinalIndex,splitFinalRiders,finalRaceLabel,finalEventLabel,finalRiderName}=require('../app.js');
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
assert.equal(finalRaceLabel('優勝戦(枠番選択)'),'優勝戦');
assert.equal(finalRaceLabel('S級 決勝'),'決勝');
assert.equal(finalRaceLabel('決勝戦'),'決勝');
assert.equal(finalEventLabel('SG日本選手権オートレース'),'日本選手権オートレース');
assert.equal(finalEventLabel('GⅢ 周防国府杯争奪戦'),'周防国府杯争奪戦');
assert.equal(finalRiderName('郡司浩平 選手','keirin'),'郡司浩平');
assert.equal(finalRiderName('清水 裕友選手','keirin'),'清水 裕友');
assert.equal(finalRiderName('郡司浩平','keirin'),'郡司浩平');
assert.equal(finalRiderName('選手A','keirin'),'選手A');
assert.equal(finalRiderName('青山 周平 選手','auto'),'青山 周平 選手');

for(const [size,left,right] of [[6,3,3],[7,4,3],[8,4,4],[9,5,4]]){
  const riders=Array.from({length:size},(_,i)=>({number:size-i,name:'選手'+i}));
  const [lhs,rhs]=splitFinalRiders(riders);
  assert.equal(lhs.length,left,'left rider count: '+size);
  assert.equal(rhs.length,right,'right rider count: '+size);
  assert.deepEqual([...lhs,...rhs].map(r=>r.number),
    Array.from({length:size},(_,i)=>i+1),'riders in ascending car number: '+size);
}

const css=fs.readFileSync(path.join(__dirname,'..','styles.css'),'utf8');
const sizes=[...css.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px\b/g)].map(m=>Number(m[1]));
assert.ok(sizes.length>15);
assert.ok(sizes.every(n=>n%10===0),'all font sizes must be multiples of 10px: '+sizes);
assert.match(css,/\.stage\.is-final \.header\s*\{[^}]*height:\s*100px;/s);
assert.match(css,/\.final-screen\s*\{[^}]*top:\s*120px;[^}]*width:\s*1920px;[^}]*height:\s*960px;/s);
assert.match(css,/\.final-screen\s*\{[^}]*background:\s*#fff;/s);
assert.match(css,/\.final-title\s*\{[^}]*background:\s*var\(--keirin\);/s);
assert.match(css,/\.final-title\[data-sport="auto"\]\s*\{[^}]*background:\s*var\(--auto\);/s);
for(const className of ['final-title','final-rider','final-number']){
  const re=new RegExp('\\.'+className+'\\s*\\{[^}]*font-size:\\s*80px;','s');
  assert.match(css,re,className+' should use 80px');
}
assert.match(css,/\.final-race\s*\{[^}]*font-size:\s*60px;/s);
assert.match(css,/\.final-race \.grade\s*\{[^}]*font-size:\s*60px;/s);
assert.match(css,/\.final-card\s*\{[^}]*width:\s*1600px;/s);
assert.match(css,/\.final-riders\s*\{[^}]*grid-template-columns:\s*repeat\(2,/s);
assert.match(css,/\.final-rider-column\s*\{[^}]*grid-template-rows:\s*repeat\(5,/s);
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
assert.match(html,/id="final-screen"[^>]*hidden/);
console.log('Final board tests passed: race info+grade label 60px, keirin suffix removal, 2-column riders and other text 80px');
