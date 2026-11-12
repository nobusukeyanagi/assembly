#!/usr/bin/env python3
"""JST daily meeting collector. Public official schedules; failures are visible."""
from __future__ import annotations
import argparse, json, logging, re
from unicodedata import normalize
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
KEIRIN_ARCHIVE='https://keirin.kdreams.jp/kaisai/{year}/{month:02d}/{day:02d}/'
KEIRIN_RACES='https://keirinhex.jp/races/{day}/'
AUTO='https://www.winticket.jp/autorace/schedules/'
BOAT='https://www.boatrace.jp/owpc/pc/race/index'
MORI='https://www.winticket.jp/autorace/autoracer/2529/'
ASSEN='https://sp.atrc.jp/racer/racerasseninfo/player_id/2529'
ODDSPARK='https://sp.oddspark.com/autorace/SpPlayerDetail.do?playerCd=2529'
AUTO_OFFICIAL='https://autorace.jp/race_info/Program/'
KAWAGUCHI_SCHEDULE='https://www.kawaguchiauto.jp/race-calender/'
NIGHT_BOAT={'桐生','蒲郡','若松'}
SOURCES={'keirin':KEIRIN,'keirin_archive':KEIRIN_ARCHIVE,'keirin_races':KEIRIN_RACES,'auto':AUTO,'auto_official':'https://autorace.jp/','soda':'https://so-da.jp/aud/top','soda_schedule':BOAT,'mori':MORI,'mori_official':ASSEN,'mori_racecard':ODDSPARK,'auto_racecard':AUTO_OFFICIAL,'mori_venue_schedule':KAWAGUCHI_SCHEDULE}
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
    return {'GI':'G1','GII':'G2','GIII':'G3','FI':'F1','FII':'F2','特GI':'特G1','普通':'一般'}.get(x,x)

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

def sort_by_time(items):
    """Stable morning, day, night, midnight order; unknowns stay unlabelled."""
    order={'モーニング':0,'デイ':1,None:1,'ナイター':2,'ミッドナイト':3}
    return sorted(items,key=lambda item:order.get(item.get('timeType'),4))

def parse_keirin(html,today):
    """Read verified KEIRIN.JP schedule grade, time category, and day."""
    soup=soup_with_alt(html)
    tokens=[re.sub(r'\s+',' ',t).strip() for t in soup.stripped_strings]
    # Schedule image alt codes: 1=day, 8=morning, 3=night, 5=midnight.
    time_codes={'1':'デイ','8':'モーニング','3':'ナイター','5':'ミッドナイト'}
    items=[];name=None;gr=None;time_type=None;girls=False
    for token in tokens:
        if token in KEIRIN_NAMES:
            name=token;gr=None;time_type=None;girls=False
            continue
        if token.startswith('開催がありません'):
            gr=None;time_type=None;girls=False
            continue
        g=re.search(r'\b(?:GP|SG|G[123]|F[12]|GI{1,3})\b',token,re.I)
        if g and len(token)<28:
            gr=grade(g.group());time_type=None;girls=False
            continue
        if gr and time_type is None and token in time_codes:
            time_type=time_codes[token]
        if gr and token=='02':girls=True
        m=DATE_RANGE.search(token)
        if not m or not name:continue
        bounds=period(today,*map(int,m.groups()))
        if not bounds or not bounds[0]<=today<=bounds[1]:continue
        if not gr:raise ValueError(name+' のグレードを読み取れません')
        items.append({'name':name,'grade':gr,'timeType':time_type or '確認中',
                      'girls':girls,'day':day_label(today,*bounds)})
        gr=None;time_type=None;girls=False
    if sum(bool(DATE_RANGE.search(t)) for t in tokens)<12:raise ValueError('競輪開催日程のDOMを解析できません')
    if not items:raise ValueError('競輪開催場を特定できません')
    return sort_by_time(items)


def parse_keirin_archive(html, target):
    """Read every meeting in a dated K Dreams event archive, including ended events."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    heading_text=f'{target.year}年{target.month}月{target.day}日 開催一覧'
    heading=next((h for h in soup.find_all(['h1','h2','h3'])
                  if normalize('NFKC',h.get_text(' ',strip=True))==heading_text),None)
    if heading is None:raise ValueError('対象日の開催一覧がありません: '+heading_text)
    names='|'.join(map(re.escape,sorted(KEIRIN_NAMES,key=len,reverse=True)))
    pattern=re.compile(r'^('+names+r')(GP|GIII|GII|GI|G[123]|FII|FI|F[12])
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


def race_time_type(title):
    """Use only explicit meeting descriptions to classify a race time slot."""
    t=normalize('NFKC',title).replace(' ','').replace('　','').lower()
    if 'ミッドナイト' in t:return 'ミッドナイト'
    if any(x in t for x in ('ナイトレース','ナイター','アフター5')):return 'ナイター'
    if 'デイ' in t:return 'デイ'
    return None

def check_auto_official(html,name,today):
    """Independently match the official racecard by venue, start date and day number."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    m=re.search(r'開催期間[：:]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日',text)
    if not m or name not in text[:650]:return None
    st=date(*map(int,m.groups()))
    d=re.search(r'開催\s*第\s*(\d{1,2})\s*日目',text[m.end():m.end()+130])
    if not d or (today-st).days!=int(d.group(1))-1:return None
    return {'name':name,'timeType':race_time_type(text[:m.start()])}

def parse_auto_calendar(html,today):
    """Read all five track blocks and dates, not a misleading racecard default."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    h=re.search(r'(\d{4})年(\d{1,2})月\s*開催日程',text)
    if not h or (int(h.group(1)),int(h.group(2)))!=(today.year,today.month):
        raise ValueError('開催日程の対象年月が不一致')
    text=text[h.end():].split('全国のオートレース場一覧')[0]
    parts=list(re.finditer(r'(川口|伊勢崎|浜松|飯塚|山陽)\s*オートレース',text))
    items=[];verified=set();count=0
    for n,heading in enumerate(parts):
        name=heading.group(1)
        end=parts[n+1].start() if n+1<len(parts) else len(text)
        block=text[heading.end():end]
        periods=list(re.finditer(r'(\d{1,2})月(\d{1,2})日\s*[〜～~\-]+\s*(\d{1,2})月(\d{1,2})日',block))
        if not periods:continue
        verified.add(name);count+=len(periods)
        for i,p in enumerate(periods):
            dates=period(today,*map(int,p.groups()))
            if not dates or not dates[0]<=today<=dates[1]:continue
            name_event=block[p.end():periods[i+1].start() if i+1<len(periods) else len(block)]
            gm=re.search(r'(特G(?:III|II|I|[123])|SG|G(?:III|II|I|[123]))',name_event[:120],re.I)
            items.append({'name':name,'grade':grade(gm.group(1)) if gm else '一般','timeType':race_time_type(name_event),'day':day_label(today,*dates)})
    if len(verified)!=5 or count<8:raise ValueError('全5場の開催日程を確認できません')
    return items

def parse_kawaguchi_official_meeting(html,scheduled):
    """Match the venue's published event start date, not just the track name."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    lines=[normalize('NFKC',x.strip()) for x in soup.get_text('\n').splitlines() if x.strip()]
    event_dates=re.compile(r'^(\d{1,2})/(\d{1,2})\s*\([^)]{1,12}\)\s*[〜～~\-]\s*(\d{1,2})/(\d{1,2})\s*\([^)]{1,12}\)')
    for n,line in enumerate(lines):
        match=event_dates.match(line)
        if not match or n==0:continue
        bounds=period(scheduled,*map(int,match.groups()))
        if not bounds or bounds[0]!=scheduled:continue
        title=lines[n-1]
        if '場外' in title:continue
        gr=re.search(r'(SG|特G(?:III|II|I|[123])|G(?:III|II|I|[123]))',title,re.I)
        return {'grade':grade(gr.group(1)) if gr else '一般',
                'timeType':race_time_type(title)}
    return None

def mori_meeting_metadata(schedule_html,scheduled,name,official_html=None):
    """Add grades/slots only for the meeting matching Mori's venue and start date."""
    if schedule_html is None:return {}
    try:
        meeting=next((x for x in parse_auto_calendar(schedule_html,scheduled)
                      if x['name']==name),None)
    except ValueError:return {}
    if not meeting:return {}
    details={key:meeting[key] for key in ('grade','timeType') if meeting.get(key)}
    # Match an independent official venue schedule when available; conflicting
    # information must not be shown until the sources agree.
    if name=='川口' and official_html:
        official=parse_kawaguchi_official_meeting(official_html,scheduled)
        if official:
            for key in ('grade','timeType'):
                if official.get(key) and details.get(key) and official[key]!=details[key]:
                    details.pop(key,None)
    return details

def parse_mori_calendar(html,today):
    """WINTICKET race meeting assignments; days/race numbers are not guaranteed."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '森且行' not in text:raise ValueError('選手プロフィールを検証できません')
    start=text.find('出場予定')
    if start<0:raise ValueError('出場予定欄がありません')
    end=text.find('直近5走',start)
    block=text[start:end if end>start else start+2500]
    entries=[]
    for m in re.finditer(r'(川口|伊勢崎|浜松|飯塚|山陽)\s*オートレース\s*(\d{1,2})\s*/\s*(\d{1,2})\s*[〜～~\-]+\s*(\d{1,2})\s*/\s*(\d{1,2})',block):
        bounds=period(today,*map(int,m.group(2,3,4,5)))
        if not bounds or bounds[1]<today:continue
        current=bounds[0]<=today<=bounds[1]
        entries.append({'date':today.isoformat() if current else bounds[0].isoformat(),
                        'name':m.group(1),'type':'today' if current else 'next',
                        'unconfirmed':True})
    return sorted(entries,key=lambda x:x['date'])

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
            icons={normalize('NFKC',a) for a in imgs}
            is_night='ナイター' in icons or (name in NIGHT_BOAT and 'モーニング' not in icons)
            morning='モーニング' in icons and not is_night
            ladies=bool(re.search(r'オールレディース|ヴィーナスシリーズ|レディースチャンピオン|レディースオールスター|クイーンズクライマックス|女子戦',normalize('NFKC',text))) or '女子戦' in icons
            result[name]={'name':name,'grade':grades[0] if grades else '一般',
                          'day':normalize('NFKC',dm.group(1)),
                          'timeType':'ナイター' if is_night else 'モーニング' if morning else None,
                          'girls':ladies}
    if not result and len(soup.select('tr'))<12:raise ValueError('BOAT RACE公式開催表の構造を解析できません')
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
    """Parse official racer assignments, including events crossing month boundaries."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '森且行' not in re.sub(r'\s+','',text):raise ValueError('公式選手情報を検証できません')
    start=text.find('出場情報')
    if start<0:raise ValueError('公式出場情報欄がありません')
    pattern=(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日(?:\s*\([^)]{0,6}\))?\s*[～〜~\-]\s*'
             r'(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日(?:\s*\([^)]{0,6}\))?\s*'
             r'(川口|伊勢崎|浜松|飯塚|山陽)\s*/')
    entries=[]
    for m in re.finditer(pattern,text[start:]):
        start_m,start_d=int(m.group(1)),int(m.group(2))
        end_m,end_d=int(m.group(3) or m.group(1)),int(m.group(4))
        bounds=period(today,start_m,start_d,end_m,end_d)
        if not bounds or bounds[1]<today:continue
        current=bounds[0]<=today<=bounds[1]
        entries.append({'date':today.isoformat() if current else bounds[0].isoformat(),
                        'name':m.group(5),'type':'today' if current else 'next','unconfirmed':True})
    return sorted(entries,key=lambda x:x['date'])

def mori_previous_item(previous,today):
    """Retain a verified assignment only while its displayed date is still in the future."""
    if not isinstance(previous,dict):return None
    section=previous.get('sections',{}).get('mori',{})
    item=section.get('item') if isinstance(section,dict) else None
    if not isinstance(item,dict) or item.get('name') not in AUTO_NAMES:return None
    try:dt=date.fromisoformat(item.get('date',''))
    except (TypeError,ValueError):return None
    if dt<today:return None
    if item.get('type')=='today' and dt!=today:return None
    return item


def ok(items=None,item=None,note=None):
    d={'status':'ok','items':items or []}
    if item:d['item']=item
    if note:d['note']=note
    return d

def bad(error):
    return {'status':'error','items':[],'message':str(error)[:150]}

def collect(today,s,previous=None):
    out={'date':today.isoformat(),'updatedAt':datetime.now(TZ).isoformat(timespec='minutes'),'sources':SOURCES,'sections':{}}
    sections=out['sections']
    try:
        if today<datetime.now(TZ).date():
            sections['keirin']=ok(collect_past_keirin(s,today))
        else:
            sections['keirin']=ok(parse_keirin(fetch(s,KEIRIN),today))
    except Exception as e:log.exception('競輪取得');sections['keirin']=bad(e)
    try:
        auto_html=fetch(s,AUTO)
        auto=parse_auto_calendar(auto_html,today)
        for meet in auto:
            try:
                url=AUTO_OFFICIAL+AUTO_NAMES[meet['name']]+'/'+today.isoformat()
                official=check_auto_official(fetch(s,url),meet['name'],today)
                if not official:continue
                primary=meet.get('timeType');other=official.get('timeType')
                if primary and other and primary!=other:
                    log.warning('オート開催時間帯が不一致: %s (%s vs %s)',meet['name'],primary,other)
                    meet['timeType']=None
                elif other:meet['timeType']=other
            except Exception as e:log.info('オートの公式照合ができません: %s: %s',meet['name'],e)
        sections['auto']=ok(sort_by_time(auto))
    except Exception as e:
        log.warning('オート日程取得: %s',e)
        sections['auto']=bad('開催日程を確認できません: '+str(e))
    
    try:
        sections['soda']=ok(sort_by_time(parse_boat(fetch(s,BOAT,{'hd':today.strftime('%Y%m%d')}),today)),
            note='SODA対応場で開催。SODAライブ配信を保証するものではありません。')
    except Exception as e:log.exception('SODA開催場');sections['soda']=bad(e)
    candidates={}
    for url,parser,source in (
            (ASSEN,parse_assen,'official'),
            (MORI,parse_mori_calendar,'winticket'),
            (ODDSPARK,parse_mori,'oddspark')):
        try:
            for item in parser(fetch(s,url),today):
                candidate=dict(item)
                dt=date.fromisoformat(candidate['date'])
                if dt<today or candidate.get('name') not in AUTO_NAMES:continue
                candidate.setdefault('type','today' if dt==today else 'next')
                candidates.setdefault((candidate['date'],candidate['name']),[]).append((source,candidate))
        except Exception as e:log.warning('森選手 %s 日程取得失敗: %s',source,e)
    if candidates:
        scored=[]
        for key,records in candidates.items():
            sources={name for name,_ in records}
            item=next((x for _,x in records if x.get('type')=='today' and isinstance(x.get('race'),int)),None)
            if item is None:item=next((x for name,x in records if name=='official'),records[0][1])
            scored.append((item['date'],0 if len(sources)>=2 else 1,0 if 'official' in sources else 1,item))
        item=min(scored,key=lambda x:x[:3])[3]
        # Resolve the exact future/current event in the published calendar.
        # Do not invent a grade/time from the rider's biography or past races.
        scheduled=date.fromisoformat(item['date'])
        try:
            monthly_html=auto_html if 'auto_html' in locals() else fetch(s,AUTO)
            venue_html=None
            if item['name']=='川口':
                try:venue_html=fetch(s,KAWAGUCHI_SCHEDULE)
                except Exception as e:log.info('森選手の川口公式開催日程を照合できません: %s',e)
            item.update(mori_meeting_metadata(monthly_html,scheduled,item['name'],venue_html))
        except Exception as e:log.warning('森選手の次回開催属性を確認できません: %s',e)
        if item['type']=='today' and not isinstance(item.get('race'),int):
            sections['mori']={'status':'partial','items':[],'item':item,'message':'出走R確認中'}
        else:sections['mori']=ok(item=item)
    else:
        cached=mori_previous_item(previous,today)
        if cached:
            sections['mori']=ok(item=cached)
            log.warning('森選手: 前回確認済みの将来予定を継続')
        else:
            sections['mori']=bad('公式・WINTICKET・オッズパークの日程を確認できません')
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--date')
    parser.add_argument('--output',default=str(ROOT/'data'/'today.json'))
    args=parser.parse_args()
    today=date.fromisoformat(args.date) if args.date else datetime.now(TZ).date()
    previous=None
    snapshot=ROOT/'data'/'today.json'
    if snapshot.exists():
        try:previous=json.loads(snapshot.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    out=collect(today,session(),previous)
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
,re.I)
    venues={}
    # A dated index is an explicit, bounded list; never scan the footer's venue links.
    for element in heading.next_elements:
        if getattr(element,'name',None) in ('h2','h3','h4'):break
        if not isinstance(element,str):continue
        txt=normalize('NFKC',str(element)).replace(' ','').replace('\u3000','').strip()
        match=pattern.fullmatch(txt)
        if match:venues[match.group(1)]=grade(match.group(2))
    if not venues:raise ValueError('開催一覧から開催場を読み取れません')
    day_pattern=re.compile(r'(初日|最終日|[0-9]+日目)
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


def race_time_type(title):
    """Use only explicit meeting descriptions to classify a race time slot."""
    t=normalize('NFKC',title).replace(' ','').replace('　','').lower()
    if 'ミッドナイト' in t:return 'ミッドナイト'
    if any(x in t for x in ('ナイトレース','ナイター','アフター5')):return 'ナイター'
    if 'デイ' in t:return 'デイ'
    return None

def check_auto_official(html,name,today):
    """Independently match the official racecard by venue, start date and day number."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    m=re.search(r'開催期間[：:]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日',text)
    if not m or name not in text[:650]:return None
    st=date(*map(int,m.groups()))
    d=re.search(r'開催\s*第\s*(\d{1,2})\s*日目',text[m.end():m.end()+130])
    if not d or (today-st).days!=int(d.group(1))-1:return None
    return {'name':name,'timeType':race_time_type(text[:m.start()])}

def parse_auto_calendar(html,today):
    """Read all five track blocks and dates, not a misleading racecard default."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    h=re.search(r'(\d{4})年(\d{1,2})月\s*開催日程',text)
    if not h or (int(h.group(1)),int(h.group(2)))!=(today.year,today.month):
        raise ValueError('開催日程の対象年月が不一致')
    text=text[h.end():].split('全国のオートレース場一覧')[0]
    parts=list(re.finditer(r'(川口|伊勢崎|浜松|飯塚|山陽)\s*オートレース',text))
    items=[];verified=set();count=0
    for n,heading in enumerate(parts):
        name=heading.group(1)
        end=parts[n+1].start() if n+1<len(parts) else len(text)
        block=text[heading.end():end]
        periods=list(re.finditer(r'(\d{1,2})月(\d{1,2})日\s*[〜～~\-]+\s*(\d{1,2})月(\d{1,2})日',block))
        if not periods:continue
        verified.add(name);count+=len(periods)
        for i,p in enumerate(periods):
            dates=period(today,*map(int,p.groups()))
            if not dates or not dates[0]<=today<=dates[1]:continue
            name_event=block[p.end():periods[i+1].start() if i+1<len(periods) else len(block)]
            gm=re.search(r'(特G(?:III|II|I|[123])|SG|G(?:III|II|I|[123]))',name_event[:120],re.I)
            items.append({'name':name,'grade':grade(gm.group(1)) if gm else '一般','timeType':race_time_type(name_event),'day':day_label(today,*dates)})
    if len(verified)!=5 or count<8:raise ValueError('全5場の開催日程を確認できません')
    return items

def parse_kawaguchi_official_meeting(html,scheduled):
    """Match the venue's published event start date, not just the track name."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    lines=[normalize('NFKC',x.strip()) for x in soup.get_text('\n').splitlines() if x.strip()]
    event_dates=re.compile(r'^(\d{1,2})/(\d{1,2})\s*\([^)]{1,12}\)\s*[〜～~\-]\s*(\d{1,2})/(\d{1,2})\s*\([^)]{1,12}\)')
    for n,line in enumerate(lines):
        match=event_dates.match(line)
        if not match or n==0:continue
        bounds=period(scheduled,*map(int,match.groups()))
        if not bounds or bounds[0]!=scheduled:continue
        title=lines[n-1]
        if '場外' in title:continue
        gr=re.search(r'(SG|特G(?:III|II|I|[123])|G(?:III|II|I|[123]))',title,re.I)
        return {'grade':grade(gr.group(1)) if gr else '一般',
                'timeType':race_time_type(title)}
    return None

def mori_meeting_metadata(schedule_html,scheduled,name,official_html=None):
    """Add grades/slots only for the meeting matching Mori's venue and start date."""
    if schedule_html is None:return {}
    try:
        meeting=next((x for x in parse_auto_calendar(schedule_html,scheduled)
                      if x['name']==name),None)
    except ValueError:return {}
    if not meeting:return {}
    details={key:meeting[key] for key in ('grade','timeType') if meeting.get(key)}
    # Match an independent official venue schedule when available; conflicting
    # information must not be shown until the sources agree.
    if name=='川口' and official_html:
        official=parse_kawaguchi_official_meeting(official_html,scheduled)
        if official:
            for key in ('grade','timeType'):
                if official.get(key) and details.get(key) and official[key]!=details[key]:
                    details.pop(key,None)
    return details

def parse_mori_calendar(html,today):
    """WINTICKET race meeting assignments; days/race numbers are not guaranteed."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '森且行' not in text:raise ValueError('選手プロフィールを検証できません')
    start=text.find('出場予定')
    if start<0:raise ValueError('出場予定欄がありません')
    end=text.find('直近5走',start)
    block=text[start:end if end>start else start+2500]
    entries=[]
    for m in re.finditer(r'(川口|伊勢崎|浜松|飯塚|山陽)\s*オートレース\s*(\d{1,2})\s*/\s*(\d{1,2})\s*[〜～~\-]+\s*(\d{1,2})\s*/\s*(\d{1,2})',block):
        bounds=period(today,*map(int,m.group(2,3,4,5)))
        if not bounds or bounds[1]<today:continue
        current=bounds[0]<=today<=bounds[1]
        entries.append({'date':today.isoformat() if current else bounds[0].isoformat(),
                        'name':m.group(1),'type':'today' if current else 'next',
                        'unconfirmed':True})
    return sorted(entries,key=lambda x:x['date'])

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
            icons={normalize('NFKC',a) for a in imgs}
            is_night='ナイター' in icons or (name in NIGHT_BOAT and 'モーニング' not in icons)
            morning='モーニング' in icons and not is_night
            ladies=bool(re.search(r'オールレディース|ヴィーナスシリーズ|レディースチャンピオン|レディースオールスター|クイーンズクライマックス|女子戦',normalize('NFKC',text))) or '女子戦' in icons
            result[name]={'name':name,'grade':grades[0] if grades else '一般',
                          'day':normalize('NFKC',dm.group(1)),
                          'timeType':'ナイター' if is_night else 'モーニング' if morning else None,
                          'girls':ladies}
    if not result and len(soup.select('tr'))<12:raise ValueError('BOAT RACE公式開催表の構造を解析できません')
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
    """Parse official racer assignments, including events crossing month boundaries."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '森且行' not in re.sub(r'\s+','',text):raise ValueError('公式選手情報を検証できません')
    start=text.find('出場情報')
    if start<0:raise ValueError('公式出場情報欄がありません')
    pattern=(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日(?:\s*\([^)]{0,6}\))?\s*[～〜~\-]\s*'
             r'(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日(?:\s*\([^)]{0,6}\))?\s*'
             r'(川口|伊勢崎|浜松|飯塚|山陽)\s*/')
    entries=[]
    for m in re.finditer(pattern,text[start:]):
        start_m,start_d=int(m.group(1)),int(m.group(2))
        end_m,end_d=int(m.group(3) or m.group(1)),int(m.group(4))
        bounds=period(today,start_m,start_d,end_m,end_d)
        if not bounds or bounds[1]<today:continue
        current=bounds[0]<=today<=bounds[1]
        entries.append({'date':today.isoformat() if current else bounds[0].isoformat(),
                        'name':m.group(5),'type':'today' if current else 'next','unconfirmed':True})
    return sorted(entries,key=lambda x:x['date'])

def mori_previous_item(previous,today):
    """Retain a verified assignment only while its displayed date is still in the future."""
    if not isinstance(previous,dict):return None
    section=previous.get('sections',{}).get('mori',{})
    item=section.get('item') if isinstance(section,dict) else None
    if not isinstance(item,dict) or item.get('name') not in AUTO_NAMES:return None
    try:dt=date.fromisoformat(item.get('date',''))
    except (TypeError,ValueError):return None
    if dt<today:return None
    if item.get('type')=='today' and dt!=today:return None
    return item


def ok(items=None,item=None,note=None):
    d={'status':'ok','items':items or []}
    if item:d['item']=item
    if note:d['note']=note
    return d

def bad(error):
    return {'status':'error','items':[],'message':str(error)[:150]}

def collect(today,s,previous=None):
    out={'date':today.isoformat(),'updatedAt':datetime.now(TZ).isoformat(timespec='minutes'),'sources':SOURCES,'sections':{}}
    sections=out['sections']
    try:sections['keirin']=ok(parse_keirin(fetch(s,KEIRIN),today))
    except Exception as e:log.exception('競輪取得');sections['keirin']=bad(e)
    try:
        auto_html=fetch(s,AUTO)
        auto=parse_auto_calendar(auto_html,today)
        for meet in auto:
            try:
                url=AUTO_OFFICIAL+AUTO_NAMES[meet['name']]+'/'+today.isoformat()
                official=check_auto_official(fetch(s,url),meet['name'],today)
                if not official:continue
                primary=meet.get('timeType');other=official.get('timeType')
                if primary and other and primary!=other:
                    log.warning('オート開催時間帯が不一致: %s (%s vs %s)',meet['name'],primary,other)
                    meet['timeType']=None
                elif other:meet['timeType']=other
            except Exception as e:log.info('オートの公式照合ができません: %s: %s',meet['name'],e)
        sections['auto']=ok(sort_by_time(auto))
    except Exception as e:
        log.warning('オート日程取得: %s',e)
        sections['auto']=bad('開催日程を確認できません: '+str(e))
    
    try:
        sections['soda']=ok(sort_by_time(parse_boat(fetch(s,BOAT,{'hd':today.strftime('%Y%m%d')}),today)),
            note='SODA対応場で開催。SODAライブ配信を保証するものではありません。')
    except Exception as e:log.exception('SODA開催場');sections['soda']=bad(e)
    candidates={}
    for url,parser,source in (
            (ASSEN,parse_assen,'official'),
            (MORI,parse_mori_calendar,'winticket'),
            (ODDSPARK,parse_mori,'oddspark')):
        try:
            for item in parser(fetch(s,url),today):
                candidate=dict(item)
                dt=date.fromisoformat(candidate['date'])
                if dt<today or candidate.get('name') not in AUTO_NAMES:continue
                candidate.setdefault('type','today' if dt==today else 'next')
                candidates.setdefault((candidate['date'],candidate['name']),[]).append((source,candidate))
        except Exception as e:log.warning('森選手 %s 日程取得失敗: %s',source,e)
    if candidates:
        scored=[]
        for key,records in candidates.items():
            sources={name for name,_ in records}
            item=next((x for _,x in records if x.get('type')=='today' and isinstance(x.get('race'),int)),None)
            if item is None:item=next((x for name,x in records if name=='official'),records[0][1])
            scored.append((item['date'],0 if len(sources)>=2 else 1,0 if 'official' in sources else 1,item))
        item=min(scored,key=lambda x:x[:3])[3]
        # Resolve the exact future/current event in the published calendar.
        # Do not invent a grade/time from the rider's biography or past races.
        scheduled=date.fromisoformat(item['date'])
        try:
            monthly_html=auto_html if 'auto_html' in locals() else fetch(s,AUTO)
            venue_html=None
            if item['name']=='川口':
                try:venue_html=fetch(s,KAWAGUCHI_SCHEDULE)
                except Exception as e:log.info('森選手の川口公式開催日程を照合できません: %s',e)
            item.update(mori_meeting_metadata(monthly_html,scheduled,item['name'],venue_html))
        except Exception as e:log.warning('森選手の次回開催属性を確認できません: %s',e)
        if item['type']=='today' and not isinstance(item.get('race'),int):
            sections['mori']={'status':'partial','items':[],'item':item,'message':'出走R確認中'}
        else:sections['mori']=ok(item=item)
    else:
        cached=mori_previous_item(previous,today)
        if cached:
            sections['mori']=ok(item=cached)
            log.warning('森選手: 前回確認済みの将来予定を継続')
        else:
            sections['mori']=bad('公式・WINTICKET・オッズパークの日程を確認できません')
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--date')
    parser.add_argument('--output',default=str(ROOT/'data'/'today.json'))
    args=parser.parse_args()
    today=date.fromisoformat(args.date) if args.date else datetime.now(TZ).date()
    previous=None
    snapshot=ROOT/'data'/'today.json'
    if snapshot.exists():
        try:previous=json.loads(snapshot.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    out=collect(today,session(),previous)
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
)
    days={}
    for h in soup.find_all(['h3','h4']):
        label=normalize('NFKC',h.get_text(' ',strip=True)).strip()
        for name in venues:
            if label.startswith(name+'競輪'):
                dm=day_pattern.search(label)
                if dm:days[name]=dm.group(1)
    missing=set(venues)-set(days)
    if missing:raise ValueError('日数を取得できない開催場: '+','.join(sorted(missing)))
    return [{'name':name,'grade':gr,'timeType':'確認中','girls':False,'day':days[name]}
            for name,gr in venues.items()]


def parse_keirin_race_times(html, target):
    """Verified date-specific race time groups and girl's-race existence."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    h1=soup.find('h1')
    matchdate=f'{target.year}年{target.month}月{target.day}日'
    if h1 is None or matchdate not in normalize('NFKC',h1.get_text(' ',strip=True)):
        raise ValueError('レース一覧の年月日が不一致')
    names='|'.join(map(re.escape,sorted(KEIRIN_NAMES,key=len,reverse=True)))
    pattern=re.compile(r'^(GP|G[123]|F[12])\s*('+names+r')競輪\s*(\d+)日目')
    groups={'モーニング','デイ','ナイター','ミッドナイト'}
    group=None;venues={}
    for h in soup.find_all(['h2','h3']):
        text=normalize('NFKC',h.get_text(' ',strip=True)).strip()
        if h.name=='h2':
            group=text if text in groups else None
            continue
        if not group:continue
        match=pattern.match(text)
        if not match:continue
        g,name,day=match.groups()
        girls=False
        for el in h.next_elements:
            if getattr(el,'name',None) in ('h2','h3'):break
            if isinstance(el,str) and re.search(r'L級\s*ガールズ',normalize('NFKC',str(el))):
                girls=True
        if name in venues:raise ValueError('同日の開催場が重複: '+name)
        venues[name]={'name':name,'grade':grade(g),'timeType':group,
                      'girls':girls,'dayNumber':int(day)}
    if not venues:raise ValueError('日付指定の時間帯を取得できません')
    return venues


def collect_past_keirin(s,target):
    """Complete past-day list from a date-specific archive, with verified slot data."""
    url=KEIRIN_ARCHIVE.format(year=target.year,month=target.month,day=target.day)
    archive_error=None
    try:records=parse_keirin_archive(fetch(s,url),target)
    except Exception as exc:
        archive_error=exc;records=[]
        log.warning('過去日の競輪開催一覧: %s',exc)
    try:times=parse_keirin_race_times(
        fetch(s,KEIRIN_RACES.format(day=target.strftime('%Y%m%d'))),target)
    except Exception as exc:
        times={}
        log.warning('過去日の競輪時間帯: %s',exc)
    if not records:
        if not times:raise ValueError('過去日の開催場を網羅できません: '+str(archive_error))
        records=[{'name':n,'grade':v['grade'],'timeType':v['timeType'],
                  'girls':v['girls'],'day':str(v['dayNumber'])+'日目'} for n,v in times.items()]
    else:
        for row in records:
            t=times.get(row['name'])
            if not t or t['grade']!=row['grade']:continue
            if row['day']=='初日' and t['dayNumber']!=1:continue
            if row['day'] not in ('初日','最終日',str(t['dayNumber'])+'日目'):continue
            row['timeType']=t['timeType']
            row['girls']=t['girls']
    if times and set(times)!={x['name'] for x in records}:
        log.warning('日付別開催情報の取得場数が不一致: archive=%s race=%s',len(records),len(times))
    return sort_by_time(records)

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


def race_time_type(title):
    """Use only explicit meeting descriptions to classify a race time slot."""
    t=normalize('NFKC',title).replace(' ','').replace('　','').lower()
    if 'ミッドナイト' in t:return 'ミッドナイト'
    if any(x in t for x in ('ナイトレース','ナイター','アフター5')):return 'ナイター'
    if 'デイ' in t:return 'デイ'
    return None

def check_auto_official(html,name,today):
    """Independently match the official racecard by venue, start date and day number."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    m=re.search(r'開催期間[：:]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日',text)
    if not m or name not in text[:650]:return None
    st=date(*map(int,m.groups()))
    d=re.search(r'開催\s*第\s*(\d{1,2})\s*日目',text[m.end():m.end()+130])
    if not d or (today-st).days!=int(d.group(1))-1:return None
    return {'name':name,'timeType':race_time_type(text[:m.start()])}

def parse_auto_calendar(html,today):
    """Read all five track blocks and dates, not a misleading racecard default."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    h=re.search(r'(\d{4})年(\d{1,2})月\s*開催日程',text)
    if not h or (int(h.group(1)),int(h.group(2)))!=(today.year,today.month):
        raise ValueError('開催日程の対象年月が不一致')
    text=text[h.end():].split('全国のオートレース場一覧')[0]
    parts=list(re.finditer(r'(川口|伊勢崎|浜松|飯塚|山陽)\s*オートレース',text))
    items=[];verified=set();count=0
    for n,heading in enumerate(parts):
        name=heading.group(1)
        end=parts[n+1].start() if n+1<len(parts) else len(text)
        block=text[heading.end():end]
        periods=list(re.finditer(r'(\d{1,2})月(\d{1,2})日\s*[〜～~\-]+\s*(\d{1,2})月(\d{1,2})日',block))
        if not periods:continue
        verified.add(name);count+=len(periods)
        for i,p in enumerate(periods):
            dates=period(today,*map(int,p.groups()))
            if not dates or not dates[0]<=today<=dates[1]:continue
            name_event=block[p.end():periods[i+1].start() if i+1<len(periods) else len(block)]
            gm=re.search(r'(特G(?:III|II|I|[123])|SG|G(?:III|II|I|[123]))',name_event[:120],re.I)
            items.append({'name':name,'grade':grade(gm.group(1)) if gm else '一般','timeType':race_time_type(name_event),'day':day_label(today,*dates)})
    if len(verified)!=5 or count<8:raise ValueError('全5場の開催日程を確認できません')
    return items

def parse_kawaguchi_official_meeting(html,scheduled):
    """Match the venue's published event start date, not just the track name."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    lines=[normalize('NFKC',x.strip()) for x in soup.get_text('\n').splitlines() if x.strip()]
    event_dates=re.compile(r'^(\d{1,2})/(\d{1,2})\s*\([^)]{1,12}\)\s*[〜～~\-]\s*(\d{1,2})/(\d{1,2})\s*\([^)]{1,12}\)')
    for n,line in enumerate(lines):
        match=event_dates.match(line)
        if not match or n==0:continue
        bounds=period(scheduled,*map(int,match.groups()))
        if not bounds or bounds[0]!=scheduled:continue
        title=lines[n-1]
        if '場外' in title:continue
        gr=re.search(r'(SG|特G(?:III|II|I|[123])|G(?:III|II|I|[123]))',title,re.I)
        return {'grade':grade(gr.group(1)) if gr else '一般',
                'timeType':race_time_type(title)}
    return None

def mori_meeting_metadata(schedule_html,scheduled,name,official_html=None):
    """Add grades/slots only for the meeting matching Mori's venue and start date."""
    if schedule_html is None:return {}
    try:
        meeting=next((x for x in parse_auto_calendar(schedule_html,scheduled)
                      if x['name']==name),None)
    except ValueError:return {}
    if not meeting:return {}
    details={key:meeting[key] for key in ('grade','timeType') if meeting.get(key)}
    # Match an independent official venue schedule when available; conflicting
    # information must not be shown until the sources agree.
    if name=='川口' and official_html:
        official=parse_kawaguchi_official_meeting(official_html,scheduled)
        if official:
            for key in ('grade','timeType'):
                if official.get(key) and details.get(key) and official[key]!=details[key]:
                    details.pop(key,None)
    return details

def parse_mori_calendar(html,today):
    """WINTICKET race meeting assignments; days/race numbers are not guaranteed."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '森且行' not in text:raise ValueError('選手プロフィールを検証できません')
    start=text.find('出場予定')
    if start<0:raise ValueError('出場予定欄がありません')
    end=text.find('直近5走',start)
    block=text[start:end if end>start else start+2500]
    entries=[]
    for m in re.finditer(r'(川口|伊勢崎|浜松|飯塚|山陽)\s*オートレース\s*(\d{1,2})\s*/\s*(\d{1,2})\s*[〜～~\-]+\s*(\d{1,2})\s*/\s*(\d{1,2})',block):
        bounds=period(today,*map(int,m.group(2,3,4,5)))
        if not bounds or bounds[1]<today:continue
        current=bounds[0]<=today<=bounds[1]
        entries.append({'date':today.isoformat() if current else bounds[0].isoformat(),
                        'name':m.group(1),'type':'today' if current else 'next',
                        'unconfirmed':True})
    return sorted(entries,key=lambda x:x['date'])

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
            icons={normalize('NFKC',a) for a in imgs}
            is_night='ナイター' in icons or (name in NIGHT_BOAT and 'モーニング' not in icons)
            morning='モーニング' in icons and not is_night
            ladies=bool(re.search(r'オールレディース|ヴィーナスシリーズ|レディースチャンピオン|レディースオールスター|クイーンズクライマックス|女子戦',normalize('NFKC',text))) or '女子戦' in icons
            result[name]={'name':name,'grade':grades[0] if grades else '一般',
                          'day':normalize('NFKC',dm.group(1)),
                          'timeType':'ナイター' if is_night else 'モーニング' if morning else None,
                          'girls':ladies}
    if not result and len(soup.select('tr'))<12:raise ValueError('BOAT RACE公式開催表の構造を解析できません')
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
    """Parse official racer assignments, including events crossing month boundaries."""
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript']):tag.decompose()
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '森且行' not in re.sub(r'\s+','',text):raise ValueError('公式選手情報を検証できません')
    start=text.find('出場情報')
    if start<0:raise ValueError('公式出場情報欄がありません')
    pattern=(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日(?:\s*\([^)]{0,6}\))?\s*[～〜~\-]\s*'
             r'(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日(?:\s*\([^)]{0,6}\))?\s*'
             r'(川口|伊勢崎|浜松|飯塚|山陽)\s*/')
    entries=[]
    for m in re.finditer(pattern,text[start:]):
        start_m,start_d=int(m.group(1)),int(m.group(2))
        end_m,end_d=int(m.group(3) or m.group(1)),int(m.group(4))
        bounds=period(today,start_m,start_d,end_m,end_d)
        if not bounds or bounds[1]<today:continue
        current=bounds[0]<=today<=bounds[1]
        entries.append({'date':today.isoformat() if current else bounds[0].isoformat(),
                        'name':m.group(5),'type':'today' if current else 'next','unconfirmed':True})
    return sorted(entries,key=lambda x:x['date'])

def mori_previous_item(previous,today):
    """Retain a verified assignment only while its displayed date is still in the future."""
    if not isinstance(previous,dict):return None
    section=previous.get('sections',{}).get('mori',{})
    item=section.get('item') if isinstance(section,dict) else None
    if not isinstance(item,dict) or item.get('name') not in AUTO_NAMES:return None
    try:dt=date.fromisoformat(item.get('date',''))
    except (TypeError,ValueError):return None
    if dt<today:return None
    if item.get('type')=='today' and dt!=today:return None
    return item


def ok(items=None,item=None,note=None):
    d={'status':'ok','items':items or []}
    if item:d['item']=item
    if note:d['note']=note
    return d

def bad(error):
    return {'status':'error','items':[],'message':str(error)[:150]}

def collect(today,s,previous=None):
    out={'date':today.isoformat(),'updatedAt':datetime.now(TZ).isoformat(timespec='minutes'),'sources':SOURCES,'sections':{}}
    sections=out['sections']
    try:sections['keirin']=ok(parse_keirin(fetch(s,KEIRIN),today))
    except Exception as e:log.exception('競輪取得');sections['keirin']=bad(e)
    try:
        auto_html=fetch(s,AUTO)
        auto=parse_auto_calendar(auto_html,today)
        for meet in auto:
            try:
                url=AUTO_OFFICIAL+AUTO_NAMES[meet['name']]+'/'+today.isoformat()
                official=check_auto_official(fetch(s,url),meet['name'],today)
                if not official:continue
                primary=meet.get('timeType');other=official.get('timeType')
                if primary and other and primary!=other:
                    log.warning('オート開催時間帯が不一致: %s (%s vs %s)',meet['name'],primary,other)
                    meet['timeType']=None
                elif other:meet['timeType']=other
            except Exception as e:log.info('オートの公式照合ができません: %s: %s',meet['name'],e)
        sections['auto']=ok(sort_by_time(auto))
    except Exception as e:
        log.warning('オート日程取得: %s',e)
        sections['auto']=bad('開催日程を確認できません: '+str(e))
    
    try:
        sections['soda']=ok(sort_by_time(parse_boat(fetch(s,BOAT,{'hd':today.strftime('%Y%m%d')}),today)),
            note='SODA対応場で開催。SODAライブ配信を保証するものではありません。')
    except Exception as e:log.exception('SODA開催場');sections['soda']=bad(e)
    candidates={}
    for url,parser,source in (
            (ASSEN,parse_assen,'official'),
            (MORI,parse_mori_calendar,'winticket'),
            (ODDSPARK,parse_mori,'oddspark')):
        try:
            for item in parser(fetch(s,url),today):
                candidate=dict(item)
                dt=date.fromisoformat(candidate['date'])
                if dt<today or candidate.get('name') not in AUTO_NAMES:continue
                candidate.setdefault('type','today' if dt==today else 'next')
                candidates.setdefault((candidate['date'],candidate['name']),[]).append((source,candidate))
        except Exception as e:log.warning('森選手 %s 日程取得失敗: %s',source,e)
    if candidates:
        scored=[]
        for key,records in candidates.items():
            sources={name for name,_ in records}
            item=next((x for _,x in records if x.get('type')=='today' and isinstance(x.get('race'),int)),None)
            if item is None:item=next((x for name,x in records if name=='official'),records[0][1])
            scored.append((item['date'],0 if len(sources)>=2 else 1,0 if 'official' in sources else 1,item))
        item=min(scored,key=lambda x:x[:3])[3]
        # Resolve the exact future/current event in the published calendar.
        # Do not invent a grade/time from the rider's biography or past races.
        scheduled=date.fromisoformat(item['date'])
        try:
            monthly_html=auto_html if 'auto_html' in locals() else fetch(s,AUTO)
            venue_html=None
            if item['name']=='川口':
                try:venue_html=fetch(s,KAWAGUCHI_SCHEDULE)
                except Exception as e:log.info('森選手の川口公式開催日程を照合できません: %s',e)
            item.update(mori_meeting_metadata(monthly_html,scheduled,item['name'],venue_html))
        except Exception as e:log.warning('森選手の次回開催属性を確認できません: %s',e)
        if item['type']=='today' and not isinstance(item.get('race'),int):
            sections['mori']={'status':'partial','items':[],'item':item,'message':'出走R確認中'}
        else:sections['mori']=ok(item=item)
    else:
        cached=mori_previous_item(previous,today)
        if cached:
            sections['mori']=ok(item=cached)
            log.warning('森選手: 前回確認済みの将来予定を継続')
        else:
            sections['mori']=bad('公式・WINTICKET・オッズパークの日程を確認できません')
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--date')
    parser.add_argument('--output',default=str(ROOT/'data'/'today.json'))
    args=parser.parse_args()
    today=date.fromisoformat(args.date) if args.date else datetime.now(TZ).date()
    previous=None
    snapshot=ROOT/'data'/'today.json'
    if snapshot.exists():
        try:previous=json.loads(snapshot.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    out=collect(today,session(),previous)
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
