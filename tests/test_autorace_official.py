import sys
import unittest
from datetime import date,datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from autorace_official import grade_meetings,kawaguchi_meetings,isesaki_meetings,iizuka_racecards,iizuka_home_meetings
from update import AUTO_NAMES,autorace_grade,day_label,period,race_time_type

UPSTREAM=SimpleNamespace(AUTO_NAMES=AUTO_NAMES,autorace_grade=autorace_grade,
                         day_label=day_label,period=period,race_time_type=race_time_type,
                         TZ=ZoneInfo('Asia/Tokyo'))

GRADE_PAGE=(
    '<html><title>2026年度 年間グレードレース日程 | AUTORACE.JP</title>'
    '<h1>2026年度 年間グレードレース日程</h1>'
    '<table><tr><th>グレード</th><th>レース名</th><th>レース場</th>'
    '<th>優勝者</th></tr>'
    '<tr><td>GII</td><td>オーバルチャンピオンカップ(ナイター)'
    '2026年10月8日(木)～2026年10月12日(月・祝)</td><td>飯塚</td></tr>'
    '<tr><td>GII</td><td>若獅子杯争奪戦'
    '2026年11月11日(水)～2026年11月15日(日)</td><td>山陽</td></tr>'
    '<tr><td>GII</td><td>ウィナーズカップ'
    '2026年11月19日(木)～2026年11月23日(月・祝)</td><td>浜松</td></tr>'
    '<tr><td>SG</td><td>スーパースターフェスタ'
    '2026年12月27日(日)～2026年12月31日(木)</td><td>川口</td></tr>'
    '<tr><td>GI</td><td>開場記念シルクカップ'
    '2027年1月7日(木)～2027年1月11日(月・祝)</td><td>伊勢崎</td></tr>'
    '</table></html>'
)

KAWAGUCHI_PAGE=(
    '<html><head><title>開催日程 | 川口オートレース</title></head>'
    '<body><h1>開催日程</h1>'
    '<h4>テレ玉presents 川口ナイトレース(無観客開催)</h4>'
    '<p>11/01(日) ～ 11/04(水)</p>'
    '<h4>第6回 埼玉高速鉄道杯</h4><p>11/07(土) ～ 11/10(火)</p>'
    '<h4>テレ玉presents 川口ナイトレース(無観客開催)</h4>'
    '<p>11/13(金) ～ 11/15(日)</p>'
    '<h4>ギャンブー杯GⅡウィナーズカップ</h4>'
    '<p>11/19(木) ～ 11/23(月)</p>'
    '</body></html>'
)


class OfficialAutoraceCalendars(unittest.TestCase):
    def test_grade_calendar_confirms_selected_day_and_g2(self):
        actual=grade_meetings(GRADE_PAGE,date(2026,11,13),UPSTREAM)
        self.assertEqual(actual,[{'name':'山陽','grade':'G2',
                                  'day':'3日目','timeType':None}])
        self.assertEqual(grade_meetings(GRADE_PAGE,date(2026,10,2),UPSTREAM),[])
        self.assertEqual(grade_meetings(GRADE_PAGE,date(2026,11,15),UPSTREAM),
                         [{'name':'山陽','grade':'G2','day':'最終日',
                           'timeType':None}])
        self.assertEqual(grade_meetings(GRADE_PAGE,date(2026,10,8),UPSTREAM),
                         [{'name':'飯塚','grade':'G2','day':'初日',
                           'timeType':'ナイター'}])

    def test_fiscal_year_and_calendar_year_are_verified(self):
        self.assertEqual(grade_meetings(GRADE_PAGE,date(2027,1,10),UPSTREAM),
                         [{'name':'伊勢崎','grade':'G1','day':'4日目',
                           'timeType':None}])
        with self.assertRaises(ValueError):
            grade_meetings(GRADE_PAGE,date(2025,11,13),UPSTREAM)
        with self.assertRaises(ValueError):
            grade_meetings(GRADE_PAGE.replace('2026年度','2025年度'),
                           date(2026,11,13),UPSTREAM)

    def test_kawaguchi_official_dates_and_night_class(self):
        selected=date(2026,11,13)
        with patch('autorace_official.datetime') as clock:
            clock.now.return_value=datetime(2026,11,13,16,0,tzinfo=UPSTREAM.TZ)
            self.assertEqual(kawaguchi_meetings(KAWAGUCHI_PAGE,selected,UPSTREAM),
                             [{'name':'川口','grade':'普通','day':'初日',
                               'timeType':'ナイター'}])
            self.assertEqual(kawaguchi_meetings(KAWAGUCHI_PAGE,
                             date(2026,11,15),UPSTREAM),
                             [{'name':'川口','grade':'普通','day':'最終日',
                               'timeType':'ナイター'}])
            self.assertEqual(kawaguchi_meetings(KAWAGUCHI_PAGE,
                             date(2026,11,10),UPSTREAM),
                             [{'name':'川口','grade':'普通','day':'最終日',
                               'timeType':None}])
            self.assertEqual(kawaguchi_meetings(KAWAGUCHI_PAGE,
                             date(2026,9,1),UPSTREAM),[])
            self.assertEqual(kawaguchi_meetings(KAWAGUCHI_PAGE,
                             date(2026,6,1),UPSTREAM),[])

    def test_conflicting_organizer_meeting_is_not_silently_selected(self):
        duplicated=KAWAGUCHI_PAGE.replace('</body>','<h4>SG他開催</h4>'
            '<p>11/13(金) ～ 11/15(日)</p></body>')
        with patch('autorace_official.datetime') as clock:
            clock.now.return_value=datetime(2026,11,13,16,0,tzinfo=UPSTREAM.TZ)
            with self.assertRaisesRegex(ValueError,'重複'):
                kawaguchi_meetings(duplicated,date(2026,11,13),UPSTREAM)


    def test_isesaki_true_home_race_not_other_tracks_broadcast(self):
        page=('<html><head><title>レース情報 | 伊勢崎オートレース</title></head>'
              '<body><h1>開催情報</h1><div>2026年 11月</div>'
              '<p>場外 普通レース 飯塚 オッズパーク杯 11/16～11/18 10:25～16:55</p>'
              '<p>本場 普通レース（無観客開催） 伊勢崎 '
              'オッズPARKでチケチャレ杯伊勢崎オートアフター５ナイター '
              '11/16～11/18 17:35～21:10</p>'
              '<p>場外 GII 浜松 ウィナーズカップ 11/19～11/23</p>'
              '</body></html>')
        expected={'name':'伊勢崎','grade':'普通','day':'初日',
                  'timeType':'ナイター'}
        self.assertEqual(isesaki_meetings(page,date(2026,11,16),UPSTREAM),[expected])
        self.assertEqual(isesaki_meetings(page,date(2026,11,17),UPSTREAM),
                         [dict(expected,day='2日目')])
        self.assertEqual(isesaki_meetings(page,date(2026,11,18),UPSTREAM),
                         [dict(expected,day='最終日')])
        self.assertEqual(isesaki_meetings(page,date(2026,11,15),UPSTREAM),[])
        self.assertEqual(isesaki_meetings(page,date(2026,11,19),UPSTREAM),[])
        self.assertEqual(isesaki_meetings(page,date(2025,11,16),UPSTREAM),[])
        self.assertEqual(isesaki_meetings(page.replace('本場 普通','場外 普通'),
                                          date(2026,11,16),UPSTREAM),[])
        self.assertEqual(isesaki_meetings(page.replace('伊勢崎オートアフター５ナイター',
                         '伊勢崎オート普通開催').replace('オッズPARKでチケチャレ杯伊勢崎',
                         'オッズPARKでチケチャレ杯伊勢崎'),date(2026,11,16),UPSTREAM),
                         [dict(expected,timeType=None)])

    def test_iizuka_organizer_dated_download_not_offsite_schedule(self):
        page=('<html><head><title>飯塚オートレース場</title></head><body>'
              '<h1>出走表サービス</h1>'
              '<h2>出走表のダウンロードサービスについて</h2>'
              '<div>2026年11月16日～11月18日 '
              'オッズパーク杯（飯塚本場開催）</div>'
              '<div>1日目出走表（表面・裏面）</div></body></html>')
        expected={'name':'飯塚','grade':'普通','day':'初日','timeType':None}
        self.assertEqual(iizuka_racecards(page,date(2026,11,16),UPSTREAM),[expected])
        self.assertEqual(iizuka_racecards(page,date(2026,11,18),UPSTREAM),
                         [dict(expected,day='最終日')])
        self.assertEqual(iizuka_racecards(page,date(2026,11,15),UPSTREAM),[])
        self.assertEqual(iizuka_racecards(page,date(2027,11,16),UPSTREAM),[])
        self.assertEqual(iizuka_racecards(
            page.replace('飯塚本場開催','飯塚場外開催'),date(2026,11,16),UPSTREAM),[])

    def test_iizuka_home_only_verifies_the_current_calendar_date(self):
        page=('<html><head><title>飯塚オートレース場</title></head>'
              '<body>RACE INFORMATION 本日の開催 '
              '飯塚本場開催 オッズパーク杯 '
              '26/11/16(月) - 26/11/18(水) SCHEDULE</body></html>')
        with patch('autorace_official.datetime') as clock:
            clock.now.return_value=datetime(2026,11,16,9,0,tzinfo=UPSTREAM.TZ)
            self.assertEqual(iizuka_home_meetings(page,date(2026,11,16),UPSTREAM),
                             [{'name':'飯塚','grade':'普通',
                               'day':'初日','timeType':None}])
            self.assertEqual(iizuka_home_meetings(page,date(2026,11,17),UPSTREAM),[])
            self.assertEqual(iizuka_home_meetings(
                page.replace('飯塚本場開催','飯塚場外開催'),
                date(2026,11,16),UPSTREAM),[])


if __name__=='__main__':unittest.main()
