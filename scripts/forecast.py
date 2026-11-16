#!/usr/bin/env python3
"""Record tomorrow's explicitly dated venue schedules before midnight.

This is a reliability reserve for the 01:10 JST publication. It uses the
normal source verification logic; it never predicts venues or race metadata.
Mori's future appearance and finals are intentionally excluded because their
exact race numbers/riders must be checked on the actual day.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import history_cache
import update
import verified_sources

TZ=ZoneInfo("Asia/Tokyo")
ROOT=Path(__file__).resolve().parents[1]
FUNCS=(("keirin",verified_sources.keirin),
       ("auto",verified_sources.auto),
       ("soda",verified_sources.soda))


def capture(day,session=None):
    """Return only entries verified for the exact following calendar date."""
    if not isinstance(day,date):raise TypeError("capture requires a date")
    s=session if session is not None else update.session()
    sections={}
    for category,collector in FUNCS:
        try:
            sections[category]=collector(s,day,None,update)
        except Exception as exc:
            sections[category]={"status":"error","items":[],
                                "verification":{"errors":[("collect",str(exc))]}}
    return {
        "date":day.isoformat(),
        "createdAt":datetime.now(TZ).isoformat(timespec="minutes"),
        "purpose":"verified-next-day-fallback",
        "sections":sections,
    }


def save_next_day(now=None,directory=ROOT/"data"/"forecast",session=None):
    now=now or datetime.now(TZ).date()
    if not isinstance(now,date):raise TypeError("now requires a date")
    target=now+timedelta(days=1)
    path=history_cache.save(capture(target,session),directory)
    # Only today's and tomorrow's reserves are useful. The normal daily
    # archive holds previous days, avoiding duplicate long-lived forecast files.
    for stale in Path(directory).glob("????-??-??.json"):
        try:dated=date.fromisoformat(stale.stem)
        except ValueError:continue
        if dated<now:stale.unlink()
    return path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--directory",default=str(ROOT/"data"/"forecast"))
    args=parser.parse_args()
    path=save_next_day(directory=Path(args.directory))
    print("翌日の検証済み開催予定を保存:",path)


if __name__=="__main__":main()
