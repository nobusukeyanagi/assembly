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
BOAT_G3='https://www.boatrace.jp/owpc/pc/race/gradesch?hcd=03'
# Published, dated final-race tables. Never guess a campaign URL for months
# that have not been independently identified and verified.
KEIRIN_MONTH_FINALS={
    (2026,10):'https://www.winticket.jp/keirin/campaign/onYZ47mxGGoqRuAo3AzxdX',
    (2026,11):'https://www.winticket.jp/keirin/campaign/pK2vUymUNoU1cwWwXXQm14',
}
KEIRIN_2026_OCT_FINALS=KEIRIN_MONTH_FINALS[(2026,10)]
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

# Highest-ranked, date-checked source wins per field, not per entire row.
# For women's races, "False" often means "not detected", not "no race".
# Names here correspond to collector result labels (not arbitrary domains).
FIELD_SOURCE_PRIORITY={
    'keirin':{
        'grade':('KEIRIN.JP','楽天Kドリームス','KEIRIN HEX','WINTICKET '),
        'day':('KEIRIN.JP','楽天Kドリームス','KEIRIN HEX','WINTICKET '),
        'timeType':('KEIRIN.JP','KEIRIN HEX','WINTICKET ','楽天Kドリームス'),
        'girls':('KEIRIN.JP','KEIRIN HEX','WINTICKET ','楽天Kドリームス'),
    },
    'auto':{
        'grade':('AUTORACE.JP出走表','WINTICKET指定月','オッズパーク日別'),
        'day':('AUTORACE.JP出走表','WINTICKET指定月','オッズパーク日別'),
        'timeType':('AUTORACE.JP出走表','オッズパーク日別','WINTICKET指定月'),
        'girls':('AUTORACE.JP出走表','オッズパーク日別','WINTICKET指定月'),
    },
    'soda':{
        'grade':('BOAT RACE公式G3日程','BOAT RACE公式','きょうの競艇'),
        'day':('BOAT RACE公式','きょうの競艇','BOAT RACE公式G3日程'),
        'timeType':('BOAT RACE公式','きょうの競艇','BOAT RACE公式G3日程'),
        'girls':('BOAT RACE公式G3日程','BOAT RACE公式','きょうの競艇'),
    },
}
VALID_TIME_TYPES={'モーニング','デイ','ナイター','ミッドナイト'}


def source_rank(category,field,source):
    """Lower rank means more reliable *for this field*, not globally."""
    preferred=FIELD_SOURCE_PRIORITY.get(category,{}).get(field,())
    for rank,label in enumerate(preferred):
        if source==label or (label.endswith(' ') and source.startswith(label)):
            return rank
    return len(preferred)


def valid_field(field,value):
    if field=='timeType':return isinstance(value,str) and value in VALID_TIME_TYPES
    if field=='day':
        return isinstance(value,str) and bool(re.fullmatch(r'初日|最終日|[1-9]\d*日目',value))
    if field=='grade':
        return isinstance(value,str) and bool(re.fullmatch(
            r'(?:GP|SG|PG1|特G1|G[123]|F[12]|一般|普通)',value))
    return value is not None and value!='確認中'


def compatible_grade(category,selected_grade,other_grade,grade_source):
    """A boat annual G3 confirmation can correct a generic daily '一般'."""
    if not valid_field('grade',other_grade) or not valid_field('grade',selected_grade):
        return True
    if selected_grade==other_grade:return True
    return (category=='soda' and grade_source=='BOAT RACE公式G3日程' and
            selected_grade=='G3' and other_grade in ('一般','普通'))


def reconcile(category,lists,venue_order,sort_by_time):
    """Merge date-validated providers with field priorities and traceable evidence.

    Do not borrow a time slot or a girls indicator from a differently graded
    meeting. Never interpret missing/False girls data as evidence of absence.
    Every displayed field records its source; incompatible fields are audited.
    """
    records={};providers={};differences=[];ignored=[]
    for source,items in lists:
        providers[source]=len(items)
        seen=set()
        for row in items:
            name=row.get('name')
            if not name:continue
            if name in seen:
                ignored.append({'name':name,'source':source,'reason':'同一情報源の開催場重複'})
                continue
            seen.add(name)
            records.setdefault(name,[]).append((source,row))
    merged=[]
    for name,entries in records.items():
        result={'name':name,'girls':False}
        result['confirmedBy']=[source for source,_ in entries]
        provenance={}
        def choose(field,candidates):
            usable=[(source,row[field],index) for index,(source,row) in candidates
                    if valid_field(field,row.get(field))]
            if not usable:return None,None
            source,value,_=min(usable,key=lambda v:(source_rank(category,field,v[0]),v[2]))
            provenance[field]=source
            for rival,rival_value,_ in usable:
                if rival_value!=value:
                    differences.append({'name':name,'field':field,'primary':value,
                                        'selectedSource':source,'alternative':rival_value,
                                        'source':rival,'alternativeSource':rival})
            return value,source
        result['grade'],grade_source=choose('grade',list(enumerate_entries(entries)))
        # Reject details belonging to a source describing a different meeting
        # grade (except the documented BOAT RACE general/G3 correction).
        eligible=[]
        for index,(source,row) in enumerate(entries):
            if compatible_grade(category,result['grade'],row.get('grade'),grade_source):
                eligible.append((index,(source,row)))
            else:
                for field in ('day','timeType','girls'):
                    if row.get(field) not in (None,False,'確認中'):
                        ignored.append({'name':name,'field':field,'source':source,
                                        'reason':'採用グレードとの不一致'})
        result['day'],_=choose('day',eligible)
        result['timeType'],_=choose('timeType',eligible)
        positive=[source for _,(source,row) in eligible if row.get('girls') is True]
        if positive:
            result['girls']=True
            result['girlsConfirmedBy']=list(dict.fromkeys(positive))
            provenance['girls']=min(positive,key=lambda source:source_rank(category,'girls',source))
        result['fieldSources']=provenance
        merged.append(result)
    merged.sort(key=lambda x:venue_order.index(x['name'])
                if x['name'] in venue_order else len(venue_order))
    ordered=sort_by_time(merged)
    fields=('grade','day','timeType')
    verification={
        'providers':providers,
        'crossConfirmed':sum(len(x['confirmedBy'])>1 for x in merged),
        'singleSource':sum(len(x['confirmedBy'])==1 for x in merged),
        'gradeCrossConfirmed':sum(
            sum(row.get('grade')==item['grade']
                for _,row in records[item['name']])>1 for item in merged),
        'fieldCoverage':{f:sum(valid_field(f,item.get(f)) for item in merged) for f in fields}
                        | {'girlsDetected':sum(item['girls'] for item in merged)},
        'priorityPolicy':FIELD_SOURCE_PRIORITY.get(category,{}),
        'conflicts':differences,
        'ignoredFields':ignored,
    }
    if differences:LOG.warning('%s 情報源の不一致: %s',category,differences)
    if ignored:LOG.warning('%s 採用しない情報: %s',category,ignored)
    return {'status':'ok','items':ordered,'verification':verification}


def enumerate_entries(entries):
    """Stable insertion order also acts as a fallback for unlisted providers."""
    for index,(source,row) in enumerate(entries):
        yield index,(source,row)


def parse_keirin_month_finals(html,selected,archive,u):
    """Recover slots and girls race evidence from a published monthly final list.

    Only use a known URL for the target year/month. Never apply the schedule
    to an unrelated date, track or grade.
    """
    if (selected.year,selected.month) not in KEIRIN_MONTH_FINALS or not archive:
        return []
    soup=BeautifulSoup(html,'html.parser')
    heading=next((h for h in soup.find_all(['h1','h2'])
                  if 'すべての決勝レースで5%還元' in h.get_text(' ',strip=True)),None)
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if heading is None or f'{selected.year}年{selected.month}月1日' not in text:
        raise ValueError('指定年月の決勝開催一覧を検証できません')
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
        found_date=re.search(rf'(?<!\d){selected.month}\s*/\s*(\d{{1,2}})(?!\d)',row)
        if found_date:
            day=int(found_date.group(1))
            try:current_date=date(selected.year,selected.month,day)
            except ValueError:current_date=None
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


def parse_keirin_oct_2026_finals(html,selected,archive,u):
    """Backwards-compatible entry point for the October-specific fixture."""
    if (selected.year,selected.month)!=(2026,10):return []
    return parse_keirin_month_finals(html,selected,archive,u)


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
    monthly_url=KEIRIN_MONTH_FINALS.get((selected.year,selected.month))
    if monthly_url:
        archive=next((rows for source,rows in lists if source=='楽天Kドリームス'),[])
        if archive:
            name=f'WINTICKET {selected.year}年{selected.month}月決勝日程'
            try:
                rows=parse_keirin_month_finals(
                    u.fetch(s,monthly_url),selected,archive,u)
                if rows:lists.append((name,rows))
            except Exception as exc:
                errors.append((name,str(exc)))
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


def parse_boat_g3_schedule(html,selected,venue_names):
    """Read BOAT RACE official G3 annual calendar with year/date/venue checks."""
    soup=BeautifulSoup(html,'html.parser')
    h2=next((h for h in soup.find_all('h2') if 'G3スケジュール' in h.get_text(' ',strip=True)),None)
    current_year=next((h for h in soup.find_all(['h2','h3'])
                       if re.fullmatch(r'\s*'+str(selected.year)+r'\s*年\s*',
                                       normalize('NFKC',h.get_text(' ',strip=True)))),None)
    if h2 is None or current_year is None:
        raise ValueError('公式G3日程のグレード・対象年が一致しません')
    # Scope table rows to the selected year heading. A page may also contain
    # previous/following years, which must never be mistaken for this date.
    table=None
    for element in current_year.next_elements:
        if getattr(element,'name',None) in ('h2','h3') and re.fullmatch(
                r'\s*20\d{2}\s*年\s*',
                normalize('NFKC',element.get_text(' ',strip=True))):
            break
        if getattr(element,'name',None)=='table':
            table=element
            break
    if table is None:
        raise ValueError('公式G3日程の対象年に一覧表がありません')
    found={}
    for tr in table.find_all('tr'):
        row=normalize('NFKC',tr.get_text(' ',strip=True))
        bounds=re.search(r'(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})\s*[-～〜~]\s*'
                         r'(\d{1,2})\s*/\s*(\d{1,2})(?!\d)',row)
        if bounds is None:continue
        m1,d1,m2,d2=map(int,bounds.groups())
        try:
            start=date(selected.year,m1,d1)
            finish=date(selected.year+int(m2<m1),m2,d2)
        except ValueError:continue
        if not start<=selected<=finish:continue
        candidates=[normalize('NFKC',img.get('alt','')).strip()
                    for img in tr.find_all('img',alt=True)]
        matches=[name for name in venue_names if name in candidates]
        if len(matches)!=1:continue
        name=matches[0]
        if name in found:raise ValueError('同じ日のG3開催が重複しています')
        found[name]={'name':name,'grade':'G3',
                     'girls':bool(re.search('オールレディース|女子戦',row))}
    return found


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
    # The general official schedule can omit a G3 badge and default to 一般.
    # Cross-check the separate official annual G3 schedule for the precise
    # date and track, and correct only that verified grade.
    try:
        official_g3=parse_boat_g3_schedule(u.fetch(s,BOAT_G3),selected,u.SODA_NAMES)
        matched=[dict(row) for row in official_g3.values()
                 if any(row['name']==item['name'] for _,items in lists for item in items)]
        if matched:
            # Keep providers' original grade claims intact and auditable.
            # The field-level policy gives the matching official G3 calendar
            # precedence, while retaining day/night details from daily tables.
            lists.append(('BOAT RACE公式G3日程',matched))
    except Exception as exc:
        errors.append(('BOAT RACE公式G3日程',str(exc)))
    result=reconcile('soda',lists,u.SODA_NAMES,u.sort_by_time)
    result['verification']['errors']=errors
    result['note']='SODA対象場で開催。SODAライブ配信を保証するものではありません。'
    return result
