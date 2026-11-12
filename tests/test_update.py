import unittest,sys
from unittest.mock import patch
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update import parse_keirin,parse_auto,parse_boat,parse_mori,parse_auto_calendar,parse_kawaguchi_official_meeting,mori_meeting_metadata,parse_mori_calendar,parse_assen,mori_previous_item,check_auto_official,race_time_type,collect,ASSEN,grade,sort_by_time,parse_keirin_archive,parse_keirin_race_times,collect_past_keirin,KEIRIN_ARCHIVE,KEIRIN_RACES
D=date(2026,11,11)
class ParserTests(unittest.TestCase):
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
        h='<html><body>森且行 出場情報 11月 22日(日)～25日(水) 川口/普通開催</body></html>'
        with patch('update.fetch',side_effect=lambda s,url,params=None:
                h if url==ASSEN else (_ for _ in ()).throw(RuntimeError('unavailable'))):
            out=collect(date(2026,11,12),object())
        self.assertEqual(out['sections']['mori']['item']['date'],'2026-11-22')
    def test_mori_kawaguchi_venue_calendar(self):
        official='<h4>テレ玉presents 川口ナイトレース(無観客開催)</h4><p>11/22(日) ～ 11/25(水)</p>'
        detail=parse_kawaguchi_official_meeting(official,date(2026,11,22))
        self.assertEqual(detail,{'grade':'一般','timeType':'ナイター'})
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
        self.assertEqual(result,{'grade':'一般','timeType':'ナイター'})
        mismatch='<h4>SG第58回</h4><p>11/22(日) ～ 11/25(水)</p>'
        self.assertNotIn('grade',mori_meeting_metadata(html,date(2026,11,22),'川口',mismatch))
    def test_mori_missing_meeting_no_guessed_metadata(self):
        html='<h2>2026年12月 開催日程</h2>'
        self.assertEqual(mori_meeting_metadata(html,date(2026,11,22),'川口'),{})
    def test_mori(self):
        h='<p>出場予定</p><p>2026/11/11 川口 9R</p><h2>総合成績</h2>'
        self.assertEqual(parse_mori(h,D),[{'date':'2026-11-11','name':'川口','race':9}])
if __name__=='__main__':unittest.main()
