"""Independent host-venue schedules for Hamamatsu and Sanyo.

Only a year/month-qualified official calendar and its 本場開催 row can
confirm a date beyond the present day. A dated today/tomorrow announcement
may confirm the immediate date, but never a historical/future occurrence.
An empty calendar result is NOT proof that no racing takes place.
"""
import calendar
from datetime import date, datetime, timedelta
import re
from unicodedata import normalize

from bs4 import BeautifulSoup

HAMAMATSU_CALENDAR = 'https://www.hamamatsuauto.jp/calendar/'
HAMAMATSU_HOME = 'https://www.hamamatsuauto.jp/'
SANYO_CALENDAR = 'https://sanyoauto.jp/calendar/'
SANYO_HOME = 'https://sanyoauto.jp/'


def clean(text):
    return normalize('NFKC', str(text or '')).replace('\u3000', ' ').strip()


def grade_from_event(label, u):
    text = clean(label).replace(' ', '')
    found = re.search(r'特G(?:III|II|I|[123])|SG|G(?:III|II|I|[123])', text, re.I)
    if found:
        return u.autorace_grade(found.group(0))
    if '普通' in text:
        return '普通'
    return None


def slot_from_event(label, u):
    text = clean(label)
    slot = u.race_time_type(text)
    if slot:
        return slot
    if re.search(r'(?<![A-Za-z])(?:OMN|MN)(?![A-Za-z])', text, re.I):
        return 'ミッドナイト'
    return 'デイ' if 'デイ' in text or 'アーリー' in text else None


def _event_row(table):
    for tr in table.find_all('tr'):
        cells = tr.find_all(['th', 'td'], recursive=False)
        if not cells:
            continue
        if clean(cells[0].get_text(' ', strip=True)).replace(' ', '') == '本場開催':
            return cells[1:]
    return []


def _date_header_valid(table, selected):
    """Reject unrelated tables and any month lacking a full day-number header."""
    for tr in table.find_all('tr'):
        cells = tr.find_all(['th', 'td'], recursive=False)
        numbers = []
        for cell in cells:
            value = clean(cell.get_text(' ', strip=True))
            if value.isdecimal():
                numbers.append(int(value))
        if len(numbers) >= min(15, calendar.monthrange(selected.year, selected.month)[1]) and \
                numbers[:3] == [1, 2, 3] and selected.day in numbers:
            return True
    return False


def month_grid_meetings(html, selected, venue, u):
    """Read year-qualified organizer tables; do not use 場外発売 rows.

    Both organizer pages have monthly date columns and a 本場開催 row.
    Colspans are dates, not event counts. A calendar that presents a race
    without a readable day-number row is deliberately not used.
    """
    soup = BeautifulSoup(html, 'html.parser')
    title = clean(soup.title.get_text(' ', strip=True)) if soup.title else ''
    if venue not in title or '開催日程' not in clean(soup.get_text(' ', strip=True)):
        raise ValueError(venue + '公式開催カレンダーの見出しがありません')
    target = re.compile(rf'(?<!\d){selected.year}\s*年\s*{selected.month}\s*月(?!\d)')
    matched = []
    for heading in soup.find_all(['h2', 'h3', 'h4', 'caption']):
        if not target.search(clean(heading.get_text(' ', strip=True))):
            continue
        table = heading.find_parent('table') if heading.name == 'caption' else heading.find_next('table')
        if table is None or not _date_header_valid(table, selected):
            continue
        cells = _event_row(table)
        col = 1
        for cell in cells:
            try:
                span = max(1, int(cell.get('colspan', 1)))
            except (ValueError, TypeError):
                span = 1
            first, last = col, col + span - 1
            col += span
            if not first <= selected.day <= last:
                continue
            # Accessible image alt text also carries the official grade/slot.
            label = clean(cell.get_text(' ', strip=True))
            for img in cell.find_all('img'):
                label += ' ' + clean(img.get('alt'))
            if not label or any(x in label for x in ('場外発売', '発売所')):
                continue
            gr = grade_from_event(label, u)
            slot = slot_from_event(label, u)
            if not gr and not slot:
                continue
            # When an event began in the prior month, its true day number
            # cannot be reconstructed from the current month's grid alone.
            day = None
            if span > 1 and (first > 1 or selected.day == 1):
                if first > 1:
                    start = date(selected.year, selected.month, first)
                    end = date(selected.year, selected.month, min(last, calendar.monthrange(selected.year, selected.month)[1]))
                    day = u.day_label(selected, start, end)
            matched.append({'name': venue, 'grade': gr, 'day': day,
                            'timeType': slot})
    if len(matched) > 1:
        distinct = {(x['grade'], x['day'], x['timeType']) for x in matched}
        if len(distinct) > 1:
            raise ValueError(venue + '公式カレンダーに対象日の開催が重複')
        return matched[:1]
    return matched


def homepage_meetings(html, selected, venue, u):
    """Conservative date-checked current-day backup, even if the page is stale.

    The page may still say 'tomorrow' after midnight: use its printed month/day,
    never the label as the date. Never apply a current homepage to past dates.
    """
    if abs((selected - datetime.now(u.TZ).date()).days) > 1:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    title = clean(soup.title.get_text(' ', strip=True)) if soup.title else ''
    if venue not in title:
        raise ValueError(venue + '公式トップページの見出しがありません')
    text = clean(soup.get_text(' ', strip=True))
    head = re.compile(r'(?:本日|今日|明日)のレース\s*(\d{1,2})月\s*(\d{1,2})日')
    for m in head.finditer(text):
        if (int(m.group(1)), int(m.group(2))) != (selected.month, selected.day):
            continue
        until_next = head.search(text, m.end())
        section = text[m.end():until_next.start() if until_next else m.end()+800]
        local = re.search(r'本場開催\s*(.*?)(?:場外開催|開催日程|出走表)', section)
        if not local:
            continue
        label = clean(local.group(1))[:220]
        if not label or '開催レースはありません' in label or 'レースはありません' in label:
            return []
        # A locally announced meeting is valid evidence of its venue/date.
        # Its grade and time category remain unknown if not explicitly given.
        return [{'name': venue, 'grade': grade_from_event(label, u),
                 'day': None, 'timeType': slot_from_event(label, u)}]
    return []
