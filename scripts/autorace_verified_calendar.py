"""Dated official evidence for historical Kawaguchi simultaneous meetings.

Only include sessions for which two separately identified events have
independent, date-specific official confirmation. These are not inferred
from the present year's rolling calendar or from a venue's name alone.

2026-02-04..06:
  Kawaguchi City, February 2026 newsletter p.21:
  https://www.city.kawaguchi.lg.jp/material/files/group/3/2026_02.pdf
  Verified against the archived official race record / February venue calendar.
"""
from datetime import date

SOURCE='川口市公式広報2026年2月'
VERIFIED_DOUBLE_PERIODS=(
    (date(2026,2,4),date(2026,2,6)),
)


def kawaguchi_meetings(selected, u):
    """Return both independently verified meetings, never just 川口２ alone."""
    for start,end in VERIFIED_DOUBLE_PERIODS:
        if not start<=selected<=end:
            continue
        common={'grade':'普通','day':u.day_label(selected,start,end),
                'meetingStart':start.isoformat(),'meetingEnd':end.isoformat()}
        return [
            dict(common,name='川口',timeType='デイ'),
            dict(common,name='川口２',timeType='ナイター'),
        ]
    return []
