"""Verified grade-final race cards for the assembly keyboard presentation.

Only same-day racecards with the explicit '決勝'/'優勝戦' classification
and all visible rider numbers are published. Unconfirmed racecards are not
shown. Both sources are independently date, venue, and race-number checked.
"""
from __future__ import annotations
import logging
import re
from datetime import date
from unicodedata import normalize
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

log=logging.getLogger("assembly.finals")
HEX_DAILY="https://keirinhex.jp/races/{day}/"
AUTO_RACE="https://autorace.tokyo-sports.co.jp/list/race/{day}{venue}{race}"
AUTO_CODES={"川口":"02","伊勢崎":"03","浜松":"04","飯塚":"05","山陽":"06"}
KEIRIN_GRADES=frozenset(("GP","G1","G2","G3"))
AUTO_GRADES=frozenset(("SG","特G1","G1","G2"))
PREFECTURES="北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄".split()
PREFECTURE_PATTERN=re.compile(r"(?:地元)?(?:"+"|".join(sorted(PREFECTURES,key=len,reverse=True))+r")[・/]")
CLOCK=re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
GRADED_ENDING=re.compile(r"決勝(?:戦)?$")


def norm(value):
    return normalize("NFKC",str(value)).replace("\u3000"," ").strip()


def text_clean(value):
    return re.sub(r"\s+"," ",norm(value)).strip()


def read_riders(table,max_count=9):
    """Read numbered rows from a real race card table, with unique, valid numbers."""
    riders={}
    for row in table.find_all("tr"):
        cells=row.find_all(["th","td"],recursive=False)
        if len(cells)<2:continue
        first=text_clean(cells[0].get_text(" ",strip=True))
        if not re.fullmatch(r"[1-9]",first):continue
        number=int(first)
        # KEIRIN HEX has car number in the first column; some other sources
        # have an extra frame-number column and require a separate parser.
        col=cells[1]
        racer_link=next((a for a in col.find_all("a",href=True)
                         if "autorace.jp" in a["href"] or "keirin" in a["href"]),None)
        if racer_link:
            name=text_clean(racer_link.get_text(" ",strip=True))
        else:
            name=text_clean(col.get_text(" ",strip=True))
            name=re.sub(r"^[◎○◯▲△×☆注印\s]+","",name)
            m=PREFECTURE_PATTERN.search(name)
            if m:name=name[:m.start()].strip()
            name=re.sub(r"\s*(?:地元)?\d{1,2}歳.*$","",name)
        name=re.sub(r"\s+"," ",name).strip()
        if not re.fullmatch(r"[\u3005\u3400-\u9fffぁ-んァ-ヶー・A-Za-z\s]{2,24}",name):
            continue
        if number in riders and riders[number]!=name:
            raise ValueError("車番に複数の選手が存在します")
        riders[number]=name
    if not 5<=len(riders)<=max_count:
        raise ValueError(f"出走選手を十分に読み取れません: {len(riders)}人")
    if set(riders)!=set(range(1,len(riders)+1)):
        raise ValueError("出走車番に欠番・不連続があります")
    return [{"number":i,"name":riders[i]} for i in sorted(riders)]


def candidate_hex_finals(html,selected,meetings):
    """Find actual graded-final race links in the dated KEIRIN HEX schedule."""
    soup=BeautifulSoup(html,"html.parser")
    heading=soup.find("h1")
    expected=f"{selected.year}年{selected.month}月{selected.day}日"
    if not heading or expected not in norm(heading.get_text(" ",strip=True)):
        raise ValueError("競輪日別レース一覧の日付が一致しません")
    graded={m["name"]:m for m in meetings
            if m.get("grade") in KEIRIN_GRADES and m.get("day")=="最終日"}
    if not graded:return []
    candidates=[]
    names="|".join(map(re.escape,sorted(graded,key=len,reverse=True)))
    heading_pattern=re.compile(r"^(GP|G[123])\s*("+names+r")競輪\s*(?:[1-9]日目|最終日)")
    race_pattern=re.compile(r"^(\d{1,2})R\s+([0-2]?\d:[0-5]\d)\s+(.+)$")
    for h3 in soup.find_all("h3"):
        m=heading_pattern.match(text_clean(h3.get_text(" ",strip=True)))
        if not m:continue
        grade,venue=m.groups()
        if grade!=graded[venue]["grade"]:continue
        event=None
        links=[]
        for obj in h3.next_elements:
            if getattr(obj,"name",None) in ("h2","h3"):break
            if getattr(obj,"name",None)=="a":
                label=text_clean(obj.get_text(" ",strip=True))
                href=obj.get("href","")
                if "/cups/" in href and label.endswith("の開催ページ"):
                    event=label.removesuffix("の開催ページ").strip()
                match=race_pattern.match(label)
                if not match or "決勝" not in match.group(3):continue
                number,start,race_name=match.groups()
                target=urljoin(HEX_DAILY.format(day=selected.strftime("%Y%m%d")),href)
                parsed=urlparse(target)
                if (parsed.netloc!="keirinhex.jp" or
                    not parsed.path.startswith(f"/races/{selected:%Y%m%d}/") or
                    not CLOCK.fullmatch(start.zfill(5)) or int(number)>12):
                    continue
                links.append({"sport":"keirin","venue":venue,"grade":grade,
                              "event":event,"raceName":race_name,"race":int(number),
                              "startTime":start.zfill(5),"sourceUrl":target})
        for c in links:
            # Only the true graded main final; exclude unrelated category finals.
            if re.search(r"(?:S級|特別|GP)\s*決勝",c["raceName"]) or (
                c["grade"]=="GP" and "決勝" in c["raceName"]):
                candidates.append(c)
    return sorted(candidates,key=lambda x:(x["startTime"],x["venue"],x["race"]))


def parse_hex_final(html,selected,candidate):
    soup=BeautifulSoup(html,"html.parser")
    title=soup.find("h1")
    expected=f"{selected.year}年{selected.month}月{selected.day}日"
    if not title:raise ValueError("レース詳細に見出しがありません")
    heading=text_clean(title.get_text(" ",strip=True))
    pattern=r"^"+re.escape(candidate["venue"])+r"競輪\s*"+str(candidate["race"])+r"R\b"
    if not re.match(pattern,heading) or expected not in heading:
        raise ValueError("競輪出走表の日付・場・Rが不一致")
    description=text_clean(soup.get_text(" ",strip=True))
    # Validate the classification in the race detail, not merely the link label.
    if not re.search(r"種別\s*決勝",description):
        raise ValueError("競輪詳細の種別が決勝ではありません")
    h=next((t for t in soup.find_all(["h2","h3"])
            if text_clean(t.get_text(" ",strip=True))=="出走表"),None)
    if not h:raise ValueError("競輪出走表の表題がありません")
    table=h.find_next("table")
    if not table:raise ValueError("競輪出走表がありません")
    riders=read_riders(table)
    # Grade/event is read from the verified day's graded-meeting header.
    return dict(candidate,riders=riders)


def parse_autorace_final(html,selected,venue,race,grade):
    """Auto race's page identifies selected date + venue + R in its title."""
    soup=BeautifulSoup(html,"html.parser")
    title=text_clean(soup.title.get_text(" ",strip=True)) if soup.title else ""
    m=re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日\s*"
                r"(川口|伊勢崎|浜松|飯塚|山陽)\s*オート\s*(\d{1,2})R",title)
    if (not m or tuple(map(int,m.group(1,2,3))) !=
        (selected.year,selected.month,selected.day) or
        m.group(4)!=venue or int(m.group(5))!=race):
        raise ValueError("オート出走表の日付・場・Rが不一致")
    event_heading=soup.find("h1")
    if not event_heading:raise ValueError("オート開催節名が取得できません")
    event=text_clean(event_heading.get_text(" ",strip=True))
    if not event:raise ValueError("オート開催節名が空欄です")
    # Restrict classification and time to the race header before the first
    # 出走表; navigation and historic race text are NOT trusted for this.
    text=text_clean(soup.get_text(" ",strip=True))
    idx=text.find(event)
    card_header=text[idx:idx+500].split("出走表")[0]
    match=re.search(r"優勝戦(?:\s*[（(][^）)]{1,16}[）)])?|決勝戦",card_header)
    if not match:raise ValueError("オートレースが優勝戦ではありません")
    start_match=re.search(r"発走\s*[：:]\s*([0-2]?\d:[0-5]\d)",card_header)
    if not start_match:raise ValueError("オート優勝戦の発走時刻が不明です")
    start=start_match.group(1).zfill(5)
    if not CLOCK.fullmatch(start):raise ValueError("オート優勝戦の時刻が不正です")
    tables=[t for t in soup.find_all("table")
            if "車番" in text_clean(t.get_text(" ",strip=True))[:400] and
               "選手名" in text_clean(t.get_text(" ",strip=True))[:400]]
    if not tables:raise ValueError("オート出走表に車番・選手名の項目がありません")
    riders=read_riders(tables[0],max_count=8)
    return {"sport":"auto","venue":venue,"grade":grade,"event":event,
            "raceName":text_clean(match.group()),"race":race,
            "startTime":start,"riders":riders,
            "sourceUrl":AUTO_RACE.format(day=selected.strftime("%Y%m%d"),
                                        venue=AUTO_CODES[venue],race=race)}


def collect(s,selected,sections,u,previous=None):
    """Fetch verified grade finals only. Stable order is start time then sport/venue."""
    keirin=[m for m in sections.get("keirin",{}).get("items",[])
            if m.get("grade") in KEIRIN_GRADES and m.get("day")=="最終日"]
    auto=[m for m in sections.get("auto",{}).get("items",[])
          if m.get("grade") in AUTO_GRADES and m.get("day")=="最終日"]
    found=[];errors=[]
    if keirin:
        try:
            html=u.fetch(s,HEX_DAILY.format(day=selected.strftime("%Y%m%d")))
            candidates=candidate_hex_finals(html,selected,keirin)
            for candidate in candidates:
                try:
                    detail=u.fetch(s,candidate["sourceUrl"])
                    found.append(parse_hex_final(detail,selected,candidate))
                except Exception as exc:
                    errors.append(f"競輪 {candidate['venue']} {candidate['race']}R: {exc}")
        except Exception as exc:errors.append(f"競輪日別一覧: {exc}")
    for meeting in auto:
        venue=meeting["name"]
        if venue not in AUTO_CODES:continue
        # Most graded championship races are race 12. Check other late races
        # ONLY when race 12 was not a verified final.
        for race in (12,11,10,9):
            uri=AUTO_RACE.format(day=selected.strftime("%Y%m%d"),venue=AUTO_CODES[venue],race=race)
            try:
                page=u.fetch(s,uri)
                final=parse_autorace_final(page,selected,venue,race,meeting["grade"])
                found.append(final)
                break
            except Exception as exc:
                if race==9:errors.append(f"オート {venue} 優勝戦未確認: {exc}")
    # Deduplicate one race across sources and ensure no identical seat numbers.
    results={}
    for item in found:
        key=(item["sport"],item["venue"],item["race"])
        results[key]=item
    ordered=sorted(results.values(),key=lambda x:(x["startTime"],x["sport"],x["venue"],x["race"]))
    # Same-day confirmed records can survive brief source outages, never
    # another date, another race, or a change in the known meeting's grade.
    if isinstance(previous,dict) and previous.get("date")==selected.isoformat():
        old=previous.get("finals",{})
        for race in old.get("items",[]) if isinstance(old,dict) else []:
            if not isinstance(race,dict):continue
            grade_set=keirin if race.get("sport")=="keirin" else auto
            current=next((m for m in grade_set if m["name"]==race.get("venue")
                          and m["grade"]==race.get("grade")),None)
            key=(race.get("sport"),race.get("venue"),race.get("race"))
            if current and key not in results and (
                5<=len(race.get("riders",[]))<=9 and
                CLOCK.fullmatch(str(race.get("startTime","")))):
                results[key]=race
        ordered=sorted(results.values(),key=lambda x:(x["startTime"],x["sport"],x["venue"],x["race"]))
    status="ok" if not errors else "partial"
    return {"status":status,"items":ordered,
            "verification":{"targetDate":selected.isoformat(),
                            "eligibleMeetings":len(keirin)+len(auto),
                            "confirmedRaces":len(ordered),"errors":errors}}
