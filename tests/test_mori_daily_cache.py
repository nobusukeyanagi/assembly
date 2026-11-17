"""Cross-day fallback tests for Mori's verified *future* assignment."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update


class MoriDailyCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.archive=self.root/'data'/'history'
        self.archive.mkdir(parents=True)

    def save(self, snapshot_date, event='2026-11-22', name='川口',
             state='ok', record_type='next', iso=None):
        d=snapshot_date.isoformat()
        row={'date':event,'name':name,'type':record_type,
             'unconfirmed':True,'grade':'普通','timeType':'ナイター'}
        data={'date':iso or d,'sections':{'mori':{'status':state,
                                                 'items':[],'item':row}}}
        (self.archive/(d+'.json')).write_text(
            json.dumps(data,ensure_ascii=False),encoding='utf-8')

    def test_previous_day_assignment_survives_403_outage(self):
        self.save(date(2026,11,16))
        restored=update.mori_recent_assignment(date(2026,11,17),self.root)
        self.assertEqual(restored['date'],'2026-11-22')
        self.assertEqual(restored['name'],'川口')
        self.assertEqual(restored['timeType'],'ナイター')
        self.assertEqual(restored['retainedFromDate'],'2026-11-16')
        self.assertNotIn('race',restored)
        with patch.object(update,'ROOT',self.root), patch.object(
                update,'fetch',side_effect=RuntimeError('403 forbidden')), patch.object(
                update,'datetime') as clock:
            clock.now.return_value=datetime(2026,11,17,9,10,tzinfo=update.TZ)
            actual=update.collect(date(2026,11,17),object())
        section=actual['sections']['mori']
        self.assertEqual(section['status'],'cached')
        self.assertEqual(section['item']['date'],'2026-11-22')
        self.assertEqual(section['item']['retainedFromDate'],'2026-11-16')
        self.assertEqual(section['item']['name'],'川口')
        self.assertNotIn('race',section['item'])
        self.assertNotIn('startTimes',section['item'])

    def test_recent_snapshot_preferred_over_older_one(self):
        self.save(date(2026,11,15),event='2026-11-30')
        self.save(date(2026,11,16),event='2026-11-22')
        found=update.mori_recent_assignment(date(2026,11,17),self.root)
        self.assertEqual(found['date'],'2026-11-22')

    def test_previous_days_only_not_expired_or_todays_unconfirmed(self):
        self.save(date(2026,11,16))
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,22),self.root))
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,23),self.root))
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,16),self.root))

    def test_never_reuse_error_or_invalid_venue(self):
        self.save(date(2026,11,16),state='error')
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,17),self.root))
        self.save(date(2026,11,16),name='不明')
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,17),self.root))

    def test_file_date_must_match_actual_snapshot(self):
        self.save(date(2026,11,16),iso='2026-11-01')
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,17),self.root))

    def test_old_or_far_future_assignments_are_not_carried_indefinitely(self):
        self.save(date(2026,11,1))
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,17),self.root))
        self.save(date(2026,11,16),event='2027-04-10')
        self.assertIsNone(update.mori_recent_assignment(date(2026,11,17),self.root))


if __name__=='__main__':
    unittest.main()
