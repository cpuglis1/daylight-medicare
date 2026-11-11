#!/usr/bin/env python3
"""Rebuild the research L01 package from immutable receipts and source bytes.

No acceptance is generated here. Typed research facts are proposed canonical
interpretations; observations and conflicts are kept separately.
"""
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from l01_acquire import PACKAGE, ROOT, dump, require_research_revision

VERSION = 'l01-normalize/1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class SourceHTML(HTMLParser):
    """Small dependency-free parser retaining table, row and text block locators."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.blocks, self.text = [], [], []
        self.table = None
        self.row = None
        self.cell = None
        self.block = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.skip += 1
        if self.skip:
            return
        if tag == 'table' and self.table is None:
            self.table = {'id': dict(attrs).get('id'), 'rows': [], 'line': self.getpos()[0]}
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in {'td', 'th'} and self.row is not None:
            self.cell = []
        if tag in {'p', 'h1', 'h2', 'h3', 'h4', 'li'} and self.block is None:
            self.block = {'tag': tag, 'line': self.getpos()[0], 'text': []}

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.skip = max(0, self.skip - 1)
        if self.skip:
            return
        if tag in {'td', 'th'} and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table['rows'].append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None
        if self.block and tag == self.block['tag']:
            self.block['text'] = ' '.join(' '.join(self.block['text']).split())
            self.blocks.append(self.block)
            self.block = None

    def handle_data(self, data):
        if self.skip:
            return
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)
        if self.block:
            self.block['text'].append(data)


def cents(value):
    return int(Decimal(value.replace('$', '').replace(',', '').strip()) * 100)


def bounds(text):
    values = [cents(x) for x in re.findall(r'\$[\d,]+(?:\.\d+)?', text)]
    text = text.lower()
    if len(values) == 1 and text.startswith('less'):
        return {'lower_cents': None, 'upper_cents': values[0], 'lower_inclusive': False, 'upper_inclusive': True}
    if len(values) == 1 and text.startswith('greater than or equal'):
        return {'lower_cents': values[0], 'upper_cents': None, 'lower_inclusive': True, 'upper_inclusive': False}
    if len(values) == 2 and text.startswith('greater than'):
        return {'lower_cents': values[0], 'upper_cents': values[1], 'lower_inclusive': False, 'upper_inclusive': 'less than or equal' in text}
    raise ValueError('Unsupported income-bound syntax: ' + text)


def receipts(package):
    # Latest receipt is chosen explicitly in the immutable build output.
    result = {}
    for path in sorted(package.glob('acquisitions/*/*.json')):
        r = json.loads(path.read_text())
        r['receipt_path'] = str(path.relative_to(package))
        result[r['id']] = r
    return result


def build(package=PACKAGE):
    require_research_revision(package)
    rs = receipts(package)
    texts = {}
    parsers = {}
    for id, r in rs.items():
        if r['status'] != 'acquired':
            continue
        assert hashlib.sha256((package / r['artifact']).read_bytes()).hexdigest() == r['sha256']
        text = (package / r['extracted_artifact']).read_text()
        if r['media_type'] == 'text/html':
            parser = SourceHTML()
            parser.feed(text)
            parsers[id] = parser
            text = ' '.join(' '.join(parser.text).split())
        texts[id] = text
        # Current manual acquisition is not a blanket 2026 effective-date claim.
        r['content_year_verified'] = (2026 if id in {'CMS-ANNUAL', 'CMS-MM14279', 'FR-B', 'FR-A-DEDUCT', 'FR-A-PREMIUM', 'SSA-POMS-TABLE', 'DCF-59106'} and '2026' in text else None)
        r['temporal_scope'] = '2026 annual section only; historical columns excluded' if r['content_year_verified'] else 'Section-specific revision/effective dates required; no global benefit-year assertion'
        r['publication_date'] = r.get('publication_date')
        r['effective_interval'] = ['2026-01-01', '2027-01-01'] if id in {'CMS-ANNUAL', 'CMS-MM14279', 'FR-B', 'FR-A-DEDUCT', 'FR-A-PREMIUM'} else None
        r['proposed_review_cadence_days'] = 30
    observations, facts, bands, mappings = [], [], [], []

    def observation(id, source, locator, value, quote):
        r = rs[source]
        row = {'id': id, 'source_id': source, 'snapshot_sha256': r['sha256'], 'locator': locator,
               'observed': value, 'source_text': quote, 'transform': VERSION}
        observations.append(row)
        return id

    # Exact independent extraction anchors; assert every value against raw-derived text.
    specs = [
        ('a_premium_full', 'money', 56500, 'month', 'Part A base premium (BP): $565 a month', 'CMS-MM14279', 'p2', 'Voluntary full-premium category; entitlement not determined'),
        ('a_premium_reduced', 'money', 31100, 'month', '$311 a month', 'CMS-MM14279', 'p2', 'Voluntary reduced premium; 30–39 quarters or qualifying spouse conditions'),
        ('a_deductible', 'money', 173600, 'benefit_period', 'Part A deductible: $1,736', 'CMS-MM14279', 'p2', 'Covered inpatient services per benefit period; deductible liability exceptions remain relevant'),
        ('hospital_61_90', 'money', 43400, 'covered_day', '$434 a day for days 61–90', 'CMS-MM14279', 'p2', 'Days counted within the same benefit period'),
        ('hospital_reserve', 'money', 86800, 'covered_day', '$868 a day for days 91–150', 'CMS-MM14279', 'p2', 'Only elected available lifetime reserve days; at most 60 lifetime'),
        ('snf_21_100', 'money', 21700, 'covered_day', '$217 a day for days 21–100', 'CMS-MM14279', 'p2', 'Qualifying covered SNF services within benefit period; entitlement/coverage supplied separately'),
        ('b_premium', 'money', 20290, 'month', '$202.90 a month', 'CMS-MM14279', 'p3', 'Standard full B before adjustments, protection, assistance, reduction or penalties'),
        ('b_deductible', 'money', 28300, 'calendar_year', '$283 a year', 'CMS-MM14279', 'p3', 'Deductible applies only to subject covered services; not inevitable spending'),
        ('immuno_premium', 'money', 12160, 'month', '$121.60 a month', 'CMS-MM14279', 'p3', 'Immunosuppressive-only Part B context; not full B'),
        ('b_coinsurance', 'rate', {'numerator': 20, 'denominator': 100}, 'service', 'Part B coinsurance: 20%', 'CMS-MM14279', 'p3', 'Ordinary applicable service, after deductible; Medicare-approved charge basis; exceptions not generalized'),
    ]
    for id, kind, value, period, quote, source, locator, condition in specs:
        assert quote in texts[source], (id, quote)
        obs = observation('OBS-' + id, source, locator, value, quote)
        facts.append({'id': id, 'version': '2026-r1', 'coverage_context': 'immuno_b' if id.startswith('immuno') else 'full_b' if id.startswith('b_') else 'part_a',
                      'jurisdiction': 'US-federal-50-states-DC', 'effective_from': '2026-01-01', 'effective_until': '2027-01-01',
                      'value_type': kind, 'value': value, 'currency': 'USD' if kind == 'money' else None,
                      'unit': 'cents' if kind == 'money' else 'fraction_of_Medicare_approved_amount', 'period': period,
                      'conditions': condition, 'cost_basis': 'Medicare-approved charge' if kind == 'rate' else 'published federal obligation',
                      'observation_ids': [obs], 'canonical_status': 'proposed_research', 'conflict_ids': ['L01-G09'] if id == 'a_deductible' else []})
    contextual = [
        ('home_services_base', 'money', 0, 'service', 'MANUAL-HOME', '100-02 ch7 §60.4; Rev233 effective 2017-01-01', 'There is no coinsurance, copayment, or deductible for home health services and supplies', 'Covered home services except DME, disposable NPWT and osteoporosis-drug exceptions; coverage conditions not determined', 'published covered-service base'),
        ('home_dme_rate', 'rate', {'numerator':20,'denominator':100}, 'service', 'MANUAL-HOME', '100-02 ch7 §60.4; Rev233 effective 2017-01-01', '20 percent of the fee schedule amount', 'DME furnished under home health benefit; approved fee-schedule input required', 'fee_schedule_amount'),
        ('home_npwt_rate', 'rate', {'numerator':20,'denominator':100}, 'service', 'MANUAL-HOME', '100-02 ch7 §60.4; Rev233 effective 2017-01-01', '20 percent of the payment amount', 'Disposable NPWT furnishing home health service; payment basis differs from DME fee schedule', 'Medicare_payment_amount'),
        ('hospice_drug_cap', 'formula', {'schedule':'hospice_MAC_approved','approximate_rate':{'numerator':5,'denominator':100},'maximum_cents':500}, 'prescription', 'MANUAL-HOSPICE', '100-02 ch9 §30.1; Rev188 effective 2014-08-04', 'may not exceed $5.00', 'Palliative prescription during routine/continuous home care; no related-drug coinsurance during general inpatient/respite care; do not substitute plan drug pricing', 'hospice_drug_cost_and_approved_schedule'),
        ('hospice_respite_rate', 'rate', {'numerator':5,'denominator':100}, 'covered_day', 'MANUAL-HOSPICE', '100-02 ch9 §30.2; Rev188 effective 2014-08-04', '5 percent of the payment', 'Capped by inpatient deductible for year hospice coinsurance period began; period ends after14 consecutive days without election; not a universal annual hospice cap', 'Medicare_respite_day_payment'),
    ]
    for id, kind, value, period, source, locator, quote, condition, basis in contextual:
        assert quote in ' '.join(texts[source].split()), id
        obs = observation('OBS-' + id, source, locator, value, quote)
        facts.append({'id':id,'version':'2026-r1','coverage_context':'home_health' if id.startswith('home') else 'hospice',
                      'jurisdiction':'US-federal-50-states-DC','effective_from':'2026-01-01','effective_until':'2027-01-01',
                      'value_type':kind,'value':value,'currency':'USD' if kind in {'money','formula'} else None,
                      'unit':'cents' if kind=='money' else 'typed_formula' if kind=='formula' else 'fraction_of_'+basis,
                      'period':period,'cost_basis':basis,'conditions':condition,'observation_ids':[obs],
                      'canonical_status':'proposed_research_section_temporality_pending','conflict_ids':[],
                      'calculation_status':'lookup_only_no_executable_personal_calculation'})
    # All CMS annual tables, headers, rows and paragraphs remain source-indexed.
    annual = parsers['CMS-ANNUAL']
    selected = [t for t in annual.tables if any(any('modified adjusted gross' in c.lower() for c in row) for row in t['rows'])]
    assert len(selected) == 6, 'Annual table inventory changed; review new denominator'
    contexts = [('full_b', ['individual', 'joint']), ('immuno_b', ['individual', 'joint']),
                ('full_b', ['separate_together']), ('immuno_b', ['separate_together']),
                ('part_d', ['individual', 'joint']), ('part_d', ['separate_together'])]
    for ti, (table, (context, filings)) in enumerate(zip(selected, contexts), 1):
        row_number = 0
        for ri, row in enumerate(table['rows'], 1):
            locator = f'HTML table {ti}, row {ri}, source line {table["line"]}'
            if not row or not row[0].startswith(('Less than', 'Greater than')):
                mappings.append({'source_id': 'CMS-ANNUAL', 'locator': locator, 'row': row, 'disposition': 'table_heading', 'obligations': []})
                continue
            rowid = f'OBS-CMS-T{ti}-R{ri}'
            observation(rowid, 'CMS-ANNUAL', locator, row, ' | '.join(row))
            mapped = []
            for fi, filing in enumerate(filings):
                id = f'L01-IRMAA-{context}-{filing}-{row_number}'
                base = 20290 if context == 'full_b' else 12160 if context == 'immuno_b' else None
                adjustment = cents(row[len(filings)])
                total = cents(row[len(filings) + 1]) if context != 'part_d' else None
                assert total is None or base + adjustment == total, id
                bands.append({'id': id, 'version': '2026-r1', 'premium_year': 2026, 'coverage_context': context,
                              'filing_status': filing, 'living_arrangement': 'together_any_time_in_tax_year' if filing == 'separate_together' else None,
                              **bounds(row[fi]), 'income_precision': 'USD cents', 'base_cents': base,
                              'adjustment_cents': adjustment, 'published_total_cents': total, 'period': 'month', 'currency': 'USD',
                              'tax_return_basis': {'normal_year': 2024, 'fallback_year': 2023, 'requires_basis_confirmation': True},
                              'jurisdiction': 'US-federal-50-states-DC', 'effective_from': '2026-01-01', 'effective_until': '2027-01-01',
                              'observation_ids': [rowid], 'canonical_status': 'proposed_research',
                              'conflict_ids': (['L01-G04'] + (['L01-G03'] if context == 'full_b' and row_number == 2 else [])) if filing == 'separate_together' and context != 'part_d' and row_number > 0 else []})
                mapped.append(id)
            mappings.append({'source_id': 'CMS-ANNUAL', 'locator': locator, 'row': row, 'disposition': 'normalized', 'obligations': mapped})
            row_number += 1
        assert row_number == (6 if len(filings) == 2 else 3)
    for bi, block in enumerate(annual.blocks):
        if any(word in block['text'].lower() for word in ['2026', 'premium', 'taxable', 'income-related', 'coverage', 'deductible']):
            mappings.append({'source_id': 'CMS-ANNUAL', 'locator': f'{block["tag"]} block {bi}, source line {block["line"]}',
                             'text': block['text'], 'disposition': 'context_retained_requires_domain_review', 'obligations': ['L01-B-immuno_entitlement'] if '36 months' in block['text'] else []})
    # Do not discard bulletin operational fields merely because L01 does not own them.
    operational = [('Part A BP with 10% surcharge: $621.50', 'L13'), ('$342.10 a month', 'L13'),
                   ('$191.17 first month', 'CMS operational pro-rata; not personal premium'), ('$91.83 second month', 'CMS operational pro-rata; not personal premium')]
    for i, (quote, owner) in enumerate(operational):
        assert quote in texts['CMS-MM14279']
        observation(f'OBS-MM-OP-{i}', 'CMS-MM14279', 'pp2–3', {'raw': quote, 'owner': owner}, quote)
        mappings.append({'source_id': 'CMS-MM14279', 'locator': 'pp2–3: ' + quote, 'disposition': 'operational_or_other_layer', 'owner': owner, 'obligations': []})
    # All 2026 POMS rows and their footnotes: other years remain explicit exclusions.
    poms = parsers['SSA-POMS-TABLE']
    for ti, table in enumerate(poms.tables):
        is2026 = any('2024 (or 2023' in c for row in table['rows'] for c in row)
        for ri, row in enumerate(table['rows']):
            if not is2026:
                continue
            locator = f'HTML {table["id"] or ti}, row {ri + 1}'
            observation(f'OBS-POMS-T{ti}-R{ri}', 'SSA-POMS-TABLE', locator, row, ' | '.join(row))
            mappings.append({'source_id': 'SSA-POMS-TABLE', 'locator': locator, 'row': row,
                             'disposition': '2026_corroboration' if any('$' in c for c in row) else '2026_header', 'obligations': ['L01-APPLICABILITY-tax_year_normal', 'L01-APPLICABILITY-older_return_fallback']})
    # Formal notice: retain EVERY income table row with section/page, including repeats.
    for page, text in enumerate(texts['FR-B'].split('\f'), 1):
        for li, line in enumerate(text.splitlines(), 1):
            if re.search(r'(Less than or equal|Greater than).*\$[\d,]+', line):
                observation(f'OBS-FR-B-P{page}-L{li}', 'FR-B', f'PDF page {page}, line {li}', {'raw': line.strip()}, line.strip())
                mappings.append({'source_id': 'FR-B', 'locator': f'PDF page {page}, line {li}', 'text': line.strip(),
                                 'disposition': 'retained_comparison_conflict_if_repeated_500000', 'obligations': ['L01-RECONCILIATION-fr_391000_vs_500000']})
    formal_tables, comparisons = [], []
    if 'FR-B-XML' in rs and rs['FR-B-XML']['status'] == 'acquired':
        xml = ET.fromstring((package / rs['FR-B-XML']['artifact']).read_bytes())
        for ti, table in enumerate(xml.iter('GPOTABLE'), 1):
            title = ' '.join(''.join(table.find('TTITLE').itertext()).split())
            context = 'immuno_b' if title.startswith('Part B Immuno') else 'full_b' if title == 'Full Part B Coverage' else None
            rows = [[' '.join(''.join(c.itertext()).split()) for c in row.findall('ENT')] for row in table.findall('ROW')]
            notes = [' '.join(''.join(note.itertext()).split()) for note in table.findall('TNOTE')]
            formal_tables.append({'table': ti, 'title': title, 'row_count': len(rows), 'notes': notes, 'disposition': 'consumer_premium_comparison' if context else 'actuarial_or_operational_not_beneficiary_bill'})
            for ri, row in enumerate(rows, 1):
                locator = f'2025-20251 XML GPOTABLE[{ti}] ROW[{ri}]'
                ids = []
                if context and row and row[0].startswith(('Less than', 'Greater than')):
                    filings = ['individual', 'joint'] if len(row) == 4 else ['separate_together']
                    for fi, filing in enumerate(filings):
                        published_bounds = bounds(row[fi])
                        # Keep nonmatching repeated thresholds as disagreements, never coerce.
                        matches = [b for b in bands if b['coverage_context'] == context and b['filing_status'] == filing and all(b[k] == v for k, v in published_bounds.items())]
                        match = matches[0] if len(matches) == 1 else None
                        ids += [match['id']] if match else ['L01-RECONCILIATION-fr_391000_vs_500000']
                        comparisons.append({'source_id': 'FR-B-XML', 'locator': locator, 'context': context, 'filing_status': filing, 'bounds': published_bounds,
                                            'adjustment_cents': cents(row[len(filings)]), 'total_cents': cents(row[len(filings) + 1]), 'band_id': match['id'] if match else None,
                                            'comparison': 'equal' if match and match['adjustment_cents'] == cents(row[len(filings)]) and match['published_total_cents'] == cents(row[len(filings) + 1]) else 'conflict'})
                mappings.append({'source_id': 'FR-B-XML', 'locator': locator, 'row': row, 'obligations': ids,
                                 'disposition': 'compared_or_conflicting' if context else 'actuarial_or_operational_not_beneficiary_bill'})
            for ni, note in enumerate(notes, 1):
                mappings.append({'source_id': 'FR-B-XML', 'locator': f'GPOTABLE[{ti}] TNOTE[{ni}]', 'text': note, 'disposition': 'retained_table_footnote_requires_review', 'obligations': []})
    dump(package / 'formal-table-inventory.json', formal_tables)
    dump(package / 'field-comparisons.json', comparisons)
    # Exact reverified conflicting observation. SSA public raw fetch was denied;
    # its earlier permitted web-rendered observation is separately identified.
    dcf_quote = '$1,736 (annual)'
    assert dcf_quote in texts['DCF-59106']
    observation('OBS-DCF-ANNUAL', 'DCF-59106', 'p1, 2026 Medicare Premiums, Part A row', {'value_cents': 173600, 'period': 'annual'}, dcf_quote)
    for value in ['391,000', '500,000']:
        assert value in texts['FR-B']
    conflicts = [
        {'id': 'L01-G03', 'observations': ['SSA public web table: standard + $487.90 (raw fetch 403)', 'CMS annual T3: $487.00 adjustment/$689.90 total', 'POMS 2026 married-separate: $689.90 total'],
         'affected': ['L01-IRMAA-full_b-separate_together-2'], 'proposed_disposition': 'Use $487.00 as proposed research canonical adjustment: formal Part B determination publishes adjustment and total, while $202.90 + $487.90 does not equal $689.90. This is an authority-and-arithmetic proposal, not acceptance or a correction to SSA source.',
         'required_closure': 'Qualified SSA/Medicare reviewer receipt accepting exact adjustment and arithmetic basis; preserve denied raw-source gap'},
        {'id': 'L01-G04', 'observations': ['FR 52067 initial full-B and immuno married-separate tables: $391,000', 'FR 52072 full-B and 52073 immuno repeated determination tables: $500,000', 'CMS annual married-separate tables: $391,000'],
         'affected': [b['id'] for b in bands if 'L01-G04' in b['conflict_ids']],
         'proposed_disposition': 'Propose $391,000 from the filing-status-specific statutory threshold derivation and initial tables; repeated $500,000 appears to reuse the individual top threshold. FR metadata corrections array is empty at retrieval. No correction found is bounded search evidence, not proof of none; qualified interpretation still required.',
         'required_closure': 'Qualified reviewer governing-section/statutory analysis or applicable correction receipt, including immuno coverage context'},
        {'id': 'L01-G09', 'observations': ['DCF Appendix A-9.1 p1: $1,736 (annual)', 'CMS MM14279 p2: deductible during a spell of illness', 'CMS General Information ch3 §10.1: each benefit period'],
         'affected': ['a_deductible', 'hospital_stay'], 'proposed_disposition': 'Use federal benefit-period basis in research. DCF is state assistance material and cannot govern federal Part A cost period. Preserve its annual label verbatim. No source-owner correction requested.',
         'required_closure': 'Qualified reviewer accepts federal period and source hierarchy for L01; DCF observation remains in L12 evidence'},
    ]
    for c in conflicts:
        c.update(status='proposed_pending_independent_review', responsible_role='qualified Medicare/SSA rules reviewer', discovered_date='2026-10-25', last_checked_date='2026-10-25')
    fact_checks=[]
    checks={'a_premium_full':'FR-A-PREMIUM','a_premium_reduced':'FR-A-PREMIUM','a_deductible':'FR-A-DEDUCT',
            'hospital_61_90':'FR-A-DEDUCT','hospital_reserve':'FR-A-DEDUCT','snf_21_100':'FR-A-DEDUCT',
            'b_premium':'CMS-ANNUAL','b_deductible':'CMS-ANNUAL','immuno_premium':'CMS-ANNUAL','b_coinsurance':'GENERAL-COSTS'}
    for fact in facts:
        source=checks.get(fact['id'])
        if source:
            amount=Decimal(fact['value'])/100 if fact['value_type']=='money' else Decimal(20)
            pattern=r'(?<![\d.])\$?'+re.escape(format(amount,',.2f').removesuffix('.00'))+r'(?:\.00)?(?![\d.])' if fact['value_type']=='money' else r'\b20\s*percent\b'
            match=re.search(pattern,texts[source])
            assert match,(fact['id'],source,pattern)
            fact_checks.append({'fact_id':fact['id'],'source_id':source,'snapshot_sha256':rs[source]['sha256'],
                                'locator':f'raw-derived text characters {match.start()}–{match.end()}; annual determination/premium context',
                                'matched_source_text':match.group(0),'comparison':'equal_value',
                                'conditions_and_period_review':'Separate from numeric equality; exact source section and conflict packet still require domain review'})
        else:
            fact_checks.append({'fact_id':fact['id'],'comparison':'missing_designated_crosscheck','reason':'Primary manual observation retained; secondary claim-specific evidence not acquired'})
    dump(package/'fact-comparisons.json',fact_checks)
    rule_specs = [
        ('premium_months', 'Explicit unique YYYY-MM covered months; no automatic annualization. Select A category only if explicitly provided; omit A if not requested.', ['covered_months', 'coverage_context'], ['CMS-MM14279'], ['premiums']),
        ('irmaa', '2026 normal 2024 MAGI or a sufficient single-band income range; explicitly confirmed 2023 fallback only because 2024 unavailable. Exact income is optional. Never infer SSA determination. Separate filing requires lived-together condition; lived-apart, amended/new return or changed-income route is withheld for official determination.', ['filing_status', 'magi_cents_or_single_band_range', 'tax_year', 'return_basis', 'lived_together_if_separate'], ['SSA-POMS-TABLE', 'SSA-LIVED-APART', 'SSA-NEW-DETERMINATION'], ['irmaa']),
        ('hospital', 'Covered inpatient day indices in one stated benefit period. Deductible context explicitly reported; reserve election and remaining lifetime days supplied. Unknown charges beyond coverage are not zero. Coinsurance uses service-year package; cross-year deductible requires that year package.', ['first_day', 'days', 'benefit_period_start', 'deductible_satisfied', 'reserve_remaining', 'use_reserve', 'coverage_confirmed'], ['CMS-MM14279', 'MANUAL-DURATION', 'MANUAL-RESERVE', 'GENERAL-COSTS'], ['hospital_stay']),
        ('snf', 'Scenario assumes qualifying covered SNF services; no eligibility or 3-day-stay determination. Count cumulative covered days in benefit period. Days over 100 have unavailable actual charges.', ['first_day', 'days', 'coverage_confirmed'], ['CMS-MM14279', 'MANUAL-SNF-EXACT'], ['snf_stay']),
        ('benefit_reset', '60 consecutive qualifying days outside inpatient status as defined by General Information §10.4.2–10.4.4. A different diagnosis and January 1 do not reset the period. Caller must confirm the rule-specific inpatient definition.', ['days_out', 'inpatient_definition_confirmed'], ['MANUAL-DURATION', 'GENERAL-COSTS'], ['benefit_reset']),
        ('ordinary_b', 'Only explicitly applicable ordinary B services; after remaining annual deductible, 20% of Medicare-approved amount. No rate-only bill. Service-specific waivers/facility/excess charges and other layers remain outside this component.', ['approved_charge_cents', 'deductible_remaining_cents', 'ordinary_rule_confirmed'], ['CMS-MM14279', 'GENERAL-COSTS'], ['ordinary_b']),
    ]
    rules = [{'id': id, 'version': '2026-r1', 'conditions': text, 'required_inputs': inputs, 'source_sections': [{'source_id': s, 'locator': 'p2–3' if s == 'CMS-MM14279' else '2026 section B and notes' if s == 'SSA-POMS-TABLE' else 'chapter sections named in conditions; see source-index.json'} for s in sources], 'supported_outputs': outputs, 'status': 'proposed_research', 'exception_route': 'unresolved; official determination or owning layer'} for id, text, inputs, sources, outputs in rule_specs]
    exact_sections = {
        'CMS-MM14279': 'pp2–3; Background and Key Updates (effective 2026-01-01)',
        'SSA-POMS-TABLE': 'HI 01101.020 §B1–B3 and both footnotes and NOTE (effective 2025-12-02, explicitly premium year 2026)',
        'SSA-LIVED-APART': 'HI 01120.060 §A (effective 2011-10-04; new determination, not automatic user assumption)',
        'SSA-NEW-DETERMINATION': 'HI 01120.001 §A and §B (effective 2026-06-05; historical applicability before that date not established)',
        'MANUAL-DURATION': '100-02 ch3 §10 and §20 (Rev261, effective 2019-11-05)',
        'MANUAL-RESERVE': '100-02 ch5 §10 and §20 (section revisions retained; see temporal-audit.json)',
        'GENERAL-COSTS': '100-01 ch3 §10.1, §10.2.1, §10.4.2–10.4.4, §20.2–20.4 (annual chart is older; amounts from MM14279)',
        'MANUAL-SNF-EXACT': '100-02 ch8 §20, §30 and §40 (coverage predicates not evaluated; conditional scenario only)',
    }
    for rule in rules:
        for section in rule['source_sections']:
            section['locator'] = exact_sections[section['source_id']]
        rule['temporal_limit'] = '2026 published scenario only; source section revisions retained. Changed-income/amended-return routes return unavailable, including historical requests.'
    initial = json.loads((package / 'expected-inventory.json').read_text())
    inventory = json.loads(json.dumps(initial))
    inventory['version'] = '2026-r1-discovery-1'
    inventory['revision_reason'] = 'Add service-specific preventive inventory from acquired claims manual TOC; preserve initial broad and MVP obligations.'
    inventory['version'] = '2026-r1-discovery-2'
    inventory['revision_reason'] += ' Add distinct home-health disposable NPWT and hospice drug/respite applicability observations; source attempts separated from document obligations.'
    inventory['obligations'].append({'id':'L01-HOME_HOSPICE-home_npwt','group':'HOME_HOSPICE','concept':'home disposable negative pressure wound therapy cost basis','scope':'broad','status':'required','required_fields':['value_or_rule','period','conditions','source_locator','effective_interval']})
    # Explicit service section obligations from the top-level preventive TOC.
    toc = texts['CLAIMS-PREVENTIVE'].split('1 - Medicare Preventive and Screening Services', 2)[1]
    for section, title in re.findall(r'^\s*(\d+) - ([^\n]+)', toc, re.M):
        if section == '1':
            continue
        oid = 'L01-PREVENTIVE-' + section
        if any(o['id'] == oid for o in inventory['obligations']):
            continue
        inventory['obligations'].append({'id': oid, 'group': 'SERVICE', 'concept': title.strip(), 'scope': 'broad', 'status': 'required', 'required_fields': ['cost_sharing', 'coverage_conditions', 'exceptions', 'effective_interval'], 'source_section': {'source_id': 'CLAIMS-PREVENTIVE', 'locator': 'chapter18 §' + section}})
    fact_obligations = {
        'a_premium_full': 'L01-A-premium_full_conditions', 'a_premium_reduced': 'L01-A-premium_reduced_conditions',
        'a_deductible': 'L01-A-hospital_deductible_period', 'hospital_61_90': 'L01-A-hospital_days_61_90',
        'hospital_reserve': 'L01-A-hospital_reserve_days', 'snf_21_100': 'L01-A-snf_days_21_100',
        'b_premium': 'L01-B-standard_premium', 'b_deductible': 'L01-B-annual_deductible', 'b_coinsurance': 'L01-B-ordinary_coinsurance', 'immuno_premium': 'L01-B-immuno_premium',
        'home_services_base':'L01-HOME_HOSPICE-home_services','home_dme_rate':'L01-HOME_HOSPICE-home_equipment','home_npwt_rate':'L01-HOME_HOSPICE-home_npwt','hospice_drug_cap':'L01-HOME_HOSPICE-hospice_drugs','hospice_respite_rate':'L01-HOME_HOSPICE-hospice_respite'}
    rules_obligations = {'benefit_reset': ['L01-A-benefit_period_reset'], 'hospital': ['L01-A-hospital_days_1_60', 'L01-A-hospital_reserve_exhaustion', 'L01-A-hospital_cross_year'],
                        'snf': ['L01-A-snf_days_1_20', 'L01-A-snf_exhaustion'], 'irmaa': ['L01-APPLICABILITY-tax_year_normal', 'L01-APPLICABILITY-older_return_fallback', 'L01-APPLICABILITY-separate_lived_together'], 'ordinary_b': ['L01-B-approved_charge_basis']}
    supported_ids = set(fact_obligations.values()) | {b['id'] for b in bands} | {o for v in rules_obligations.values() for o in v}
    for o in inventory['obligations']:
        o['implementation_status'] = 'research_supported' if o['id'] in supported_ids else 'unsupported_or_dependency'
        o['source_section'] = o.get('source_section') or {'source_id': 'CMS-ANNUAL' if o['group'] == 'IRMAA' else 'GENERAL-COSTS' if o['group'] in {'A', 'B'} else 'CLAIMS-PREVENTIVE' if o['group'] == 'SERVICE' else 'SSA-POMS-TABLE' if o['group'] == 'APPLICABILITY' else 'MEDICARE-BENEFITS', 'locator': 'Exact normalized observation/rule where supported; otherwise open source-section mapping obligation'}
        o['independently_reviewed'] = False
        o['enabled_runtime'] = False
        o['backing_records'] = ['fact:'+id for id,oid in fact_obligations.items() if oid==o['id']] + ['rule:'+id for id,oids in rules_obligations.items() if o['id'] in oids] + (['band:'+o['id']] if o['group']=='IRMAA' else [])
        o['locator_status'] = 'exact_normalized_observation_or_rule' if o['id'] in supported_ids or o['id'].startswith('L01-PREVENTIVE-') else 'unresolved_locator_gap'
        if o['id'] in [fact_obligations[id] for id,*_ in specs]:
            o['scope'] = 'mvp'
    # Source-indexed service exception register. Documentation is kept separate
    # from executable support and never counted as implemented coverage.
    service_sections = {
        'home_services':('MANUAL-HOME','60.4'), 'home_equipment':('MANUAL-HOME','60.4'), 'home_npwt':('MANUAL-HOME','60.4'),
        'hospice_drugs':('MANUAL-HOSPICE','30.1'), 'hospice_respite':('MANUAL-HOSPICE','30.2'),
        'preventive_zero_conditions':('CLAIMS-PREVENTIVE','1.3'), 'preventive_diagnostic_conversion':('CLAIMS-PREVENTIVE','20.3'),
        'laboratory':('MANUAL-MEDICAL','80.1'), 'outpatient_hospital':('MANUAL-OUTPATIENT','20'),
        'mental_health_outpatient':('MANUAL-MEDICAL','170'), 'dme_rental_purchase':('MANUAL-MEDICAL','110'),
        'therapy':('MANUAL-MEDICAL','220'), 'telehealth':('MANUAL-MEDICAL','270'), 'vaccines':('CLAIMS-PREVENTIVE','10'),
        'blood':('GENERAL-COSTS','20.5'), 'observation_vs_inpatient':('MANUAL-OUTPATIENT','20.6'),
        'foreign_care':('MANUAL-EXCLUSIONS','60'), 'home_infusion':('MANUAL-MEDICAL','320'),
        'behavioral_partial_hospital':('MANUAL-OUTPATIENT','70.3'), 'dental_exceptions':('MANUAL-MEDICAL','150'),
    }
    exception_register = []
    for o in inventory['obligations']:
        key = o['concept']
        section = ('CLAIMS-PREVENTIVE',o['id'].split('-')[-1]) if o['id'].startswith('L01-PREVENTIVE-') else service_sections.get(key)
        if not section:
            continue
        source, number = section
        text = texts[source]
        matches = list(re.finditer(r'^\s*' + re.escape(number) + r'\s*[–-]\s*[^\n]+', text, re.M))
        body = next((hit for hit in reversed(matches) if '(Rev.' in text[hit.end():hit.end()+240]), None)
        if body is None:
            continue
        after = text[body.end():]
        next_heading = re.search(r'\n\s*\d+(?:\.\d+)*\s*[–-]\s*[^\n]+\n\(Rev\.', after)
        end = body.end()+next_heading.start() if next_heading else min(body.start()+6000,len(text))
        excerpt = text[body.start():end].strip()
        o['source_section']={'source_id':source,'locator':f'§{number}; extracted text characters {body.start()}–{end}'}
        o['locator_status']='exact_section_observed_temporal_review_pending'
        exception_register.append({'obligation_id':o['id'],'source_id':source,'snapshot_sha256':rs[source]['sha256'],'locator':o['source_section']['locator'],
                                   'section_text':excerpt,'revision_headers':re.findall(r'\(Rev\.[^)]{1,240}\)',excerpt),
                                   'status':'observed_unaccepted_not_executable','cost_basis_and_exceptions':'Section text retained; exact conditions and historical applicability require qualified review'})
    dump(package/'service-exceptions.json',exception_register)
    dump(package/'correction-history.json',[
        {'source_id':id,'notice_document':json.loads((package/rs[id]['artifact']).read_text()).get('document_number'),
         'corrections':json.loads((package/rs[id]['artifact']).read_text()).get('corrections'),
         'status':'No linked correction in retrieved official metadata; bounded evidence, not proof none exists',
         'retrieved_at_utc':rs[id]['retrieved_at_utc'],'sha256':rs[id]['sha256']}
        for id in ['FR-B-METADATA','FR-A-DEDUCT-METADATA','FR-A-PREMIUM-METADATA'] if rs.get(id,{}).get('status')=='acquired'])
    dependencies = [
        {'id': id, 'owner': owner, 'status': 'external_unresolved', 'effect': effect} for id, owner, effect in [
            ('assistance', 'L12', 'Payment effects and protection do not rewrite federal base amounts'),
            ('penalties', 'L13', 'Penalty determination and amount; never inferred by L01'),
            ('plan_premiums', 'plan layer', 'Part D plan premium; add L01 D IRMAA once only'),
            ('medigap', 'Medigap layer', 'Supplement premium and coverage of cost sharing'),
            ('drug_prices', 'drug layer', 'Drug utilization and out-of-pocket prices'),
            ('approved_charges', 'charge/fee layer', 'Location-specific actual Medicare-approved amounts'),
            ('utilization', 'personal scenario', 'Covered dates, services, benefit periods, reserve history and coverage'),
            ('eligibility', 'enrollment/entitlement layer', 'A category, immuno entitlement, covered SNF and service conditions')]]
    capabilities = {
        'published_standard': {'facts': [f['id'] for f in facts if f['coverage_context'] in {'part_a','full_b','immuno_b'}], 'rules': [], 'sources': ['CMS-MM14279'], 'output_schema': 'l01-result/1'},
        'premiums': {'facts': ['a_premium_full', 'a_premium_reduced', 'b_premium', 'immuno_premium'], 'rules': ['premium_months'], 'sources': ['CMS-MM14279'], 'output_schema': 'l01-result/1'},
        'irmaa': {'facts': [], 'rules': ['irmaa', 'premium_months'], 'band_ids': [b['id'] for b in bands], 'sources': ['CMS-ANNUAL', 'SSA-POMS-TABLE', 'FR-B'], 'output_schema': 'l01-result/1'},
        'hospital_stay': {'facts': ['a_deductible', 'hospital_61_90', 'hospital_reserve'], 'rules': ['hospital'], 'sources': ['CMS-MM14279', 'GENERAL-COSTS', 'MANUAL-RESERVE', 'MANUAL-DURATION'], 'output_schema': 'l01-result/1'},
        'snf_stay': {'facts': ['snf_21_100'], 'rules': ['snf'], 'sources': ['CMS-MM14279', 'MANUAL-SNF-EXACT'], 'output_schema': 'l01-result/1'},
        'ordinary_b': {'facts': ['b_deductible', 'b_coinsurance'], 'rules': ['ordinary_b'], 'sources': ['CMS-MM14279', 'GENERAL-COSTS'], 'output_schema': 'l01-result/1'},
        'benefit_reset': {'facts': [], 'rules': ['benefit_reset'], 'sources': ['GENERAL-COSTS', 'MANUAL-DURATION'], 'output_schema': 'l01-result/1'},
        'published_cost_lookup': {'facts':[f['id'] for f in facts], 'band_ids':[b['id'] for b in bands], 'rules':[], 'sources':['CMS-MM14279','CMS-ANNUAL','SSA-POMS-TABLE','FR-B','MANUAL-HOME','MANUAL-HOSPICE'], 'output_schema':'l01-result/1'},
    }
    gaps = []
    descriptions = {'G01': 'Structured research package now exists; acceptance pending', 'G02': 'Inventory versioned; broad service completeness remains partial', 'G03': 'SSA adjustment disagreement', 'G04': 'Formal repeated threshold disagreement', 'G05': 'Broad exception/applicability obligations remain unsupported', 'G06': 'Capability adapter implemented separately from legacy gate; pending receipts', 'G07': 'No real independent reviewer acceptance supplied', 'G08': 'Personal total depends on other layers and personal facts', 'G09': 'DCF deductible period disagreement'}
    for id, description in descriptions.items():
        gaps.append({'id': 'L01-' + id, 'description': description, 'status': 'pending_independent_review' if id in {'G03','G04','G07','G09'} else 'partial_or_external', 'affected_obligations': [o['id'] for o in inventory['obligations'] if o['implementation_status'] != 'research_supported'] if id == 'G05' else next((c['affected'] for c in conflicts if c['id'] == 'L01-' + id), []), 'blocked_output': 'Dependent consumer capabilities; personal total/recommendations always unavailable', 'responsible_role': 'qualified Medicare/SSA rules reviewer' if id in {'G03','G04','G07','G09'} else 'engineering / owning layer', 'next_action': 'Review exact versioned evidence, resolve consequential exceptions and obtain genuine scoped receipt' if id in {'G03','G04','G07','G09'} else 'Close listed obligations and dependencies with year-correct evidence', 'required_closure_receipt': 'Dated source/version/case-specific evidence and scope', 'discovered_date': '2026-10-25', 'last_checked_date': '2026-10-25'})
    for id, r in rs.items():
        if r['status'] != 'acquired':
            gaps.append({'id': 'L01-SOURCE-' + id, 'description': r['reason'], 'status': 'unavailable', 'affected_obligations': [o['id'] for o in inventory['obligations'] if o['source_section']['source_id'] == id], 'blocked_output': 'Source-dependent claims and completeness', 'responsible_role': 'engineering/source access owner', 'next_action': 'Resolve allowed source route; do not bypass restriction', 'required_closure_receipt': 'Allowed immutable source acquisition', 'discovered_date': '2026-10-25', 'last_checked_date': '2026-10-25'})
    superseded = {'MANUAL-HOSPITAL': 'MANUAL-DURATION', 'MANUAL-SNF': 'MANUAL-SNF-EXACT', 'MANUAL-PREVENTIVE': 'CLAIMS-PREVENTIVE', 'SSA-POMS-PROTECT': 'SSA-HOLD-HARMLESS'}
    # Attempts are preserved, but alias failures cannot inflate source obligations.
    source_obligations = []
    for id, r in rs.items():
        r['actual_title'] = re.search(r'<title>(.*?)</title>', (package / r['artifact']).read_text(errors='replace'), re.S).group(1) if r.get('media_type') == 'text/html' and re.search(r'<title>(.*?)</title>', (package / r['artifact']).read_text(errors='replace'), re.S) else r['title']
        r['discovery_role'] = 'superseded_attempt' if id in superseded else 'alternative_representation' if r.get('representation_of') else 'required_source'
        r['superseded_by'] = superseded.get(id)
        if id not in superseded and not r.get('representation_of'):
            source_obligations.append({'id': 'SOURCE-' + id, 'source_id': id, 'status': r['status'], 'required': True})
    for gap in gaps:
        id = gap['id'].removeprefix('L01-SOURCE-')
        if id in superseded:
            gap.update(status='superseded_discovery_attempt', superseded_by=superseded[id], blocked_output='None from this URL attempt; required replacement tracked separately')
    for o in inventory['obligations']:
        if o['locator_status'] == 'unresolved_locator_gap':
            gaps.append({'id': 'LOCATOR-' + o['id'], 'status': 'unresolved', 'affected_obligations': [o['id']], 'blocked_output': o['concept'], 'responsible_role': 'engineering / qualified rule reviewer', 'next_action': 'Map exact governing paragraph, conditions and temporal applicability; do not count as implemented', 'required_closure_receipt': 'Raw-source hash, exact locator and section effective-date analysis', 'discovered_date': '2026-10-25', 'last_checked_date': '2026-10-25'})
    for id in [c['fact_id'] for c in fact_checks if c['comparison']=='missing_designated_crosscheck']+[b['id'] for b in bands if b['coverage_context']=='part_d' and b['adjustment_cents']==0]:
        gaps.append({'id':'L01-CROSSCHECK-'+id,'status':'missing_corroboration','affected_obligations':[id],'blocked_output':'Claim acceptance and completeness','responsible_role':'engineering / qualified reviewer','next_action':'Acquire designated independent publication observation or reviewer-approved alternative; do not count primary extraction as corroboration','required_closure_receipt':'Exact second-source locator and claim comparison','discovered_date':'2026-10-25','last_checked_date':'2026-10-25'})
    temporal = []
    for id, text in texts.items():
        if id.startswith(('MANUAL-', 'CLAIMS-', 'GENERAL-')):
            temporal.append({'source_id': id, 'revision_headers': re.findall(r'\(Rev\.[^)]{1,240}\)', text), 'status': 'section_dates_retained_not_blanket_2026_approval', 'consequence': 'Annual chart cannot override MM14279; new or changed service rules require date-specific review'})
    dump(package / 'temporal-audit.json', temporal)
    dump(package / 'source-obligations.json', {'version': '2026-r1-discovery-2', 'denominator_policy': 'Required documents, excluding explicitly superseded URL discovery attempts; all attempts retained separately', 'obligations': source_obligations, 'superseded_attempts': superseded})
    outputs = {'sources.json': list(rs.values()), 'observations.json': observations, 'facts.json': facts, 'bands.json': bands, 'rules.json': rules,
               'source-index.json': mappings, 'inventory.json': inventory, 'conflicts.json': conflicts, 'gaps.json': gaps,
               'dependencies.json': dependencies, 'requirements.json': {'schema': 'l01-acceptance-requirements/1', 'package_id': 'L01-US-2026-r1', 'year': 2026, 'revision': 1, 'capabilities': capabilities, 'actual_review_status': 'pending'}}
    for name, data in outputs.items():
        dump(package / name, data)
    # Evidence states are independent; parser success cannot set acceptance/current.
    dump(package / 'transformation-log.json', {'version': VERSION, 'inputs': {k: r.get('sha256') for k, r in rs.items()}, 'outputs': {n: digest(v) for n, v in outputs.items()}, 'acceptance_generated': False})
    seal(package)
    return outputs


def seal(package=PACKAGE):
    """Bind all research inputs, derived data and runtime algorithms, excluding QA and mutable registry."""
    payloads = [p for p in package.glob('*.json') if p.name not in {'manifest.json', 'validation.json', 'coverage.json', 'runtime-evidence.json', 'baseline.json'}]
    payloads += list(package.glob('raw/*')) + list(package.glob('acquisitions/*/*.json')) + list(package.glob('extracted/*'))
    code = ['l01.py', 'l01_build.py', 'l01_acquire.py', 'l01_http.py', 'l01_validate.py', 'l01_runtime.py', 'l01_maintenance.py']
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in payloads}
    for name in code:
        p = ROOT / 'cms-slice/scripts' / name
        if p.exists():
            files[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    dump(package / 'manifest.json', {'schema': 'l01-manifest/1', 'package_id': 'L01-US-2026-r1', 'year': 2026, 'revision': 1, 'package_path': str(package.relative_to(ROOT)),
         'tax_return_basis': {'normal_year': 2024, 'fallback_year': 2023, 'normal_basis': 'normal_2024', 'fallback_basis': '2023_because_2024_unavailable'},
         'effective_from': '2026-01-01', 'effective_until': '2027-01-01', 'source_review_after_utc': '2026-11-24T00:00:00+00:00',
         'files_sha256': files, 'inventory_version': '2026-r1-discovery-2', 'status': 'research_pending_independent_acceptance'})


if __name__ == '__main__':
    out = build()
    print(json.dumps({k: len(v) if isinstance(v, list) else 'object' for k, v in out.items()}, sort_keys=True))
