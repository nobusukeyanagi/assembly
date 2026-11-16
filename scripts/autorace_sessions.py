"""Model same-day double Kawaguchi meetings without confusing other venues.

"川口" is the daytime session. "川口２" is the separately verified night
session. The suffix is *never* introduced when only one meeting is known.
"""
from copy import deepcopy

NIGHT=('ナイター','ミッドナイト')
SECOND='川口２'


def split_kawaguchi(items):
    """Relabel exactly two confirmed same-day Kawaguchi sessions.

    Detect the pair from an explicit day/night difference, not merely
    different grade predictions or dates from unrelated sources.
    """
    rows=[deepcopy(x) for x in items]
    same=[row for row in rows if row.get('name') in ('川口',SECOND)]
    if len(same)>2:
        raise ValueError('川口の同日開催は3件以上となっています')
    if len(same)==2:
        nights=[x for x in same if x.get('timeType') in NIGHT]
        days=[x for x in same if x.get('timeType') not in NIGHT]
        if len(nights)!=1 or len(days)!=1:
            raise ValueError('川口の昼・夜2開催を区別できません')
        # A true one-day-two-meetings format can use identical start/end
        # dates and day labels for its daytime and nighttime sessions.
        a,b=days[0],nights[0]
        a['name']='川口'
        b['name']=SECOND
    return rows


def normalize_sources(lists):
    """Align another provider's solo Kawaguchi record to the confirmed pair.

    A night-only official record belongs to 川口２ only if a separate
    two-session source exists. For a record without a time category use
    grade/day/meeting-start only if it uniquely identifies one of the pair;
    otherwise omit the ambiguous provider claim (not the verified pair).
    """
    prepared=[]
    for source,rows in lists:
        prepared.append((source,split_kawaguchi(rows)))
    reference=next((rows for _,rows in prepared if
                    {'川口',SECOND}.issubset({r.get('name') for r in rows})),None)
    if reference is None:return prepared,[]
    primary=next(x for x in reference if x.get('name')=='川口')
    secondary=next(x for x in reference if x.get('name')==SECOND)
    ignored=[];output=[]
    for source,rows in prepared:
        updated=[]
        for row in rows:
            if row.get('name')!='川口' or SECOND in {r.get('name') for r in rows}:
                updated.append(row)
                continue
            t=row.get('timeType')
            if t in NIGHT:
                row['name']=SECOND
                updated.append(row)
                continue
            if t in ('デイ','モーニング'):
                updated.append(row)
                continue
            candidates=[]
            for meeting in (primary,secondary):
                if (row.get('grade') and meeting.get('grade') and
                    row['grade']!=meeting['grade']):
                    continue
                if (row.get('day') and meeting.get('day') and
                    row['day']!=meeting['day']):
                    continue
                if (row.get('meetingStart') and meeting.get('meetingStart')
                    and row['meetingStart']!=meeting['meetingStart']):
                    continue
                candidates.append(meeting['name'])
            if len(candidates)==1:
                row['name']=candidates[0]
                updated.append(row)
            else:
                ignored.append({'source':source,'name':'川口',
                                'reason':'2開催のどちらか特定できない単独情報'})
        output.append((source,updated))
    return output,ignored
