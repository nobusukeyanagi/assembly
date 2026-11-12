"""Verified G3-or-higher keirin and graded autorace championship racecards.

Only a race explicitly labelled 決勝 or 優勝戦 qualifies.  A meeting's final
day by itself never qualifies.  All entries, clock times, and rider names
must be read from the dated racecard; no generated example data.
"""
from __future__ import annotations
import re
from datetime import date
from unicodedata import normalize
from urllib.parse import urljoin
from bs4 import BeautifulSoup

GRADE_KEIRIN={'GP','G1','G2','G3'}
GRADE_AUTO={'SG','G1','G2','特G1'}
KEIRIN_HEX='https://keirinhex.jp/races/{day}/'
TOKYO_SPORTS='https://autorace.tokyo-sports.co.jp/list/race/{day}{code}{race}'
AUTO_CODES={'川口':'02','伊勢崎':'03','浜松':'04','飯塚':'05','山陽':'06'}
PREFECTURES='北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄'.split()
PREF_PATTERN=re.compile('|'.join(map(re.escape,sorted(PREFECTURES,key=len,reverse=True))))
TIME_PATTERN=re.compile(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b')

def txt(element):
    return normalize('NFKC',element.get_text(' ',strip=True)) if hasattr(element,'get_text') else normalize('NFKC',str(element).strip())

def grade(value):
    v=normalize('NFKC',str(value)).replace(' ','').upper()
    return {'GI':'G1','GII':'G2','GIII':'G3','特GI':'特G1','特GII':'特G2'}.get(v,v)

def verify_riders(items,maximum=9):
    if not 1<=len(items)<=maximum:raise ValueError('出走表の選手数が不正です')
    nums=[row['number'] for row in items]
    if len(nums)!=len(set(nums)) or not all(1<=n<=maximum for n in nums):
        raise ValueError('車番が重複または範囲外です')
    if not all(isinstance(row['name'],str) and 2<=len(row['name'])<=20 for row in items):
        raise ValueError('選手名を確認できません')
    return sorted(items,key=lambda row:row['number'])

def keirin_final_candidates(html,selected,venues):
    """A dated KEIRIN HEX race index has one h3 per meeting and linked races."""
    soup=BeautifulSoup(html,'html.parser')
    h1=soup.find('h1')
    d=f'{selected.year}年{selected.month}月{selected.day}日'
    if not h1 or d not in txt(h1):raise ValueError('競輪レース一覧の日付が一致しません')
    accepted={x['name']:grade(x['grade']) for x in venues
              if grade(x.get('grade')) in GRADE_KEIRIN}
    out=[]
    pattern=re.compile(r'^(GP|G[123])\s*(.+?)競輪(?:最終日|\d+日目|初日)')
    race_pattern=re.compile(r'^(\d{1,2})R\s+((?:[01]\d|2[0-3]):[0-5]\d)\s+(.+決勝)$')
    for h in soup.find_all('h3'):
        match=pattern.search(txt(h))
        if not match:continue
        gr,place=match.groups()
        if accepted.get(place)!=gr:continue
        meeting=''
        for el in h.next_elements:
            if getattr(el,'name',None) in ('h2','h3'):break
            if getattr(el,'name',None)=='a':
                title=txt(el)
                if re.match(r'^\d+R\s+',title):break
            if isinstance(el,str):
                value=txt(el)
                if (len(value)>=3 and len(value)<=100 and value!=txt(h)
                    and '競輪' not in value and '開催ページ' not in value
                    and not re.search(r'\d{1,2}R\s+\d{2}:\d{2}',value)):
                    meeting=value
                    break
        if not meeting:
            # A missing actual tournament name must not become a fake name.
            continue
        for el in h.next_elements:
            if getattr(el,'name',None) in ('h2','h3'):break
            if getattr(el,'name',None)!='a':continue
            m=race_pattern.match(txt(el))
            if not m:continue
            num,time,racename=m.groups()
            href=el.get('href','')
            if not re.fullmatch(r'/races/'+selected.strftime('%Y%m%d')+r'/[0-9a-zA-Z_-]+/?',href):
                continue
            out.append({'sport':'keirin','venue':place,'grade':gr,
                        'meeting':meeting,'raceName':racename,
                        'race':int(num),'start':time,'url':urljoin('https://keirinhex.jp',href)})
    return out

def parse_keirin_final(html,selected,candidate):
    soup=BeautifulSoup(html,'html.parser')
    h1=soup.find('h1')
    heading=f"{candidate['venue']}競輪 {candidate['race']}R"
    if not h1 or heading not in txt(h1) or f'{selected.year}年{selected.month}月{selected.day}日' not in txt(h1):
        raise ValueError('競輪出走表の日付・場・Rが一致しません')
    # Make sure the final class is explicitly identified on the detail page.
    plain=txt(soup)
    if not re.search(r'種別\s*決勝',plain):
        raise ValueError('レース詳細で決勝を確認できません')
    h2=next((h for h in soup.find_all('h2') if txt(h)=='出走表'),None)
    if h2 is None:raise ValueError('出走表欄なし')
    table=h2.find_next('table')
    if table is None:raise ValueError('選手表がありません')
    riders=[]
    for tr in table.find_all('tr'):
        cols=tr.find_all('td',recursive=False)
        if len(cols)<2:continue
        n=re.fullmatch(r'[1-9]',txt(cols[0]))
        if not n:continue
        name_cell=txt(cols[1]).replace('　','').replace(' ','')
        pref=PREF_PATTERN.search(name_cell)
        if not pref:continue
        name=re.sub(r'^[◎○△▲☆注×印本命対抗]+','',name_cell[:pref.start()])
        if name:
            riders.append({'number':int(n.group()),'name':name})
    riders=verify_riders(riders,9)
    return dict(candidate,riders=riders)

def parse_auto_final(html,selected,venue,number):
    soup=BeautifulSoup(html,'html.parser')
    title=soup.title
    title_pattern=rf'{selected.year}年{selected.month:02d}月{selected.day:02d}日\s*{re.escape(venue)}オート\s*{number}R'
    if title is None or not re.search(title_pattern,txt(title)):
        # Tokyo Sports sometimes renders non-zero-padded dates.
        pattern=rf'{selected.year}年{selected.month}月{selected.day}日\s*{re.escape(venue)}オート\s*{number}R'
        if title is None or not re.search(pattern,txt(title)):
            raise ValueError('オート出走表の日付・場・Rが一致しません')
    h1=soup.find('h1')
    if h1 is None:raise ValueError('オート開催節名がありません')
    meeting=txt(h1)
    if not meeting:raise ValueError('開催節名が空です')
    text=txt(soup)
    # Require an actual championship event label, never just an overall grade.
    match=re.search(r'優勝戦(?:\s*[（(][^）)]*[）)])?',text)
    if not match:raise ValueError('レース名に優勝戦がありません')
    start_match=re.search(r'発走\s*[：:]\s*((?:[01]\d|2[0-3]):[0-5]\d)',text)
    if not start_match:raise ValueError('発走時刻を確認できません')
    heading_prefix=text[max(0,text.find(meeting)-80):text.find(meeting)]
    g=re.search(r'\b(SG|G[12]|特G1)\b',heading_prefix)
    if not g:
        # Grade is shown immediately ahead of the event title in the source.
        pre=soup.find_previous(string=re.compile(r'\b(SG|G[12]|特G1)\b')) if False else ''
        grade_match=re.search(r'\b(SG|G[12]|特G1)\b',text[:text.find(meeting)])
        if not grade_match:raise ValueError('オート競走のグレードを確認できません')
        gr=grade_match.group(1)
    else:gr=g.group(1)
    table=next((tb for tb in soup.find_all('table')
                if '車番' in txt(tb.get_text(' ',strip=True)) and '選手名' in txt(tb.get_text(' ',strip=True))),None)
    if table is None:raise ValueError('オート出走表がありません')
    riders=[]
    for tr in table.find_all('tr'):
        cells=tr.find_all('td',recursive=False)
        if not cells:continue
        first=cells[0]
        first_text=txt(first)
        num=re.match(r'^([1-8])(?:\s|$)',first_text)
        if not num:continue
        link=first.find('a',href=re.compile(r'autorace\.jp'))
        if not link:continue
        name=re.sub(r'\s+','',txt(link))
        if name:riders.append({'number':int(num.group(1)),'name':name})
    riders=verify_riders(riders,8)
    return {'sport':'auto','venue':venue,'grade':gr,'meeting':meeting,
            'raceName':match.group(0),'race':number,'start':start_match.group(1),
            'riders':riders,'url':TOKYO_SPORTS.format(day=selected.strftime('%Y%m%d'),
                                                      code=AUTO_CODES[venue],race=number)}

def collect_finals(s,selected,sections,fetch,log):
    """Discover and verify exact championship racecards, no speculative entries."""
    races=[];warnings=[]
    keirin=sections.get('keirin',{}).get('items',[])
    eligible=[x for x in keirin if grade(x.get('grade')) in GRADE_KEIRIN]
    if eligible:
        try:
            day_html=fetch(s,KEIRIN_HEX.format(day=selected.strftime('%Y%m%d')))
            for candidate in keirin_final_candidates(day_html,selected,eligible):
                try:
                    races.append(parse_keirin_final(fetch(s,candidate['url']),selected,candidate))
                except Exception as exc:
                    warnings.append('競輪 '+candidate['venue']+': '+str(exc))
        except Exception as exc:warnings.append('競輪決勝一覧: '+str(exc))

    auto=sections.get('auto',{}).get('items',[])
    for meet in auto:
        if grade(meet.get('grade')) not in GRADE_AUTO or meet.get('day')!='最終日':
            continue
        name=meet['name']
        if name not in AUTO_CODES:continue
        for race_no in (12,11):
            url=TOKYO_SPORTS.format(day=selected.strftime('%Y%m%d'),
                                     code=AUTO_CODES[name],race=race_no)
            try:
                card=parse_auto_final(fetch(s,url),selected,name,race_no)
                if grade(card['grade'])==grade(meet['grade']):races.append(card)
            except Exception as exc:
                # Most meetings have no championship at 11R; this is normal.
                if race_no==12:log.info('オート優勝戦照合: %s %sR %s',name,race_no,exc)
    # Preserve only confirmed card data, then order by scheduled race start.
    ids=set();valid=[]
    for row in races:
        key=(row['sport'],row['venue'],row['race'])
        if key in ids:continue
        ids.add(key);valid.append(row)
    valid.sort(key=lambda x:(x['start'],x['sport'],x['venue'],x['race']))
    for w in warnings:log.warning(w)
    return {'status':'ok','items':valid,'warnings':warnings}
