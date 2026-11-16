import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import forecast
import history_cache
from update import load_same_date_evidence


def verified_sport(name,venue):
    return {"status":"ok","items":[{
        "name":venue,"grade":"普通" if name=="auto" else "F2",
        "day":"初日","timeType":None,
        "fieldSources":{"grade":"official-test-source",
                        "day":"official-test-source"}
    }],"verification":{"providers":{"official-test-source":1}}}


class PreverifiedTomorrowTests(unittest.TestCase):
    def test_capture_uses_target_date_not_calendar_today(self):
        target=date(2026,11,17)
        calls=[]
        def collector(name):
            def collect(sess,day,previous,u):
                calls.append((name,day,previous,u.__name__))
                return verified_sport(name,"伊勢崎" if name=="auto" else "富山")
            return collect
        with patch.object(forecast,"FUNCS",(
                ("keirin",collector("keirin")),
                ("auto",collector("auto")),
                ("soda",collector("soda")))):
            out=forecast.capture(target,object())
        self.assertEqual(out["date"],target.isoformat())
        self.assertEqual(out["purpose"],"verified-next-day-fallback")
        self.assertEqual(len(calls),3)
        self.assertTrue(all(day==target and old is None and mod=="update"
                            for _,day,old,mod in calls))

    def test_selected_date_uses_forecast_only_when_same_day(self):
        target=date(2026,11,17)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reserved=root/"data"/"forecast"/"2026-11-17.json"
            reserved.parent.mkdir(parents=True)
            expected={"date":target.isoformat(),"sections":{
                "auto":verified_sport("auto","伊勢崎")}}
            reserved.write_text(json.dumps(expected),encoding="utf-8")
            today=root/"data"/"today.json"
            today.write_text(json.dumps({"date":"2026-11-16","sections":{
                "auto":verified_sport("auto","飯塚")}}),encoding="utf-8")
            selected=load_same_date_evidence(target,today,root)
            self.assertEqual(selected["date"],target.isoformat())
            self.assertEqual(selected["sections"]["auto"]["items"][0]["name"],
                             "伊勢崎")
            failed={"date":target.isoformat(),"sections":{
                "auto":{"status":"error","items":[]}}}
            result=history_cache.merge(selected,failed)
            self.assertEqual(result["sections"]["auto"]["status"],"cached")
            self.assertEqual(result["sections"]["auto"]["items"][0]["name"],
                             "伊勢崎")
            self.assertIsNone(load_same_date_evidence(date(2026,11,18),today,root))

    def test_more_recent_verified_same_date_wins_over_earlier_forecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reserved=root/"data"/"forecast"/"2026-11-17.json"
            reserved.parent.mkdir(parents=True)
            reserved.write_text(json.dumps({"date":"2026-11-17","sections":{
                "auto":verified_sport("auto","飯塚")}}),encoding="utf-8")
            today=root/"data"/"today.json"
            today.write_text(json.dumps({"date":"2026-11-17","sections":{
                "auto":{"status":"ok","items":[{
                    "name":"伊勢崎","grade":"普通","day":"初日",
                    "fieldSources":{"grade":"WINTICKET指定月",
                                    "day":"WINTICKET指定月"}}],
                    "verification":{"providers":{"WINTICKET指定月":1}}}}}),
                encoding="utf-8")
            selected=load_same_date_evidence(date(2026,11,17),today,root)
            self.assertEqual([x["name"] for x in selected["sections"]["auto"]["items"]],
                             ["伊勢崎"])

    def test_forecast_archive_keeps_previous_verified_when_new_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            now=date(2026,11,16)
            previous_file=root/"2026-11-15.json"
            previous_file.write_text("{}")
            initial={"date":"2026-11-17","sections":{
                "auto":verified_sport("auto","伊勢崎")}}
            outage={"date":"2026-11-17","sections":{
                "auto":{"status":"error","items":[]}}}
            with patch.object(forecast,"capture",return_value=initial):
                path=forecast.save_next_day(now,root,object())
            self.assertEqual(path,root/"2026-11-17.json")
            with patch.object(forecast,"capture",return_value=outage):
                forecast.save_next_day(now,root,object())
            stored=json.loads(path.read_text())
            self.assertEqual(stored["sections"]["auto"]["status"],"cached")
            self.assertEqual(stored["sections"]["auto"]["items"][0]["name"],
                             "伊勢崎")
            self.assertFalse(previous_file.exists())

    def test_precheck_runs_only_at_0910_and_1710_not_every_push(self):
        workflow=(Path(__file__).resolve().parents[1]/
                  ".github/workflows/refresh.yml").read_text(encoding="utf-8")
        condition="github.event_name == 'schedule' && (github.event.schedule == '10 0 * * *' || github.event.schedule == '10 8 * * *')"
        self.assertIn(condition,workflow)
        self.assertEqual(workflow.count("run: python scripts/forecast.py"),1)
        self.assertLess(workflow.index("name: Gather today's information"),
                        workflow.index("name: Pre-check tomorrow's verified race schedule"))


if __name__=="__main__":
    unittest.main()
