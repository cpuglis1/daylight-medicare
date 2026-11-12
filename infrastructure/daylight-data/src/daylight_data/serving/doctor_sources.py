"""Project L08 observations into separate search identities and office edges."""

from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
from hashlib import sha256
import json
import re
import sqlite3

from psycopg import sql

from .binding import ResearchServingError
from .pilot_foundation import SCHEMA, file_hash
from .provider_candidates import _label
from .provider_identity import NPI

SCOPE = {'year': 2026, 'county_fips': '12021', 'purpose': 'offline_research'}
COUNTIES = {'collier', 'lee', 'hendry', 'charlotte', 'glades', 'monroe'}
EXTRA_REGIONAL_ZIPS = {'33440', '33471', '34223', '34224'}
CREDENTIAL = re.compile(r'\b(?:MD|DO|OD|DPM|DDS|DMD|DC|NP|PA|APRN|PHD|PSYD)(?:\(M\))?[^\w]*$', re.I)
MEDICAL_CREDENTIAL = re.compile(r'\b(?:MD|DO|NP|APRN|PA|DPM)(?:\(M\))?(?:[\W\d⁰-⁹]*|\s*,\s*[FM][\W\d]*)$', re.I)
MEDICAL_HEADING = re.compile(r'family (?:practice|medicine)|internal medicine|primary care|cardiology|'
                             r'neurology|dermatology|gastroenterology|oncology|orthopedi|ob[- /]?gyn|'
                             r'nephrology|endocrinology|general surgery|pulmon|rheumatology', re.I)
WELLCARE_SECTIONS = {'Primary Care Providers (PCP)', 'Specialty Providers', 'Behavioral Health'}
HUMANA_NONMEDICAL = {'Dental Providers', 'Vision Providers'}
DATE_FORMATS = ('%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y')
ALIAS_PATH = 'docs/data/l08-provider-networks-2026-10-27/build-r1/hospital-identity-aliases.json'
ALIAS_SHA = '602a0150893ee05d10ec4639c9db73ccac228d0a2168a04008865b226a47cfcd'


def source_date(value):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value[:10] if fmt == '%Y-%m-%d' else value, fmt).date()
        except (TypeError, ValueError):
            pass
    return None


def parsed(row, key):
    return json.loads(row[key]) if row.get(key) else None


def explicit_npis(values):
    return tuple(sorted({npi for npi in values if isinstance(npi, str) and NPI.fullmatch(npi)}))


def address(street, city, state, postal, county=None):
    if not (street and city and state and postal):
        return None
    # Source ZIPs and city names are catchment signals. Only a native county
    # field is displayed as a published county, and even that is not geocoding.
    county_key = (county or '').strip().casefold().removesuffix(' county')
    regional = county_key in COUNTIES or state.upper() == 'FL' and (
        postal[:3] in {'339', '341', '330'} or postal[:5] in EXTRA_REGIONAL_ZIPS)
    return {'street': street, 'city': city, 'state': state, 'postal': postal,
            'published_county': county, 'regional_search_hint': regional}


def native_address(fields, county=None):
    return address(fields.get('street_raw'), fields.get('city_raw') or fields.get('city'),
                   fields.get('state_raw') or fields.get('state'),
                   fields.get('postal_raw') or fields.get('postal_code'), county)


def rows(conn, dataset, where=sql.SQL('TRUE'), params=(), *, fields=None):
    data = sql.SQL('data')
    if fields:
        data = sql.SQL('(SELECT jsonb_object_agg(key,value) FROM jsonb_each(data) WHERE key IN ({}))').format(
            sql.SQL(',').join(map(sql.Literal, fields)))
    with conn.cursor('doctor_' + dataset) as cursor:
        cursor.execute(sql.SQL('SELECT ordinal, {} AS data FROM {} WHERE {}').format(
            data, sql.Identifier(SCHEMA, dataset), where), params)
        yield from cursor


def locator(manifest, dataset, record):
    spec = manifest['datasets'][dataset]
    return {'dataset': dataset, 'ordinal': record['ordinal'], 'artifact': spec['artifact'],
            'artifact_sha256': spec['artifact_sha256'], 'source_table': spec['source_table'],
            'key': {k: record['data'][k] for k in spec['locator_fields']}}


class DoctorCorpus:
    """Memory-only derivative. Identity keys never come from spelling or scores."""

    def __init__(self, reader):
        self.manifest = reader.manifest
        self.actors = {}
        self.sites = {}
        self.edges = defaultdict(dict)
        self.listings = defaultdict(list)
        self.offerings = {}
        self.plan_holds = defaultdict(set)
        self.identity_conflicts = {}
        self.supplemental_assignments = {}
        self.supplemental_enrollments = defaultdict(list)
        self.plan_stats = defaultdict(Counter)
        self.regional_plan_stats = defaultdict(Counter)
        with reader.snapshot(**SCOPE) as conn:
            self.load_plans(conn)
            self.load_structured(conn)
            self.load_federal(conn, reader.root)
            self.load_directories(conn)
            self.load_hospital_aliases(conn, reader.root / ALIAS_PATH)

    def ref(self, dataset, record):
        return locator(self.manifest, dataset, record)

    def actor(self, key, kind, names, npis, ref):
        actor = self.actors.setdefault(key, {'candidate_id': key, 'kind': kind,
            'names': {}, 'npis': npis, 'source': ref})
        for name in names:
            if name:
                actor['names'].setdefault(name, ref)
        return actor

    def site(self, key, office, ref):
        self.sites.setdefault(key, {'site_id': key, 'address': office, 'source': ref})
        return key

    def link(self, actor, site, specialty=(), organizations=(), source=None):
        edge = self.edges[actor].setdefault(site, {'specialties': set(), 'organizations': set(), 'sources': []})
        edge['specialties'].update(v for v in specialty if v)
        edge['organizations'].update(organizations)
        if source and source not in edge['sources']:
            edge['sources'].append(source)

    def observe(self, actor, site, plan, observed, ref, **details):
        if observed and self.actors[actor]['kind'] == 'clinician':
            self.listings[actor, site].append({'offering_id': plan, 'observed_on': observed.isoformat(),
                'kind': 'directory', 'membership': 'listed_in_network', 'source': ref, **details})
            self.plan_stats[plan][ref['dataset']] += 1
            if self.sites[site]['address']['regional_search_hint']:
                self.regional_plan_stats[plan][ref['dataset']] += 1

    def load_plans(self, conn):
        for record in rows(conn, 'ma_offerings'):
            f = record['data']
            self.offerings[f['id']] = {'name': f['name'], 'parent': f['parent']}
        for record in rows(conn, 'ma_plan_networks'):
            f = record['data']
            if f['state'].startswith('held'):
                self.plan_holds[f['offering_id']].add(f['state'])
        # Includes qualified PDFs as well as residual network ambiguities.
        gap_path = next(path for path in self.manifest['controls'] if path.endswith('/hospital-reference-r7/genuine-gaps.json'))
        self.gap_path = gap_path

    def load_structured(self, conn):
        actors = {}
        for record in rows(conn, 'provider_entities', sql.SQL("data->>'type' IN ('Practitioner','Organization')")):
            f = record['data']
            native = parsed(f, 'name_json')
            names = [_label(variant) for variant in (native if isinstance(native, list) else [native])]
            if any(names):
                key = 'L08:' + f['entity_key']
                actors[f['entity_key']] = key
                self.actor(key, 'clinician' if f['type'] == 'Practitioner' else 'organization',
                           names, explicit_npis(parsed(f, 'npi_json') or []), self.ref('provider_entities', record))

        locations = {}
        for record in rows(conn, 'provider_sites'):
            f = record['data']
            addr = parsed(f, 'address_json') or {}
            office = address(' '.join(addr.get('line') or []), addr.get('city'), addr.get('state'),
                             addr.get('postalCode'), addr.get('district'))
            if office:
                key = self.site('L08:' + f['entity_key'], office, self.ref('provider_sites', record))
                locations[f['entity_key']] = key

        roles = {}
        for record in rows(conn, 'provider_roles', fields=(
                'entity_key', 'observation_id', 'provider_key', 'organization_key', 'locations_json',
                'specialty_json', 'period_json', 'qualifiers_json')):
            f = record['data']
            actor = actors.get(f['provider_key'])
            if not actor:
                continue
            ref = self.ref('provider_roles', record)
            organization = actors.get(f['organization_key'])
            organizations = [organization] if organization and organization != actor else []
            specialty = [value.get('text') or next((coding.get('display') for coding in value.get('coding', [])
                                                      if coding.get('display')), None)
                         for value in parsed(f, 'specialty_json') or [] if isinstance(value, dict)]
            for raw_site in parsed(f, 'locations_json') or []:
                if site := locations.get(raw_site):
                    self.link(actor, site, specialty, organizations, ref)
                    for org in organizations:
                        self.link(org, site, source=ref)
            roles[f['entity_key']] = f

        sources = {r['data']['id']: r for r in rows(conn, 'provider_sources')}
        observed = {r['data']['id']: r for r in rows(conn, 'provider_observation_locators',
                   sql.SQL("data->>'type' IN ('PractitionerRole','OrganizationAffiliation')"))}
        for record in rows(conn, 'ma_role_networks', sql.SQL("data->>'state' = 'source_listed_observation'")):
            f = record['data']
            actor, site = actors.get(f['provider_key']), locations.get(f['location_key'])
            role = roles.get(f['role_key'])
            observation = observed.get(f['role_observation'])
            if not (actor and site and site in self.edges[actor] and role and observation
                    and role['observation_id'] == f['role_observation']
                    and f['location_key'] in (parsed(role, 'locations_json') or [])):
                continue
            publisher = sources.get(observation['data']['source_id'])
            if publisher and observation['data']['pointer']:
                source = publisher['data']
                self.observe(actor, site, f['offering_id'], source_date(source['retrieved']),
                    self.ref('ma_role_networks', record), native={'network_key': f['network_key'],
                        'publisher_sha256': source['sha256'], 'publisher_pointer': observation['data']['pointer'],
                        'role_period': parsed(role, 'period_json'), 'role_active': (parsed(role, 'qualifiers_json') or {}).get('active')},
                    bridges=[self.ref('provider_observation_locators', observation), self.ref('provider_sources', publisher)])

        for record in rows(conn, 'provider_source_conflicts'):
            facts = parsed(record['data'], 'fields_json') or {}
            if facts.get('directory_npi'):
                self.identity_conflicts[facts['directory_npi']] = self.ref('provider_source_conflicts', record)

    def load_federal(self, conn, root):
        projected = set()
        for record in rows(conn, 'federal_provider_rows', sql.SQL("data->>'source_id' = 'clinicians'")):
            projected.add(record['data']['source_row'])
            self.add_federal(record)
        # The foundation seeds only 339/341/330. Reuse additional selected r6
        # rows in adjacent ZIPs from the same pinned, read-only artifact.
        spec = self.manifest['datasets']['federal_provider_rows']
        path = (root / spec['artifact']).resolve()
        try:
            if not path.is_relative_to(root) or file_hash(path) != spec['artifact_sha256']:
                raise ResearchServingError('PILOT_SOURCE_FEDERAL_BINDING_MISMATCH')
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as native:
                native.row_factory = sqlite3.Row
                placeholders = ','.join('?' for _ in EXTRA_REGIONAL_ZIPS)
                extra = native.execute(f"""SELECT * FROM observations WHERE source_id='clinicians' AND state_raw='FL'
                            AND substr(postal_raw,1,5) IN ({placeholders}) ORDER BY source_row""",
                                       sorted(EXTRA_REGIONAL_ZIPS))
                npis = set()
                for row in extra:
                    if row['source_row'] not in projected:
                        f = dict(row)
                        self.add_federal({'ordinal': None, 'data': f})
                        self.supplemental_assignments[f['source_row']] = f
                        if f['npi']:
                            npis.add(f['npi'])
                for npi in sorted(npis):
                    for row in native.execute('SELECT * FROM enrollment_status WHERE npi=? ORDER BY source_row', (npi,)):
                        self.supplemental_enrollments[npi].append({'ordinal': None, 'data': dict(row)})
        except (OSError, sqlite3.Error):
            raise ResearchServingError('PILOT_SOURCE_FEDERAL_UNAVAILABLE') from None

    def add_federal(self, record):
        f = record['data']
        facts = parsed(f, 'fields_json')
        name = ' '.join(facts[k] for k in ('Provider First Name', 'Provider Middle Name',
                        'Provider Last Name', 'suff', 'Cred') if facts.get(k))
        npis = explicit_npis([f['npi']])
        # Use the explicit federal NPI + individual PAC pair. Keep rows
        # with missing identifiers source-keyed, with no cross-source merge.
        pac = facts.get('Ind_PAC_ID')
        key = ('CMS:clinician:' + f['npi'] + ':' + pac if npis and pac
               else 'CMS:clinician-row:' + str(f['source_row']))
        ref = self.ref('federal_provider_rows', record)
        self.actor(key, 'clinician', [name], npis, ref)
        organization = facts.get('org_pac_id')
        practice = facts.get('Facility Name')
        org = None
        if practice:
            org = ('CMS:group:' + organization if organization
                   else 'CMS:group-row:' + str(f['source_row']))
            self.actor(org, 'organization', [practice], (), ref)
        office = address(' '.join(filter(None, (facts.get('adr_ln_1'), facts.get('adr_ln_2')))),
                         f['city_raw'], f['state_raw'], f['postal_raw'])
        if office:
            site = self.site('CMS:site:' + (facts.get('adrs_id') or str(f['source_row'])), office, ref)
            self.link(key, site, [facts.get('pri_spec'), *(facts.get('sec_spec_' + str(i)) for i in range(1, 5))],
                      [org] if org else [], ref)
            if org:
                self.link(org, site, source=ref)

    def load_directories(self, conn):
        docs = {r['data']['sha256']: r['data'] for r in rows(conn, 'ma_documents')}
        bridges = defaultdict(list)
        for dataset in ('ma_plan_documents', 'ma_wellcare_plan_documents'):
            for record in rows(conn, dataset):
                f = record['data']
                bridges[f['document_sha256']].append((f['offering_id'], self.ref(dataset, record), f.get('scope_state')))

        for record in rows(conn, 'ma_wellcare_listings'):
            f = record['data']
            raw = parsed(f, 'fields_json')
            name = raw.get('name_raw')
            kind = 'clinician' if (name and CREDENTIAL.search(name) and f['section_raw'] in WELLCARE_SECTIONS) else 'unclassified'
            if f['section_raw'] == 'Hospitals':
                kind = 'organization'
            if f['section_raw'] in {'Vision', 'Additional Benefits', 'Other Services'}:
                continue
            ref = self.ref('ma_wellcare_listings', record)
            # Document/row identity is deliberate. A publisher provider ID
            # alone is not proof that two renderings refer to the same office.
            actor = 'Wellcare:listing:' + f['id']
            self.actor(actor, kind, [name], explicit_npis([raw.get('npi')]), ref)
            org = self.practice(actor, raw.get('practice_raw'), ref)
            for i, location in enumerate(raw.get('addresses') or []):
                office = native_address(location, f['county_raw'])
                if not office or location.get('state') != 'literal_source_site':
                    continue
                site = self.site(actor + ':site:' + str(i), office, ref)
                self.link(actor, site, [raw.get('specialty_raw'), f['section_raw']], org, ref)
                for plan, bridge, _ in bridges[f['document_sha256']]:
                    # r5's plan-name bridge is qualified to printed Collier.
                    if (f['county_raw'] or '').strip().casefold() == 'collier' and bridge['dataset'] == 'ma_wellcare_plan_documents':
                        self.observe(actor, site, plan, source_date(docs[f['document_sha256']]['published_date_text']),
                            ref, bridges=[bridge], native={'page': f['page'], 'document_sha256': f['document_sha256'],
                                'publisher_provider_id': f['publisher_provider_id'], 'address_index': i,
                                'source_conditions': raw.get('other_source_text'), 'practice': raw.get('practice_raw')})
                for practice in org:
                    self.link(practice, site, source=ref)

        # Bounded name-to-address links are separate from the raw printed row.
        links = defaultdict(list)
        for record in rows(conn, 'ma_humana_address_links'):
            if parsed(record['data'], 'fields_json').get('state') == 'bounded_source_entry_address':
                links[record['data']['entry_id']].append(record)
        addresses = {r['data']['id']: r for r in rows(conn, 'ma_humana_addresses')}
        for record in rows(conn, 'ma_humana_listings', sql.SQL("data->>'name_kind' <> 'published_specialty_heading'")):
            f = record['data']
            raw = parsed(f, 'fields_json')
            if raw.get('section_raw') in HUMANA_NONMEDICAL:
                continue
            name_kind = {'credentialed_clinician_name': 'clinician', 'organization_or_practice_name': 'organization'}
            actor = 'Humana:entry:' + f['id']
            ref = self.ref('ma_humana_listings', record)
            self.actor(actor, name_kind.get(f['name_kind'], 'unclassified'), [raw.get('name_raw')], (), ref)
            for link in links[f['id']]:
                source = addresses.get(link['data']['address_id'])
                if not source or source['data']['document_sha256'] != f['document_sha256']:
                    continue
                fields = parsed(source['data'], 'fields_json')['fields']
                office = native_address(fields, fields.get('county_context_raw'))
                if not office:
                    continue
                site_ref = self.ref('ma_humana_addresses', source)
                site = self.site('Humana:office:' + source['data']['id'], office, site_ref)
                link_ref = self.ref('ma_humana_address_links', link)
                self.link(actor, site, [raw.get('section_raw'), raw.get('specialty_raw')], source=link_ref)
                for plan, bridge, state in bridges[f['document_sha256']]:
                    if state == 'published_exact_plan_directory; explicitly_partial':
                        self.observe(actor, site, plan, source_date(docs[f['document_sha256']]['published_date_text']),
                            ref, bridges=[bridge, link_ref, site_ref], native={'page': f['page'],
                                'document_sha256': f['document_sha256'], 'source_conditions': raw.get('conditions_raw')})

        for dataset in ('ma_aetna_query', 'ma_aetna_additive_query'):
            where = sql.SQL("data->>'family' = 'aetna'") if dataset.endswith('additive_query') else sql.SQL('TRUE')
            for record in rows(conn, dataset, where):
                f = record['data']
                raw = parsed(f, 'fields_json')
                facts = raw.get('fields') or {}
                name = facts.get('name_raw')
                if not name:
                    continue
                kind = 'clinician' if CREDENTIAL.search(name) else 'organization' if (
                    'hospital' in (raw.get('category') or '') or re.search(r'\b(?:LLC|PLLC|INC|GROUP)\b', name, re.I)
                ) else 'unclassified'
                actor = 'Aetna:card:' + f['id']
                ref = self.ref(dataset, record)
                self.actor(actor, kind, [name], explicit_npis([facts.get('npi')]), ref)
                if office := native_address(facts):
                    site = self.site(actor + ':site', office, ref)
                    self.link(actor, site, [facts.get('specialty_or_role_raw') or facts.get('specialty_raw')], source=ref)
                    network = facts.get('published_network_label') or ''
                    if re.search(r'\bin network\b', network, re.I) and not re.search(r'\b(?:out of|not in) network\b', network, re.I):
                        self.observe(actor, site, f['offering_id'], source_date(raw.get('observation_date')), ref,
                            native={'network_label': network, 'publisher_provider_id': facts.get('publisher_provider_id'),
                                'publisher_path': f['source_path'], 'publisher_sha256': raw.get('source_sha256')})
        self.load_legacy(conn, docs, bridges)

    def practice(self, actor, name, ref):
        if not name or not isinstance(name, str):
            return []
        key = actor + ':practice'
        self.actor(key, 'organization', [name], (), ref)
        return [key]

    def load_hospital_aliases(self, conn, path):
        # The r1 alias register is sealed by the L08 execution manifest.
        # Its links identify AHCA organizations, never carrier network edges.
        try:
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != ALIAS_SHA:
                raise ResearchServingError('PILOT_SOURCE_ALIAS_BINDING_MISMATCH')
            aliases = json.loads(raw)['aliases']
        except OSError:
            raise ResearchServingError('PILOT_SOURCE_ALIASES_UNAVAILABLE') from None
        for record in rows(conn, 'ma_hospitals'):
            f = record['data']
            ref = self.ref('ma_hospitals', record)
            actor = self.actor(f['id'], 'organization', [f['name']], (), ref)
            for label in aliases.get(f['id'], []):
                actor['names'].setdefault(label, {'artifact': ALIAS_PATH, 'artifact_sha256': ALIAS_SHA,
                                                  'key': {'AHCA_organization': f['id']}})
            for i, raw_address in enumerate(parsed(f, 'addresses_json') or []):
                if raw_address.get('AddressType') != 'ST':
                    continue
                office = address(' '.join(filter(None, (raw_address.get('Address'), raw_address.get('Address2')))),
                                 raw_address.get('City'), raw_address.get('State'), raw_address.get('Zip'),
                                 raw_address.get('County') or f.get('county'))
                if office:
                    site = self.site(f['id'] + ':office:' + str(i), office, ref)
                    self.link(f['id'], site, ['Hospital'], source=ref)

    def load_legacy(self, conn, docs, bridges):
        resolutions = {r['data']['record_id']: r for r in rows(conn, 'ma_pdf_site_resolutions')
                       if r['data']['state'] == 'same_document_exact_provider_and_primary_care_ID_resolves_unique_reprinted_site'}
        for record in rows(conn, 'ma_pdf_listings', sql.SQL("data->>'domain' = 'medical_or_supplemental_provider'")):
            f = record['data']
            name = f['name_raw']
            if not name:
                continue
            raw = parsed(f, 'fields_json')
            qualifiers = raw.get('published_qualifiers') or []
            specialties = [q['value_raw'] for q in qualifiers if q.get('kind') == 'source_section_heading_raw']
            medical = bool(MEDICAL_CREDENTIAL.search(name) or (
                f['identifier_kind'] == 'npi' and ',' in name
                and any(MEDICAL_HEADING.search(label) for label in specialties)))
            actor = 'L08:pdf:' + f['id']
            ref = self.ref('ma_pdf_listings', record)
            self.actor(actor, 'clinician' if medical or CREDENTIAL.search(name) else 'unclassified', [name],
                       explicit_npis([f['identifier']]) if f['identifier_kind'] == 'npi' else (), ref)
            sites = [(v, None) for v in (raw.get('addresses') or [])]
            if not sites and (resolution := resolutions.get(f['id'])):
                sites = [(parsed(resolution['data'], 'fields_json')['resolved_site'],
                          self.ref('ma_pdf_site_resolutions', resolution))]
            for i, (native, resolution_ref) in enumerate(sites):
                if not (office := native_address(native)):
                    continue
                site = self.site(actor + ':site:' + str(i), office, resolution_ref or ref)
                self.link(actor, site, specialties, source=resolution_ref or ref)
                # Only exact product publications. Shared carrier references
                # retain their conditions but are held from this positive join.
                for plan, bridge, state in bridges[f['document_sha256']]:
                    if state == 'exact_2026_product_publication' and medical and (
                            resolution_ref or f['state'].startswith('published_native_listing')):
                        self.observe(actor, site, plan, source_date(docs[f['document_sha256']]['published_date_text']),
                            ref, bridges=[bridge] + ([resolution_ref] if resolution_ref else []),
                            native={'page': f['page'], 'document_sha256': f['document_sha256'],
                                    'address_index': i, 'source_conditions': raw.get('conditions'),
                                    'published_qualifiers': qualifiers})
