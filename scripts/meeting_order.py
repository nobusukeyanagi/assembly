"""Canonical race-board ordering for all three sports.

Sort by session (morning/day/night/midnight), descending meeting grade,
then the established venue order.  A missing non-keirin time category
keeps the legacy daytime-position fallback without claiming that the
actual race has been independently verified as a day session.
"""
from unicodedata import normalize

KEIRIN_VENUES = ('函館 青森 いわき平 弥彦 前橋 取手 宇都宮 大宮 西武園 京王閣 立川 '
                 '松戸 千葉 川崎 平塚 小田原 伊東 静岡 名古屋 岐阜 大垣 豊橋 '
                 '富山 松阪 四日市 福井 奈良 向日町 和歌山 岸和田 玉野 広島 '
                 '防府 高松 小松島 高知 松山 小倉 久留米 武雄 佐世保 別府 熊本').split()
AUTO_VENUES = ['川口', '川口２', '伊勢崎', '浜松', '飯塚', '山陽']
SODA_VENUES = '桐生 戸田 多摩川 浜名湖 蒲郡 三国 びわこ 宮島 若松 芦屋'.split()

VENUES = {'keirin': KEIRIN_VENUES,
          'auto': AUTO_VENUES,
          'soda': SODA_VENUES}

TIME_RANK = {'モーニング': 0, 'デイ': 1, None: 1,
             'ナイター': 2, 'ミッドナイト': 3}

# Different sports have different grade ladders.  All lists are highest first.
GRADE_RANK = {
    'keirin': ('GP', 'G1', 'G2', 'G3', 'F1', 'F2'),
    'auto': ('SG', '特G1', 'G1', 'G2', '普通', '一般'),
    'soda': ('SG', 'PG1', 'G1', 'G2', 'G3', '一般', '普通'),
}


def canonical_grade(grade):
    """Accept stored numeric grades and official Roman-numeral variants."""
    value = normalize('NFKC', str(grade or '')).upper().replace(' ', '').replace('　', '')
    replacements = {'GI': 'G1', 'GII': 'G2', 'GIII': 'G3',
                    'FI': 'F1', 'FII': 'F2', 'PGI': 'PG1',
                    '特GI': '特G1'}
    return replacements.get(value, value)


def sort_meetings(items, category, venue_order=None):
    """Sort rows without mutating source data or inferring unknown attributes."""
    if category not in VENUES:
        raise ValueError('開催競技の分類が不明です: ' + str(category))
    sequence = list(venue_order if venue_order is not None else VENUES[category])
    venue_rank = {name: i for i, name in enumerate(sequence)}
    grade_rank = {name: i for i, name in enumerate(GRADE_RANK[category])}

    def key(row):
        name = str(row.get('name') or '')
        grade = canonical_grade(row.get('grade'))
        return (TIME_RANK.get(row.get('timeType'), 4),
                grade_rank.get(grade, len(grade_rank)),
                venue_rank.get(name, len(venue_rank)),
                name)

    return sorted(items, key=key)
