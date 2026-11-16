import calendar
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import autorace_local
import update


def grid(year, month, venue='山陽', event='山陽ミッドナイト', place='本場開催'):
    days=calendar.monthrange(year, month)[1]
    numbers=''.join('<th>'+str(i)+'</th>' for i in range(1, days+1))
    # Meeting on the 19th through the 21st, as in November 2026.
    rows=('<tr><th>'+place+'</th><td colspan="18"></td>'
          '<td colspan="3">'+event+'<img alt="普通"/><img alt="MN"/></td>'
          '<td colspan="'+str(days-21)+'"></td></tr>')
    return ('<html><head><title>'+venue+'オート 開催日程</title></head><body>'
            '<h2>'+str(year)+'年'+str(month)+'月</h2><table>'
            '<tr><th>日程</th>'+numbers+'</tr>'+rows+'</table></body></html>')


class OfficialHostCalendarTests(unittest.TestCase):
    def test_sanyo_midnight_is_two_days_into_verified_meeting(self):
        rows=autorace_local.month_grid_meetings(
            grid(2026,11),date(2026,11,20),'山陽',update)
        self.assertEqual(rows,[{'name':'山陽','grade':'普通',
                               'day':'2日目','timeType':'ミッドナイト'}])

    def test_do_not_use_another_year_or_month(self):
        for d in (date(2025,11,20),date(2026,12,20)):
            with self.subTest(date=d):
                self.assertEqual(autorace_local.month_grid_meetings(
                    grid(2026,11),d,'山陽',update),[])

    def test_ignore_off_site_betting(self):
        self.assertEqual(autorace_local.month_grid_meetings(
            grid(2026,11,place='場外発売'),date(2026,11,20),
            '山陽',update),[])

    def test_hamamatsu_grade_and_day(self):
        html=grid(2026,11,'浜松','GⅡウィナーズカップ デイ')
        self.assertEqual(autorace_local.month_grid_meetings(
            html,date(2026,11,20),'浜松',update),
            [{'name':'浜松','grade':'G2','day':'2日目','timeType':'ミッドナイト'}])

    def test_homepage_date_matched_not_today_label(self):
        today=datetime.now(update.TZ).date()
        html=('<html><head><title>山陽オート公式サイト</title></head>'
              '<body>本日のレース '+str(today.month)+'月'+str(today.day)+'日 '
              '本場開催 普通開催 山陽ミッドナイト 場外開催 飯塚</body></html>')
        actual=autorace_local.homepage_meetings(html,today,'山陽',update)
        self.assertEqual(actual,[{'name':'山陽','grade':'普通',
                                  'day':None,'timeType':'ミッドナイト'}])
        self.assertEqual(autorace_local.homepage_meetings(
            html,today-timedelta(days=10),'山陽',update),[])

    def test_homepage_no_local_race_is_not_evidence(self):
        today=datetime.now(update.TZ).date()
        html=('<title>浜松オート公式</title>今日のレース '
              +str(today.month)+'月'+str(today.day)+
              '日 本場開催 開催レースはありません 場外開催 山陽')
        self.assertEqual(autorace_local.homepage_meetings(
            html,today,'浜松',update),[])


if __name__=='__main__':
    unittest.main()
