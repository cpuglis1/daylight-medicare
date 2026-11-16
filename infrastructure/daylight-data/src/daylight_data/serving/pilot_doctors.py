"""D146 provider discovery and exact evidence, for offline research only."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
import heapq
from itertools import chain
import json
import re
import unicodedata

from psycopg import sql

from .binding import ResearchServingError, digest
from .doctor_sources import DoctorCorpus, SCOPE, locator, parsed, rows, source_date
from .provider_candidates import _query

VERSION = 'daylight-pilot-doctors/1'
DIRECTORY_DAC_DATE = date(2026, 10, 2)
ENROLLMENT_DATE = date(2026, 10, 1)
OPT_OUT_RELEASE_DATE = date(2026, 10, 26)
ASSIGNMENT = {'Y': 'published_accepts_assignment', 'M': 'published_may_accept_assignment'}
MAX_RESULTS = 20
MAX_OFFSET = 1000
IGNORED_NAME_TOKENS = {'dr', 'doctor', 'md', 'do', 'od', 'dpm', 'dds', 'dmd', 'np', 'pa', 'aprn', 'phd', 'psyd'}
STREET_WORDS = {'street': 'st', 'avenue': 'ave', 'boulevard': 'blvd', 'road': 'rd', 'drive': 'dr',
                'trail': 'trl', 'court': 'ct', 'suite': 'ste', 'building': 'bldg',
                'north': 'n', 'south': 's', 'east': 'e', 'west': 'w'}


def words(value):
    plain = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
    return tuple(re.findall(r'[^\W_]+', plain))


def place_matches(office, place):
    """Match the published city, optionally qualified by state or ZIP."""
    if not place:
        return False
    city = words(office.get('city') or '')
    state = words(office.get('state') or '')
    postal = (office.get('postal') or '')[:5]
    requested = words(place)
    return bool(city and requested in (city, city + state, city + (postal,),
                                       city + state + (postal,), (postal,)))


def place_office(office, place):
    postal = re.fullmatch(r'(\d{5})(?:-?(\d{4}))?', (office.get('postal') or '').strip())
    return {'line': office.get('street'), 'city': office.get('city'), 'state': office.get('state'),
            'zip5': postal[1] if postal else None, 'zip4': postal[2] if postal else None,
            'place_match': place_matches(office, place)}


source_words = lru_cache(maxsize=32768)(words)


def name_words(value):
    return tuple(w for w in words(value) if w not in IGNORED_NAME_TOKENS)


def office_key(office):
    # Never remove unit numbers, infer an office from a phone, or use a
    # nearby ZIP. ZIP+4 and suffix expansions are formatting differences.
    return (tuple(STREET_WORDS.get(w, w) for w in words(office['street'])),
            words(office['city']), office['state'].upper(), office['postal'][:5])


def deletions(word):
    return {word[:i] + word[i + 1:] for i in range(len(word))}


def match_score(asked, found):
    if asked == found:
        return 5
    if len(asked) == 1 and found.startswith(asked):
        return 2
    if len(asked) < 4 or abs(len(asked) - len(found)) > 1:
        return 0
    if len(asked) == len(found):
        positions = [i for i, (a, b) in enumerate(zip(asked, found)) if a != b]
        if len(positions) == 1:
            return 1
        if len(positions) == 2:
            i, j = positions
            return int(j == i + 1 and asked[i] == found[j] and asked[j] == found[i])
        return 0
    short, long = sorted((asked, found), key=len)
    return int(short in deletions(long))


def two_edits(asked, found):
    if abs(len(asked) - len(found)) > 2:
        return False
    if len(asked) == len(found) and sum(a != b for a, b in zip(asked, found)) <= 2:
        return True
    # Delete or insert one character before a single-edit comparison.
    if len(asked) == len(found):
        return not deletions(asked).isdisjoint(deletions(found))
    short, long = sorted((asked, found), key=len)
    return any(match_score(short, candidate) for candidate in deletions(long))


def variant_score(asked, variant, rescue=None):
    if rescue and not any(token in variant for token in asked if token != rescue and len(token) >= 3):
        return 0
    available = list(variant)
    scores = []
    # Match strong tokens before initials. Each requested token consumes one
    # source token, and all name tokens must come from the same variant.
    for token in sorted(asked, key=len, reverse=True):
        score, i = max(((match_score(token, w), i) for i, w in enumerate(available)), default=(0, 0))
        if not score and token == rescue:
            score, i = next(((1, i) for i, w in enumerate(available) if two_edits(token, w)), (0, 0))
        if not score:
            return 0
        scores.append(score)
        available.pop(i)
    return 10 * sum(scores) + (10 if not available else 0)


def validated_words(value, *, name=False):
    if value is None or value == '':
        return ()
    tokens, _ = _query(value)
    result = (name_words if name else words)(' '.join(tokens))
    if not result:
        raise ResearchServingError('DOCTOR_QUERY_EMPTY')
    return result


def contains(tokens, wanted):
    return set(wanted).issubset(tokens)


class DoctorIndex:
    def __init__(self, corpus):
        self.corpus = corpus
        self.variants = {}
        self.tokens = defaultdict(set)
        self.facets = defaultdict(set)
        self.deletes = defaultdict(set)
        self.npi_sites = defaultdict(set)
        self.npi_actors = defaultdict(set)
        self.actor_ordinals = list(corpus.actors)
        self.actor_ordinals.sort()
        self.locality_stats = Counter()
        self.county_stats = Counter()
        self.specialty_stats = Counter()
        self.source_stats = Counter()
        for index, key in enumerate(self.actor_ordinals):
            actor = corpus.actors[key]
            variants = {name: name_words(name) for name in actor['names']}
            self.variants[key] = variants
            for token in {token for variant in variants.values() for token in variant}:
                self.tokens[token].add(index)
            self.source_stats[actor['source']['dataset'], actor['kind']] += 1
            for site, edge in corpus.edges.get(key, {}).items():
                office = corpus.sites[site]['address']
                self.locality_stats[actor['source']['dataset'], office['state'], office['city']] += 1
                self.county_stats[actor['source']['dataset'], office['published_county'] or '(not published)'] += 1
                for specialty in edge['specialties'] or {'(not published)'}:
                    self.specialty_stats[actor['source']['dataset'], specialty] += 1
                for facet in self.edge_facets(actor, site, edge):
                    for token in facet:
                        self.facets[token].add(index)
                if actor['kind'] == 'clinician':
                    for npi in actor['npis']:
                        self.npi_sites[npi, office_key(office)].add((key, site))
                        if len(actor['npis']) == 1 and npi not in corpus.identity_conflicts:
                            self.npi_actors[npi].add(key)
        for token in self.tokens:
            if len(token) >= 3:
                for short in deletions(token):
                    self.deletes[short].add(token)

    def edge_facets(self, actor, site, edge):
        office = self.corpus.sites[site]['address']
        location = source_words(' '.join(v for k, v in office.items() if k != 'regional_search_hint' and v))
        location = (*location, office['postal'][:5])
        practice = tuple(w for org in edge['organizations'] for name in self.corpus.actors[org]['names']
                         for w in source_words(name))
        if actor['kind'] == 'organization':
            practice += tuple(w for name in actor['names'] for w in source_words(name))
        specialty = tuple(w for value in edge['specialties'] for w in source_words(value))
        return location, practice, specialty

    def related_sites(self, actor, site):
        # Use exact explicit identity/address edges to find evidence; search
        # candidates themselves remain separate. A multi-NPI identity is held.
        record = self.corpus.actors[actor]
        if record['kind'] != 'clinician' or len(record['npis']) != 1:
            return {(actor, site)}
        address = self.corpus.sites[site]['address']
        return self.npi_sites[record['npis'][0], office_key(address)] | {(actor, site)}

    def name_postings(self, token):
        if len(token) == 1:
            # Single-character initials may be scored when a full token or
            # a facet provides a bounded candidate set.
            return None
        variants = {token}
        if len(token) >= 4:
            shorter = deletions(token)
            variants.update(shorter)
            variants.update(self.deletes.get(token, ()))
            for deleted in shorter:
                variants.update(self.deletes.get(deleted, ()))
        return set().union(*(self.tokens.get(w, set()) for w in variants if match_score(token, w)))

    def identity(self, key):
        actor = self.corpus.actors[key]
        npis = actor['npis']
        return npis[0] if actor['kind'] == 'clinician' and len(npis) == 1 and npis[0] in self.npi_actors else key

    def offices(self, key, place=None, *, combine_identity=False):
        actors = self.npi_actors.get(self.identity(key), {key}) if combine_identity else {key}
        ordered = sorted(
            ((actor, site) for actor in actors for site in self.corpus.edges.get(actor, ())),
            key=lambda pair: (
                bool(place) and not place_matches(self.corpus.sites[pair[1]]['address'], place),
                not pair[0].startswith('CMS:'), pair[0] != key, pair))
        distinct = {}
        for actor, site in ordered:
            address = office_key(self.corpus.sites[site]['address'])
            identity = address if combine_identity and all(address) else (actor, site)
            distinct.setdefault(identity, (actor, site))
        return list(distinct.values())

    def site_page(self, key, offset, place=None, *, combine_identity=False):
        offices = self.offices(key, place, combine_identity=combine_identity)
        page = offices[offset:offset + MAX_RESULTS]
        return {'sites': [{**self.corpus.sites[site], 'evidence_candidate_id': actor,
                           'specialties': sorted(self.corpus.edges[actor][site]['specialties']),
                           'organizations': [{'candidate_id': org,
                                'label': next(iter(self.corpus.actors[org]['names']), ''),
                                'source': self.corpus.actors[org]['source']}
                               for org in sorted(self.corpus.edges[actor][site]['organizations'])]}
                          for actor, site in page],
                'next_offset': offset + len(page) if offset + len(page) < len(offices) else None,
                'site_count': len(offices)}

    def describe(self, key, *, matching_sites, matched_name, score):
        actor = self.corpus.actors[key]
        edges = self.corpus.edges.get(key, {})
        return {'candidate_id': key, 'kind': actor['kind'], 'label': next(iter(actor['names'])),
                'published_names': [{'label': name, 'source': ref} for name, ref in list(actor['names'].items())[:20]],
                'published_name_count': len(actor['names']),
                'source_npis': actor['npis'], 'source': actor['source'], 'matched_name': matched_name,
                'match_score': score, 'site_count': len(edges),
                'matching_site_ids': matching_sites[:MAX_RESULTS],
                'matching_site_count': len(matching_sites),
                'office_previews': [self.corpus.sites[site]['address']
                                    for site in (matching_sites or sorted(edges))[:2]],
                'identity_confirmed': False}

    def search(self, *, name=None, location=None, practice=None, specialty=None,
               region='regional', offset=0, limit=5, prefer_place=False, combine_identity=False):
        if (not isinstance(region, str) or region not in {'regional', 'all_retained'}
                or type(offset) is not int or not 0 <= offset <= MAX_OFFSET
                or type(limit) is not int or not 1 <= limit <= MAX_RESULTS):
            raise ResearchServingError('DOCTOR_INVALID_SEARCH')
        asked = validated_words(name, name=True)
        facets = tuple(validated_words(value) for value in (location, practice, specialty))
        if prefer_place and any(len(token) > 1 for token in asked):
            facets = ((), *facets[1:])
        name_matches = {w: self.name_postings(w) for w in set(asked)}
        missing = [w for w, postings in name_matches.items() if postings is not None and not postings]
        rescue = (missing[0] if len(missing) == 1 and len(missing[0]) >= 7 and any(
            len(w) >= 3 and w in self.tokens for w in asked if w != missing[0]) else None)
        candidate_sets = [postings for w, postings in name_matches.items() if postings is not None and w != rescue]
        candidate_sets.extend(self.facets.get(token, set()) for field in facets for token in set(field))
        if not candidate_sets:
            raise ResearchServingError('DOCTOR_SEARCH_NEEDS_NAME_OR_DETAIL')
        candidates = set.intersection(*sorted(candidate_sets, key=len))

        def matches():
            for ordinal in candidates:
                key = self.actor_ordinals[ordinal]
                actor = self.corpus.actors[key]
                if prefer_place and actor['kind'] != 'clinician':
                    continue
                variants = self.variants[key]
                if not variants:
                    continue
                score, label = max(((variant_score(asked, tokens, rescue), name)
                                    for name, tokens in variants.items())) if asked else (0, None)
                if asked and not score:
                    continue
                sites = []
                for site, edge in self.corpus.edges.get(key, {}).items():
                    office = self.corpus.sites[site]['address']
                    local = office['regional_search_hint'] or (prefer_place and place_matches(office, location))
                    if (region == 'all_retained' or local) and all(
                            contains(facet, requested)
                            for facet, requested in zip(self.edge_facets(actor, site, edge), facets)):
                        sites.append(site)
                if not sites and (prefer_place or region == 'regional' or any(facets)):
                    continue
                if not asked and facets[1] and actor['kind'] == 'organization':
                    score = 1
                elif asked and actor['kind'] == 'clinician' and actor['npis']:
                    score += 11
                sites.sort(key=lambda site: (
                    prefer_place and not place_matches(self.corpus.sites[site]['address'], location), site))
                away = prefer_place and not place_matches(self.corpus.sites[sites[0]]['address'], location)
                yield (away, -score, key, label, sites)

        count = 0
        def identities():
            if not combine_identity:
                yield from matches()
                return
            best = {}
            for match in matches():
                identity = self.identity(match[2])
                if identity not in best or match < best[identity]:
                    best[identity] = match
            yield from best.values()

        def counted():
            nonlocal count
            for match in identities():
                count += 1
                yield match

        results = heapq.nsmallest(offset + limit, counted())[offset:]
        return {'candidates': [self.describe(key, matching_sites=sites, matched_name=label, score=-score)
                               for _, score, key, label, sites in results],
                'total_source_candidates': count,
                'next_offset': offset + limit if offset + limit < count and offset + limit <= MAX_OFFSET else None,
                'search_window_limited': count > MAX_OFFSET + limit,
                'state': 'candidates_require_selection' if results else 'unknown_no_candidate',
                'region': region, 'county_completeness_established': False, 'automatic_confirmation': False}


@dataclass(frozen=True)
class Selection:
    candidate_id: str
    site_id: str
    offering_id: str | None
    intended_date: date
    route: str


@dataclass(frozen=True)
class Confirmation:
    """Trusted offline adapter record. No request field may create one."""

    selection: Selection
    membership: str
    observed_on: date
    effective_from: date
    effective_through: date
    source: str

    def __post_init__(self):
        if (self.selection.route != 'medicare_advantage' or self.membership not in {'in_network', 'out_of_network'}
                or not self.source or self.effective_from > self.effective_through):
            raise ValueError('Invalid exact confirmation')


def state_for_ma(listings, confirmations, intended, today):
    applicable = []
    inactive = []
    for row in listings:
        observed = date.fromisoformat(row['observed_on'])
        period = row['native'].get('role_period') or {}
        start, end = source_date(period.get('start')), source_date(period.get('end'))
        if end and end < intended:
            inactive.append(row)
        elif observed <= min(intended, today) and (not start or start <= intended) and row['native'].get('role_active') is not False:
            applicable.append(row)
    valid = [row for row in confirmations if row.observed_on <= today
             and row.effective_from <= intended <= row.effective_through]
    memberships = {row.membership for row in valid}
    if len(memberships) > 1 or any(
            row.membership == 'out_of_network' and any(
                row.effective_from <= date.fromisoformat(listing['observed_on']) <= row.effective_through
                for listing in applicable) for row in valid):
        return 'conflict', None
    if valid:
        return 'confirmed', next(iter(memberships))
    if applicable:
        return 'dated_listing', 'listed_in_network'
    if inactive or any(row.effective_through < intended and row.observed_on <= today for row in confirmations):
        return 'stale', None
    return 'unknown', None


class PilotDoctors:
    """Offline search/evidence; all operations reconcile the bound STOP authority."""

    def __init__(self, reader, *, confirmations=()):
        self.reader = reader
        self.binding_id = reader.manifest['binding_id']
        self.corpus = DoctorCorpus(reader)
        self.index = DoctorIndex(self.corpus)
        self.confirmations = defaultdict(list)
        for row in confirmations:
            if not isinstance(row, Confirmation):
                raise ValueError('Confirmations must be trusted exact evidence records')
            self.confirmations[row.selection].append(row)
        gaps = json.loads((reader.root / self.corpus.gap_path).read_text())
        self.gaps = defaultdict(list)
        for gap in gaps:
            for plan in gap.get('scope', []):
                if plan in self.corpus.offerings:
                    self.gaps[plan].append({'id': gap['id'], 'need': gap['need']})
        with self.reader.snapshot(**SCOPE):
            pass

    def search(self, *, year=2026, **query):
        with self.reader.snapshot(**(SCOPE | {'year': year})):
            result = self.index.search(**query)
        return {**result, 'binding_id': self.binding_id, 'contract': VERSION, 'year': year,
                'clinician_types_searched': 'All clinician types in the retained directories',
                'radius_or_area_searched': ('Retained directory records flagged as regional'
                    if result['region'] == 'regional' else 'All retained directory regions')}

    def sites(self, candidate_id, *, offset=0, place=None, combine_identity=False):
        if (not isinstance(candidate_id, str) or candidate_id not in self.corpus.actors
                or type(offset) is not int or not 0 <= offset <= MAX_OFFSET):
            raise ResearchServingError('DOCTOR_INVALID_SITE_PAGE')
        with self.reader.snapshot(**SCOPE):
            result = self.index.site_page(candidate_id, offset, place, combine_identity=combine_identity)
        return {**result, 'candidate_id': candidate_id, 'binding_id': self.binding_id}

    def selection(self, candidate_id, site_id, offering_id, intended_date, route):
        if (not isinstance(candidate_id, str) or not isinstance(site_id, str) or
                not isinstance(route, str) or not isinstance(intended_date, str)
                or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', intended_date)):
            raise ResearchServingError('DOCTOR_INVALID_SELECTION')
        try:
            intended = date.fromisoformat(intended_date)
        except ValueError:
            raise ResearchServingError('DOCTOR_INVALID_DATE') from None
        if intended.year != SCOPE['year']:
            raise ResearchServingError('PILOT_WRONG_YEAR')
        if (candidate_id not in self.corpus.actors or self.corpus.actors[candidate_id]['kind'] != 'clinician'
                or site_id not in self.corpus.edges.get(candidate_id, {})):
            raise ResearchServingError('DOCTOR_EXACT_CLINICIAN_SITE_REQUIRED')
        if route == 'medicare_advantage':
            if not isinstance(offering_id, str) or offering_id not in self.corpus.offerings:
                raise ResearchServingError('DOCTOR_EXACT_OFFERING_REQUIRED')
        elif route != 'original_medicare' or offering_id is not None:
            raise ResearchServingError('DOCTOR_INVALID_ROUTE')
        return Selection(candidate_id, site_id, offering_id, intended, route)

    def evidence(self, selection):
        sel = self.selection(selection.candidate_id, selection.site_id, selection.offering_id,
                             selection.intended_date.isoformat(), selection.route)
        base = {'contract': VERSION, 'binding_id': self.binding_id, 'year': sel.intended_date.year,
                'selection': {'candidate_id': sel.candidate_id, 'site_id': sel.site_id,
                              'offering_id': sel.offering_id, 'intended_date': sel.intended_date.isoformat(),
                              'route': sel.route},
                'appointment_availability': 'not_checked', 'participant_release': False}
        try:
            with self.reader.snapshot(**SCOPE) as conn:
                today = self.reader.clock().date()
                result = (self.original_medicare(conn, sel, today) if sel.route == 'original_medicare'
                          else self.medicare_advantage(sel, today))
        except ResearchServingError as error:
            if str(error) != 'PILOT_EVIDENCE_STALE':
                raise
            result = {'state': 'stale', 'reason': 'offline_package_expired', 'observations': [],
                      'outside_evidence_needed': ['Renew or withdraw the bound evidence after exact source and scope review.']}
        return base | result

    def network_matrix(self, candidate_id, site_id, intended_date):
        """Use the exact confirmed office and one source-gated read for both paths."""
        original = self.selection(candidate_id, site_id, None, intended_date, 'original_medicare')
        with self.reader.snapshot(**SCOPE) as conn:
            today = self.reader.clock().date()
            plans = {plan: {'name': offering['name'], **self.medicare_advantage(
                Selection(candidate_id, site_id, plan, original.intended_date, 'medicare_advantage'), today)}
                     for plan, offering in self.corpus.offerings.items()}
            return {'original_medicare': self.original_medicare(conn, original, today), 'plans': plans}

    def medicare_advantage(self, selection, today):
        sel = selection
        related = self.index.related_sites(sel.candidate_id, sel.site_id)
        npis = self.corpus.actors[sel.candidate_id]['npis']
        conflicts = [self.corpus.identity_conflicts[npi] for npi in npis if npi in self.corpus.identity_conflicts]
        observations = []
        for actor, site in sorted(related):
            for record in self.corpus.listings.get((actor, site), ()):
                if record['offering_id'] == sel.offering_id:
                    observations.append({**record, 'source_candidate_id': actor, 'source_site_id': site,
                        'identity_basis': 'selected_native_edge' if (actor, site) == (sel.candidate_id, sel.site_id)
                        else 'explicit_same_npi_and_complete_office_address'})
        confirmations = self.confirmations[sel]
        state, membership = state_for_ma(observations, confirmations, sel.intended_date, today)
        if conflicts or len(npis) > 1:
            state, membership = 'conflict', None
        confirmations = [{'kind': 'targeted_confirmation', 'membership': row.membership, 'source': row.source,
                          'observed_on': row.observed_on.isoformat(), 'effective_from': row.effective_from.isoformat(),
                          'effective_through': row.effective_through.isoformat()} for row in confirmations]
        return {'state': state, 'membership': membership, 'observations': observations + confirmations,
                'source_identity_conflicts': conflicts,
                'held_plan_joins': sorted(self.corpus.plan_holds[sel.offering_id]),
                'plan_source_gaps': self.gaps[sel.offering_id],
                'outside_evidence_needed': [] if state == 'confirmed' else [
                    'Permitted dated carrier or office evidence for this exact clinician, complete office address, '
                    'CMS contract/PBP/segment and intended date. Resolve identity or source disagreements before use.'],
                'appointment_evidence_needed': 'Office confirmation of appointment availability and applicable new-patient or concierge terms.'}

    def original_medicare(self, conn, selection, today):
        sel = selection
        actor = self.corpus.actors[sel.candidate_id]
        npis = actor['npis']
        office = self.corpus.sites[sel.site_id]['address']
        related = self.index.related_sites(sel.candidate_id, sel.site_id)
        enrollments, assignments, optouts = [], [], []
        if len(npis) == 1 and npis[0] not in self.corpus.identity_conflicts:
            npi = npis[0]
            for key, site in sorted(related):
                if not key.startswith('CMS:clinician'):
                    continue
                for ref in self.corpus.edges[key][site]['sources']:
                    if ref['ordinal'] is None:
                        record = self.corpus.supplemental_assignments[ref['key']['source_row']]
                    else:
                        matches = list(rows(conn, 'federal_provider_rows', sql.SQL('ordinal = %s'), (ref['ordinal'],)))
                        if len(matches) != 1:
                            raise ResearchServingError('PILOT_DATABASE_PROVIDER_EDGE_MISSING')
                        record = matches[0]['data']
                    facts = parsed(record, 'fields_json')
                    assignments.append({'source': ref, 'published_on': DIRECTORY_DAC_DATE.isoformat(),
                        'enrollment_id': record['enrollment_id'], 'individual_code': facts['ind_assgn'],
                        'group_code': facts['grp_assgn'], 'group_pac_id': facts.get('org_pac_id'),
                        'individual_state': ASSIGNMENT.get(facts['ind_assgn'], 'unknown'),
                        'group_state': ASSIGNMENT.get(facts['grp_assgn'], 'unknown')})
            seen = set()
            for row in chain(rows(conn, 'federal_enrollments', sql.SQL("data->>'npi' = %s"), (npi,)),
                             self.corpus.supplemental_enrollments.get(npi, ())):
                f = row['data']
                if f['source_row'] in seen:
                    continue
                seen.add(f['source_row'])
                enrollments.append({'source': locator(self.reader.manifest, 'federal_enrollments', row),
                    'published_on': ENROLLMENT_DATE.isoformat(), 'enrollment_id': f['enrollment_id'],
                    'enrollment_type': f['provider_type_raw'], 'published_state': f['state'],
                    'linked_to_selected_office_listing': any(a['enrollment_id'] == f['enrollment_id'] for a in assignments)})
            for row in rows(conn, 'federal_optout', sql.SQL("data->>'npi' = %s"), (npi,)):
                f = row['data']
                start, end = source_date(f['start_raw']), source_date(f['end_raw'])
                when = sel.intended_date
                state = 'unknown_source_interval'
                if start and end and start <= end:
                    state = ('boundary_review' if when in (start, end) else
                             'published_interval_contains_date' if start < when < end else
                             'published_interval_does_not_contain_date')
                optouts.append({'source': locator(self.reader.manifest, 'federal_optout', row),
                    'start': f['start_raw'], 'end': f['end_raw'], 'interval_state': state,
                    'catalog_modified_on': OPT_OUT_RELEASE_DATE.isoformat(), 'scope': 'clinician_npi'})
        active = any(o['interval_state'] == 'published_interval_contains_date' for o in optouts)
        boundary = any(o['interval_state'] == 'boundary_review' for o in optouts)
        dated = min(sel.intended_date, today)
        overlap = active and dated >= DIRECTORY_DAC_DATE and today >= OPT_OUT_RELEASE_DATE and bool(assignments)
        conflicts = len(npis) > 1 or any(npi in self.corpus.identity_conflicts for npi in npis)
        if conflicts or overlap:
            state = 'conflict'
        elif boundary:
            state = 'unknown'
        elif ((assignments and dated >= DIRECTORY_DAC_DATE) or (enrollments and dated >= ENROLLMENT_DATE)
                or (optouts and today >= OPT_OUT_RELEASE_DATE)):
            state = 'dated_listing'
        else:
            state = 'unknown'
        unmatched = {a['enrollment_id'] for a in assignments if a['enrollment_id']} - {
            e['enrollment_id'] for e in enrollments}
        return {'state': state, 'enrollment': enrollments, 'assignment': assignments, 'opt_out': optouts,
                'unmatched_site_enrollment_ids': sorted(unmatched),
                'scope': 'published_original_medicare_reference', 'assignment_optout_overlap': overlap,
                'enrollment_scope': 'clinician_NPI; linked enrollment ID is separate from an office guarantee',
                'outside_evidence_needed': [
                    'Current CMS enrollment and applicable opt-out record for the exact clinician NPI, and office confirmation '
                    'of assignment for the intended service/date. Resolve published assignment/opt-out disagreement if present.'],
                'office': office}

    def coverage(self):
        with self.reader.snapshot(**SCOPE):
            return {'binding_id': self.binding_id,
                    'plans': {plan: {**facts, 'dated_directory_edges_by_source': dict(self.corpus.plan_stats[plan]),
                                     'regional_hint_edges_by_source': dict(self.corpus.regional_plan_stats[plan]),
                                     'held_plan_joins': sorted(self.corpus.plan_holds[plan]),
                                     'source_gaps': self.gaps[plan], 'complete_roster': False}
                              for plan, facts in sorted(self.corpus.offerings.items())},
                    'identities': [(*key, count) for key, count in sorted(self.index.source_stats.items())],
                    'supplemental_federal_clinician_rows': len(self.corpus.supplemental_assignments),
                    'office_edges_by_source_locality': [(*key, count) for key, count in sorted(self.index.locality_stats.items())],
                    'office_edges_by_published_county': [(*key, count) for key, count in sorted(self.index.county_stats.items())],
                    'office_edges_by_source_specialty': [(*key, count) for key, count in sorted(self.index.specialty_stats.items())]}
