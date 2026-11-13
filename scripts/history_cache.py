#!/usr/bin/env python3
"""Retain independently verified daily racing snapshots without cross-date guesses.

The archive is a private build input, not part of the published Pages assets.
Newer known fields win; old verified evidence only fills missing same-meeting
fields. Changes in track, grade or event day are never backfilled.
"""
from __future__ import annotations
import argparse
import copy
import json
import re
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def matching_meeting(current, prior):
    if current.get('name')!=prior.get('name') or not current.get('grade'):
        return False
    if current['grade']!=prior.get('grade'):return False
    a,b=current.get('day'),prior.get('day')
    if not a or not b:return False
    if a==b or {a,b}=={'初日','1日目'}:return True
    return ('最終日' in (a,b) and
            any(re.fullmatch(r'[2-9]\d*日目',str(v)) for v in (a,b)))


def merge(prior, current):
    """Return the best current snapshot with only provable older values retained."""
    latest=copy.deepcopy(current)
    if not isinstance(prior,dict) or not isinstance(current,dict):
        return latest
    if prior.get('date')!=current.get('date'):
        return latest
    previous_sections=prior.get('sections',{})
    sections=latest.get('sections',{})
    for sport in ('keirin','auto','soda'):
        before=previous_sections.get(sport,{})
        after=sections.get(sport,{})
        if not isinstance(after,dict) or not isinstance(before,dict):continue
        if after.get('status')=='error' and before.get('status') in ('ok','cached'):
            sections[sport]=copy.deepcopy(before)
            sections[sport]['status']='cached'
            sections[sport]['recoveredFromArchive']=True
            continue
        if after.get('status') not in ('ok','cached') or before.get('status') not in ('ok','cached'):
            continue
        old={r.get('name'):r for r in before.get('items',[])
             if isinstance(r,dict) and r.get('name')}
        restored=[]
        for row in after.get('items',[]):
            if not isinstance(row,dict):continue
            prev=old.get(row.get('name'))
            if not prev or not matching_meeting(row,prev):continue
            sources=prev.get('fieldSources')
            if not isinstance(sources,dict):continue
            current_sources=row.setdefault('fieldSources',{})
            if (row.get('timeType') in (None,'確認中') and
                prev.get('timeType') in ('モーニング','デイ','ナイター','ミッドナイト') and
                sources.get('timeType')):
                row['timeType']=prev['timeType']
                current_sources['timeType']=sources['timeType']
                restored.append({'venue':row['name'],'field':'timeType'})
            positives=prev.get('girlsConfirmedBy')
            if (row.get('girls') is not True and prev.get('girls') is True and
                isinstance(positives,list) and positives):
                row['girls']=True
                row['girlsConfirmedBy']=copy.deepcopy(positives)
                current_sources['girls']=sources.get('girls',positives[0])
                restored.append({'venue':row['name'],'field':'girls'})
        if restored:
            checked=after.setdefault('verification',{})
            coverage=checked.setdefault('fieldCoverage',{})
            coverage['timeType']=sum(row.get('timeType') in
                ('モーニング','デイ','ナイター','ミッドナイト')
                for row in after.get('items',[]))
            coverage['girlsDetected']=sum(row.get('girls') is True
                for row in after.get('items',[]))
            checked['restoredFromArchive']=restored
    old_mori=previous_sections.get('mori',{}).get('item') if isinstance(
        previous_sections.get('mori'),dict) else None
    new_section=sections.get('mori',{})
    new_mori=new_section.get('item') if isinstance(new_section,dict) else None
    if isinstance(old_mori,dict) and isinstance(new_mori,dict):
        if (old_mori.get('date')==new_mori.get('date')==current.get('date') and
            old_mori.get('name')==new_mori.get('name') and
            old_mori.get('type')==new_mori.get('type')=='today'):
            current_races=set(new_mori.get('races',[]))
            original_races=set(old_mori.get('races',[]))
            for race,clock in old_mori.get('startTimes',{}).items():
                if (race.isdigit() and int(race) in current_races & original_races and
                    re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',str(clock))):
                    new_mori.setdefault('startTimes',{}).setdefault(race,clock)
    return latest


def save(snapshot, directory=ROOT/'data'/'history'):
    if not isinstance(snapshot,dict):raise ValueError('スナップショットが辞書形式ではありません')
    iso=snapshot.get('date')
    if not isinstance(iso,str) or date.fromisoformat(iso).isoformat()!=iso:
        raise ValueError('スナップショットの日付が不正です')
    if not isinstance(snapshot.get('sections'),dict):
        raise ValueError('スナップショットに開催情報がありません')
    path=Path(directory)/f'{iso}.json'
    prior=None
    if path.exists():
        prior=json.loads(path.read_text(encoding='utf-8'))
    retained=merge(prior,snapshot)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(retained,ensure_ascii=False,indent=2)+'\n',
                    encoding='utf-8')
    return path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default=str(ROOT/'data'/'today.json'))
    parser.add_argument('--directory',default=str(ROOT/'data'/'history'))
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding='utf-8'))
    print(f'同日データを保存: {save(data,Path(args.directory))}')


if __name__=='__main__':main()
