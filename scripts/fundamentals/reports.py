"""Reviewed report registry. Adding an adapter/report does not require another workflow."""
from datetime import date
from . import pne, zeiss, pne_quarter, droneshield, droneshield_html
from scripts.fundamentals_pilot_once import PROFILES

REPORTS = {
    'droneshield-html-fy-2025': dict(adapter=droneshield_html,execution='fundamentals-droneshield-html-fy2025-20261101-01',
        authorization='MOSA2-REPORT-droneshield-html-fy-2025:',reusable_manual=True,retention='derived_evidence',
        identity=dict(isin=droneshield_html.ISIN,name='DroneShield'),
        preserve_assets=[dict(isin=pne.ISIN,name='PNE AG',observations=11,current=6),
                         dict(isin=zeiss.ISIN,name='Carl Zeiss Meditec',observations=20,current=10)],
        periods=[('fy','2025-01-01','2025-12-31'),('fy','2024-01-01','2024-12-31')]),
    'droneshield-fy-2025': dict(adapter=droneshield,execution='fundamentals-droneshield-fy2025-20261101-01',
        authorization='MOSA2-REPORT-droneshield-fy-2025:',reusable_manual=True,
        identity=dict(isin=droneshield.ISIN,name='DroneShield'),
        preserve_assets=[dict(isin=pne.ISIN,name='PNE AG',observations=11,current=6),
                         dict(isin=zeiss.ISIN,name='Carl Zeiss Meditec',observations=20,current=10)],
        periods=[('fy','2025-01-01','2025-12-31'),('fy','2024-01-01','2024-12-31')]),
    'pne-fy-2025': PROFILES['pne'],
    'zeiss-fy-2025': PROFILES['zeiss'],
    'pne-q1-2026': dict(adapter=pne_quarter,execution='fundamentals-pne-q1-2026-20261101-01',
        authorization='MOSA2-REPORT-pne-q1-2026:',reusable_manual=True,
        identity=dict(isin=pne.ISIN,name='PNE AG'),
        preserve_assets=[dict(isin=pne.ISIN,name='PNE AG',period_type='fy',observations=7,current=4),
                         dict(isin=zeiss.ISIN,name='Carl Zeiss Meditec',observations=20,current=10)],
        periods=[('fq','2026-01-01','2026-03-31'),('fq','2025-01-01','2025-03-31')]),
}
# Deliberate execution authority, separate from supported adapters. Only this GET is approved.
APPROVED_REPORTS = ('droneshield-html-fy-2025',)

def selection(keys):
    if not keys or len(keys)>8 or len(set(keys))!=len(keys) or any(k not in REPORTS for k in keys):
        raise ValueError('REPORT_SELECTION')
    for key in keys:
        report=REPORTS[key]
        if report['identity']['isin']!=report['adapter'].ISIN:raise ValueError('REPORT_IDENTITY')
        if not report['adapter'].URL.startswith(report['adapter'].SOURCE['base_url']):raise ValueError('REPORT_SOURCE')
        for kind,start,end in report.get('periods',[]):
            if kind not in ('fy','fq') or date.fromisoformat(start)>=date.fromisoformat(end):raise ValueError('REPORT_PERIOD')
    return [REPORTS[k] for k in keys]
