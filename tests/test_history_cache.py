import json
import sys
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from history_cache import matching_meeting,merge,save


class HistoricalRetentionTests(unittest.TestCase):
    def setUp(self):
        self.date='2026-11-13'
        self.row={'name':'松戸','grade':'F2','day':'初日','timeType':'モーニング',
                  'girls':True,
                  'fieldSources':{'grade':'KEIRIN.JP','day':'KEIRIN.JP',
                                  'timeType':'KEIRIN.JP','girls':'KEIRIN.JP'},
                  'girlsConfirmedBy':['KEIRIN.JP']}
        self.old={'date':self.date,'sections':{
            'keirin':{'status':'ok','items':[deepcopy(self.row)]},
            'auto':{'status':'ok','items':[]},
            'soda':{'status':'ok','items':[]},
            'mori':{'status':'ok','items':[],
                'item':{'date':self.date,'name':'川口','type':'today',
                        'race':2,'races':[2,8],
                        'startTimes':{'2':'12:15','8':'17:10'}}}}}
        self.current={'date':self.date,'sections':{
            'keirin':{'status':'ok','items':[{
                'name':'松戸','grade':'F2','day':'初日',
                'timeType':None,'girls':False,'fieldSources':{},
            }],'verification':{'fieldCoverage':{'timeType':0,'girlsDetected':0}}},
            'auto':{'status':'error','items':[]},
            'soda':{'status':'ok','items':[]},
            'mori':{'status':'ok','items':[],
                'item':{'date':self.date,'name':'川口','type':'today',
                        'race':2,'races':[2,8],
                        'startTimes':{'8':'17:10'}}}}}

    def test_recover_known_fields_and_mori_race_times(self):
        old=deepcopy(self.old)
        current=deepcopy(self.current)
        out=merge(old,current)
        row=out['sections']['keirin']['items'][0]
        self.assertEqual(row['timeType'],'モーニング')
        self.assertTrue(row['girls'])
        self.assertEqual(row['fieldSources']['timeType'],'KEIRIN.JP')
        self.assertEqual(row['girlsConfirmedBy'],['KEIRIN.JP'])
        self.assertEqual(out['sections']['keirin']['verification']['fieldCoverage'],
                         {'timeType':1,'girlsDetected':1})
        self.assertEqual(out['sections']['auto']['status'],'cached')
        self.assertEqual(out['sections']['mori']['item']['startTimes'],
                         {'2':'12:15','8':'17:10'})
        self.assertEqual(old,self.old)
        self.assertEqual(current,self.current)

    def test_never_copy_across_dates_or_changed_meetings(self):
        self.assertEqual(merge(dict(self.old,date='2026-11-12'),self.current),
                         self.current)
        for key,value in (('grade','F1'),('day','2日目'),('name','川崎')):
            altered=deepcopy(self.current)
            altered['sections']['keirin']['items'][0][key]=value
            out=merge(self.old,altered)
            self.assertIsNone(out['sections']['keirin']['items'][0]['timeType'])
            self.assertFalse(out['sections']['keirin']['items'][0]['girls'])

    def test_never_accept_unproven_positive_girls(self):
        old=deepcopy(self.old)
        old['sections']['keirin']['items'][0].pop('girlsConfirmedBy')
        old['sections']['keirin']['items'][0]['fieldSources'].pop('timeType')
        out=merge(old,self.current)
        row=out['sections']['keirin']['items'][0]
        self.assertIsNone(row['timeType'])
        self.assertFalse(row['girls'])

    def test_prefer_newer_confirmed_values(self):
        current=deepcopy(self.current)
        current['sections']['keirin']['items'][0].update(
            timeType='ナイター',girls=True,
            fieldSources={'timeType':'KEIRIN.JP','girls':'KEIRIN.JP'},
            girlsConfirmedBy=['KEIRIN.JP'])
        out=merge(self.old,current)
        self.assertEqual(out['sections']['keirin']['items'][0]['timeType'],'ナイター')
        self.assertEqual(out['sections']['keirin']['items'][0]['girlsConfirmedBy'],
                         ['KEIRIN.JP'])

    def test_archive_repeated_update_preserves_confirmed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=save(self.old,tmp)
            self.assertEqual(path,Path(tmp)/(self.date+'.json'))
            self.assertEqual(json.loads(path.read_text())['date'],self.date)
            save(self.current,tmp)
            found=json.loads(path.read_text())
            self.assertEqual(found['sections']['keirin']['items'][0]['timeType'],
                             'モーニング')
            self.assertTrue(found['sections']['keirin']['items'][0]['girls'])

    def test_invalid_archive_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save(dict(self.current,date='2026-02-30'),tmp)
        self.assertFalse(matching_meeting(self.row,dict(self.row,grade='G3')))


if __name__=='__main__':
    unittest.main()
