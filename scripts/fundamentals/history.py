"""Select official reports by observed gaps and retain only qualified missing facts."""
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
import hashlib
import json
from pathlib import Path

from . import esef

ROOT = Path(__file__).resolve().parent


@dataclass
class Report:
    key: str
    period: tuple
    metrics: frozenset
    profile: dict
    adapter: object = None


def periods(scope):
    for year in range(scope['start'], scope['end'] + 1):
        if scope['kind'] in ('fy', 'both'):
            yield ('fy', year, None)
        if scope['kind'] in ('fq', 'both'):
            for quarter in range(1, 5):
                yield ('fq', year, quarter)


def catalog(isin):
    from .reports import REPORTS
    for name in ('esef_profiles.json', 'esef_history_profiles.json'):
        for profile in json.loads((ROOT / name).read_text(encoding='utf-8')):
            if profile['isin'] != isin:
                continue
            # The filing for the period takes priority. Later comparative columns
            # can refer to a restated perimeter and require separate qualification.
            year = profile['years'][-1]
            yield Report('esef:' + profile['url'], ('fy', year, None), frozenset(esef.TAGS.values()), profile)

    for key, entry in REPORTS.items():
        if entry['identity']['isin'] != isin or not entry.get('history_metrics'):
            continue
        adapter = entry['adapter']
        for kind, start, end in entry['periods'][:1]:
            end = date.fromisoformat(end)
            quarter = (end.month - 1) // 3 + 1 if kind == 'fq' else None
            yield Report(key, (kind, end.year, quarter), frozenset(entry['history_metrics']), entry, adapter)


def slot(row):
    kind = row['period_type']
    if kind == 'snapshot':
        return (kind, row['as_of_at'], None)
    return (kind, int(row['fiscal_year']), int(row['fiscal_quarter']) if row['fiscal_quarter'] else None)


def inventory(rows):
    slots = {}
    for row in rows:
        key = (slot(row), row['metric_key'])
        if key in slots:
            raise ValueError('HISTORY_CONFLICT')
        slots[key] = row
    return slots


def candidates(scope, reports, stored):
    requested = set(periods(scope))
    scheduled = {}
    uncovered = set(requested)
    for report in reports:
        if report.period not in requested:
            continue
        if report.period in scheduled:
            raise ValueError('HISTORY_CONFLICT')
        uncovered.discard(report.period)
        missing = {m for m in report.metrics if (report.period, m) not in stored}
        scheduled[report.period] = (report, missing)
    return sorted(scheduled.values(), key=lambda item: item[0].period), uncovered


def same_fact(new, old, unit):
    if any(new[k] != old[k] for k in ('period_start', 'period_end', 'as_of_at')):
        return False
    if old['monetary_currency_code'] != unit['monetary_currency_code']:
        return False
    if old['monetary_currency_code'] is None and new['unit_key'] != old['unit_key']:
        return False
    # Cross-multiply exact decimals to avoid rounding in rational-unit conversion.
    from fractions import Fraction
    def scaled(row, numerator, denominator):
        return Fraction(Decimal(row['value_decimal'])) * int(numerator) / int(denominator)
    return scaled(new, unit['scale_numerator'], unit['scale_denominator']) == scaled(
        old, old['scale_numerator'], old['scale_denominator'])


def select_facts(plan, report, stored, scope):
    units = {row['unit_key']: row for row in plan['units']}
    selected = []
    indexes = []
    for index, row in enumerate(plan['observations']):
        period = slot(row)
        if period != report.period:
            continue
        key = (period, row['metric_key'])
        if key in stored:
            if not same_fact(row, stored[key], units[row['unit_key']]):
                raise ValueError('HISTORY_CONFLICT')
            continue
        indexes.append(index)
        selected.append(row.copy())
    if not selected:
        return None
    result = dict(plan, observations=selected, publish_current=False, history_scope=scope)
    result['metrics'] = [m for m in plan['metrics'] if m['metric_key'] in {r['metric_key'] for r in selected}]
    result['units'] = [u for u in plan['units'] if u['unit_key'] in {r['unit_key'] for r in selected}]
    if 'evidence_json' in plan:
        doc = json.loads(plan['evidence_json'])
        doc['facts'] = [doc['facts'][index] for index in indexes]
        for index, row in enumerate(selected):
            _, position = row['field_path'].split(';source=', 1)
            row['field_path'] = f'evidence:facts/{index};source={position}'
        raw = esef.encode(doc)
        result['evidence_json'] = raw.decode('utf-8')
        result['stored_evidence'] = dict(plan['stored_evidence'], bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return result
