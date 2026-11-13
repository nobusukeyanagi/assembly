import unittest,sys
from unittest.mock import patch
from pathlib import Path
from datetime import date,datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verified_sources import parse_keirin_oct_2026_finals,parse_ikachi_boat,parse_oddspark_auto,cached_section,reconcile,auto as verified_auto,soda as verified_soda
from update import parse_mori_race_start,parse_mori_official_start,mori_start_times,MORI_RACE_START,parse_mori_history,collect_past_mori,MORI_HISTORY,parse_keirin,parse_auto,parse_boat,parse_mori,parse_auto_calendar,parse_kawaguchi_official_meeting,mori_meeting_metadata,parse_mori_calendar,parse_assen,mori_previous_item,check_auto_official,race_time_type,collect,ASSEN,day_label,grade,autorace_grade,mori_race_numbers,sort_by_time,parse_keirin_archive,parse_keirin_race_times,collect_past_keirin,KEIRIN_ARCHIVE,KEIRIN_RACES
D=date(2026,11,11)
class ParserTests(unittest.TestCase):
    def test_autorace_grade(self):
        self.assertEqual(grade('PGⅠ'),'PG1')
        self.assertEqual(grade('PG1'),'PG1')
        self.assertEqual(autorace_grade('普通'),'普通')
        self.assertEqual(autorace_grade('一般'),'普通')
        self.assertEqual(autorace_grade('GⅡ'),'G2')
        self.assertEqual(grade('一般'),'一般')


    def test_mori_historical_races_for_selected_date(self):
        history=(
            '<h1>森 且行</h1><h2>直近の出走</h2><table>'
            '<tr><th>レース</th><th>着順</th></tr>'
            '<tr><td>2026-11-09 川口9R</td><td>8着</td></tr>'
            '<tr><td>2026-11-03 浜松11R</td><td>8着</td></tr>'
            '<tr><td>2026-11-02 浜松12R</td><td>-</td></tr>'
            '<tr><td>2026-11-01 浜松5R</td><td>4着</td></tr>'
            '<tr><td>2026-10-31 浜松5R</td><td>4着</td></tr>'
            '</table><h2>キャリア成績</h2>')
        all_results=parse_mori_history(history)
        self.assertEqual(len(all_results),5)
        self.assertEqual([x for x in all_results if x['date']=='2026-11-01'],
                         [{'date':'2026-11-01','name':'浜松','race':5}])
        with patch('update.fetch',return_value=history):
            on_day=collect_past_mori(object(),date(2026,11,1))
            next_day=collect_past_mori(object(),date(2026,11,4))
            before=collect_past_mori(object(),date(2026,10,1))
        self.assertEqual(on_day['item']['name'],'浜松')
        self.assertEqual(on_day['item']['race'],5)
        self.assertEqual(on_day['item']['races'],[5])
        self.assertEqual(on_day['item']['type'],'today')
        self.assertEqual(next_day['item']['date'],'2026-11-09')
        self.assertEqual(next_day['item']['type'],'next')
        self.assertEqual(before['status'],'error')
        self.assertNotIn('item',before)

    def test_mori_historical_multiple_races_same_day(self):
        history=('<h1>森 且行</h1><h2>直近の出走</h2><table>'
                 '<tr><td>2026-11-01 浜松12R</td></tr>'
                 '<tr><td>2026-11-01 浜松3R</td></tr>'
                 '<tr><td>2026-11-01 浜松3R</td></tr>'
                 '<tr><td>2026-10-31 浜松5R</td></tr></table>')
        with patch('update.fetch',return_value=history):
            result=collect_past_mori(object(),date(2026,11,1))
        self.assertEqual(result['item']['races'],[3,12])
        self.assertEqual(result['item']['race'],3)

    def test_mori_historical_missing_source_no_current_schedule(self):
        with patch('update.fetch',side_effect=RuntimeError('blocked')):
            result=collect_past_mori(object(),date(2026,11,1))
        self.assertEqual(result['status'],'error')
        self.assertFalse(result.get('item'))

    def test_mori_history_rejects_other_rider_and_unrelated_text(self):
        with self.assertRaisesRegex(ValueError,'森且行選手'):
            parse_mori_history('<h1>別選手</h1><h2>直近の出走</h2>'
                               '<table><tr><td>2026-11-01 浜松5R</td></tr></table>')
        with self.assertRaisesRegex(ValueError,'出走履歴の項目'):
            parse_mori_history('<h1>森 且行</h1><p>2026-11-01 浜松5R</p>')


    def test_mori_start_time_from_dated_race_page(self):
        d=date(2026,11,1)
        h=('<html><head><title>2026年11月01日 浜松オート 5R 出走表 | 東スポオートレース</title></head>'
           '<body><h2>浜松 4日目</h2><div>5R</div><div>発走：12:22</div>'
           '<div>投票締切：12:20</div><p>2026年11月1日</p>'
           '<table><tr><td>2 森 且行 川口 / 25期 / 52歳</td></tr></table>'
           '</body></html>')
        self.assertEqual(parse_mori_race_start(h,d,'浜松',5),'12:22')
        self.assertEqual(
            MORI_RACE_START.format(day='20261101',venue='04',race=5),
            'https://autorace.tokyo-sports.co.jp/list/race/20261101045')
        for date_value,venue,race in (
            (date(2026,11,2),'浜松',5),(d,'川口',5),(d,'浜松',4)):
            with self.subTest(date=date_value,venue=venue,race=race),self.assertRaises(ValueError):
                parse_mori_race_start(h,date_value,venue,race)
        with self.assertRaisesRegex(ValueError,'一意'):
            parse_mori_race_start(h.replace('発走：12:22','発走：12:22 発走：12:23'),d,'浜松',5)
        with self.assertRaisesRegex(ValueError,'一意'):
            parse_mori_race_start(h.replace('発走：12:22','締切：12:22'),d,'浜松',5)

    def test_mori_official_start_time_verified_date_race_and_rider(self):
        selected=date(2026,10,2)
        def racepage(r,clock):
            return (f'<html><head><title>2026/10/02 出走表 | 飯塚オート</title></head>'
                    f'<body><h2>普通 飯塚</h2><section>'
                    f'10月2日(金) 予選{r}R 3100m 晴</section>'
                    f'<div>投票締切 14:00</div><div>発走予定 {clock}</div>'
                    f'<table><tr><th>車</th><th>選手</th></tr>'
                    f'<tr><td>8</td><td>森　　且行</td></tr></table></body></html>')
        page2=racepage(2,'15:51')
        self.assertEqual(parse_mori_official_start(page2,selected,'飯塚',2),'15:51')
        for wrong_day,wrong_venue,wrong_race in (
            (date(2026,10,3),'飯塚',2),(selected,'浜松',2),(selected,'飯塚',8)):
            with self.assertRaises(ValueError):
                parse_mori_official_start(page2,wrong_day,wrong_venue,wrong_race)
        with self.assertRaisesRegex(ValueError,'森且行'):
            parse_mori_official_start(page2.replace('森　　且行','別の選手'),selected,'飯塚',2)
        with self.assertRaisesRegex(ValueError,'一意'):
            parse_mori_official_start(page2.replace('発走予定 15:51','発走予定 15:51 発走予定 15:52'),
                                      selected,'飯塚',2)
        def mock_fetch(s,url,params=None):
            if 'tokyo-sports' in url:raise RuntimeError('404 archived source')
            if '/2026-10-02_2' in url:return racepage(2,'15:51')
            if '/2026-10-02_8' in url:return racepage(8,'18:34')
            raise AssertionError('unexpected URL: '+url)
        item={'name':'飯塚','date':selected.isoformat(),'type':'today','race':2,'races':[2,8]}
        with patch('update.fetch',side_effect=mock_fetch):
            mori_start_times(object(),item,selected=selected)
        self.assertEqual(item['startTimes'],{'2':'15:51','8':'18:34'})

    def test_oct_2026_keirin_final_calendar_crosschecks_meeting_day(self):
        from types import SimpleNamespace
        selected=date(2026,10,2)
        labels=[
            ('10/2(金)','佐世保','F2','モーニング','6R L級ガールズ決勝'),
            ('','青森','F2','ミッドナイト','6R L級ガールズ決勝'),
            ('','前橋','F2','ミッドナイト','7R A級決勝'),
            ('','奈良','F2','ミッドナイト','7R A級決勝'),
            ('10/3(土)','大宮','F1','デイ','12R S級決勝'),
            ('','川崎','F1','ナイター','12R S級決勝'),
            ('','久留米','F2','ナイター','10R L級ガールズ決勝'),
            ('10/4(日)','松阪','G3','デイ','12R S級決勝')]
        rows=''.join(f'<tr><td>{d}</td><td>{n}({g}){t}</td><td>{race}</td></tr>'
                     for d,n,g,t,race in labels)
        html=('<h1>〖10月〗すべての決勝レースで5%還元！</h1>'
              '<p>2026年10月1日（木）〜10月31日（土）</p>'
              '<table><tr><th>日程</th><th>開催場</th><th>対象レース</th></tr>'
              +rows+'</table>')
        archive=[{'name':n,'grade':g,'day':'最終日' if n in ('青森','前橋','奈良','佐世保') else '2日目'}
                 for n,g in [('青森','F2'),('前橋','F2'),('大宮','F1'),('川崎','F1'),
                             ('松阪','G3'),('奈良','F2'),('久留米','F2'),('佐世保','F2')]]
        upstream=SimpleNamespace(KEIRIN_NAMES=[x['name'] for x in archive],grade=grade)
        got=parse_keirin_oct_2026_finals(html,selected,archive,upstream)
        self.assertEqual(len(got),8)
        by_name={x['name']:x for x in got}
        self.assertEqual({n:by_name[n]['timeType'] for n in ('青森','前橋','奈良')},
                         {'青森':'ミッドナイト','前橋':'ミッドナイト','奈良':'ミッドナイト'})
        self.assertEqual(by_name['佐世保']['timeType'],'モーニング')
        self.assertEqual(by_name['松阪']['timeType'],'デイ')
        self.assertEqual(by_name['川崎']['timeType'],'ナイター')
        self.assertTrue(by_name['青森']['girls'])
        self.assertTrue(by_name['佐世保']['girls'])
        self.assertTrue(by_name['久留米']['girls'])
        self.assertFalse(by_name['前橋']['girls'])
        self.assertEqual(parse_keirin_oct_2026_finals(html,date(2026,9,2),archive,upstream),[])
        with self.assertRaises(ValueError):
            parse_keirin_oct_2026_finals(html.replace('2026年10月1日','2025年10月1日'),
                                          selected,archive,upstream)

    def test_autorace_monthly_links_do_not_leak_next_meeting_grade(self):
        selected=date(2026,10,2)
        html='<h2>2026年10月 開催日程</h2>'
        for n in ('川口','伊勢崎','浜松','飯塚','山陽'):
            html+=f'<h3>{n} オートレース</h3>'
            if n=='飯塚':
                html+='<a>10月2日 〜 10月4日令和８年度飯塚市営　普通開催　１０／２～</a>'
                html+='<a>10月8日 〜 10月12日ＧⅡオーバルチャンピオンカップ</a>'
            else:
                html+='<a>10月1日 〜 10月3日普通開催</a>'
                html+='<a>10月20日 〜 10月22日ＧⅡ選手権</a>'
        found=parse_auto_calendar(html,selected)
        self.assertEqual(next(x['grade'] for x in found if x['name']=='飯塚'),'普通')
        self.assertEqual(next(x['day'] for x in found if x['name']=='飯塚'),'初日')
        self.assertEqual(next(x['grade'] for x in parse_auto_calendar(
            html,date(2026,10,8)) if x['name']=='飯塚'),'G2')

    def test_mori_start_times_multiple_races_and_same_date_cache(self):
        d=date(2026,11,1)
        def racepage(r,clock):
            return (f'<html><head><title>2026年11月1日 浜松オート {r}R 出走表</title></head>'
                    f'<body>発走：{clock}　投票締切：10:00</body></html>')
        pages={MORI_RACE_START.format(day='20261101',venue='04',race=3):racepage(3,'10:30'),
               MORI_RACE_START.format(day='20261101',venue='04',race=12):racepage(12,'18:00')}
        obj={'date':d.isoformat(),'name':'浜松','type':'today','race':3,'races':[3,12]}
        with patch('update.fetch',side_effect=lambda s,url,params=None:pages[url]):
            mori_start_times(object(),obj,selected=d)
        self.assertEqual(obj['startTimes'],{'3':'10:30','12':'18:00'})
        cached={'date':d.isoformat(),'sections':{'mori':{'item':dict(obj)}}}
        obj2={'date':d.isoformat(),'name':'浜松','type':'today','race':3,'races':[3,12]}
        with patch('update.fetch',side_effect=RuntimeError('source down')):
            mori_start_times(object(),obj2,cached,d)
        self.assertEqual(obj2['startTimes'],obj['startTimes'])
        obj3={'date':d.isoformat(),'name':'浜松','type':'today','race':3,'races':[3,12]}
        with patch('update.fetch',side_effect=RuntimeError('source down')):
            mori_start_times(object(),obj3,dict(cached,date='2026-10-31'),d)
        self.assertNotIn('startTimes',obj3)

    def test_mori_multiple_races(self):
        records=[
            ('oddspark',{'date':'2026-11-12','name':'川口','type':'today','race':12}),
            ('oddspark',{'date':'2026-11-12','name':'川口','type':'today','race':3}),
            ('official',{'date':'2026-11-12','name':'川口','type':'today','race':3}),
            ('other',{'date':'2026-11-12','name':'川口','type':'next','race':6}),
        ]
        self.assertEqual(mori_race_numbers(records),[3,12])
        self.assertEqual(mori_race_numbers([('official',{'type':'next','race':3})]),[])
        html='<p>出場予定</p><p>2026/11/12 川口 3R 2026/11/12 川口 12R</p><h2>総合成績</h2>'
        self.assertEqual([x['race'] for x in parse_mori(html,date(2026,11,12))],[3,12])



    def test_autorace_official_independent_record(self):
        from verified_sources import parse_autorace_official_card
        from types import SimpleNamespace
        up=SimpleNamespace(parse_auto=parse_auto,check_auto_official=check_auto_official,day_label=day_label)
        h=('<h2>普通浜松</h2><h3>令和8年度浜松市営 浜松アーリー</h3>'
           '<div>開催期間：2026年10月10日(土)～12日(月) 開催 第3日目</div>'
           '<p>一般戦1R</p>')
        item=parse_autorace_official_card(h,date(2026,10,12),'浜松',up)
        self.assertEqual(item['day'],'最終日')
        self.assertEqual(item['grade'],'普通')
        with self.assertRaises(ValueError):
            parse_autorace_official_card(h,date(2026,10,11),'川口',up)
    def test_auto_oct12_dated_month_and_secondary_racecard(self):
        d=date(2026,10,12)
        names=['川口','伊勢崎','浜松','飯塚','山陽']
        calendar='<h2>2026年10月 開催日程</h2>'
        for n in names:
            cal='<h3>'+n+' オートレース</h3>'
            cal+=('<a>10月10日 〜 10月12日浜松アーリーレース</a>' if n=='浜松' else
                  '<a>10月8日 〜 10月12日ＧⅡオーバルチャンピオンカップ</a>' if n=='飯塚' else
                  '<a>10月13日 〜 10月16日普通開催</a>')
            calendar+=cal
        # The parser requires >=8 date ranges to certify a full monthly calendar.
        calendar+='<div>10月20日 〜 10月22日普通開催</div>'*6
        self.assertEqual({r['name'] for r in parse_auto_calendar(calendar,d)},{'浜松','飯塚'})
        race=('<h1>開催日（2026年10月12日（月）） 飯塚｜レース一覧</h1><h2>飯塚</h2>'
              '<h3>最終日 令和8年度G2オーバルチャンピオン（ナイター）</h3><p>1R 発売終了</p>')
        self.assertEqual(parse_oddspark_auto(race,d,'飯塚',autorace_grade,race_time_type),
                         {'name':'飯塚','grade':'G2','day':'最終日','timeType':'ナイター'})
        with self.assertRaises(ValueError):
            parse_oddspark_auto(race,date(2026,10,11),'飯塚',autorace_grade,race_time_type)
        with self.assertRaises(ValueError):
            parse_oddspark_auto(race,d,'浜松',autorace_grade,race_time_type)

    def test_boat_independent_date_and_full_count(self):
        d=date(2026,10,12)
        source='<h1>2026年10月12日（月）のボートレース全6場・72レース</h1>'
        source+=''.join('<h2>'+title+'</h2>' for title in (
            '桐生一般・最終日・杯','戸田一般・最終日・杯',
            '江戸川G3・最終日・レディース','浜名湖一般・3日目・杯',
            '津一般・最終日・杯','びわこ一般・初日・杯'))
        names='桐生 戸田 多摩川 浜名湖 蒲郡 三国 びわこ 宮島 若松 芦屋'.split()
        got=parse_ikachi_boat(source,d,names,{'桐生','蒲郡','若松'})
        self.assertEqual([x['name'] for x in got],['桐生','戸田','浜名湖','びわこ'])
        self.assertEqual(got[2]['day'],'3日目')
        with self.assertRaises(ValueError):
            parse_ikachi_boat(source.replace('全6場','全7場'),d,names,{'桐生'})

    def test_sources_union_disagreements_audited(self):
        a=[{'name':'川口','grade':'普通','day':'2日目','timeType':None}]
        b=[{'name':'川口','grade':'G1','day':'2日目','timeType':'ナイター'},
           {'name':'飯塚','grade':'G2','day':'最終日','timeType':'ナイター'}]
        got=reconcile('auto',[('a',a),('b',b)],['川口','飯塚'],sort_by_time)
        self.assertEqual(len(got['items']),2)
        self.assertEqual(got['items'][0]['grade'],'普通')
        self.assertEqual(got['items'][0]['timeType'],'ナイター')
        self.assertEqual(got['verification']['crossConfirmed'],1)
        self.assertEqual(got['verification']['singleSource'],1)
        self.assertEqual(len(got['verification']['conflicts']),1)

    def test_same_date_verified_cache_only(self):
        old={'date':'2026-10-12','updatedAt':'2026-10-12T01:10+09:00',
             'sections':{'soda':{'status':'ok','items':[{'name':'桐生','day':'最終日'}]}}}
        ok=cached_section(old,date(2026,10,12),'soda')
        self.assertEqual(ok['status'],'cached')
        self.assertIsNone(cached_section(old,date(2026,10,11),'soda'))
        self.assertIsNone(cached_section({'date':'2026-10-12','sections':{'soda':{'status':'error','items':[]}}},
                                          date(2026,10,12),'soda'))

    def test_auto_secondary_works_when_monthly_site_fails(self):
        from types import SimpleNamespace
        d=date(2026,10,12)
        race=('<h1>開催日（2026年10月12日（月）） 飯塚｜レース一覧</h1><h2>飯塚</h2>'
              '<h3>最終日 G2チャンピオン（ナイター）</h3><div>1R</div>')
        def mocked_fetch(s,url,params=None):
            if url=='https://sp.oddspark.com/autorace/SpRaceList.do' and params['joCd']=='05':
                return race
            raise RuntimeError('offline')
        upstream=SimpleNamespace(fetch=mocked_fetch,parse_auto_calendar=parse_auto_calendar,
            autorace_grade=autorace_grade,race_time_type=race_time_type,
            sort_by_time=sort_by_time,AUTO_OFFICIAL='https://autorace.jp/race_info/Program/',
            AUTO_NAMES={'飯塚':'iizuka'},check_auto_official=lambda *a:None,bad=lambda msg:{'status':'error','items':[]})
        out=verified_auto(object(),d,None,upstream)
        self.assertEqual([x['name'] for x in out['items']],['飯塚'])
        self.assertEqual(out['items'][0]['grade'],'G2')
        self.assertEqual(out['verification']['providers'],{'オッズパーク日別':1})

    def test_soda_secondary_works_when_official_is_unavailable(self):
        from types import SimpleNamespace
        d=date(2026,10,12)
        h='<h1>2026年10月12日（月）のボートレース全1場・12レース</h1><h2>桐生一般・最終日・杯</h2>'
        def mock(s,url,params=None):
            if 'ikachi.org' in url:return h
            raise RuntimeError('official unavailable')
        up=SimpleNamespace(fetch=mock,BOAT='https://www.boatrace.jp/owpc/pc/race/index',
                           parse_boat=lambda *args:[],SODA_NAMES=['桐生'],NIGHT_BOAT={'桐生'},
                           sort_by_time=sort_by_time,bad=lambda msg:{'status':'error','items':[]})
        got=verified_soda(object(),d,None,up)
        self.assertEqual([x['name'] for x in got['items']],['桐生'])
        self.assertEqual(got['verification']['singleSource'],1)
    def test_grade(self):
        self.assertEqual(grade('GⅡ'),'G2')
        self.assertEqual(grade('特GI'),'特G1')
    def test_keirin(self):
        t='<html><body>'+('<h2>松戸</h2><img alt="F1"><img alt="3"><div>11/09(月)～11/11(水)</div>'*20)+'</body></html>'
        self.assertEqual(parse_keirin(t,D)[0],{'name':'松戸','grade':'F1','timeType':'ナイター','girls':False,'day':'最終日'})
    def test_keirin_time_categories(self):
        categories={'1':'デイ','3':'ナイター','5':'ミッドナイト','8':'モーニング'}
        for code,category in categories.items():
            with self.subTest(code=code):
                row=f'<h2>大宮</h2><img alt="F2"><img alt="{code}"><div>11/10(火)～11/12(木)</div>'
                result=parse_keirin('<html><body>'+row*20+'</body></html>',D)
                self.assertEqual(result[0]['timeType'],category)
                self.assertEqual(result[0]['day'],'2日目')
                self.assertFalse(result[0]['girls'])
    def test_keirin_missing_category(self):
        row='<h2>大宮</h2><img alt="F2"><div>11/10(火)～11/12(木)</div>'
        self.assertEqual(parse_keirin('<html><body>'+row*20+'</body></html>',D)[0]['timeType'],'確認中')
    def test_keirin_girls_and_time_order(self):
        rows=[]
        cases=[('松阪','5','02'),('四日市','3','02'),('富山','1','02'),('大宮','8','')]
        for name,code,girls in cases:
            rows.append(f'<h2>{name}</h2><img alt="F2"><img alt="{code}">'+
                        (f'<img alt="{girls}">' if girls else '')+
                        '<div>11/10(火)～11/12(木)</div>')
        html='<html><body>'+''.join(rows)+'<div>11/01～11/03</div>'*12+'</body></html>'
        result=parse_keirin(html,D)
        self.assertEqual([x['name'] for x in result[:4]],['大宮','富山','四日市','松阪'])
        self.assertEqual([x['girls'] for x in result[:4]],[False,True,True,True])
    def test_sort_by_time_all_sports(self):
        items=[
            {'name':'night-A','timeType':'ナイター'},
            {'name':'midnight','timeType':'ミッドナイト'},
            {'name':'day-A','timeType':'デイ'},
            {'name':'morning','timeType':'モーニング'},
            {'name':'unverified-A','timeType':None},
            {'name':'night-B','timeType':'ナイター'},
            {'name':'unverified-B','timeType':None},
            {'name':'day-B','timeType':'デイ'}]
        got=sort_by_time(items)
        self.assertEqual([x['name'] for x in got],[
            'morning','day-A','unverified-A','unverified-B','day-B',
            'night-A','night-B','midnight'])
        self.assertIsNone(got[2]['timeType'])

    def test_nov1_past_nine_venues_and_time_categories(self):
        selected=date(2026,11,1)
        meetings=[
            ('防府','G3','2日目'),('弥彦','F1','最終日'),('久留米','F1','初日'),
            ('宇都宮','F2','最終日'),('西武園','F2','最終日'),('松戸','F2','最終日'),
            ('名古屋','F2','最終日'),('熊本','F2','2日目'),('小田原','F2','初日')]
        archive='<h2>2026年11月1日 開催一覧</h2><ul>'
        archive+=''.join(f'<li>{name}{g}</li>' for name,g,day in meetings)+'</ul>'
        archive+=''.join(f'<h3><a>{name}競輪</a> 大会名 {day}</h3>' for name,g,day in meetings)
        self.assertEqual(len(parse_keirin_archive(archive,selected)),9)
        race='<h1>2026年11月1日（日）の競輪 82レース</h1>'
        schedule=[
            ('モーニング',[('小田原','F2','1日目'),('熊本','F2','2日目')]),
            ('デイ',[('防府','G3','2日目'),('弥彦','F1','3日目')]),
            ('ナイター',[('久留米','F1','1日目'),('宇都宮','F2','3日目')]),
            ('ミッドナイト',[('西武園','F2','3日目'),('松戸','F2','3日目'),('名古屋','F2','3日目')])]
        for time_type,rows in schedule:
            race+=f'<h2>{time_type}</h2>'
            for name,g,day in rows:
                race+=f'<h3>{g}{name}競輪{day}</h3>'
                race+='<ul><li>6R L級 ガールズ予選</li></ul>' if name in ('小田原','西武園') else '<ul><li>6R A級 予選</li></ul>'
        self.assertEqual(len(parse_keirin_race_times(race,selected)),9)
        urls={KEIRIN_ARCHIVE.format(year=2026,month=11,day=1):archive,
              KEIRIN_RACES.format(day='20261101'):race}
        with patch('update.fetch',side_effect=lambda s,url,params=None:urls[url]):
            items=collect_past_keirin(object(),selected)
        self.assertEqual([x['name'] for x in items],
                         ['小田原','熊本','弥彦','防府','宇都宮','久留米','西武園','松戸','名古屋'])
        self.assertEqual([x['timeType'] for x in items],
                         ['モーニング','モーニング','デイ','デイ','ナイター','ナイター',
                          'ミッドナイト','ミッドナイト','ミッドナイト'])
        self.assertTrue(next(x for x in items if x['name']=='西武園')['girls'])
        self.assertEqual(next(x for x in items if x['name']=='弥彦')['day'],'最終日')

    def test_past_keirin_missing_sources_is_error(self):
        with patch('update.fetch',side_effect=RuntimeError('blocked')):
            with self.assertRaisesRegex(ValueError,'網羅できません'):
                collect_past_keirin(object(),date(2026,11,1))

    def test_auto(self):
        h='<h2>GII 山陽</h2><p>開催期間：2026年11月11日(水)～15日(日) 開催 第1日目</p>'
        self.assertEqual(parse_auto(h,'山陽',D),{'name':'山陽','grade':'G2','day':'初日'})
    def test_auto_regular(self):
        h='<h2>普通 川口</h2><p>開催期間：2026年11月10日(火)～12日(木) 開催 第2日目</p>'
        self.assertEqual(parse_auto(h,'川口',D)['grade'],'普通')

    def test_boat(self):
        h='<table><tr><td><img alt="蒲郡"></td><td><img alt="G1"></td><td>11/9-11/14 ３日目</td></tr></table>'
        self.assertEqual(parse_boat(h,D),[{'name':'蒲郡','grade':'G1','day':'3日目','timeType':'ナイター','girls':False}])
    def test_autorace_calendar(self):
        names=['川口','伊勢崎','浜松','飯塚','山陽']
        blocks=[]
        for name in names:
            part=f'<h3>{name} オートレース</h3>'
            for i in range(2):
                start='11月11日 〜 11月15日ＧⅡ若獅子杯' if name=='山陽' and i==0 else '11月1日 〜 11月5日令和８年度 普通開催'
                part+=f'<a>{start}</a>'
            blocks.append(part)
        h='<main><h2>2026年11月 開催日程</h2>'+''.join(blocks)+'</main>'
        self.assertEqual(parse_auto_calendar(h,D),[{'name':'山陽','grade':'G2','timeType':None,'day':'初日'}])
    def test_winticket_mori_calendar(self):
        h='<h1>森且行</h1><h2>出場予定</h2><a>令和8年</a> 飯塚 オートレース 11/16〜11/18 川口 オートレース 11/22〜11/25 <h2>直近5走</h2>'
        self.assertEqual(parse_mori_calendar(h,D)[0]['date'],'2026-11-16')
    def test_auto_classification(self):
        self.assertEqual(race_time_type('伊勢崎アフター５'),'ナイター')
        self.assertEqual(race_time_type('飯塚オーバーミッドナイト'),'ミッドナイト')
        self.assertIsNone(race_time_type('GⅡ若獅子杯'))
    def test_auto_official_confirmation(self):
        h='<h2>伊勢崎アフター５</h2><div>開催期間：2026年11月10日(火)～12日(木) 開催 第3日目</div>'
        self.assertEqual(check_auto_official(h,'伊勢崎',date(2026,11,12))['timeType'],'ナイター')
    def test_boat_ladies(self):
        h='<table><tr><td><img alt="蒲郡"></td><td>11/9-11/14 3日目 ヴィーナスシリーズ</td></tr></table>'
        self.assertTrue(parse_boat(h,D)[0]['girls'])
    def test_assen_official(self):
        h='<html><body>森 且行 出場情報 11月 07日(土)～10日(火) 川口/普通開催 '
        h+='11月 22日(日)～25日(水) 川口/ナイト 11月 30日(月)～12月03日(木) 川口/ナイト</body></html>'
        self.assertEqual([x['date'] for x in parse_assen(h,date(2026,11,12))],['2026-11-22','2026-11-30'])
    def test_verified_future_cache(self):
        old={'sections':{'mori':{'item':{'date':'2026-11-22','name':'川口','type':'next'}}}}
        self.assertEqual(mori_previous_item(old,date(2026,11,12))['name'],'川口')
        self.assertIsNone(mori_previous_item(old,date(2026,11,23)))
    def test_mori_official_fallback(self):
        # Freeze the runtime clock for this 2026-11-12 fixture. Otherwise, on
        # 2026-11-13 the collector correctly chooses the historical branch,
        # which is not what this future-schedule fallback test is testing.
        h='<html><body>森且行 出場情報 11月 22日(日)～25日(水) 川口/普通開催</body></html>'
        with patch('update.datetime') as clock, patch(
                'update.fetch',side_effect=lambda s,url,params=None:
                h if url==ASSEN else (_ for _ in ()).throw(RuntimeError('unavailable'))):
            clock.now.return_value=datetime(2026,11,12,12,0,
                                             tzinfo=__import__('update').TZ)
            out=collect(date(2026,11,12),object())
        self.assertEqual(out['sections']['mori']['item']['date'],'2026-11-22')
    def test_mori_kawaguchi_venue_calendar(self):
        official='<h4>テレ玉presents 川口ナイトレース(無観客開催)</h4><p>11/22(日) ～ 11/25(水)</p>'
        detail=parse_kawaguchi_official_meeting(official,date(2026,11,22))
        self.assertEqual(detail,{'grade':'普通','timeType':'ナイター'})
    def test_mori_grade_and_night_from_matching_meeting(self):
        venues=['川口','伊勢崎','浜松','飯塚','山陽']
        blocks=[]
        for venue in venues:
            block=f'<h3>{venue} オートレース</h3>'
            block+='<a>11月1日 〜 11月4日令和8年度 普通開催</a>'
            block+='<a>11月22日 〜 11月25日令和8年度川口ナイトレース</a>' if venue=='川口' else '<a>11月8日 〜 11月11日一般開催</a>'
            blocks.append(block)
        html='<main><h2>2026年11月 開催日程</h2>'+''.join(blocks)+'</main>'
        official='<h4>テレ玉presents 川口ナイトレース(無観客開催)</h4><p>11/22(日) ～ 11/25(水)</p>'
        result=mori_meeting_metadata(html,date(2026,11,22),'川口',official)
        self.assertEqual(result,{'grade':'普通','timeType':'ナイター'})
        mismatch='<h4>SG第58回</h4><p>11/22(日) ～ 11/25(水)</p>'
        self.assertNotIn('grade',mori_meeting_metadata(html,date(2026,11,22),'川口',mismatch))
    def test_mori_missing_meeting_no_guessed_metadata(self):
        html='<h2>2026年12月 開催日程</h2>'
        self.assertEqual(mori_meeting_metadata(html,date(2026,11,22),'川口'),{})
    def test_mori(self):
        h='<p>出場予定</p><p>2026/11/11 川口 9R</p><h2>総合成績</h2>'
        self.assertEqual(parse_mori(h,D),[{'date':'2026-11-11','name':'川口','race':9}])
if __name__=='__main__':unittest.main()
