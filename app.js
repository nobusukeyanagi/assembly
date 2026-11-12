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
  get('weekday').textContent='（'+weekday[new Date(Date.UTC(y,m-1,day)).getUTCDay()]+'）';
}
function error(root,message,detail){
  root.replaceChildren(node('p','message',message));
  if(detail)root.append(node('p','detail',detail));
}
function isMajorGrade(grade){
  return /^(?:GP|SG|G[123]|特G1)$/.test(String(grade||'').replaceAll('Ⅰ','1').replaceAll('Ⅱ','2').replaceAll('Ⅲ','3'));
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
function card(item,id){
  const el=node('article','entry');
  const title=node('div','venue',item.name||'—');
  const meta=node('div','meta');
  const grade=node('span','grade',item.grade||'—');
  grade.dataset.tier=isMajorGrade(item.grade)?'major':'regular';
  meta.append(grade);
  meta.append(node('span','day',String(item.day||'—').normalize('NFKC')));
  if(id==='keirin'||id==='auto'||id==='soda'){
    const type=item.timeType||null;
    if(type&&type!=='デイ'){
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
      meta.append(tag);
    }
    if(item.girls) {
      const heart=node('span','girls','♥');
      heart.setAttribute('aria-label','ガールズ');
      meta.append(heart);
    }
  }
  el.append(title,meta);
  return el;
}
function entries(id,section,stale){
  const root=get(id+'-entries');
  const records=section&&Array.isArray(section.items)?section.items:[];
  const max=limits[id];
  const tiles=records.slice(0,max);
  if(stale){error(root,'本日の情報を確認中');return}
  if(!section||section.status==='error'){
    error(root,'開催情報を確認できません');return;
  }
  if(!records.length){
    error(root,section.status==='ok'?'本日の開催はありません':'情報を確認中');return;
  }
  root.replaceChildren(...tiles.map(i=>card(i,id)));
  if(records.length>max)console.warn(id+' : maximum displayed entries exceeded');
}
function mori(section,stale){
  const root=get('mori-body');
  const status=get('mori-status');
  root.classList.remove('mori-today');
  status.textContent='確認中';
  if(stale){error(root,'情報確認中');return}
  if(!section||section.status==='error'||!section.item){
    error(root,'出走予定確認中');return;
  }
  const x=section.item;
  const isToday=x.type==='today'&&x.date===today();
  const hasRace=isToday&&Number.isInteger(x.race);
  const d=/^\d{4}-\d{2}-\d{2}$/.test(x.date||'')?
    Number(x.date.slice(5,7))+'月'+Number(x.date.slice(8,10))+'日':'未定';
  status.textContent=hasRace?'本日出走':isToday?'出走R確認中':'次回予定';
  const primary=hasRace?x.name+' '+x.race+'R':isToday?x.name+' R確認中':d+' '+(x.name||'');
  root.replaceChildren(node('div','mori-primary',primary));
  if(isToday)root.classList.add('mori-today');
}
function render(data){
  latest=data;
  const d=today(),stale=data.date!==d,s=data.sections||{};
  const keirinItems=s.keirin?.items;
  const fiveRows=!stale&&s.keirin?.status!=='error'&&Array.isArray(keirinItems)&&keirinItems.length<=8;
  get('stage').classList.toggle('five-rows',fiveRows);
  dateDisplay(d);
  entries('keirin',s.keirin,stale);
  entries('auto',s.auto,stale);
  entries('soda',s.soda,stale);
  mori(s.mori,stale);
}
async function refresh(){
  try{
    const response=await fetch('./data/today.json?v='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('HTTP '+response.status);
    const data=await response.json();
    if(!data.date||!data.sections)throw Error('Missing schedule fields');
    render(data);
  }catch(err){
    if(!(latest&&latest.date===today()))render({date:'',sections:{}});
    console.warn(err);
  }
}
resize();
addEventListener('resize',resize);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
refresh();
setInterval(refresh,600000);
})();