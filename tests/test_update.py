import unittest,sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update import parse_keirin,parse_auto,parse_boat,parse_mori,grade
D=date(2026,11,11)
class ParserTests(unittest.TestCase):
    def test_grade(self):
        self.assertEqual(grade('GⅡ'),'G2')
        self.assertEqual(grade('特GI'),'特G1')
    def test_keirin(self):
        t='<html><body>'+('<h2>松戸</h2><img alt="F1"><div>11/09(月)～11/11(水)</div>'*20)+'</body></html>'
        self.assertEqual(parse_keirin(t,D)[0],{'name':'松戸','grade':'F1','day':'最終日'})
    def test_auto(self):
        h='<h2>GII 山陽</h2><p>開催期間：2026年11月11日(水)～15日(日) 開催 第1日目</p>'
        self.assertEqual(parse_auto(h,'山陽',D),{'name':'山陽','grade':'G2','day':'初日'})
    def test_boat(self):
        h='<table><tr><td><img alt="蒲郡"></td><td><img alt="G1"></td><td>11/9-11/14 ３日目</td></tr></table>'
        self.assertEqual(parse_boat(h,D),[{'name':'蒲郡','grade':'G1','day':'３日目'}])
    def test_mori(self):
        h='<p>出場予定</p><p>2026/11/11 川口 9R</p><h2>総合成績</h2>'
        self.assertEqual(parse_mori(h,D),[{'date':'2026-11-11','name':'川口','race':9}])
if __name__=='__main__':unittest.main()
