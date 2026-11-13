"""Independent, date-specific schedule verification and resilient recovery.

Called by update.py. Parsers must validate the requested date before
their records can be included; never infer an event from an unverified site.
"""
from __future__ import annotations
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from unicodedata import normalize

from bs4 import BeautifulSoup

LOG=logging.getLogger('assembly')
AUTO_MONTH='https://www.winticket.jp/autorace/schedules/{year}{month:02d}'
AUTO_ODDSPARK='https://sp.oddspark.com/autorace/SpRaceList.do'
AUTO_CODES={'川口':'02','伊勢崎':'03','浜松':'04','飯塚':'05','山陽':'06'}
BOAT_DAILY='https://www.ikachi.org/kyotei/{day}'
# Verified completed-finals calendar for the October 2026 period only.
# Never extrapolate its entries to another month.
KEIRIN_2026_OCT_FINALS='https://www.winticket.jp/keirin/campaign/onYZ47mxGGoqRuAo3AzxdX'
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
                    # Different wording for the same day: a numbered day can
                    # also be the final day. Prefer the more informative label.
                    if key=='day' and (old[key]=='最終日' or new=='最終日'):
                        old[key]='最終日'
                        continue
                    if key=='day' and ((old[key]=='初日' and new=='1日目') or
                                       (new=='初日' and old[key]=='1日目')):
                        old[key]='初日'
                        continue
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

def parse_keirin_oct_2026_finals(html,selected,archive,u):
    """Recover explicitly named time slots and girls races from a dated final calendar.

    Rows are accepted only when event date, venue, grade, and meeting-day
    progression match the independently validated K Dreams daily archive.
    This campaign source is scoped to October 2026.
    """
    if (selected.year,selected.month)!=(2026,10) or not archive:
        return []
    soup=BeautifulSoup(html,'html.parser')
    heading=next((h for h in soup.find_all(['h1','h2'])
                  if 'すべての決勝レースで5%還元' in h.get_text(' ',strip=True)),None)
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if heading is None or '2026年10月1日' not in text:
        raise ValueError('2026年10月の決勝開催一覧を検証できません')
    table=next((t for t in soup.find_all('table')
                if all(x in normalize('NFKC',t.get_text(' ',strip=True))
                       for x in ('日程','開催場','対象レース'))),None)
    if table is None:
        raise ValueError('日別の決勝開催表がありません')
    names='|'.join(re.escape(n) for n in sorted(u.KEIRIN_NAMES,key=len,reverse=True))
    # Each row can omit repeated dates or venue names because of rowspan.
    place_pattern=re.compile(r'('+names+r')\s*[(（]\s*(F[12]|GIII|GII|GI|G[123]|GP)\s*[)）]\s*'
                             r'(モーニング|デイ|ナイター|ミッドナイト)',re.I)
    entries={}
    current_date=None
    current_key=None
    for tr in table.find_all('tr'):
        row=normalize('NFKC',tr.get_text(' ',strip=True))
        found_date=re.search(r'(?<!\d)10\s*/\s*(\d{1,2})(?!\d)',row)
        if found_date:
            day=int(found_date.group(1))
            current_date=date(2026,10,day) if 1<=day<=31 else None
            current_key=None
        found_place=place_pattern.search(row)
        if found_place and current_date:
            name,grade,slot=found_place.groups()
            current_key=(current_date.isoformat(),name)
            item=entries.setdefault(current_key,{'grade':u.grade(grade),'timeType':slot,'girls':False})
            if item['grade']!=u.grade(grade) or item['timeType']!=slot:
                raise ValueError('同一開催に複数の競技区分があります')
        if current_key and re.search(r'L級\s*ガールズ',row):
            entries[current_key]['girls']=True

    result=[]
    for event in archive:
        day_label=event.get('day','')
        if day_label=='最終日':
            days_remaining=0
        elif day_label=='初日':
            days_remaining=2 if event.get('grade') in ('F1','F2') else 3 if event.get('grade')=='G3' else None
        else:
            dm=re.fullmatch(r'(\d+)日目',day_label)
            current_day=int(dm.group(1)) if dm else 0
            total=3 if event.get('grade') in ('F1','F2') else 4 if event.get('grade')=='G3' else 0
            days_remaining=total-current_day if 1<=current_day<=total else None
        if days_remaining is None or not 0<=days_remaining<=3:
            continue
        final_date=selected+timedelta(days=days_remaining)
        info=entries.get((final_date.isoformat(),event['name']))
        if not info or info['grade']!=event.get('grade'):
            continue
        result.append({'name':event['name'],'grade':event['grade'],'day':day_label,
                       'timeType':info['timeType'],'girls':info['girls']})
    if not result:
        raise ValueError('指定日の開催と一致する決勝日程がありません')
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
    if (selected.year,selected.month)==(2026,10):
        archive=next((rows for source,rows in lists if source=='楽天Kドリームス'),[])
        if archive:
            try:
                rows=parse_keirin_oct_2026_finals(
                    u.fetch(s,KEIRIN_2026_OCT_FINALS),selected,archive,u)
                if rows:lists.append(('WINTICKET 2026年10月決勝日程',rows))
            except Exception as exc:
                errors.append(('WINTICKET 2026年10月決勝日程',str(exc)))
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


def parse_autorace_official_card(html,selected,venue,u):
    """An independent official, date-and-track checked racecard."""
    parsed=u.parse_auto(html,venue,selected)
    checked=u.check_auto_official(html,venue,selected)
    if not parsed or not checked:
        raise ValueError('AUTORACE.JPの指定日・開催場を照合できません')
    result=dict(parsed,timeType=checked.get('timeType'))
    normalized=normalize('NFKC',BeautifulSoup(html,'html.parser').get_text(' ',strip=True))
    m=re.search(
        r'開催期間\s*[：:]\s*(20\d{2})年(\d{1,2})月(\d{1,2})日\s*(?:\([^)]*\))?\s*'
        r'[～〜~\-]\s*(?:(\d{1,2})月)?\s*(\d{1,2})日',
        normalized)
    if m:
        from datetime import date
        y,mo,d=map(int,m.group(1,2,3))
        end_m=int(m.group(4) or mo)
        end_d=int(m.group(5))
        try:
            st=date(y,mo,d);en=date(y+int(end_m<mo),end_m,end_d)
            if st<=selected<=en:result['day']=u.day_label(selected,st,en)
        except ValueError:pass
    return result


def auto(s,selected,previous,u):
    lists=[];errors=[]
    try:
        html=u.fetch(s,AUTO_MONTH.format(year=selected.year,month=selected.month))
        month=u.parse_auto_calendar(html,selected)
        lists.append(('WINTICKET指定月',month))
    except Exception as exc:errors.append(('WINTICKET指定月',str(exc)))

    def check_official(pair):
        name,_=pair
        try:
            url=u.AUTO_OFFICIAL+u.AUTO_NAMES[name]+'/'+selected.isoformat()
            html=u.fetch(s,url)
            return name,parse_autorace_official_card(html,selected,name,u),None
        except Exception as exc:return name,None,str(exc)

    official=[];missed_official=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for name,item,issue in pool.map(check_official,AUTO_CODES.items()):
            if item:official.append(item)
            else:missed_official.append({'name':name,'reason':issue})
    if official:lists.append(('AUTORACE.JP出走表',official))

    # Oddspark is an additional fallback. Its site may reject cloud runners,
    # so do not make any venue depend on its successful response.
    racecard=[];missed_oddspark=[]
    if not official or not lists or (lists and len(lists)>1 and
                                     len(official)<len(lists[0][1])):
        def check_oddspark(pair):
            name,code=pair
            params={'gamenId':'S711','gamenKoumokuId':'iconAutoraceRaceList',
                    'joCd':code,'kaisaiBi':selected.strftime('%Y%m%d')}
            try:
                html=u.fetch(s,AUTO_ODDSPARK,params)
                return name,parse_oddspark_auto(html,selected,name,u.autorace_grade,u.race_time_type),None
            except Exception as exc:return name,None,str(exc)
        with ThreadPoolExecutor(max_workers=5) as pool:
            for name,item,issue in pool.map(check_oddspark,AUTO_CODES.items()):
                if item:racecard.append(item)
                else:missed_oddspark.append({'name':name,'reason':issue})
        if racecard:lists.append(('オッズパーク日別',racecard))

    if not lists:
        saved=cached_section(previous,selected,'auto')
        return saved if saved else u.bad('すべてのオートレース開催日程が取得できません')
    result=reconcile('auto',lists,list(AUTO_CODES),u.sort_by_time)
    result['verification'].update(errors=errors,unconfirmedOfficial=missed_official,
                                   unconfirmedRacecards=missed_oddspark)
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
