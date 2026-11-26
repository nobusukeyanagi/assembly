"""Date-specific publicly published Mori race-card evidence.

A racer-profile calendar can return 403 in GitHub Actions even while dated
racecards work. Use an independently dated and venue-qualified entry list.
Only emit the rider's race identity, not the provider's prediction table.
"""
from datetime import date
import re
from unicodedata import normalize
from bs4 import BeautifulSoup

PREDICTIONS='https://www.chariloto.com/auto/predictions/{venue}/{day}'
KAWAGUCHI_NIGHT='https://www.kawaguchiauto.jp/nightrace/'
CODES={'川口':'002','伊勢崎':'003','浜松':'004','飯塚':'005','山陽':'006'}


def compact(value):
    return re.sub(r'\s+','',normalize('NFKC',str(value or '')))


def predictions(html, selected, venue):
    """Read only racer names attached to a numbered race in a dated card.

    A page-wide '森且行' search is unsafe: navigation, news and historical
    stats can mention the rider without his being an entrant today.
    """
    if venue not in CODES:
        raise ValueError('対象外のオートレース場')
    soup=BeautifulSoup(html,'html.parser')
    headings=[compact(h.get_text(' ',strip=True)) for h in soup.find_all('h1')]
    if venue+'オート予想' not in headings:
        raise ValueError('チャリロトの対象開催場の予想見出しがありません')
    text=compact(soup.get_text(' ',strip=True))
    day=f'{selected.year}年{selected.month}月{selected.day}日'
    if day+venue+'オートレース' not in text[:4000]:
        raise ValueError('チャリロトの対象日付・開催場が一致しません')
    races=set()
    seen_tables=0
    for table in soup.find_all('table'):
        headers=compact(' '.join(th.get_text(' ',strip=True)
                                 for th in table.find_all('th')))
        if '選手名' not in headers or 'レース' not in headers:
            continue
        seen_tables+=1
        current=None
        for tr in table.find_all('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if not cells:
                continue
            first=compact(cells[0].get_text(' ',strip=True))
            marker=re.fullmatch(r'(1[0-2]|[1-9])R',first,re.I)
            if marker:
                current=int(marker.group(1))
            if current is None:
                continue
            # Only a runner cell, never a heading or page-wide biography.
            if any(compact(cell.get_text(' ',strip=True))=='森且行'
                   for cell in cells[1:]):
                races.add(current)
    if not seen_tables:
        raise ValueError('チャリロトの競走選手一覧表を確認できません')
    return sorted(races)


def kawaguchi_night_starts(html, selected, races):
    """Return organizer-published race times for this *specific* meeting.

    Don't interpret '発売締切' or '試走開始' as 発走予定. Require the
    explicit year and meeting interval in the same official page.
    """
    soup=BeautifulSoup(html,'html.parser')
    title=compact(soup.title.get_text(' ',strip=True)) if soup.title else ''
    text=normalize('NFKC',soup.get_text(' ',strip=True))
    if ('川口' not in title and '川口ナイトレース' not in text[:1000]) or \
            '川口ナイトレース' not in text:
        raise ValueError('川口公式ナイトレースのページではありません')
    # Official current-meeting banner: "2026 11/22 SUN ▶ 25 WED".
    period=re.search(
        r'(20\d{2})\s+(\d{1,2})/(\d{1,2})\s+[A-Za-z]{2,5}\s*'
        r'[▶～〜~-]\s*(?:(\d{1,2})/)?(\d{1,2})\s+[A-Za-z]{2,5}',
        text)
    if not period:
        raise ValueError('公式の年度付き開催期間を確認できません')
    year,month,start_day,end_month,end_day=period.groups()
    try:
        first=date(int(year),int(month),int(start_day))
        final_month=int(end_month or month)
        last_year=int(year)+(final_month<int(month))
        last=date(last_year,final_month,int(end_day))
    except ValueError as exc:
        raise ValueError('公式開催期間の日付が不正') from exc
    if not first<=selected<=last:
        raise ValueError('公式ナイトレースの対象開催期間外です')
    found={}
    for table in soup.find_all('table'):
        heads=compact(' '.join(h.get_text(' ',strip=True)
                               for h in table.find_all('th')))
        if 'レース' not in heads or '発走予定' not in heads:
            continue
        for tr in table.find_all('tr'):
            cells=tr.find_all(['th','td'],recursive=False)
            if len(cells)<4:
                continue
            race=compact(cells[0].get_text(' ',strip=True))
            match=re.fullmatch(r'(1[0-2]|[1-9])R',race,re.I)
            if not match:
                continue
            num=int(match.group(1))
            clock=compact(cells[-1].get_text(' ',strip=True))
            if not re.fullmatch(r'(?:[01]?\d|2[0-3]):[0-5]\d',clock):
                continue
            if num in found and found[num]!=clock.zfill(5):
                raise ValueError('発走予定時刻が複数存在します')
            found[num]=clock.zfill(5)
    if len(found)<6:
        raise ValueError('公式の発走予定時刻表が不足しています')
    return {n:found[n] for n in races if n in found}


def kawaguchi_night_assignment(html, selected):
    """The dated meeting's featured entrant roster, not the generic future calendar."""
    soup=BeautifulSoup(html,'html.parser')
    heads=[compact(h.get_text(' ',strip=True)) for h in soup.find_all(['h1','title'])]
    if not any('川口ナイトレース' in h for h in heads):
        raise ValueError('川口ナイトレース公式見出し未確認')
    def section(label):
        heading=next((h for h in soup.find_all('h2')
                      if compact(h.get_text(' ',strip=True))==label),None)
        if heading is None:raise ValueError(label+'欄未確認')
        nodes=[]
        for el in heading.next_elements:
            if getattr(el,'name',None) in ('h1','h2'):break
            nodes.append(el)
        return nodes
    from bs4 import NavigableString
    dates=' '.join(str(el) for el in section('開催日程') if isinstance(el,NavigableString))
    period=re.search(
        r'(20\d{2})\s+(\d{1,2})/(\d{1,2})\s+[A-Za-z]{2,5}\s*'
        r'[▶～〜~-]\s*(?:(\d{1,2})/)?(\d{1,2})\s+[A-Za-z]{2,5}',
        normalize('NFKC',dates))
    if not period:raise ValueError('注目選手の対象開催期間未確認')
    year,month,first,end_month,last=period.groups()
    start=date(int(year),int(month),int(first))
    em=int(end_month or month)
    end=date(int(year)+(em<int(month)),em,int(last))
    if not (selected<start<=end and (start-selected).days<=45 and (end-start).days<=7):
        return []
    featured=section('注目選手')
    for el in featured:
        if getattr(el,'name',None) not in ('a','img'):continue
        name=compact(el.get('alt','') if el.name=='img' else el.get_text(' ',strip=True))
        if name in ('森且行','森且行選手'):
            return [{'date':start.isoformat(),'meetingEnd':end.isoformat(),
                     'name':'川口','type':'next','grade':'普通','timeType':'ナイター',
                     'source':'kawaguchi-featured-entrants','sourceUrl':KAWAGUCHI_NIGHT}]
    return []
