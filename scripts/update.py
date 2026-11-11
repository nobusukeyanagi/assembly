#!/usr/bin/env python3
"""JST daily meeting collector. Public official schedules; failures are visible."""
from __future__ import annotations
import argparse, json, logging, re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Asia/Tokyo')
KEIRIN='https://keirin.jp/sp/raceschedule'
AUTO='https://autorace.jp/race_info/Program'
BOAT='https://www.boatrace.jp/owpc/pc/race/index'
MORI='https://www.oddspark.com/autorace/PlayerDetail.do?playerCd=2529'
ASSEN='https://sp.atrc.jp/racer/racerasseninfo/player_id/2529'
SOURCES={'keirin':KEIRIN,'auto':'https://autorace.jp/','soda':'https://so-da.jp/aud/top','mori':ASSEN}
KEIRIN_NAMES='函館 青森 いわき平 弥彦 前橋 取手 宇都宮 大宮 西武園 京王閣 立川 松戸 千葉 川崎 平塚 小田原 伊東 静岡 名古屋 岐阜 大垣 豊橋 富山 松阪 四日市 福井 奈良 向日町 和歌山 岸和田 玉野 広島 防府 高松 小松島 高知 松山 小倉 久留米 武雄 佐世保 別府 熊本'.split()
AUTO_NAMES={'川口':'kawaguchi','伊勢崎':'isesaki','浜松':'hamamatsu','飯塚':'iizuka','山陽':'sanyo'}
SODA_NAMES='桐生 戸田 多摩川 浜名湖 蒲郡 三国 びわこ 宮島 若松 芦屋'.split()
DATE_RANGE=re.compile(r'(\d{1,2})\s*/\s*(\d{1,2})\s*[^\d/]{0,8}[～~〜\-－]\s*(\d{1,2})\s*/\s*(\d{1,2})')
BOAT_RANGE=re.compile(r'(\d{1,2})\s*/\s*(\d{1,2})\s*[-～~]\s*(\d{1,2})\s*/\s*(\d{1,2})')
GRADES=re.compile(r'^(?:GP|SG|特G[ⅠI1]|G[123ⅠⅡⅢI]{1,3}|F[12]|一般|普通)$',re.I)
logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
log=logging.getLogger('assembly')

def session():
    s=requests.Session()
    s.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=1,status_forcelist=[429,500,502,503,504],allowed_methods=['GET'])))
    s.headers.update({'User-Agent':'AssemblyMorningBoard/1.0 (public schedule dashboard)','Accept-Language':'ja-JP,ja;q=0.9'})
    return s

def fetch(s,url,params=None):
    r=s.get(url,params=params,timeout=(10,24))
    r.raise_for_status()
    if r.encoding is None or r.encoding.lower() in ('iso-8859-1','ascii'):r.encoding=r.apparent_encoding
    text=r.text
    if len(text)<1000 or any(x in text[:4500].lower() for x in ("verify that you're not a robot","captcha","access denied")):
        raise ValueError('自動アクセス制限または空の応答')
    return text

def grade(x):
    x=x.upper().replace(' ','').replace('　','').replace('Ⅰ','I').replace('Ⅱ','II').replace('Ⅲ','III')
    return {'GI':'G1','GII':'G2','GIII':'G3','特GI':'特G1','普通':'一般'}.get(x,x)

def period(today,a,b,c,d):
    all_dates=[]
    for y in range(today.year-1,today.year+2):
        try:
            st=date(y,a,b)
            en=date(y+int((c,d)<(a,b)),c,d)
            all_dates.append((min(abs((today-st).days),abs((today-en).days)),st,en))
        except ValueError:continue
    if not all_dates:return None
    _,st,en=min(all_dates,key=lambda x:x[0])
    return st,en

def day_label(today,st,en):
    if today==st:return '初日'
    if today==en:return '最終日'
    return str((today-st).days+1)+'日目'

def soup_with_alt(html):
    soup=BeautifulSoup(html,'html.parser')
    for x in soup(['script','style','noscript']):x.decompose()
    for img in soup.select('img[alt]'):
        val=img.get('alt','').strip()
        if val:img.replace_with(' '+val+' ')
    return soup

def parse_keirin(html,today):
    soup=soup_with_alt(html)
    tokens=[re.sub(r'\s+',' ',t).strip() for t in soup.stripped_strings]
    items=[];name=None;gr=None
    for token in tokens:
        if token in KEIRIN_NAMES:name=token;gr=None;continue
        if token.startswith('開催がありません'):gr=None;continue
        g=re.search(r'\b(?:GP|SG|G[123]|F[12]|GI{1,3})\b',token,re.I)
        if g and len(token)<28:gr=grade(g.group())
        m=DATE_RANGE.search(token)
        if not m or not name:continue
        bounds=period(today,*map(int,m.groups()))
        if not bounds or not bounds[0]<=today<=bounds[1]:continue
        if not gr:raise ValueError(name+' のグレードを読み取れません')
        items.append({'name':name,'grade':gr,'day':day_label(today,*bounds)})
    if sum(bool(DATE_RANGE.search(t)) for t in tokens)<12:raise ValueError('競輪開催日程のDOMを解析できません')
    if not items:raise ValueError('競輪開催場を特定できません')
    return items

def parse_auto(html,name,today):
    soup=BeautifulSoup(html,'html.parser')
    for x in soup(['script','style','noscript']):x.decompose()
    text=soup.get_text(' ',strip=True)
    pm=re.search(r'開催期間\s*[：:]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日',text)
    dm=re.search(r'開催\s*第\s*(\d{1,2})\s*日目',text)
    if not pm or not dm:return None
    st=date(*map(int,pm.groups()));n=int(dm.group(1))
    if (today-st).days!=n-1 or not 1<=n<=8:return None
    heading=text[max(0,pm.start()-210):pm.start()]
    gm=re.search(r'(特\s*G[ⅠI1]|SG|G\s*(?:Ⅰ|Ⅱ|Ⅲ|III|II|I|[123])|普通)',heading,re.I)
    if not gm:raise ValueError(name+' のグレードが確認できません')
    return {'name':name,'grade':grade(gm.group(1)),'day':'初日' if n==1 else str(n)+'日目'}

def parse_boat(html,today):
    soup=BeautifulSoup(html,'html.parser')
    result={}
    for row in soup.select('tr'):
        imgs=[im.get('alt','').replace('ボートレース','').strip() for im in row.find_all('img')]
        text=row.get_text(' ',strip=True)
        for name in SODA_NAMES:
            if name in result or (name not in imgs and not re.search(r'(?<![一-龥])'+re.escape(name)+r'(?![一-龥])',text)):continue
            dm=re.search(r'(初日|最終日|[0-9０-９]日目)',text)
            pm=BOAT_RANGE.search(text)
            if not dm or not pm:continue
            bounds=period(today,*map(int,pm.groups()))
            if not bounds or not bounds[0]<=today<=bounds[1]:continue
            grades=[grade(a) for a in imgs if GRADES.fullmatch(a)]
            result[name]={'name':name,'grade':grades[0] if grades else '一般','day':dm.group(1)}
    if not result:raise ValueError('BOAT RACE公式開催表の構造を解析できません')
    return [result[name] for name in SODA_NAMES if name in result]

def parse_mori(html,today):
    soup=BeautifulSoup(html,'html.parser')
    text=soup.get_text(' ',strip=True)
    start=text.find('出場予定')
    if start<0:return []
    ends=[text.find(tag,start) for tag in ('総合成績','成績 全国ランキング','出走履歴')]
    end=min((x for x in ends if x>start),default=start+2500)
    block=text[start:end]
    entries=[]
    for m in re.finditer(r'(20\d{2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})\s+.{0,38}?(川口|伊勢崎|浜松|飯塚|山陽)\s*(\d{1,2})\s*R',block,re.I):
        try:dt=date(*map(int,m.group(1,2,3)))
        except ValueError:continue
        if dt>=today:entries.append({'date':dt.isoformat(),'name':m.group(4),'race':int(m.group(5))})
    return sorted(entries,key=lambda e:(e['date'],e['race']))

def parse_assen(html,today):
    soup=BeautifulSoup(html,'html.parser')
    text=soup.get_text(' ',strip=True)
    start=text.find('出場情報')
    if start<0:return []
    entries=[]
    for m in re.finditer(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日.{0,30}?[～〜~\-]\s*\d{1,2}\s*日.{0,35}?(川口|伊勢崎|浜松|飯塚|山陽)\s*/',text[start:]):
        for year in (today.year,today.year+1):
            try:d=date(year,int(m.group(1)),int(m.group(2)))
            except ValueError:continue
            if 0<(d-today).days<180:entries.append({'date':d.isoformat(),'name':m.group(3)})
    return sorted(entries,key=lambda e:e['date'])

def ok(items=None,item=None,note=None):
    d={'status':'ok','items':items or []}
    if item:d['item']=item
    if note:d['note']=note
    return d

def bad(error):
    return {'status':'error','items':[],'message':str(error)[:150]}

def collect(today,s):
    out={'date':today.isoformat(),'updatedAt':datetime.now(TZ).isoformat(timespec='minutes'),'sources':SOURCES,'sections':{},'diagnostics':{'autorace':{},'mori':{}}}
    sections=out['sections']
    try:sections['keirin']=ok(parse_keirin(fetch(s,KEIRIN),today))
    except Exception as e:log.exception('競輪取得');sections['keirin']=bad(e)
    auto=[];errors=[]
    for name,slug in AUTO_NAMES.items():
        try:
            html=fetch(s,AUTO+'/'+slug+'/'+today.isoformat())
            visible=BeautifulSoup(html,'html.parser').get_text(' ',strip=True)
            out['diagnostics']['autorace'][name]={'chars':len(html),'period':visible.find('開催期間'),'snippet':visible[:1300]}
            item=parse_auto(html,name,today)
            if item:auto.append(item)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code==404:continue
            errors.append(name);out['diagnostics']['autorace'][name]={'error':str(e)[:150]};log.warning('オート %s: %s',name,e)
        except Exception as e:errors.append(name);log.warning('オート %s: %s',name,e)
    sections['auto']=({'status':'partial' if auto else 'error','items':auto,'message':'取得未確認: '+'・'.join(errors)} if errors else ok(auto))
    try:
        sections['soda']=ok(parse_boat(fetch(s,BOAT,{'hd':today.strftime('%Y%m%d')}),today),
            note='SODA対応場で開催。SODAライブ配信を保証するものではありません。')
    except Exception as e:log.exception('SODA開催場');sections['soda']=bad(e)
    races=[]
    try:
        html=fetch(s,MORI)
        out['diagnostics']['mori']['oddspark']={'chars':len(html),'snippet':BeautifulSoup(html,'html.parser').get_text(' ',strip=True)[:1200]}
        races=parse_mori(html,today)
    except Exception as e:
        out['diagnostics']['mori']['oddspark']={'error':str(e)[:150]}
        log.warning('森選手の出走予定: %s',e)
    if races:
        item=races[0];item['type']='today' if item['date']==today.isoformat() else 'next'
        sections['mori']=ok(item=item)
    else:
        try:
            html=fetch(s,ASSEN)
            out['diagnostics']['mori']['official']={'chars':len(html),'snippet':BeautifulSoup(html,'html.parser').get_text(' ',strip=True)[:1300]}
            assens=parse_assen(html,today)
            if assens:
                item=assens[0];item.update({'type':'next','unconfirmed':True})
                sections['mori']=ok(item=item,note='次回あっせん予定（出走Rは未確定）')
            else:sections['mori']=bad('次回の出走予定日を確認できません')
        except Exception as e:
            out['diagnostics']['mori']['official']={'error':str(e)[:150]}
            log.warning('森選手のあっせん: %s',e)
            sections['mori']=bad('出走予定を確認できません')
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--date')
    parser.add_argument('--output',default=str(ROOT/'data'/'today.json'))
    args=parser.parse_args()
    today=date.fromisoformat(args.date) if args.date else datetime.now(TZ).date()
    out=collect(today,session())
    override=ROOT/'overrides'/(today.isoformat()+'.json')
    if override.exists():
        patch=json.loads(override.read_text(encoding='utf-8'))
        for key,value in patch.get('sections',{}).items():
            if key in out['sections']:out['sections'][key]=value
        out['overridden']=True
    dst=Path(args.output);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    log.info('保存: %s / %s',dst,{k:(v['status'],len(v.get('items',[]))) for k,v in out['sections'].items()})

if __name__=='__main__':main()
