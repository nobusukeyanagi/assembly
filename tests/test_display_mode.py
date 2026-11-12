import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from display_mode import config_for,valid_date,set_mode,check

class DisplayModeTests(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(config_for('当日','2026-11-23'),{'mode':'today','date':None})
        self.assertEqual(config_for('日付指定','2026-11-23'),{'mode':'selected','date':'2026-11-23'})
    def test_invalid_dates(self):
        for s in ('','2026-02-30','2026/11/23','none','2026-13-01'):
            with self.subTest(date=s),self.assertRaises(ValueError):valid_date(s)
    def test_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'display.json'
            b=Path(tmp)/'selected.json'
            b.write_text(json.dumps({'date':'2026-11-23','sections':{}}),encoding='utf-8')
            set_mode('日付指定','2026-11-23',a,b)
            self.assertEqual(check(a,b)['mode'],'selected')
            set_mode('当日','NOT_A_DATE',config_path=a,selected_path=b)
            self.assertEqual(check(a,b)['mode'],'today')
            self.assertFalse(b.exists())
    def test_selected_requires_matching_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'display.json'
            b=Path(tmp)/'selected.json'
            set_mode('日付指定','2026-11-23',a,b)
            with self.assertRaises(FileNotFoundError):check(a,b)
            b.write_text(json.dumps({'date':'2026-11-22','sections':{}}),encoding='utf-8')
            with self.assertRaises(ValueError):check(a,b)
