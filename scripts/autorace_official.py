"""Independent official autorace calendars; do not rely on client-rendered racecards.

A dated annual grade table from AUTORACE.JP independently confirms SG/G1/G2
meetings. Kawaguchi's organizer calendar confirms locally published regular
night meets. Both are keyed by event date, venue and grade.
"""
from datetime import date, datetime
import re
from unicodedata import normalize
from bs4 import BeautifulSoup

JKA_GRADE_CALENDAR='https://autorace.jp/calendar/graderace/'
KAWAGUCHI_CALENDAR='https://www.kawaguchiauto.jp/race-calender/'
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
        if '場外' in event:continue
        gm=re.search(r'(SG|特\s*G(?:III|II|I|[123])|G(?:III|II|I|[123]))',
                     event,re.I)
        result.append({
            'name':'川口',
            'grade':u.autorace_grade(gm.group(1)) if gm else '普通',
            'day':u.day_label(selected,start,end),
            'timeType':u.race_time_type(event)})
    if len(result)>1:
        raise ValueError('川口オート公式日程で同日開催が重複')
    return result
