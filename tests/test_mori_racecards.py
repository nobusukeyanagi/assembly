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
