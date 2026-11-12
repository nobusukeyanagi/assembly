(() => {
'use strict';
const weekday=['日','月','火','水','木','金','土'];
const limits={keirin:12,auto:3,soda:8};
let latest=null;
const get=id=>document.getElementById(id);
function node(tag,cls,text){
  const el=document.createElement(tag);
  if(cls)el.className=cls;
  if(text!==undefined)el.textContent=text;
  return el;
}
function today(){
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{
    timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'
  }).formatToParts(new Date()).map(x=>[x.type,x.value]));
  return parts.year+'-'+parts.month+'-'+parts.day;
}
function resize(){
  get('stage').style.setProperty('--scale',String(Math.min(innerWidth/1920,innerHeight/1080)));
}
function dateDisplay(d){
  const [y,m,day]=d.split('-').map(Number);
  get('date').textContent=y+'年'+m+'月'+day+'日';
  const holiday=window.AssemblyHoliday?.isJapaneseHoliday(d)===true;
  const label=get('weekday-label');
  const dayOfWeek=new Date(Date.UTC(y,m-1,day)).getUTCDay();
  label.textContent=weekday[dayOfWeek]+(holiday?'祝':'');
  label.classList.toggle('is-holiday',holiday);
  label.classList.toggle('is-sunday',dayOfWeek===0&&!holiday);
  label.classList.toggle('is-saturday',dayOfWeek===6&&!holiday);
}
function error(root,message,detail){
  root.replaceChildren(node('p','message',message));
  if(detail)root.append(node('p','detail',detail));
}
function isMajorGrade(grade){
  return /^(?:GP|SG|G[123]|特G1)$/.test(String(grade||'').replaceAll('Ⅰ','1').replaceAll('Ⅱ','2').replaceAll('Ⅲ','3'));
}
// Keep source grade codes normalized; use Roman numerals only in Keirin/Autorace labels.
function displayGrade(grade,id){
  const value=String(grade||'—');
  if(id==='auto'&&(value==='一般'||value==='普通'))return '普通';
  if(id!=='keirin'&&id!=='auto')return value;
  const roman={'1':'Ⅰ','2':'Ⅱ','3':'Ⅲ'};
  return value.replace(/([GF])([123])/g,(_,letter,number)=>letter+roman[number]);
}
const timeIcons={'モーニング':'☀','ミッドナイト':'★'};
function filledMoon(){
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 16 16');
  svg.setAttribute('class','moon-symbol');
  svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS(ns,'path');
  path.setAttribute('d','M6 .278a.768.768 0 0 1 .08.858 7.2 7.2 0 0 0-.878 3.48c0 4.072 3.314 7.385 7.385 7.385a7.2 7.2 0 0 0 3.48-.878.77.77 0 0 1 .858.08A8 8 0 1 1 6 .278');
  svg.append(path);
  return svg;
}
function timeBadge(type){
  if(!type||type==='デイ'||type==='確認中')return null;
  const tag=node('span','time-type');
  tag.dataset.type=type;
  if(type==='ナイター'){
    const icon=node('span','time-icon');
    icon.append(filledMoon());
    tag.append(icon);
  } else if(timeIcons[type]){
    tag.append(node('span','time-icon',timeIcons[type]));
  } else {
    tag.append(node('span','time-text',type));
  }
  tag.setAttribute('aria-label',type);
  return tag;
}
function card(item,id){
  const el=node('article','entry');
  const title=node('div','venue',item.name||'—');
  const meta=node('div','meta');
  const grade=node('span','grade',displayGrade(item.grade,id));
  grade.dataset.tier=isMajorGrade(item.grade)?'major':'regular';
  meta.append(grade);
  meta.append(node('span','day',String(item.day||'—').normalize('NFKC')));
  if(id==='keirin'||id==='auto'||id==='soda'){
    const icon=timeBadge(item.timeType);
    if(icon)meta.append(icon);
    if(item.girls) {
      const heart=node('span','girls','♥');
      heart.setAttribute('aria-label','ガールズ');
      meta.append(heart);
    }
  }
  el.append(title,meta);
  return el;
}
function isEmptyVenueSection(section,stale){
  return !stale&&Boolean(section)&&
    (section.status==='ok'||section.status==='cached')&&
    Array.isArray(section.items)&&section.items.length===0;
}
function venueStatusText(section,stale,mode){
  if(stale)return mode==='selected'?'指定日の情報を確認中':'本日の情報を確認中';
  if(!section||section.status==='error')return '開催情報を確認できません';
  if(isEmptyVenueSection(section,false))return '開催情報がありません';
  if(!Array.isArray(section.items)||section.items.length===0)return '情報を確認中';
  return null;
}
function entries(id,section,stale,mode){
  const root=get(id+'-entries');
  root.classList.remove('is-notice');
  const message=venueStatusText(section,stale,mode);
  if(message){
    root.classList.add('is-notice');
    root.replaceChildren(node('p','band-notice',message));
    return;
  }
  const records=section.items;
  const max=limits[id];
  root.replaceChildren(...records.slice(0,max).map(i=>card(i,id)));
  if(records.length>max)console.warn(id+' : maximum displayed entries exceeded');
}
function mori(section,stale,targetDate){
  const root=get('mori-body');
  const status=get('mori-status');
  root.classList.remove('mori-today');
  status.textContent='確認中';
  if(stale){error(root,'情報確認中');return}
  if(!section||section.status==='error'||!section.item){
    error(root,'出走予定確認中');return;
  }
  const x=section.item;
  const isToday=x.type==='today'&&x.date===targetDate;
  const numbers=Array.isArray(x.races)?x.races:[x.race];
  const races=[...new Set(numbers.filter(n=>Number.isInteger(n)&&n>=1&&n<=12))].sort((a,b)=>a-b);
  const hasRace=isToday&&races.length>0;
  const d=/^\d{4}-\d{2}-\d{2}$/.test(x.date||'')?
    Number(x.date.slice(5,7))+'月'+Number(x.date.slice(8,10))+'日':'未定';
  status.textContent=hasRace?'本日出走':isToday?'出走R確認中':'次回予定';
  const venue=node('div','venue mori-primary',(x.name||'—')+(hasRace?' '+races.map(n=>n+'R').join('・'):''));
  const meta=node('div','meta mori-detail');
  if(x.grade){
    const gr=node('span','grade',displayGrade(x.grade,'auto'));
    gr.dataset.tier=isMajorGrade(x.grade)?'major':'regular';
    meta.append(gr);
  }
  if(hasRace){
    const times=x.startTimes&&typeof x.startTimes==='object'?x.startTimes:{};
    const starts=races.map(n=>times[String(n)]);
    const verified=starts.length>0&&starts.every(t=>typeof t==='string'&&/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(t));
    meta.append(node('span','day',verified?starts.join('/'):'発走時刻確認中'));
  } else {
    meta.append(node('span','day',d));
  }
  const timeIcon=timeBadge(x.timeType);
  if(timeIcon)meta.append(timeIcon);
  root.replaceChildren(venue,meta);
  if(isToday)root.classList.add('mori-today');
}
function layoutRows(sections,stale){
  const hasVerifiedItems=section=>!stale&&section&&
    (section.status==='ok'||section.status==='cached')&&Array.isArray(section.items);
  const keirinRows=hasVerifiedItems(sections.keirin)&&sections.keirin.items.length<=8?2:3;
  const sodaRows=hasVerifiedItems(sections.soda)&&sections.soda.items.length<=4?1:2;
  return {keirinRows,sodaRows,totalRows:keirinRows+1+sodaRows};
}

const vehiclePalette={
  1:['#ffffff','#15191b'],2:['#181a1d','#ffffff'],3:['#d92735','#ffffff'],
  4:['#2364c9','#ffffff'],5:['#ffd21c','#171717'],6:['#288452','#ffffff'],
  7:['#e97923','#181818'],8:['#f0a0be','#181818'],9:['#783da4','#ffffff']
};
let finalCards=[];
let activeFinalIndex=-1;
let activeFinalKey=null;
function verifiedFinals(data,targetDate){
  if(!data||data.date!==targetDate||!Array.isArray(data.finals?.items))return [];
  return data.finals.items.filter(r=>(
    (r.sport==='keirin'||r.sport==='auto')&&
    typeof r.event==='string'&&r.event.length>0&&
    typeof r.raceName==='string'&&/決勝|優勝戦/.test(r.raceName)&&
    typeof r.venue==='string'&&r.venue.length>0&&
    Number.isInteger(r.race)&&r.race>=1&&r.race<=12&&
    /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(r.startTime)&&
    Array.isArray(r.riders)&&r.riders.length>=5&&r.riders.length<=9&&
    r.riders.every(p=>Number.isInteger(p.number)&&p.number>=1&&p.number<=9&&
                   typeof p.name==='string'&&p.name.length>0)
  ));
}
function finalIdentity(item){
  return item.sport+'|'+item.venue+'|'+item.race;
}
function nextFinalIndex(index,length){
  return length>0 ? (index+1<length ? index+1 : -1) : -1;
}
function finalRaceLabel(name){
  if(String(name).includes('優勝戦'))return '優勝戦';
  if(String(name).includes('決勝'))return '決勝';
  return '—';
}
function finalEventLabel(event){
  return String(event||'').replace(/^(?:特G[ⅠⅡⅢ123]|G[ⅠⅡⅢ123]|F[ⅠⅡ12]|SG|GP)[\s　]*/i,'').trim();
}
function finalRiderName(name,sport){
  const value=String(name||'').trim();
  return sport==='keirin' ? value.replace(/\\s*選手\\s*$/,'').trim() : value;
}
function splitFinalRiders(riders){
  const sorted=[...riders].sort((a,b)=>a.number-b.number);
  const leftCount=Math.ceil(sorted.length/2);
  return [sorted.slice(0,leftCount),sorted.slice(leftCount)];
}
function paintFinal(){
  const active=activeFinalIndex>=0&&activeFinalIndex<finalCards.length;
  const stage=get('stage');
  const screen=get('final-screen');
  stage.classList.toggle('is-final',active);
  screen.hidden=!active;
  if(!active)return;
  const data=finalCards[activeFinalIndex];
  const board=get('final-card');
  const heading=node('div','final-title',finalEventLabel(data.event));
  heading.dataset.sport=data.sport;
  const race=node('div','final-race');
  const grade=node('span','grade',displayGrade(data.grade||'—',data.sport));
  grade.dataset.tier=isMajorGrade(data.grade)?'major':'regular';
  race.append(grade,node('span','final-race-detail',
    data.venue+' '+data.race+'R '+finalRaceLabel(data.raceName)+' '+data.startTime+'発走'));
  const grid=node('div','final-riders');
  for(const riders of splitFinalRiders(data.riders)){
    const column=node('div','final-rider-column');
    for(const rider of riders){
      const row=node('div','final-row');
      const number=node('span','final-number',String(rider.number));
      number.dataset.number=String(rider.number);
      const [background,color]=vehiclePalette[rider.number];
      number.style.backgroundColor=background;
      number.style.color=color;
      row.append(number,node('span','final-rider',finalRiderName(rider.name,data.sport)));
      column.append(row);
    }
    for(let n=riders.length;n<5;n++){
      const empty=node('div','final-row final-row-empty');
      empty.setAttribute('aria-hidden','true');
      column.append(empty);
    }
    grid.append(column);
  }
  board.replaceChildren(heading,race,grid);
}
function advanceFinal(){
  activeFinalIndex=nextFinalIndex(activeFinalIndex,finalCards.length);
  activeFinalKey=activeFinalIndex>=0?finalIdentity(finalCards[activeFinalIndex]):null;
  paintFinal();
}
function onSpaceKey(event){
  if(event.code!=='Space'&&event.key!==' ')return;
  if(event.repeat||event.ctrlKey||event.metaKey||event.altKey)return;
  const target=event.target;
  if(target&&target.closest&&target.closest('input,textarea,select,button,[contenteditable="true"]'))return;
  if(finalCards.length===0)return;
  event.preventDefault();
  advanceFinal();
}
function render(data,targetDate,mode){
  latest=data;
  const stale=data.date!==targetDate,s=data.sections||{};
  const layout=layoutRows(s,stale);
  const stage=get('stage');
  stage.style.setProperty('--keirin-rows',String(layout.keirinRows));
  stage.style.setProperty('--soda-rows',String(layout.sodaRows));
  stage.dataset.totalRows=String(layout.totalRows);
  get('display-mode-indicator').hidden=mode!=='selected';
  dateDisplay(targetDate);
  entries('keirin',s.keirin,stale,mode);
  entries('auto',s.auto,stale,mode);
  entries('soda',s.soda,stale,mode);
  mori(s.mori,stale,targetDate);
  const selected=activeFinalKey;
  finalCards=verifiedFinals(data,targetDate);
  activeFinalIndex=selected?finalCards.findIndex(r=>finalIdentity(r)===selected):-1;
  activeFinalKey=activeFinalIndex>=0?selected:null;
  paintFinal();
}
async function displayChoice(){
  try{
    const response=await fetch('./data/display.json?v='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('Display setting HTTP '+response.status);
    const choice=await response.json();
    if(choice.mode==='selected'&&/^\d{4}-\d{2}-\d{2}$/.test(choice.date)){
      return {date:choice.date,mode:'selected',file:'selected.json'};
    }
  }catch(err){
    console.warn('Display setting unavailable; using today',err);
  }
  return {date:today(),mode:'today',file:'today.json'};
}
async function refresh(){
  const choice=await displayChoice();
  try{
    const response=await fetch('./data/'+choice.file+'?v='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('HTTP '+response.status);
    const data=await response.json();
    if(!data.date||!data.sections)throw Error('Missing schedule fields');
    render(data,choice.date,choice.mode);
  }catch(err){
    if(!(latest&&latest.date===choice.date))render({date:choice.date,sections:{}},choice.date,choice.mode);
    console.warn(err);
  }
}
// Allow unit testing the actual row selection logic without a browser.
if(typeof module!=='undefined'&&module.exports)module.exports={layoutRows,isEmptyVenueSection,venueStatusText,verifiedFinals,nextFinalIndex,splitFinalRiders,finalRaceLabel,finalEventLabel,finalRiderName};
if(typeof document==='undefined')return;
resize();
addEventListener('resize',resize);
document.addEventListener('keydown',onSpaceKey);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
refresh();
setInterval(refresh,600000);
})();