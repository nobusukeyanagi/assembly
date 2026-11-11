import unittest,sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update import parse_keirin,parse_auto,parse_boat,parse_mori,parse_auto_calendar,parse_mori_calendar,grade
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
    def test_auto(self):
        h='<h2>GII 山陽</h2><p>開催期間：2026年11月11日(水)～15日(日) 開催 第1日目</p>'
        self.assertEqual(parse_auto(h,'山陽',D),{'name':'山陽','grade':'G2','day':'初日'})
    def test_boat(self):
        h='<table><tr><td><img alt="蒲郡"></td><td><img alt="G1"></td><td>11/9-11/14 ３日目</td></tr></table>'
        self.assertEqual(parse_boat(h,D),[{'name':'蒲郡','grade':'G1','day':'3日目'}])
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
        self.assertEqual(parse_auto_calendar(h,D),[{'name':'山陽','grade':'G2','day':'初日'}])
    def test_winticket_mori_calendar(self):
        h='<h1>森且行</h1><h2>出場予定</h2><a>令和8年</a> 飯塚 オートレース 11/16〜11/18 川口 オートレース 11/22〜11/25 <h2>直近5走</h2>'
        self.assertEqual(parse_mori_calendar(h,D)[0]['date'],'2026-11-16')
    def test_mori(self):
        h='<p>出場予定</p><p>2026/11/11 川口 9R</p><h2>総合成績</h2>'
        self.assertEqual(parse_mori(h,D),[{'date':'2026-11-11','name':'川口','race':9}])
if __name__=='__main__':unittest.main()
