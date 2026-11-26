"""Mori's same-day entrant evidence must survive three profile HTTP 403s."""
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mori_racecards
import update
import verified_sources


def prediction_page(day=date(2026,11,24),venue='川口',mori=True,
                    race=6,extra_races=()):
    venue_label=venue+'オート予想'
    tables=[]
    for n in sorted({1,2,3,4,5,6,7,8}|set(extra_races)):
        who=('森　　且行' if mori and (n==race or n in extra_races)
             else '森谷　隼人')
        tables.append(
            '<table><thead><tr><th>レース</th><th>予想</th><th>車番</th>'
            '<th>選手名</th><th>ハンデ</th></tr></thead><tbody>'
            '<tr><td rowspan="2">'+str(n)+'R</td><td></td><td>1</td>'
            '<td>山田　徹</td><td>0</td></tr>'
            '<tr><td></td><td>6</td><td>'+who+'</td><td>20</td></tr>'
            '</tbody></table>')
    return (
        '<html><head><title>川口オートレース 予想</title></head><body>'
        '<h1>レース予想</h1><h1>'+venue_label+'</h1>'
        '<p>'+str(day.year)+'年'+str(day.month)+'月'+str(day.day)+'日 '
        +venue+'オートレース</p>'
        +''.join(tables)+'</body></html>')


def night_page(day=date(2026,11,24),times=None):
    times=times or {i:'20:55' if i==6 else '19:15'
                     for i in range(1,9)}
    rows=''.join('<tr><td>'+str(i)+'R</td><td>20:34</td>'
                 '<td>20:53</td><td>'+times[i]+'</td></tr>'
                 for i in range(1,9))
    return ('<html><head><title>川口ナイトレース 特設サイト</title></head>'
            '<body><h2>開催日程</h2>'
            '<div>テレ玉・WINTICKET presents 川口ナイトレース</div>'
            '<div>2026 11/22 SUN ▶ 25 WED</div>'
            '<table><tr><th>レース</th><th>試走開始</th>'
            '<th>発売締切</th><th>発走予定</th></tr>'
            +rows+'</table></body></html>')


class MoriDatedRaces(unittest.TestCase):
    def test_realistic_sixth_race(self):
        expected=[6]
        self.assertEqual(mori_racecards.predictions(
            prediction_page(),date(2026,11,24),'川口'),expected)

    def test_multi_race_recognized_independently(self):
        out=mori_racecards.predictions(prediction_page(extra_races=(8,)),
                                       date(2026,11,24),'川口')
        self.assertEqual(out,[6,8])

    def test_other_riders_do_not_match(self):
        self.assertEqual(mori_racecards.predictions(
            prediction_page(mori=False),date(2026,11,24),'川口'),[])

    def test_wrong_venue_date_or_missing_table_rejected(self):
        html=prediction_page()
        for d,venue in [(date(2026,11,23),'川口'),
                        (date(2027,11,24),'川口'),
                        (date(2026,11,24),'伊勢崎')]:
            with self.subTest(date=d,venue=venue):
                with self.assertRaises(ValueError):
                    mori_racecards.predictions(html,d,venue)
        with self.assertRaises(ValueError):
            mori_racecards.predictions(
                html.replace('選手名','レース予想'),date(2026,11,24),'川口')

    def test_official_night_start_distinguishes_cutoff(self):
        found=mori_racecards.kawaguchi_night_starts(
            night_page(),date(2026,11,24),[6])
        self.assertEqual(found,{6:'20:55'})
        for bad_day in [date(2025,11,24),date(2026,11,26),
                        date(2026,12,24)]:
            with self.subTest(day=bad_day),self.assertRaises(ValueError):
                mori_racecards.kawaguchi_night_starts(
                    night_page(),bad_day,[6])
        with self.assertRaises(ValueError):
            mori_racecards.kawaguchi_night_starts(
                night_page().replace('発走予定','発売予定'),
                date(2026,11,24),[6])

    def test_full_collection_with_three_403_profiles(self):
        target=date(2026,11,24)
        pages={
            mori_racecards.PREDICTIONS.format(venue='002',
                                            day='2026-11-24'):prediction_page(),
            mori_racecards.KAWAGUCHI_NIGHT:night_page()
        }
        def fetch(_session,url,params=None):
            if url in pages:
                return pages[url]
            raise RuntimeError('HTTP 403 unavailable: '+url)
        sections={
            'auto':{'status':'ok','items':[
                {'name':'川口','grade':'普通','day':'3日目',
                 'timeType':'ナイター'},
                {'name':'飯塚','grade':'普通','day':'初日'}]},
        }
        with tempfile.TemporaryDirectory() as temporary,patch.object(
                update,'ROOT',Path(temporary)),patch.object(
                update,'fetch',side_effect=fetch),patch.object(
                verified_sources,'keirin',return_value={'status':'ok','items':[]}),patch.object(
                verified_sources,'auto',return_value=sections['auto']),patch.object(
                verified_sources,'soda',return_value={'status':'ok','items':[]}),patch.object(
                update,'datetime') as clock,patch.object(
                update.finals,'collect',return_value={'items':[]}):
            clock.now.return_value=datetime(2026,11,24,11,11,tzinfo=update.TZ)
            out=update.collect(target,object())
        entry=out['sections']['mori']
        self.assertEqual(entry['status'],'ok')
        self.assertEqual(entry['item']['name'],'川口')
        self.assertEqual(entry['item']['date'],'2026-11-24')
        self.assertEqual(entry['item']['races'],[6])
        self.assertEqual(entry['item']['grade'],'普通')
        self.assertEqual(entry['item']['timeType'],'ナイター')
        self.assertEqual(entry['item']['startTimes'],{'6':'20:55'})

    def test_future_official_featured_entrant_cross_month(self):
        html=('<title>川口ナイトレース 特設サイト</title>'
              '<h2>開催日程</h2><div>2026</div><div>11/30 MON ▶ 12/3 THU</div>'
              '<h2>注目選手</h2><ul><li><a><img alt="森 且行選手"></a></li></ul>'
              '<h2>今後の開催日程</h2><p>12/10 ▶ 12/12</p>')
        day=date(2026,11,26)
        expected=mori_racecards.kawaguchi_night_assignment(html,day)
        self.assertEqual(expected[0]['date'],'2026-11-30')
        self.assertEqual(expected[0]['meetingEnd'],'2026-12-03')
        self.assertEqual(expected[0]['type'],'next')
        self.assertEqual(mori_racecards.kawaguchi_night_assignment(html,date(2026,11,30)),[])
        self.assertEqual(mori_racecards.kawaguchi_night_assignment(
            html.replace('森 且行選手','森谷 隼人選手')+'森 且行選手',day),[])
        with tempfile.TemporaryDirectory() as temporary,patch.object(
                update,'ROOT',Path(temporary)),patch.object(
                update,'fetch',side_effect=lambda s,u,params=None:
                    html if u==mori_racecards.KAWAGUCHI_NIGHT else
                    (_ for _ in ()).throw(RuntimeError('403'))),patch.object(
                verified_sources,'keirin',return_value={'status':'ok','items':[]}),patch.object(
                verified_sources,'auto',return_value={'status':'ok','items':[]}),patch.object(
                verified_sources,'soda',return_value={'status':'ok','items':[]}),patch.object(
                update,'datetime') as clock,patch.object(
                update.finals,'collect',return_value={'items':[]}):
            clock.now.return_value=datetime(2026,11,26,9,0,tzinfo=update.TZ)
            section=update.collect(day,object())['sections']['mori']
        self.assertEqual(section['item']['date'],'2026-11-30')
        self.assertEqual(section['item']['grade'],'普通')
        self.assertEqual(section['futureAssignments'][0]['date'],'2026-11-30')

    def test_future_assignments_survive_previous_days_visible_race(self):
        import json
        day=date(2026,11,26)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'data'/'history'
            path.mkdir(parents=True)
            section={'status':'ok','item':{'name':'川口','date':'2026-11-25','type':'today','race':6},
                     'futureAssignments':[{'name':'川口','date':'2026-11-30','type':'next',
                                           'grade':'普通','timeType':'ナイター'},
                                          {'name':'飯塚','date':'2026-12-10','type':'next'}]}
            (path/'2026-11-25.json').write_text(json.dumps(
                {'date':'2026-11-25','sections':{'mori':section}}),encoding='utf-8')
            got=update.mori_recent_assignment(day,root=root)
            self.assertEqual(got['date'],'2026-11-30')
            self.assertEqual(got['retainedFromDate'],'2026-11-25')
            self.assertNotIn('race',got)
            later=update.mori_recent_assignment(date(2026,12,1),root=root)
            self.assertEqual(later['date'],'2026-12-10')

    def test_additional_future_sources(self):
        day=date(2026,11,26)
        desktop='<h3>森　且行 選手の 出場予定</h3><table><tr><th>年月日</th><th>開催場</th><th>R</th></tr><tr><td>2026/11/30</td><td>川口</td><td>4</td></tr></table><h3>出走履歴</h3>'
        self.assertEqual(mori_racecards.oddspark_desktop_assignments(desktop,day)[0]['date'],'2026-11-30')
        roster='<h1>出場者一覧</h1><p>川口オートレース 2026年11月30日〜12月3日</p><a href="/autorace/autoracer/2529/">森且行川口25期</a>'
        result=mori_racecards.winticket_roster_assignment(roster,day,'川口',date(2026,11,30))
        self.assertEqual(result['meetingEnd'],'2026-12-03')
        self.assertIsNone(mori_racecards.winticket_roster_assignment(roster.replace('/2529/','/1234/'),day,'川口',date(2026,11,30)))
        with self.assertRaises(ValueError):
            mori_racecards.winticket_roster_assignment(roster,day,'飯塚',date(2026,11,30))
        official='<h2>あっせん検索</h2><table><tr><th>選手名</th><th>開催場</th><th>開催期間</th></tr><tr><td>森　且行</td><td>飯塚</td><td>2026年12月5日～12月8日</td></tr><tr><td>森谷隼人</td><td>川口</td><td>2026年11月30日～12月3日</td></tr></table>'
        items=mori_racecards.official_search_assignments(official,day)
        self.assertEqual([(x['date'],x['name']) for x in items],[('2026-12-05','飯塚')])
        with self.assertRaises(ValueError):
            mori_racecards.official_search_assignments(official.replace('森　且行','別選手'),day)

    def test_future_cache_keeps_multiple_and_original_verification_date(self):
        import json
        day=date(2026,11,26)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'data'/'history'
            path.mkdir(parents=True)
            items=[{'date':'2026-11-30','name':'川口','type':'next','verifiedOn':'2026-11-25'},
                   {'date':'2026-12-10','name':'飯塚','type':'next','verifiedOn':'2026-11-25'},
                   {'date':'2026-12-11','name':'山陽','type':'next','verifiedOn':'2026-11-01'}]
            (path/'2026-11-25.json').write_text(json.dumps(
                {'date':'2026-11-25','sections':{'mori':{'status':'ok','futureAssignments':items}}}),encoding='utf-8')
            got=update.mori_recent_assignments(day,root=root)
            self.assertEqual([x['name'] for x in got],['川口','飯塚'])
            self.assertTrue(all(x['verifiedOn']=='2026-11-25' for x in got))

    def test_no_false_today_when_no_verified_entry(self):
        target=date(2026,11,24)
        with tempfile.TemporaryDirectory() as temporary,patch.object(
                update,'ROOT',Path(temporary)),patch.object(
                update,'fetch',side_effect=lambda s,u,params=None:
                  prediction_page(mori=False) if '/auto/predictions/' in u else
                    (_ for _ in ()).throw(RuntimeError('403'))),patch.object(
                verified_sources,'keirin',return_value={'status':'ok','items':[]}),patch.object(
                verified_sources,'auto',return_value={'status':'ok','items':[{'name':'川口'}]}),patch.object(
                verified_sources,'soda',return_value={'status':'ok','items':[]}),patch.object(
                update,'datetime') as clock,patch.object(
                update.finals,'collect',return_value={'items':[]}):
            clock.now.return_value=datetime(2026,11,24,11,11,tzinfo=update.TZ)
            section=update.collect(target,object())['sections']['mori']
        self.assertEqual(section['status'],'error')


if __name__=='__main__':
    unittest.main()
