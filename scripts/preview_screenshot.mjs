// Preview-only renderer. Never alters production HTML, JS, or data/today.json.
// Run: PREVIEW_DATE=2026-11-23 KEIRIN_COUNT=12 node scripts/preview_screenshot.mjs
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const date=process.env.PREVIEW_DATE || '2026-11-23';
const countText=process.env.KEIRIN_COUNT || '12';
const count=Number(countText);
if(!/^\d{4}-\d{2}-\d{2}$/.test(date) ||
   !Number.isFinite(Date.parse(date+'T00:00:00Z')) ||
   new Date(date+'T00:00:00Z').toISOString().slice(0,10)!==date){
  throw Error('Invalid PREVIEW_DATE (YYYY-MM-DD): '+date);
}
if(!/^(?:0|[1-9]|1[0-2])$/.test(countText)){
  throw Error('KEIRIN_COUNT must be 0–12: '+countText);
}

const keirinNames=['いわき平','函館','青森','弥彦','松戸','平塚','豊橋','四日市','防府','小倉','松阪','佐世保'];
const autoNames=['伊勢崎','山陽','飯塚'];
const sodaNames=['桐生','戸田','多摩川','浜名湖','蒲郡','三国','びわこ','宮島'];
const timeType=(n,total)=>{
  if(n<Math.min(2,total))return 'モーニング';
  if(n<Math.ceil(total/2))return 'デイ';
  if(n<total-2)return 'ナイター';
  return 'ミッドナイト';
};
const item=(name,i,total,category)=>({
  name,
  grade:category==='keirin'?['F2','F1','G3','G2','G1'][i%5]:
    category==='auto'?['一般','G2','一般'][i%3]:['一般','G1','G2','一般'][i%4],
  timeType:category==='soda'?(i%4===0?'ナイター':'デイ'):timeType(i,total),
  day:['初日','2日目','3日目','最終日'][i%4],
  girls:category!=='auto'&&i%5===0,
});
const keirin=keirinNames.slice(0,count).map((name,i)=>item(name,i,count,'keirin'));
const auto=autoNames.map((name,i)=>item(name,i,autoNames.length,'auto'));
const soda=sodaNames.map((name,i)=>item(name,i,sodaNames.length,'soda'));
const fixture={
  date,
  updatedAt:null,
  preview:true,
  note:'All scheduled events and rider data in this file are fictitious layout fixtures, NOT actual race schedules.',
  sections:{
    keirin:{status:'ok',items:keirin},
    auto:{status:'ok',items:auto},
    soda:{status:'ok',items:soda},
    mori:{status:'ok',items:[],item:{date,name:'川口',type:'today',race:9,grade:'G1',timeType:'ナイター'}},
  },
};

const directory=resolve(process.cwd(),'preview-output');
await mkdir(directory,{recursive:true});
const json=(obj)=>JSON.stringify(obj,null,2)+'\n';
await writeFile(resolve(directory,'fixture.json'),json(fixture),'utf8');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};
const assetPaths={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/holidays.js':'holidays.js','/styles.css':'styles.css'};
const server=createServer(async (req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1');
  if(url.pathname==='/data/today.json'){
    res.writeHead(200,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
    res.end(json(fixture));return;
  }
  const filename=assetPaths[url.pathname];
  if(!filename){res.writeHead(404);res.end('Not found');return;}
  try{
    const bytes=await readFile(resolve(process.cwd(),filename));
    const ext=filename.slice(filename.lastIndexOf('.'));
    res.writeHead(200,{'Content-Type':types[ext]||'application/octet-stream'});
    res.end(bytes);
  }catch(err){res.writeHead(500);res.end('Cannot read asset');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const address=server.address();
let browser;
try{
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(iso=>{
    const RealDate=Date;
    const fixed=new RealDate(iso+'T12:00:00+09:00').getTime();
    window.Date=class extends RealDate{
      constructor(...args){super(...(args.length?args:[fixed]));}
      static now(){return fixed;}
    };
  },date);
  const url='http://127.0.0.1:'+address.port+'/';
  await page.goto(url,{waitUntil:'networkidle'});
  await page.waitForFunction(expected=>{
    const label=document.querySelector('#date')?.textContent;
    const got=document.querySelectorAll('#keirin-entries .entry').length;
    return label&&!label.includes('--')&&(expected===0||got===expected);
  },count,{timeout:15000});
  // Wait until the 2-second F11 introduction has disappeared.
  await page.waitForTimeout(2200);
  await page.evaluate(()=>{
    const marker=document.createElement('div');
    marker.textContent='PREVIEW / サンプルデータ（実開催情報ではありません）';
    marker.style.cssText='position:fixed;z-index:9999;right:12px;top:8px;background:#25323a;color:#fff;padding:7px 12px;font:700 18px sans-serif;border-radius:5px;pointer-events:none';
    document.body.append(marker);
  });
  const inspection=await page.evaluate(()=>{
    const rect=el=>{
      const r=el.getBoundingClientRect();
      return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
    };
    const venues=[...document.querySelectorAll('.entry .venue')];
    const clipped=venues.filter(el=>el.scrollWidth>el.clientWidth+1).map(el=>({name:el.textContent,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth}));
    const outside=[...document.querySelectorAll('.entry')].filter(el=>{
      const r=el.getBoundingClientRect();
      return r.left<-.5||r.top<-.5||r.right>innerWidth+.5||r.bottom>innerHeight+.5;
    }).map(el=>el.textContent.slice(0,30));
    return {
      header:document.querySelector('.header')?.textContent.trim(),
      date:document.querySelector('#date')?.textContent,
      weekday:document.querySelector('#weekday')?.textContent,
      holidayRed:document.querySelector('#weekday-label')?.classList.contains('is-holiday'),
      keirinCount:document.querySelectorAll('#keirin-entries .entry').length,
      autoCount:document.querySelectorAll('#auto-entries .entry').length,
      sodaCount:document.querySelectorAll('#soda-entries .entry').length,
      fiveRows:document.querySelector('#stage')?.classList.contains('five-rows'),
      stage:rect(document.querySelector('#stage')),
      clippedVenues:clipped,
      offscreenCards:outside,
    };
  });
  const screenshot=resolve(directory,date+'-keirin'+count+'.png');
  await page.screenshot({path:screenshot,fullPage:false,animations:'disabled'});
  const report={
    testedDate:date,requestedKeirinCount:count,viewport:'1920x1080',simulated:true,
    warning:'Fixture data does not represent actual venues or races for the selected date.',
    ...inspection,
    browserErrors:errors,
  };
  await writeFile(resolve(directory,'report.json'),json(report),'utf8');
  process.stdout.write(json(report));
  if(inspection.keirinCount!==count)throw Error('Expected '+count+' Keirin cards, got '+inspection.keirinCount);
  if(inspection.autoCount!==3||inspection.sodaCount!==8)throw Error('Sample auto/SODA cards are missing');
  if(inspection.fiveRows!==(count<=8))throw Error('Incorrect 5/6-row arrangement');
  if(inspection.offscreenCards.length||inspection.clippedVenues.length)throw Error('Card clipping or overflow detected');
  if(errors.length)throw Error('Browser JavaScript errors');
  if(date==='2026-11-23'&&(inspection.weekday!=='（月祝）'||!inspection.holidayRed)){
    throw Error('2026-11-23 holiday display mismatch');
  }
  console.log('Preview screenshot saved: '+screenshot);
}finally{
  if(browser)await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
