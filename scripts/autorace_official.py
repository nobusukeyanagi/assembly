"""Independent official autorace calendars; do not rely on client-rendered racecards.

A dated annual grade table from AUTORACE.JP independently confirms SG/G1/G2
meetings. Kawaguchi's organizer calendar confirms locally published regular
night meets. Both are keyed by event date, venue and grade.
"""
from datetime import date, datetime
import re
from unicodedata import normalize
from bs4 import BeautifulSoup
from autorace_sessions import split_kawaguchi

JKA_GRADE_CALENDAR='https://autorace.jp/calendar/graderace/'
KAWAGUCHI_CALENDAR='https://www.kawaguchiauto.jp/race-calender/'
ISESAKI_CALENDAR='https://www.isesaki-auto.jp/race/'
IIZUKA_RACECARDS='https://www.iizuka-auto.jp/dl/'
IIZUKA_HOME='https://www.iizuka-auto.jp/'
GRADES={'SG','G1','G2','特G1'}


def normalize_text(value):
    return normalize('NFKC',value or '').replace('\u3000',' ').strip()


def grade_meetings(html,selected,u):
    """Validate a fiscal-year-specific official grade table, not site navigation."""
    soup=BeautifulSoup(html,'html.parser')
    heading=next((h for h in soup.find_all(['h1','h2'])
                  if '年間グレードレース日程' in normalize_text(h.get_text(' ',strip=True))),None)
    fiscal_year=selected.year if selected.month>=4 else selected.year-1
    if heading is None or f'{fiscal_year}年度' not in normalize_text(
            heading.get_text(' ',strip=True)):
        raise ValueError('AUTORACE.JPの対象年度グレード日程を確認できません')
    # The public table includes a dated race title, the grade, and the venue.
    table=next((table for table in soup.find_all('table')
                if 'グレード' in normalize_text(table.get_text(' ',strip=True))
                and 'レース場' in normalize_text(table.get_text(' ',strip=True))),None)
    if table is None:raise ValueError('AUTORACE.JPグレード日程表を確認できません')
    date_range=re.compile(
        r'(?<!\d)(20\d{2})年(\d{1,2})月(\d{1,2})日(?:\([^)]{1,12}\))?'
        r'\s*[～〜~\-]\s*(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日')
    output={}
    for row in table.find_all('tr'):
        cells=row.find_all(['td','th'],recursive=False)
        if len(cells)<3:continue
        grade_text=normalize_text(cells[0].get_text(' ',strip=True)).replace(' ','')
        gr=u.autorace_grade(grade_text)
        if gr not in GRADES:continue
        event=normalize_text(cells[1].get_text(' ',strip=True))
        venue=normalize_text(cells[2].get_text(' ',strip=True))
        if venue not in u.AUTO_NAMES:continue
        dm=date_range.search(event)
        if not dm:continue
        sy,sm,sd,ey,em,ed=dm.groups()
        try:
            start=date(int(sy),int(sm),int(sd))
            end=date(int(ey) if ey else int(sy)+int(int(em)<int(sm)),
                     int(em),int(ed))
        except ValueError:continue
        if not start<=selected<=end:continue
        if venue in output:raise ValueError('公式グレード開催の日付・場名が重複')
        output[venue]={
            'name':venue,'grade':gr,'day':u.day_label(selected,start,end),
            'timeType':u.race_time_type(event)}
    return list(output.values())


def kawaguchi_host_event(heading):
    """The organizer publishes both 本場 and 場外 event modals.

    The modal's 出場予定選手 link points to the actual host venue.
    Require positive venue evidence, not merely the absence of 場外
    in a race title. Stop at the next event heading to avoid borrowing
    a different meeting's link.
    """
    event=normalize_text(heading.get_text(' ',strip=True))
    if '場外' in event:return False
    venues=set()
    for part in heading.next_elements:
        if getattr(part,'name',None) in ('h1','h2','h3','h4'):break
        if getattr(part,'name',None)!='a':continue
        href=part.get('href','')
        match=re.search(r'(?:/netstadium/|/race_info/)Player/'
                        r'(kawaguchi|isesaki|hamamatsu|iizuka|sanyo|sanyou)(?:/|[?#]|$)',
                        href,re.I)
        if match:venues.add(match.group(1).lower())
    if venues:
        return venues=={'kawaguchi'}
    # Explicit home-venue titles are safe when the link is absent.
    return bool(re.search(r'川口(?:オート|ナイトレース|自場|本場)',event))


def kawaguchi_meetings(html,selected,u):
    """Read Kawaguchi organizer's date-ranged event titles, not venue navigation.

    This schedule omits event years, so only use its current-season view near
    the current date and check the exact date interval for every event.
    """
    if abs((selected-datetime.now(u.TZ).date()).days)>120:return []
    soup=BeautifulSoup(html,'html.parser')
    title=normalize_text(soup.title.get_text(' ',strip=True)) if soup.title else ''
    heading=' '.join(normalize_text(h.get_text(' ',strip=True)) for h in soup.find_all('h1'))
    if '川口' not in title and '開催日程' not in heading:
        raise ValueError('川口オート公式開催日程の見出しが不一致')
    ranges=re.compile(
        r'(?<!\d)(\d{1,2})/(\d{1,2})\s*(?:\([^)]{1,12}\))?\s*'
        r'[～〜~\-]\s*(\d{1,2})/(\d{1,2})(?:\([^)]{1,12}\))?')
    result=[]
    for h in soup.find_all(['h3','h4']):
        event=normalize_text(h.get_text(' ',strip=True))
        if not event or event in ('開催日程','SCHEDULE'):continue
        # Only the event's immediately following date paragraph qualifies.
        sibling=h.find_next_sibling()
        if sibling is None:continue
        label=normalize_text(sibling.get_text(' ',strip=True))
        dm=ranges.search(label)
        if not dm:continue
        start_end=u.period(selected,*map(int,dm.groups()))
        if not start_end:continue
        start,end=start_end
        if not start<=selected<=end:continue
        if not kawaguchi_host_event(h):continue
        gm=re.search(r'(SG|特\s*G(?:III|II|I|[123])|G(?:III|II|I|[123]))',
                     event,re.I)
        result.append({
            'name':'川口',
            'grade':u.autorace_grade(gm.group(1)) if gm else '普通',
            'day':u.day_label(selected,start,end),
            'timeType':u.race_time_type(event)})
    if len(result)>1:
        # A daytime event and a separate night event are both valid. The
        # suffix is assigned only when the official page confirms the pair.
        return split_kawaguchi(result)
    return result


def isesaki_meetings(html,selected,u):
    """Read only '本場' event blocks in the organizer's dated race calendar.

    The same calendar advertises other tracks as 場外: those must never be
    mistaken for races actually hosted by 伊勢崎.
    """
    soup=BeautifulSoup(html,'html.parser')
    title=normalize_text(soup.title.get_text(' ',strip=True)) if soup.title else ''
    text=normalize_text(soup.get_text(' ',strip=True))
    if '伊勢崎' not in title or '開催情報' not in text:
        raise ValueError('伊勢崎オート公式開催日程の見出しがありません')
    if not re.search(rf'(?<!\d){selected.year}\s*年\s*{selected.month}\s*月',text):
        return []
    blocks=re.split(r'(?<!\S)(本場|場外)\s+',text)
    dates=re.compile(r'(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})\s*'
                     r'[～〜~\-]\s*(\d{1,2})\s*/\s*(\d{1,2})(?!\d)')
    matched={}
    for i in range(1,len(blocks)-1,2):
        if blocks[i]!='本場':continue
        event=blocks[i+1]
        if '伊勢崎' not in event[:180]:continue
        marker=re.search(r'(普通レース|SG|特\s*G(?:III|II|I|[123])|G(?:III|II|I|[123]))',
                         event[:140],re.I)
        if not marker:continue
        for dm in dates.finditer(event):
            bounds=u.period(selected,*map(int,dm.groups()))
            if not bounds or not bounds[0]<=selected<=bounds[1]:continue
            # Ignore unrelated published broadcast hours; the event's date
            # and local track must be in the same 本場 block.
            grade=(u.autorace_grade(marker.group(1))
                   if marker.group(1)!='普通レース' else '普通')
            row={'name':'伊勢崎','grade':grade,
                 'day':u.day_label(selected,*bounds),
                 'timeType':u.race_time_type(event[:dm.end()])}
            existing=matched.get('伊勢崎')
            if existing and row!=existing:
                raise ValueError('伊勢崎公式日程で対象日の開催が重複')
            matched['伊勢崎']=row
    return list(matched.values())


def iizuka_racecards(html,selected,u):
    """Read the Iizuka organizer's year-qualified downloadable racecard notice."""
    soup=BeautifulSoup(html,'html.parser')
    text=normalize_text(soup.get_text(' ',strip=True))
    title=normalize_text(soup.title.get_text(' ',strip=True)) if soup.title else ''
    if '飯塚' not in title or '出走表' not in text:
        raise ValueError('飯塚オート公式出走表サービスの見出しがありません')
    period_rx=re.compile(
        r'(?<!\d)(20\d{2})年(\d{1,2})月(\d{1,2})日\s*'
        r'[～〜~\-]\s*(?:(20\d{2})年)?(?:(\d{1,2})月)?(\d{1,2})日')
    result=[]
    for dm in period_rx.finditer(text):
        sy,sm,sd,ey,em,ed=dm.groups()
        try:
            start=date(int(sy),int(sm),int(sd))
            month=int(em or sm)
            end=date(int(ey) if ey else int(sy)+int(month<int(sm)),month,int(ed))
        except ValueError:continue
        if not start<=selected<=end:continue
        # The same official page may advertise PDFs for 場外 races.
        # Require a positive label that the meeting is held at 飯塚.
        event=text[dm.end():dm.end()+100]
        if not re.search(r'飯塚本場開催|本場開催',event):
            continue
        label=event.split('（')[0].split('(')[0]
        gm=re.search(r'(SG|特\s*G(?:III|II|I|[123])|G(?:III|II|I|[123]))',
                     label,re.I)
        result.append({
            'name':'飯塚',
            'grade':u.autorace_grade(gm.group(1)) if gm else '普通',
            'day':u.day_label(selected,start,end),
            'timeType':u.race_time_type(label)})
    if len(result)>1:
        raise ValueError('飯塚公式出走表に複数の当日開催情報があります')
    return result


def iizuka_home_meetings(html,selected,u):
    """Last-resort current-day organizer record, when its PDF list is unavailable.

    The homepage's 本日の開催 section is ephemeral, so never reuse for another
    calendar date, even when the published date range spans several days.
    """
    if selected!=datetime.now(u.TZ).date():return []
    soup=BeautifulSoup(html,'html.parser')
    text=normalize_text(soup.get_text(' ',strip=True))
    title=normalize_text(soup.title.get_text(' ',strip=True)) if soup.title else ''
    if '飯塚' not in title or 'RACE INFORMATION' not in text:
        raise ValueError('飯塚公式トップページの開催情報を確認できません')
    anchor=text.find('本日の開催')
    if anchor<0:raise ValueError('飯塚公式トップの当日開催欄がありません')
    section=text[anchor:anchor+280].split('SCHEDULE')[0]
    if '飯塚本場開催' not in section:return []
    m=re.search(r'(?<!\d)(\d{2})/(\d{1,2})/(\d{1,2})\s*\([^)]*\)\s*'
                r'[-～〜~]\s*(\d{2})/(\d{1,2})/(\d{1,2})',section)
    if not m:return []
    yy,mm,dd,yy2,mm2,dd2=map(int,m.groups())
    try:
        start=date(2000+yy,mm,dd);end=date(2000+yy2,mm2,dd2)
    except ValueError:return []
    if not start<=selected<=end:return []
    event=section.split('飯塚本場開催',1)[1].split(m.group(0))[0]
    gm=re.search(r'(SG|特\s*G(?:III|II|I|[123])|G(?:III|II|I|[123]))',
                 event,re.I)
    return [{'name':'飯塚','grade':u.autorace_grade(gm.group(1)) if gm else '普通',
             'day':u.day_label(selected,start,end),
             'timeType':u.race_time_type(event)}]
