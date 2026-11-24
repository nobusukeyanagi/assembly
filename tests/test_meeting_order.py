"""All three sports share session -> grade -> venue order."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import meeting_order
import update
from verified_sources import reconcile


def row(name,grade,slot,day='初日'):
    return {'name':name,'grade':grade,'timeType':slot,'day':day}


class SharedMeetingOrderTests(unittest.TestCase):
    def test_keirin_today_grade_first_and_north_to_south_ties(self):
        items=[
            row('松山','F1','ナイター'),
            row('西武園','F2','ナイター'),
            row('静岡','F1','デイ'),
            row('奈良','F2','デイ'),
            row('武雄','F2','モーニング'),
            row('広島','F2','モーニング'),
            row('玉野','F2','ミッドナイト'),
            row('川崎','F2','ミッドナイト'),
            row('四日市','F2','ミッドナイト'),
        ]
        result=meeting_order.sort_meetings(items,'keirin')
        self.assertEqual([r['name'] for r in result],[
            '広島','武雄','静岡','奈良','松山','西武園',
            '川崎','四日市','玉野'])
        # Input is not mutated or changed by repeated reconciliation.
        self.assertEqual(items[0]['name'],'松山')
        self.assertEqual(update.sort_by_time(items,update.KEIRIN_NAMES,'keirin'),result)

    def test_time_still_takes_priority_over_grade(self):
        items=[row('川崎','GP','ミッドナイト'),
               row('奈良','F2','デイ'),
               row('広島','F2','モーニング'),
               row('立川','G1','ナイター')]
        self.assertEqual([r['name'] for r in meeting_order.sort_meetings(items,'keirin')],
                         ['広島','奈良','立川','川崎'])

    def test_keirin_grade_order(self):
        names=['松山','武雄','川崎','広島','静岡','奈良']
        grades=['F2','F1','G3','G2','G1','GP']
        items=[row(n,g,'デイ') for n,g in zip(names,grades)]
        self.assertEqual([r['grade'] for r in meeting_order.sort_meetings(items,'keirin')],
                         ['GP','G1','G2','G3','F1','F2'])

    def test_autorace_day_and_night_with_kawaguchi_second_session(self):
        items=[
            row('川口２','普通','ナイター'),
            row('山陽','普通','ナイター'),
            row('川口','普通',None),
            row('伊勢崎','G2','デイ'),
            row('飯塚','SG','デイ'),
            row('浜松','G1','デイ'),
        ]
        self.assertEqual([r['name'] for r in meeting_order.sort_meetings(items,'auto')],
                         ['飯塚','浜松','伊勢崎','川口','川口２','山陽'])
        # Exactly the same grade and session: 川口 before 川口２.
        pair=[row('川口２','普通','ナイター'),row('川口','普通','ナイター')]
        self.assertEqual([r['name'] for r in meeting_order.sort_meetings(pair,'auto')],
                         ['川口','川口２'])

    def test_soda_all_grades_and_venue_tiebreak(self):
        items=[
            row('蒲郡','一般','ナイター'),
            row('戸田','G3',None),
            row('三国','G1','デイ'),
            row('びわこ','G3',None),
            row('多摩川','一般','デイ'),
            row('芦屋','PG1','モーニング'),
            row('桐生','SG','ミッドナイト'),
        ]
        self.assertEqual([r['name'] for r in meeting_order.sort_meetings(items,'soda')],
                         ['芦屋','三国','戸田','びわこ','多摩川','蒲郡','桐生'])

    def test_roman_grade_normalization_and_unknown_slots(self):
        rows=[row('静岡','FⅡ','デイ'),row('奈良','GⅠ','デイ'),
              row('函館','GP','確認中'),row('松阪','F1','デイ')]
        self.assertEqual([r['name'] for r in meeting_order.sort_meetings(rows,'keirin')],
                         ['奈良','松阪','静岡','函館'])
        self.assertEqual(meeting_order.canonical_grade('特GⅠ'),'特G1')

    def test_reconcile_all_sports_uses_same_rule(self):
        cases=[
            ('keirin',['西武園','松山'],[row('松山','F1','ナイター'),
                                      row('西武園','F2','ナイター')]),
            ('auto',['浜松','川口'],[row('川口','普通','デイ'),
                                   row('浜松','G1','デイ')]),
            ('soda',['びわこ','戸田'],[row('びわこ','一般',None),
                                    row('戸田','G3',None)]),
        ]
        for sport,want,items in cases:
            with self.subTest(sport=sport):
                output=reconcile(sport,[('official',items)],
                                 meeting_order.VENUES[sport],update.sort_by_time)
                self.assertEqual([r['name'] for r in output['items']],want)
                self.assertEqual(output['status'],'ok')
                self.assertEqual(len(output['items']),2)


if __name__=='__main__':
    unittest.main()
