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


ODDSPARK_DESKTOP='https://www.oddspark.com/autorace/PlayerDetail.do?playerCd=2529'
OFFICIAL_SEARCH='https://autorace.jp/race_info/SearchRecommend'
WINTICKET_ROSTER='https://www.winticket.jp/autorace/{slug}/racecard/{day}{code}/autoracers'
SLUGS={'川口':'kawaguchi','伊勢崎':'isesaki','浜松':'hamamatsu','飯塚':'iizuka','山陽':'sanyo'}


def oddspark_desktop_assignments(html, selected):
    """Read only the named rider's future table, not completed results."""
    soup=BeautifulSoup(html,'html.parser')
    head=next((h for h in soup.find_all(['h2','h3','h4'])
               if compact(h.get_text(' ',strip=True))=='森且行選手の出場予定'),None)
    if head is None:raise ValueError('森選手PC版出場予定欄未確認')
    table=head.find_next('table')
    if table is None:raise ValueError('PC版出場予定表未確認')
    headers=[compact(x.get_text(' ',strip=True)) for x in table.find_all('th')]
    if not all(x in headers for x in ('年月日','開催場','R')):raise ValueError('出場予定表項目不一致')
    result=[]
    for row in table.find_all('tr'):
        cells=[compact(x.get_text(' ',strip=True)) for x in row.find_all('td',recursive=False)]
        if len(cells)<3:continue
        dm=re.fullmatch(r'(20\d{2})[/-](\d{1,2})[/-](\d{1,2})',cells[0])
        if not dm or cells[1] not in CODES or not re.fullmatch(r'(?:1[0-2]|[1-9])R?',cells[2]):continue
        d=date(*map(int,dm.groups()))
        if not 0<=(d-selected).days<=45:continue
        item={'date':d.isoformat(),'name':cells[1],'type':'today' if d==selected else 'next',
              'sourceUrl':ODDSPARK_DESKTOP,'source':'oddspark-desktop'}
        if d==selected:item['race']=int(cells[2].removesuffix('R'))
        result.append(item)
    return result


def winticket_roster_assignment(html, selected, venue, start):
    """Validate event date, host and stable rider ID in the actual roster."""
    soup=BeautifulSoup(html,'html.parser')
    if not any(compact(h.get_text(' ',strip=True))=='出場者一覧' for h in soup.find_all('h1')):
        raise ValueError('出場者一覧未確認')
    text=compact(soup.get_text(' ',strip=True))
    dm=re.search(re.escape(venue)+rf'オートレース{start.year}年{start.month}月{start.day}日[〜～~-](?:(20\d{{2}})年)?(\d{{1,2}})月(\d{{1,2}})日',text)
    if not dm:raise ValueError('出場者一覧の開催期間不一致')
    ey,em,ed=dm.groups()
    end=date(int(ey or (start.year+(int(em)<start.month))),int(em),int(ed))
    if not selected<start<=end or (end-start).days>10 or (start-selected).days>45:return None
    exact=[a for a in soup.find_all('a',href=True)
           if re.search(r'/autorace/autoracer/2529/?(?:[?#].*)?$',a['href'])
           and re.fullmatch(r'森且行(?:川口25期)?',compact(a.get_text(' ',strip=True)))]
    if not exact:return None
    return {'date':start.isoformat(),'meetingEnd':end.isoformat(),'name':venue,'type':'next',
            'source':'winticket-event-roster','sourceUrl':WINTICKET_ROSTER.format(
                slug=SLUGS[venue],day=start.strftime('%Y%m%d'),code=CODES[venue][-2:])}


def official_search_assignments(html, selected):
    """Reject the form itself and unrelated names, dates and venue navigation."""
    soup=BeautifulSoup(html,'html.parser')
    if not any('あっせん検索' in compact(h.get_text(' ',strip=True))
               for h in soup.find_all(['h1','h2','h3','title'])):
        raise ValueError('公式あっせん検索見出し未確認')
    rows=[]
    for table in soup.find_all('table'):
        headers=[compact(c.get_text(' ',strip=True)) for c in table.find_all('th')]
        if not any('選手' in x for x in headers) or not any('開催場' in x or x=='場名' for x in headers) or not any('開催日' in x or '開催期間' in x for x in headers):
            continue
        for tr in table.find_all('tr'):
            values=[compact(c.get_text(' ',strip=True)) for c in tr.find_all('td',recursive=False)]
            if not any(v in ('森且行','モリカツユキ','森且行(川口)') or re.fullmatch(r'森且行(?:川口)?25期',v) for v in values):continue
            hosts=[v for v in values if v in CODES]
            if len(hosts)!=1:continue
            for v in values:
                dm=re.fullmatch(r'(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?(?:\([^)]*\))?(?:[〜～~-](?:(20\d{2})[年/-])?(?:(\d{1,2})[月/-])?(\d{1,2})日?(?:\([^)]*\))?)?',v)
                if not dm:continue
                y,mo,d,ey,em,ed=dm.groups()
                try:
                    start=date(int(y),int(mo),int(d))
                    end=date(int(ey or (int(y)+(bool(em) and int(em)<int(mo)))),int(em or mo),int(ed or d))
                except ValueError:continue
                if not start<=end or (end-start).days>10 or end<selected or (start-selected).days>45:continue
                item={'date':max(start,selected).isoformat(),'meetingEnd':end.isoformat(),
                      'name':hosts[0],'type':'today' if start<=selected else 'next',
                      'source':'official-national-search','sourceUrl':OFFICIAL_SEARCH}
                rows.append(item);break
    if not rows:raise ValueError('公式検索結果の森選手・開催日・場を照合できません')
    return rows


def browser_official_assignments(selected):
    """Ordinary public browser form, not an access-control workaround."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        try:
            page=browser.new_page(locale='ja-JP',timezone_id='Asia/Tokyo')
            page.set_default_timeout(8000)
            response=page.goto(OFFICIAL_SEARCH,wait_until='domcontentloaded',timeout=20000)
            if not response or response.status>=400:raise ValueError('公式検索アクセス不可')
            form=page.locator('form').filter(has=page.get_by_text('選手名（カタカナ）',exact=False)).filter(has=page.get_by_role('button',name='送信する'))
            if form.count()!=1:raise ValueError('公式あっせん検索フォーム変更')
            fields=form.locator('input:not([type]), input[type="text"], input[type="search"]')
            field=next((fields.nth(i) for i in range(fields.count()) if fields.nth(i).is_visible() and fields.nth(i).is_editable()),None)
            if field is None:raise ValueError('選手名入力欄未確認')
            field.fill('モリ　カツユキ')
            nationwide=form.get_by_label('全国',exact=True)
            if nationwide.count()==1:nationwide.check()
            else:
                control=form.locator('label').filter(has_text=re.compile(r'^\s*全国\s*$'))
                if control.count()!=1:raise ValueError('全国指定欄未確認')
                control.click()
            form.get_by_role('button',name='送信する').click()
            page.wait_for_function("""() => [...document.querySelectorAll('table')].some(t => t.innerText.replace(/\\s/g,'').includes('森且行'))""",timeout=12000)
            return official_search_assignments(page.content(),selected)
        finally:
            browser.close()
