import re
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from finals import (
    candidate_hex_finals,parse_hex_final,parse_autorace_final,collect,
    AUTO_RACE,HEX_DAILY,read_riders,parse_autorace_race,
    parse_soda_final,parse_soda_start,BOAT_FINAL,BOAT_START
)
from bs4 import BeautifulSoup

DAY=date(2026,11,3)


def hex_list():
    return (
        '<h1>2026年11月3日（火）の競輪 86レース</h1>'
        '<h2>デイ</h2>'
        '<h3>G3防府競輪4日目</h3>'
        '<p>周防国府杯争奪戦</p>'
        '<a href="/cups/2026103163/">周防国府杯争奪戦の開催ページ</a>'
        '<a href="/races/20261103/126320261103/">12R 16:26 S級 決勝</a>'
        '<a href="/races/20261103/116320261103/">11R 15:50 S級 特秀</a>'
        '<h3>F2富山競輪3日目</h3>'
        '<a href="/races/20261103/114620261103/">11R 16:00 A級 決勝</a>'
    )


def hex_detail():
    riders="".join(
        f"<tr><td>{n}</td><td>{name}山口・S1・99期</td><td>100.00</td></tr>"
        for n,name in enumerate(("佐藤一郎","田中二郎","山本三郎","鈴木四郎",
                                 "高橋五郎","山田六郎","渡辺七郎","吉田八郎","小林九郎"),1))
    return ('<h1>防府競輪 12R 2026年11月3日（火）</h1>'
            '<section>級 S級 種別 決勝 発走 16:26</section>'
            '<h2>出走表</h2><table><tr><th>車</th><th>選手</th></tr>'+riders+'</table>')


def auto_detail(race=12,kind="優勝戦（枠番選択）"):
    riders="".join(
        f'<tr><td>{n} <a href="https://autorace.jp/race_info/Profile/'
        f'3{n:03d}">{name}</a> 浜松 / 32期</td><td>0</td></tr>'
        for n,name in enumerate(("佐藤　励","青山　周平","丹村　飛竜","荒尾　聡",
                                 "金子　大輔","鈴木　圭一郎","永井　大介","中村　雅人"),1))
    return (
        f'<title>2026年11月03日 浜松オート {race}R 出走表 | 東スポオートレース</title>'
        '<h1>ＳＧ日本選手権オートレース</h1>'
        f'<p>{kind}</p><p>発走：16:10 投票締切：16:08</p>'
        '<h2>出走表</h2><table><thead><tr><th>車番</th><th>選手名</th>'
        '</tr></thead><tbody>'+riders+'</tbody></table>'
    )


class GradeFinalTests(unittest.TestCase):
    def test_keirin_candidates_only_main_graded_final(self):
        schedule=[{"name":"防府","grade":"G3","day":"最終日"},
                  {"name":"富山","grade":"F2","day":"最終日"}]
        candidates=candidate_hex_finals(hex_list(),DAY,schedule)
        self.assertEqual(len(candidates),1)
        c=candidates[0]
        self.assertEqual((c["venue"],c["race"],c["event"]),("防府",12,"周防国府杯争奪戦"))
        self.assertEqual(c["startTime"],"16:26")
        self.assertEqual(c["raceName"],"S級 決勝")
        self.assertEqual(candidate_hex_finals(hex_list(),DAY,[
            {"name":"防府","grade":"G3","day":"3日目"}]),[])
        with self.assertRaisesRegex(ValueError,"日付"):
            candidate_hex_finals(hex_list(),date(2026,11,4),schedule)

    def test_keirin_final_exact_card_and_nine_names(self):
        candidate=candidate_hex_finals(hex_list(),DAY,[
            {"name":"防府","grade":"G3","day":"最終日"}])[0]
        output=parse_hex_final(hex_detail(),DAY,candidate)
        self.assertEqual(len(output["riders"]),9)
        self.assertEqual(output["riders"][0],{"number":1,"name":"佐藤一郎"})
        self.assertEqual(output["riders"][-1],{"number":9,"name":"小林九郎"})
        with self.assertRaisesRegex(ValueError,"不一致"):
            parse_hex_final(hex_detail(),date(2026,11,4),candidate)
        with self.assertRaisesRegex(ValueError,"決勝"):
            parse_hex_final(hex_detail().replace("種別 決勝","種別 準決勝"),DAY,candidate)

    def test_auto_final_exact_title_and_eight_riders(self):
        item=parse_autorace_final(auto_detail(),DAY,"浜松",12,"SG")
        self.assertEqual((item["event"],item["raceName"],item["startTime"]),
                         ("SG日本選手権オートレース","優勝戦","16:10"))
        self.assertEqual(len(item["riders"]),8)
        self.assertEqual(item["riders"][0],{"number":1,"name":"佐藤 励"})
        self.assertEqual(item["riders"][7],{"number":8,"name":"中村 雅人"})
        for d,v,r in ((date(2026,11,2),"浜松",12),(DAY,"川口",12),(DAY,"浜松",11)):
            with self.assertRaisesRegex(ValueError,"不一致"):
                parse_autorace_final(auto_detail(),d,v,r,"SG")
        with self.assertRaisesRegex(ValueError,"優勝戦"):
            parse_autorace_final(auto_detail(kind="最終予選"),DAY,"浜松",12,"SG")

    def test_union_and_start_time_order(self):
        url=HEX_DAILY.format(day="20261103")
        detail="https://keirinhex.jp/races/20261103/126320261103/"
        auto=AUTO_RACE.format(day="20261103",venue="04",race=12)
        docs={url:hex_list(),detail:hex_detail(),auto:auto_detail()}
        def fetch(_,uri):
            if uri not in docs:raise RuntimeError("not available")
            return docs[uri]
        sections={"keirin":{"items":[{"name":"防府","grade":"G3","day":"最終日"}]},
                  "auto":{"items":[{"name":"浜松","grade":"SG","day":"最終日"}]}}
        u=SimpleNamespace(fetch=fetch)
        result=collect(object(),DAY,sections,u)
        self.assertEqual(len(result["items"]),2)
        self.assertEqual([item["sport"] for item in result["items"]],["keirin","auto"])
        self.assertEqual([item["startTime"] for item in result["items"]],["16:26","16:10"])
        self.assertEqual(result["verification"]["confirmedRaces"],2)

    def test_no_graded_final_and_safe_same_day_reuse(self):
        sections={"keirin":{"items":[{"name":"防府","grade":"G3","day":"2日目"}]},
                  "auto":{"items":[{"name":"浜松","grade":"SG","day":"4日目"}]}}
        u=SimpleNamespace(fetch=lambda *_: (_ for _ in ()).throw(AssertionError("should not fetch")))
        result=collect(object(),DAY,sections,u)
        self.assertEqual(result["items"],[])
        previous={"date":"2026-11-03","finals":{"items":[
            dict(sport="auto",venue="浜松",grade="SG",race=12,startTime="16:10",
                 event="SG日本選手権",raceName="優勝戦",
                 riders=[{"number":i,"name":"選手"} for i in range(1,9)])]}}
        # Do not reuse graded finals if the current meeting has not reached final day.
        self.assertEqual(collect(object(),DAY,sections,u,previous)["items"],[])
        self.assertEqual(collect(object(),date(2026,11,4),sections,u,previous)["items"],[])


    def test_scratched_keirin_and_autorace_riders(self):
        table=BeautifulSoup(
            '<table><tr><td>1</td><td>佐藤太郎</td><td>欠場</td></tr>'
            '<tr><td>2</td><td><s>田中二郎</s></td></tr>'
            '<tr><td>3</td><td>山本三郎</td></tr>'
            '<tr><td>4</td><td>鈴木四郎</td></tr>'
            '<tr><td>5</td><td>高橋五郎</td></tr></table>',"html.parser").table
        riders=read_riders(table)
        self.assertEqual(riders[0]["status"],"scratched")
        self.assertEqual(riders[1]["status"],"scratched")
        self.assertNotIn("status",riders[2])
        appended=BeautifulSoup(
            '<table><tr><td>1</td><td>佐藤太郎 欠場</td></tr>'
            '<tr><td>2</td><td>田中二郎</td></tr>'
            '<tr><td>3</td><td>山本三郎</td></tr>'
            '<tr><td>4</td><td>鈴木四郎</td></tr>'
            '<tr><td>5</td><td>高橋五郎</td></tr></table>',"html.parser").table
        cleaned=read_riders(appended)
        self.assertEqual(cleaned[0],{"number":1,"name":"佐藤太郎","status":"scratched"})

    def test_mori_racecard_appended_after_final_and_deduped(self):
        url=HEX_DAILY.format(day="20261103")
        detail="https://keirinhex.jp/races/20261103/126320261103/"
        final_uri=AUTO_RACE.format(day="20261103",venue="04",race=12)
        mori_uri=AUTO_RACE.format(day="20261103",venue="04",race=11)
        mori_html=auto_detail(11,"一般戦").replace(
            "中村　雅人","森　且行")
        docs={url:hex_list(),detail:hex_detail(),
              final_uri:auto_detail(),mori_uri:mori_html}
        def fetch(_,uri):
            if uri not in docs:raise RuntimeError("missing fixture")
            return docs[uri]
        sections={"keirin":{"items":[{"name":"防府","grade":"G3","day":"最終日"}]},
                  "auto":{"items":[{"name":"浜松","grade":"SG","day":"最終日"}]},
                  "mori":{"item":{"name":"浜松","date":DAY.isoformat(),"type":"today",
                                  "grade":"SG","races":[11]}}}
        out=collect(object(),DAY,sections,SimpleNamespace(fetch=fetch))
        self.assertEqual([(x["venue"],x["race"]) for x in out["items"]],
                         [("防府",12),("浜松",12),("浜松",11)])
        self.assertEqual(out["items"][-1]["feature"],"mori")
        self.assertEqual(out["verification"]["moriRaces"],1)
        # Mori in the same race as a featured final must not create a duplicate.
        sections["mori"]["item"]["races"]=[12]
        same=collect(object(),DAY,sections,SimpleNamespace(fetch=fetch))
        self.assertEqual(len(same["items"]),2)
        # Exclude a race if Mori is not actually listed in that racecard.
        with self.assertRaisesRegex(ValueError,"森且行"):
            parse_autorace_race(auto_detail(11,"一般戦"),DAY,"浜松",11,"SG",
                                require_final=False,require_mori=True)

    def test_soda_official_final_and_start_time_source(self):
        racers="".join(
            f'<tr><td><a href="/owpc/pc/data/racersearch/profile?toban={1000+i}">'
            f'選手{i}</a></td></tr>' for i in range(6))
        racers="".join(
            f'<tr><td><a href="/owpc/pc/data/racersearch/profile?toban={1000+i}">'
            f'佐藤 太郎</a></td></tr>' for i in range(6))
        clocks="".join(f"<td>15:{i+10:02d}</td>" for i in range(12))
        official=(
            '<img alt="宮島" src="venue.png">'
            '<h2>宮島オータムカップ</h2>'
            '<nav><span>11月12日最終日</span></nav>'
            f'<table><tr><th>締切予定時刻</th>{clocks}</tr></table>'
            '<h3>優勝戦 1800m</h3>'
            '<table>'+racers+'</table>')
        data=parse_soda_final(official,date(2026,11,12),"宮島","一般")
        self.assertEqual(data["sport"],"soda")
        self.assertEqual(data["officialClosingTime"],"15:21")
        self.assertEqual(len(data["riders"]),6)
        self.assertIsNone(data["startTime"])
        self.assertEqual(parse_soda_start(
            "<h1>宮島 12R</h1><p>11月12日 / 宮島オータムカップ / 15:25 発走</p>",
            date(2026,11,12),"宮島","15:21"),"15:25")
        with self.assertRaisesRegex(ValueError,"同一"):
            parse_soda_start(
                "<h1>宮島 12R</h1><p>11月12日 / イベント / 15:21 発走</p>",
                date(2026,11,12),"宮島","15:21")

    def test_mori_race_types(self):
        html=auto_detail(11,"準優勝戦").replace("中村　雅人","森　且行")
        race=parse_autorace_race(html,DAY,"浜松",11,"SG",
                                 require_final=False,require_mori=True)
        self.assertEqual(race["raceName"],"準優勝戦")
        html2=auto_detail(11,"予選").replace("中村　雅人","森　且行")
        race2=parse_autorace_race(html2,DAY,"浜松",11,"SG",
                                  require_final=False,require_mori=True)
        self.assertEqual(race2["raceName"],"予選")

    def test_reject_unverified_riders(self):
        table=BeautifulSoup("<table><tr><td>1</td><td>佐藤太郎東京・S1</td></tr></table>","html.parser").table
        with self.assertRaises(ValueError):
            read_riders(table)


if __name__=="__main__":
    unittest.main()
