import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from autorace_sessions import split_kawaguchi,normalize_sources
from update import parse_auto_calendar,sort_by_time
from verified_sources import reconcile


def monthly(*,double=True,duplicate=False):
    html='<h2>2026年11月 開催日程</h2>'
    for n in ('川口','伊勢崎','浜松','飯塚','山陽'):
        html+=f'<h3>{n} オートレース</h3>'
        if n=='川口':
            html+='<a>11月20日 〜 11月22日川口普通開催</a>'
            if double:
                html+=('<a>11月20日 〜 11月22日'
                       +(('川口普通開催' if duplicate else '川口ナイトレース')+'</a>'))
        else:
            html+='<a>11月5日 〜 11月7日普通開催</a>'
            html+='<a>11月15日 〜 11月17日普通開催</a>'
    return html


class KawaguchiDoubleMeetTests(unittest.TestCase):
    def test_monthly_calendar_creates_two_distinct_rows(self):
        rows=parse_auto_calendar(monthly(),date(2026,11,20))
        self.assertEqual([x['name'] for x in rows],['川口','川口２'])
        self.assertEqual([x['timeType'] for x in rows],[None,'ナイター'])
        self.assertEqual([x['day'] for x in rows],['初日','初日'])
        self.assertEqual(rows[0]['meetingStart'],rows[1]['meetingStart'])
        self.assertEqual(rows[0]['meetingEnd'],rows[1]['meetingEnd'])
        # The second label is reserved for two distinct confirmed sessions.
        self.assertEqual([r['name'] for r in parse_auto_calendar(
            monthly(double=False),date(2026,11,20))],['川口'])
        with self.assertRaisesRegex(ValueError,'重複'):
            parse_auto_calendar(monthly(duplicate=True),date(2026,11,20))

    def test_one_night_meeting_remains_kawaguchi_not_kawaguchi_two(self):
        rows=split_kawaguchi([{'name':'川口','grade':'普通',
                              'day':'初日','timeType':'ナイター'}])
        self.assertEqual(rows[0]['name'],'川口')
        self.assertEqual(split_kawaguchi([]),[])

    def test_reconcile_sources_by_session_and_preserve_both(self):
        source=[{'name':'川口','grade':'普通','day':'初日',
                 'timeType':None},
                {'name':'川口','grade':'普通','day':'初日',
                 'timeType':'ナイター'}]
        official=[{'name':'川口','grade':'普通','day':'初日',
                   'timeType':'ナイター'}]
        ambiguous=[{'name':'川口','grade':'普通','day':'初日'}]
        all_sources=[('WINTICKET指定月',source),
                     ('川口オート公式日程',official),
                     ('AUTORACE.JP出走表',ambiguous)]
        normalized,ignored=normalize_sources(all_sources)
        self.assertEqual(normalized[0][1][1]['name'],'川口２')
        self.assertEqual(normalized[1][1][0]['name'],'川口２')
        self.assertEqual(normalized[2][1],[])
        self.assertEqual(len(ignored),1)
        out=reconcile('auto',normalized,['川口','川口２'],sort_by_time)
        self.assertEqual([r['name'] for r in out['items']],['川口','川口２'])
        self.assertEqual(out['verification']['providers'],{
            'WINTICKET指定月':2,'川口オート公式日程':1,
            'AUTORACE.JP出走表':0})
        self.assertEqual(out['items'][1]['confirmedBy'],
                         ['WINTICKET指定月','川口オート公式日程'])
        self.assertEqual(out['verification']['gradeCrossConfirmed'],1)
        self.assertIsNone(out['items'][0]['timeType'])
        self.assertEqual(out['items'][1]['timeType'],'ナイター')

    def test_sole_source_with_day_night_rows_not_mistaken_for_two_sites(self):
        sources=[('川口オート公式日程',[
            {'name':'川口','grade':'普通','day':'2日目','timeType':None},
            {'name':'川口','grade':'普通','day':'初日','timeType':'ナイター'}])]
        normalized,ignored=normalize_sources(sources)
        self.assertFalse(ignored)
        result=reconcile('auto',normalized,['川口','川口２'],sort_by_time)
        self.assertEqual(len(result['items']),2)
        self.assertEqual(result['verification']['crossConfirmed'],0)
        self.assertEqual(result['items'][0]['day'],'2日目')
        self.assertEqual(result['items'][1]['day'],'初日')


if __name__=='__main__':
    unittest.main()
