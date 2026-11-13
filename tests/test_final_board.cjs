'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {verifiedFinals,nextFinalIndex,splitFinalRiders,finalRaceLabel,finalRaceText,finalEventLabel,finalRiderName,finalSort,displayGrade,isMajorGrade}=require('../app.js');
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
const sample=[
  {...card('auto','浜松',11,'15:24'),feature:'mori'},
  {...card('auto','浜松',12,'16:10')},
  {...card('keirin','防府',12,'16:20')},
  {...card('soda','宮島',12,'15:40'),startTime:null}
];
assert.deepEqual(finalSort(sample).map(x=>x.sport+(x.feature||'')),
                 ['keirin','auto','automori','soda']);
assert.equal(finalRaceLabel('優勝戦(枠番選択)'),'優勝戦');
assert.equal(finalRaceLabel('S級 決勝'),'決勝');
assert.equal(finalRaceLabel('決勝戦'),'決勝');
assert.equal(finalRaceText({venue:'戸田',race:12,raceName:'優勝戦',startTime:null}),'戸田 12R　優勝戦');
assert.equal(finalRaceText({venue:'戸田',race:12,raceName:'優勝戦',startTime:'16:15'}),'戸田 12R　優勝戦　16:15発走');
assert.equal(finalRaceText({venue:'浜松',race:11,raceName:'準優勝戦',startTime:'15:24',feature:'mori'}),'浜松 11R　準優勝戦　15:24発走');
assert.equal(finalEventLabel('SG日本選手権オートレース'),'日本選手権オートレース');
assert.equal(finalEventLabel('GⅢ 周防国府杯争奪戦'),'周防国府杯争奪戦');
assert.equal(displayGrade('G3','keirin'),'GⅢ');
assert.equal(displayGrade('G1','auto'),'GⅠ');
assert.equal(displayGrade('G2','soda'),'G2');
assert.equal(displayGrade('一般','auto'),'普通');
assert.equal(isMajorGrade('GⅢ'),true);
assert.equal(isMajorGrade('普通'),false);
assert.equal(finalRiderName('郡司浩平 選手','keirin'),'郡司 浩平');
assert.equal(finalRiderName('清水 裕友選手','keirin'),'清水 裕友');
assert.equal(finalRiderName('郡司浩平','keirin'),'郡司 浩平');
assert.equal(finalRiderName('選手A','keirin'),'選手A');
assert.equal(finalRiderName('青山 周平 選手','auto'),'青山 周平 選手');
assert.equal(finalRiderName('郡司浩平','keirin'),'郡司 浩平');
assert.equal(finalRiderName('佐々木豪','keirin'),'佐々木 豪');
assert.equal(finalRiderName('清水裕友 地元','keirin'),'清水 裕友');
assert.equal(finalRiderName('森且行','keirin'),'森 且行');
const moriRace={...card('auto','浜松',11,'15:24'),raceName:'森且行出走',
  feature:'mori',riders:[
    ...Array.from({length:7},(_,i)=>({number:i+1,name:'選手'+(i+1)})),
    {number:8,name:'森 且行'}]};
assert.equal(verifiedFinals({date:day,finals:{items:[moriRace]}},day).length,1);
assert.equal(verifiedFinals({date:day,finals:{items:[
  {...moriRace,riders:moriRace.riders.slice(0,7)}]}},day).length,0);

for(const [size,left,right] of [[6,3,3],[7,4,3],[8,4,4],[9,5,4]]){
  const riders=Array.from({length:size},(_,i)=>({number:size-i,name:'選手'+i}));
  const [lhs,rhs]=splitFinalRiders(riders);
  assert.equal(lhs.length,left,'left rider count: '+size);
  assert.equal(rhs.length,right,'right rider count: '+size);
  assert.deepEqual([...lhs,...rhs].map(r=>r.number),
    Array.from({length:size},(_,i)=>i+1),'riders in ascending car number: '+size);
}

const css=fs.readFileSync(path.join(__dirname,'..','styles.css'),'utf8');
const fontTokens={30:7,60:6,80:5};
for(const [size,expectedCount] of Object.entries(fontTokens)){
  const token='--font-'+size;
  const definition=new RegExp('\\s'+token+':\\s*'+size+'px;');
  assert.match(css,definition,'font token must directly specify its px size: '+token);
  const usages=[...css.matchAll(new RegExp('font-size:\\s*var\\('+token+'\\);','g'))];
  assert.equal(usages.length,expectedCount,'all existing '+size+'px styles must directly use '+token);
}
assert.doesNotMatch(css,/font-size:\s*\d+(?:\.\d+)?px\b/,
                    'font-size must use the shared CSS tokens directly');
assert.doesNotMatch(css,/--font-(?:30|60|80):\s*var\(/,
                    'font variables must never alias other variables');
assert.doesNotMatch(css,/--muted\s*:/,'unused secondary-text variable must be removed');
assert.doesNotMatch(css,/\.message,\s*\.detail\s*\{/,'unused message styles removed');
assert.doesNotMatch(css,/\.entry \.time-type\[data-type=/,'time icon color directly declared');
assert.match(css,/\.entry \.time-icon\s*\{[^}]*color:\s*#e4a529;/s);
assert.match(css,/\.grade\s*\{[^}]*height:\s*35px;/s,
             'all grade labels use the same 35px base height');
assert.match(css,/\.grade\[data-tier="major"\]\s*\{[^}]*background:\s*var\(--grade-major\);/s,
             'major grade labels use the shared grade selector');
assert.match(css,/\.final-race \.grade\s*\{[^}]*height:\s*80px;/s,
             'racecard badge retains its special 80px height');
assert.match(css,/\.header\s*\{[^}]*height:\s*100px;[^}]*margin-bottom:\s*8px;/s,
             'the header is shared unchanged by both venue and final screens');
assert.doesNotMatch(css,/\.stage\.is-final \.header\s*\{/,
                    'do not duplicate the shared date header styles');
assert.match(css,/\.final-screen\s*\{[^}]*top:\s*120px;[^}]*width:\s*1920px;[^}]*height:\s*960px;/s);
assert.match(css,/\.final-screen\s*\{[^}]*background:\s*var\(--white\);/s);
assert.match(css,/:root\s*\{[^}]*--white:\s*#fff;/s);
assert.doesNotMatch(css,/#ffffff\b/);
assert.match(css,/\.panel\s*\{[^}]*gap:\s*var\(--tile-gap\);/s);
assert.match(css,/\.final-title\s*\{[^}]*background:\s*var\(--keirin\);/s);
assert.match(css,/\.final-title\[data-sport="auto"\]\s*\{[^}]*background:\s*var\(--auto\);/s);
assert.match(css,/\.final-title\[data-sport="soda"\]\s*\{[^}]*background:\s*var\(--soda\);/s);
assert.match(css,/\.final-title-text\s*\{[^}]*transform-origin:/s);
assert.match(css,/\.final-rider\.is-mori\s*\{[^}]*var\(--grade-major\)/s);
for(const className of ['final-title','final-rider','final-number']){
  const re=new RegExp('\\.'+className+'\\s*\\{[^}]*font-size:\\s*var\\(--font-80\\);','s');
  assert.match(css,re,className+' should use 80px');
}
assert.match(css,/\.final-race\s*\{[^}]*font-size:\s*var\(--font-60\);/s);
assert.match(css,/\.final-race \.grade\s*\{[^}]*font-size:\s*var\(--font-60\);/s);
assert.match(css,/\.final-card\s*\{[^}]*width:\s*1600px;/s);
assert.match(css,/\.final-rider\.is-scratched::after\s*\{[^}]*var\(--grade-major\)/s);
assert.match(css,/\.fullscreen-hint-line\s*\{/s);
assert.match(css,/\.final-riders\s*\{[^}]*grid-template-columns:\s*repeat\(2,/s);
assert.match(css,/\.final-rider-column\s*\{[^}]*grid-template-rows:\s*repeat\(5,/s);
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
const appSource=fs.readFileSync(path.join(__dirname,'..','app.js'),'utf8');
assert.doesNotMatch(html,/class="entries auto-tiles"/,'unused class removed');
assert.doesNotMatch(appSource,/mori-today/,'unused Mori class removed');
assert.equal((appSource.match(/gradeBadge\(/g)||[]).length,4,
             'one badge factory, used by all three renderers');
assert.doesNotMatch(html,/読み込み中|確認中/,'initial HTML must be blank until verified data arrives');
assert.doesNotMatch(appSource,/['"`][^'"`]*(?:情報確認中|出走予定確認中|出走R確認中|発走時刻確認中)[^'"`]*['"`]/,
                    'do not render pending-verification text');
assert.match(html,/id="final-screen"[^>]*hidden/);
assert.match(html,/<kbd>Space Key<\/kbd><span>で出走表表示<\/span>/);
console.log('Final board tests passed: race info+grade label 60px, keirin suffix removal, 2-column riders and other text 80px');
