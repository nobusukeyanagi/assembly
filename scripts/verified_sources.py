"""Independent, date-specific schedule verification and resilient recovery.

Called by update.py. Parsers must validate the requested date before
their records can be included; never infer an event from an unverified site.
"""
from __future__ import annotations
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unicodedata import normalize

from bs4 import BeautifulSoup

LOG=logging.getLogger('assembly')
AUTO_MONTH='https://www.winticket.jp/autorace/schedules/{year}{month:02d}'
AUTO_ODDSPARK='https://sp.oddspark.com/autorace/SpRaceList.do'
AUTO_CODES={'川口':'02','伊勢崎':'03','浜松':'04','飯塚':'05','山陽':'06'}
BOAT_DAILY='https://www.ikachi.org/kyotei/{day}'
BOAT_ALL='桐生 戸田 江戸川 平和島 多摩川 浜名湖 蒲郡 常滑 津 三国 びわこ 住之江 尼崎 鳴門 丸亀 児島 宮島 徳山 下関 若松 芦屋 福岡 唐津 大村'.split()

def parse_ikachi_boat(html,selected,venue_names,night_names):
    soup=BeautifulSoup(html,'html.parser')
    for el in soup(['script','style','noscript']):el.decompose()
    h1=soup.find('h1')
    date_label=f'{selected.year}年{selected.month}月{selected.day}日'
    if not h1 or date_label not in normalize('NFKC',h1.get_text(' ',strip=True)):
        raise ValueError('日別ボートレース一覧の日付が不一致')
    heading=normalize('NFKC',h1.get_text(' ',strip=True))
    size=re.search(r'全(\d+)場',heading)
    all_names='|'.join(map(re.escape,sorted(BOAT_ALL,key=len,reverse=True)))
    target_names='|'.join(map(re.escape,sorted(venue_names,key=len,reverse=True)))
    total=0;items=[]
    for h in soup.find_all('h2'):
        value=normalize('NFKC',h.get_text('',strip=True)).replace(' ','')
        if re.match(r'^('+all_names+r')(?:PG1|SG|G[123]|一般|普通)[・･](?:初日|最終日|\d+日目)',value):
            total+=1
        matched=re.match(r'^('+target_names+r')(PG1|SG|G[123]|一般|普通)[・･](初日|最終日|\d+日目)',value)
        if not matched:continue
        name,grade,day=matched.groups()
        items.append({'name':name,'grade':'一般' if grade=='普通' else grade,
                      'day':day,'timeType':'ナイター' if name in night_names else None,
                      'girls':bool(re.search('オールレディース|ヴィーナスシリーズ|レディースチャンピオン|クイーンズクライマックス|女子戦',value))})
    if size and total!=int(size.group(1)):
        raise ValueError(f'日別ボート一覧の全場数が不一致: {total}/{size.group(1)}')
    if not items:raise ValueError('日別ボートレース一覧で対象場を特定できません')
    if len({x['name'] for x in items})!=len(items):raise ValueError('日別ボート一覧で開催場重複')
    return items

def parse_oddspark_auto(html,selected,venue,grade_fn,time_fn):
    soup=BeautifulSoup(html,'html.parser')
    for el in soup(['script','style','noscript']):el.decompose()
    title=soup.find('h1')
    date_label=f'{selected.year}年{selected.month}月{selected.day}日'
    if not title or date_label not in normalize('NFKC',title.get_text(' ',strip=True)):
        raise ValueError('オッズパーク掲載日が指定日と異なる')
    if not any(normalize('NFKC',h.get_text(' ',strip=True))==venue for h in soup.find_all('h2')):
        raise ValueError('オッズパーク掲載場が指定場と異なる')
    race_heading=next((h for h in soup.find_all('h3')
                       if re.match(r'^(初日|最終日|第?\d+日目)',normalize('NFKC',h.get_text(' ',strip=True)))),None)
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if race_heading is None or not re.search(r'\b1R\b',text):
        raise ValueError('指定開催のレースを確認できません')
    label=normalize('NFKC',race_heading.get_text(' ',strip=True))
    day=re.match(r'^(初日|最終日|第?\d+日目)',label).group(1).removeprefix('第')
    grade_match=re.search(r'(SG|特G[123I]+|G[123I]{1,3})',label,re.I)
    return {'name':venue,'grade':grade_fn(grade_match.group(1)) if grade_match else '普通',
            'day':day,'timeType':time_fn(label)}

def cached_section(previous,selected,category):
    """Only reuse previously verified data for the SAME calendar date."""
    if not isinstance(previous,dict) or previous.get('date')!=selected.isoformat():return None
    result=previous.get('sections',{}).get(category)
    if not isinstance(result,dict) or result.get('status') not in ('ok','cached'):return None
    items=result.get('items')
    if not isinstance(items,list) or not items:return None
    return dict(result,status='cached',note='取得元の障害により同じ日付の前回確認済みデータを再表示',
                reusedFrom=previous.get('updatedAt'))

def reconcile(category,lists,venue_order,sort_by_time):
    """Union independently dated records, retaining provenance and discrepancies."""
    merged={};confirmed={};differences=[]
    for source,items in lists:
        for row in items:
            name=row.get('name')
            if not name:continue
            if name not in merged:
                merged[name]=dict(row);confirmed[name]=[source];continue
            old=merged[name];confirmed[name].append(source)
            for key in ('grade','day','timeType'):
                new=row.get(key)
                if new is None or new=='確認中':continue
                if old.get(key) in (None,'確認中'):
                    old[key]=new
                elif old[key]!=new:
                    differences.append({'name':name,'field':key,'primary':old[key],
                                        'alternative':new,'source':source})
            if row.get('girls') is True:old['girls']=True
    items=list(merged.values())
    items.sort(key=lambda x:venue_order.index(x['name']) if x['name'] in venue_order else len(venue_order))
    for x in items:x['confirmedBy']=confirmed[x['name']]
    result={'status':'ok','items':sort_by_time(items),'verification':{
        'providers':{source:len(items) for source,items in lists},
        'crossConfirmed':sum(len(v)>1 for v in confirmed.values()),
        'singleSource':sum(len(v)==1 for v in confirmed.values()),
        'conflicts':differences}}
    if differences:LOG.warning('%s 取得元の不一致: %s',category,differences)
    return result

def keirin(s,selected,previous,u):
    lists=[];errors=[]
    url=u.KEIRIN_ARCHIVE.format(year=selected.year,month=selected.month,day=selected.day)
    try:
        rows=u.parse_keirin_archive(u.fetch(s,url),selected)
        if rows:lists.append(('楽天Kドリームス',rows))
    except Exception as exc:errors.append(('楽天Kドリームス',str(exc)))
    try:
        info=u.parse_keirin_race_times(u.fetch(s,u.KEIRIN_RACES.format(day=selected.strftime('%Y%m%d'))),selected)
        rows=[{'name':name,'grade':val['grade'],
               'day':'初日' if val['dayNumber']==1 else str(val['dayNumber'])+'日目',
               'timeType':val['timeType'],'girls':val.get('girls',False)}
              for name,val in info.items()]
        if rows:lists.append(('KEIRIN HEX',rows))
    except Exception as exc:errors.append(('KEIRIN HEX',str(exc)))
    if selected>=datetime.now(u.TZ).date():
        try:
            rows=u.parse_keirin(u.fetch(s,u.KEIRIN),selected)
            if rows:lists.append(('KEIRIN.JP',rows))
        except Exception as exc:errors.append(('KEIRIN.JP',str(exc)))
    if not lists:
        saved=cached_section(previous,selected,'keirin')
        return saved if saved else u.bad('すべての競輪開催日程が取得できません')
    result=reconcile('keirin',lists,u.KEIRIN_NAMES,u.sort_by_time)
    result['verification']['errors']=errors
    return result

def auto(s,selected,previous,u):
    lists=[];errors=[]
    try:
        month_html=u.fetch(s,AUTO_MONTH.format(year=selected.year,month=selected.month))
        rows=u.parse_auto_calendar(month_html,selected)
        lists.append(('WINTICKET指定月',rows))
    except Exception as exc:errors.append(('WINTICKET指定月',str(exc)))

    def fetch_track(pair):
        name,code=pair
        params={'gamenId':'S711','gamenKoumokuId':'iconAutoraceRaceList',
                'joCd':code,'kaisaiBi':selected.strftime('%Y%m%d')}
        try:
            html=u.fetch(s,AUTO_ODDSPARK,params)
            return name,parse_oddspark_auto(html,selected,name,u.autorace_grade,u.race_time_type),None
        except Exception as exc:return name,None,str(exc)

    racecard=[];missed=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for name,item,issue in pool.map(fetch_track,AUTO_CODES.items()):
            if item:racecard.append(item)
            else:missed.append({'name':name,'reason':issue})
    if racecard:lists.append(('オッズパーク日別',racecard))
    if not lists:
        saved=cached_section(previous,selected,'auto')
        return saved if saved else u.bad('すべてのオートレース開催日程が取得できません')
    result=reconcile('auto',lists,list(AUTO_CODES),u.sort_by_time)
    result['verification'].update(errors=errors,unconfirmedRacecards=missed)
    # Additional independent grade/time validation when official racecards exist.
    for row in result['items']:
        try:
            url=u.AUTO_OFFICIAL+u.AUTO_NAMES[row['name']]+'/'+selected.isoformat()
            details=u.check_auto_official(u.fetch(s,url),row['name'],selected)
            if not details or not details.get('timeType'):continue
            if row.get('timeType') in (None,'確認中'):row['timeType']=details['timeType']
            elif row['timeType']!=details['timeType']:
                result['verification']['conflicts'].append({
                    'name':row['name'],'field':'timeType',
                    'primary':row['timeType'],'alternative':details['timeType'],
                    'source':'AUTORACE.JP'})
        except Exception as exc:LOG.info('AUTORACE.JP照合不可: %s %s',row['name'],exc)
    result['items']=u.sort_by_time(result['items'])
    return result

def soda(s,selected,previous,u):
    lists=[];errors=[]
    try:
        rows=u.parse_boat(u.fetch(s,u.BOAT,{'hd':selected.strftime('%Y%m%d')}),selected)
        if rows:lists.append(('BOAT RACE公式',rows))
    except Exception as exc:errors.append(('BOAT RACE公式',str(exc)))
    try:
        html=u.fetch(s,BOAT_DAILY.format(day=selected.isoformat()))
        rows=parse_ikachi_boat(html,selected,u.SODA_NAMES,u.NIGHT_BOAT)
        if rows:lists.append(('きょうの競艇',rows))
    except Exception as exc:errors.append(('きょうの競艇',str(exc)))
    if not lists:
        saved=cached_section(previous,selected,'soda')
        return saved if saved else u.bad('すべてのSODA対象開催日程が取得できません')
    result=reconcile('soda',lists,u.SODA_NAMES,u.sort_by_time)
    result['verification']['errors']=errors
    result['note']='SODA対象場で開催。SODAライブ配信を保証するものではありません。'
    return result
