"""Additional date-validated keirin time-slot and girls-event sources.

No race may be invented from these pages: both are used only to enrich a
same-day meeting already identified by a dated archive or official listing.
"""
from datetime import date, datetime
from unicodedata import normalize
import re

from bs4 import BeautifulSoup


JKA_MORNING='https://keirin.jp/pc/dfw/portal/guest/campaign/morning/index.html'
CTC_SCHEDULE='https://ctc.gr.jp/schedule/'


def official_morning(html, selected, records, u):
    """Confirm morning meetings from JKA's explicitly dated monthly calendar."""
    soup=BeautifulSoup(html,'html.parser')
    if 'モーニング競輪' not in normalize('NFKC',soup.get_text(' ',strip=True))[:500]:
        raise ValueError('公式モーニング開催のタイトルを確認できません')
    months=[h for h in soup.find_all(['h2','h3']) if re.search(
        rf'{selected.year}年\s*{selected.month}月',
        normalize('NFKC',h.get_text(' ',strip=True)))]
    if len(months)!=1:raise ValueError('対象年月の公式モーニング日程がありません')
    pieces=[]
    for element in months[0].next_elements:
        if getattr(element,'name',None) in ('h2','h3'):break
        if isinstance(element,str):
            value=normalize('NFKC',element).strip()
            if value:pieces.append(value)
    block=' '.join(pieces)
    periods=list(re.finditer(
        r'(?:(\d{1,2})月)?(\d{1,2})日(?:\([^)]*\))?\s*[~〜～\-]+\s*'
        r'(?:(\d{1,2})月)?(\d{1,2})日(?:\([^)]*\))?',block))
    known=set(u.KEIRIN_NAMES)
    matched=set()
    for i,period in enumerate(periods):
        start_month,start_day,end_month,end_day=period.groups()
        a=int(start_month or selected.month)
        b=int(start_day)
        c=int(end_month or a)
        d=int(end_day)
        years=[selected.year] if a<=c else [selected.year,selected.year-1]
        bounds=[]
        for year in years:
            try:
                st=date(year,a,b);en=date(year+int(c<a),c,d)
            except ValueError:continue
            if st<=selected<=en:bounds.append((st,en))
        if len(bounds)!=1:continue
        segment=block[period.end():periods[i+1].start() if i+1<len(periods) else len(block)]
        names={n for n in known if n+'競輪場' in segment}
        if len(names)==1:matched.update(names)
    # The original official calendar does not reliably expose girls-event
    # badges as accessible text. Confirm only the time classification.
    return [{'name':r['name'],'timeType':'モーニング'}
            for r in records if r.get('name') in matched]


def ctc_listing(html,selected,records,u):
    """Cross-check near-current CTC schedules against independently dated venues.

    Event rows show a venue number, grade and dates, plus explicit
    モーニング/ナイター/ミッドナイト and ガールズ annotations.
    They do not supply a reliable year for each event: restrict this
    source to selected dates within 65 days of today in Japan.
    """
    if abs((selected-datetime.now(u.TZ).date()).days)>65 or not records:return []
    soup=BeautifulSoup(html,'html.parser')
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if '開催情報' not in text[:500]:raise ValueError('CTC開催情報の見出しがありません')
    names='|'.join(map(re.escape,sorted(u.KEIRIN_NAMES,key=len,reverse=True)))
    blocks=list(re.finditer(r'('+names+r')\s*\d{2}#',text))
    if not blocks:raise ValueError('CTC開催場の番号を確認できません')
    dates=re.compile(r'(\d{1,2})/(\d{1,2})(?:\([^)]*\))?\s*[~〜～\-]+\s*'
                     r'(\d{1,2})/(\d{1,2})(?:\([^)]*\))?')
    verified={}
    for i,match in enumerate(blocks):
        name=match.group(1)
        body=text[match.end():blocks[i+1].start() if i+1<len(blocks) else len(text)]
        times=dates.search(body)
        if not times:continue
        a,b,c,d=map(int,times.groups())
        possible=[]
        for year in (selected.year-1,selected.year,selected.year+1):
            try:st=date(year,a,b);en=date(year+int(c<a),c,d)
            except ValueError:continue
            if st<=selected<=en:possible.append((st,en))
        if len(possible)!=1:continue
        grade=re.search(r'(GP|G(?:III|II|I|[123])|F(?:II|I|[12]))\s*$',
                        body[:times.start()],re.I)
        if not grade:continue
        grade=u.grade(grade.group(1))
        descriptors=body[times.end():][:40]
        slot=next((word for word in ('ミッドナイト','モーニング','ナイター')
                   if word in descriptors),None)
        verified[name]={'grade':grade,'timeType':slot,
                        'girls':'ガールズ' in descriptors}
    return [{'name':r['name'],'grade':verified[r['name']]['grade'],
             'timeType':verified[r['name']]['timeType'],
             'girls':verified[r['name']]['girls']}
            for r in records if r.get('name') in verified and
            r.get('grade')==verified[r['name']]['grade']]
