/* Japanese public holidays under the current law (2022–2099).
 * Includes citizens' holidays and substitute holidays. Equinoxes outside
 * officially published years are astronomical approximations. */
(() => {
  'use strict';
  const cache=new Map();
  const key=d=>d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0')+'-'+String(d.getUTCDate()).padStart(2,'0');
  const utc=(y,m,d)=>new Date(Date.UTC(y,m-1,d));
  const monday=(y,m,n)=>{
    const first=utc(y,m,1).getUTCDay();
    return 1+(8-first)%7+7*(n-1);
  };
  function holidaysForYear(y){
    if(cache.has(y))return cache.get(y);
    const base=new Set();
    const add=(m,d)=>base.add(key(utc(y,m,d)));
    const spring=Math.floor(20.8431+0.242194*(y-1980)-Math.floor((y-1980)/4));
    const autumn=Math.floor(23.2488+0.242194*(y-1980)-Math.floor((y-1980)/4));
    add(1,1);add(1,monday(y,1,2));
    add(2,11);add(2,23);add(3,spring);
    add(4,29);add(5,3);add(5,4);add(5,5);
    add(7,monday(y,7,3));add(8,11);
    add(9,monday(y,9,3));add(9,autumn);
    add(10,monday(y,10,2));add(11,3);add(11,23);

    // A non-holiday between two national holidays is also a holiday.
    const citizens=new Set();
    for(let date=utc(y,1,2);date.getUTCFullYear()===y;date.setUTCDate(date.getUTCDate()+1)){
      const before=new Date(date),after=new Date(date);
      before.setUTCDate(before.getUTCDate()-1);
      after.setUTCDate(after.getUTCDate()+1);
      if(!base.has(key(date))&&base.has(key(before))&&base.has(key(after)))citizens.add(key(date));
    }
    // Sunday national holidays move to the nearest subsequent free day.
    const substitute=new Set();
    for(const iso of base){
      const date=new Date(iso+'T00:00:00Z');
      if(date.getUTCDay()!==0)continue;
      do{date.setUTCDate(date.getUTCDate()+1);}
      while(base.has(key(date))||citizens.has(key(date))||substitute.has(key(date)));
      substitute.add(key(date));
    }
    const result=new Set([...base,...citizens,...substitute]);
    cache.set(y,result);
    return result;
  }
  function isJapaneseHoliday(iso){
    if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))return false;
    const y=Number(iso.slice(0,4));
    if(y<2022||y>2099)return false;
    return holidaysForYear(y).has(iso);
  }
  if(typeof window!=='undefined')window.AssemblyHoliday={isJapaneseHoliday};
  if(typeof module!=='undefined'&&module.exports)module.exports={isJapaneseHoliday};
})();
