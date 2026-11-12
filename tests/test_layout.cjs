'use strict';
const assert=require('node:assert/strict');
const {layoutRows}=require('../app.js');

// The same function used by the published browser determines all row counts.
function sections(keirin,soda,keirinStatus='ok',sodaStatus='ok'){
  return {
    keirin:{status:keirinStatus,items:Array.from({length:keirin},(_,i)=>({name:'k'+i}))},
    soda:{status:sodaStatus,items:Array.from({length:soda},(_,i)=>({name:'s'+i}))},
  };
}
const cases=[
  {k:12,s:8,expected:[3,2,6,146]},
  {k:12,s:4,expected:[3,1,5,177.6]},
  {k:9,s:1,expected:[3,1,5,177.6]},
  {k:8,s:8,expected:[2,2,5,177.6]},
  {k:8,s:4,expected:[2,1,4,225]},
  {k:4,s:0,expected:[2,1,4,225]},
  {k:0,s:4,expected:[2,1,4,225]},
];
const tileHeights={4:225,5:177.6,6:146};
for(const {k,s,expected} of cases){
  const out=layoutRows(sections(k,s),false);
  const h=tileHeights[out.totalRows];
  assert.deepEqual([out.keirinRows,out.sodaRows,out.totalRows,h],expected,`keirin=${k} soda=${s}`);
  const band=rowCount=>rowCount*h+(rowCount-1)*12+16;
  const used=band(out.keirinRows)+band(1)+band(out.sodaRows);
  assert.ok(Math.abs(used-960)<0.00001,`must fill exactly 960px: ${used}`);
}
assert.deepEqual(layoutRows(sections(12,4,'error','ok'),false),{keirinRows:3,sodaRows:1,totalRows:5});
assert.deepEqual(layoutRows(sections(8,4,'ok','error'),false),{keirinRows:2,sodaRows:2,totalRows:5});
assert.deepEqual(layoutRows(sections(8,4),true),{keirinRows:3,sodaRows:2,totalRows:6});
assert.deepEqual(layoutRows(sections(8,4,'cached','cached'),false),{keirinRows:2,sodaRows:1,totalRows:4});
console.log('Layout tests passed: 4–6-row height, SODA/Keirin boundaries, errors, cache, stale data');
