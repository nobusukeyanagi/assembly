"""Regression tests for verified historical 川口／川口２ meetings."""
import sys
import unittest
from datetime import date,datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import autorace_verified_calendar
import autorace_official
import update
from verified_sources import auto as collect_auto, reconcile
from autorace_sessions import normalize_sources


class VerifiedKawaguchiHistory(unittest.TestCase):
    def test_february_fourth_through_sixth_are_two_separate_meetings(self):
        for day,expected_day in ((4,'初日'),(5,'2日目'),(6,'最終日')):
            with self.subTest(day=day):
                rows=autorace_verified_calendar.kawaguchi_meetings(
                    date(2026,2,day),update)
                self.assertEqual([r['name'] for r in rows],['川口','川口２'])
                self.assertEqual([r['day'] for r in rows],[expected_day,expected_day])
                self.assertEqual([r['timeType'] for r in rows],['デイ','ナイター'])
                self.assertEqual([r['meetingStart'] for r in rows],['2026-02-04']*2)

    def test_only_verified_days_have_double_session_evidence(self):
        for day in (date(2026,2,3),date(2026,2,7),
                    date(2025,2,6),date(2027,2,6),
                    date(2026,11,16)):
            with self.subTest(day=day):
                self.assertEqual(
                    autorace_verified_calendar.kawaguchi_meetings(day,update),[])

    def test_both_survive_total_remote_blackout(self):
        def blocked(*_args,**_kwargs):
            raise RuntimeError('403')
        with patch.object(update,'fetch',side_effect=blocked):
            result=collect_auto(object(),date(2026,2,6),None,update)
        self.assertEqual(result['status'],'ok')
        self.assertEqual([r['name'] for r in result['items']],['川口','川口２'])
        self.assertEqual([r['day'] for r in result['items']],['最終日','最終日'])
        self.assertEqual([r['timeType'] for r in result['items']],['デイ','ナイター'])
        self.assertEqual(result['verification']['officialVerifiedVenues'],
                         ['川口','川口２'])
        self.assertTrue(result['verification']['errors'])

    def test_live_official_double_meetings_survive_winticket_403(self):
        # A dynamic current-date fixture also protects the normal (non-archive)
        # path after the test date used in 2026 has moved out of the window.
        selected=datetime.now(update.TZ).date()
        d=f'{selected.month:02}/{selected.day:02}'
        html=('<html><head><title>開催日程 | 川口オートレース</title>'
              '</head><body><h1>開催日程</h1>'
              '<h4>普通開催 川口自場</h4><p>'+d+'(月) ～ '+d+'(月)</p>'
              '<h4>川口ナイトレース</h4><p>'+d+'(月) ～ '+d+'(月)</p>'
              '</body></html>')
        def fetch(_session,url,params=None):
            if url==autorace_official.KAWAGUCHI_CALENDAR:
                return html
            raise RuntimeError('403 unavailable: '+url)
        with patch.object(update,'fetch',side_effect=fetch):
            result=collect_auto(object(),selected,None,update)
        self.assertEqual(result['status'],'ok')
        self.assertEqual([r['name'] for r in result['items']],['川口','川口２'])
        self.assertEqual(result['items'][1]['timeType'],'ナイター')
        self.assertEqual(result['verification']['organizerConfirmed']
                         ['川口オート公式日程'],['川口','川口２'])

    def test_single_generic_provider_cannot_erase_the_second_meeting(self):
        verified=autorace_verified_calendar.kawaguchi_meetings(
            date(2026,2,6),update)
        mixed=[(autorace_verified_calendar.SOURCE,verified),
               ('generic', [{'name':'川口','grade':'普通','day':'最終日',
                             'timeType':None}])]
        prepared,issues=normalize_sources(mixed)
        out=reconcile('auto',prepared,['川口','川口２'],update.sort_by_time)
        self.assertEqual([r['name'] for r in out['items']],['川口','川口２'])
        self.assertEqual(len(issues),1)
        self.assertEqual(out['items'][1]['timeType'],'ナイター')


if __name__=='__main__':
    unittest.main()
