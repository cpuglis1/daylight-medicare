"""Small, scope-aware checks for supported conversational propositions.

These checks cover explicit current-coverage, application-status and provider-
access propositions. They are not an entailment engine or a replacement for
independent language evaluation. Unknown phrasing is not silently converted into
a new report, authorization or verified finding.
"""
import re


_COVERAGE = {
    'original': r'\boriginal medicare\b',
    'advantage': r'\bmedicare advantage\b',
    'medigap': r'\bmedigap\b|\bmedicare supplement\b',
    'drug': r'\b(?:separate|standalone|stand-alone) (?:prescription )?drug (?:plan|coverage)\b|\bpart d\b',
    'employer': r'\b(?:current[- ]job|employer|employment|job[- ]based)\b|\b(?:through|from) (?:your |a |the )?(?:spouse.s |wife.s |husband.s )?(?:current )?(?:job|work)\b',
    'retiree': r'\bretiree\b|\b(?:former|old) employer\b|\bretirement (?:insurance|coverage)\b',
    'cobra': r'\bcobra\b',
    'military': r'\b(?:tricare|va|military)\b',
    'medicaid': r'\bmedicaid\b',
}
_INACTIVE = {'unknown', 'deferred', 'stale', 'tentative', 'conflicting'}
_PERSONAL_COVERAGE_NOUN = r'(?:(?:current|present|medical|health|drug|prescription|original|medicare|advantage|employer|employment|retiree|cobra|medicaid|military|va|tricare|medigap|supplement)\s+){0,3}(?:insurance|coverage|health plan)'


def clauses(text):
    """Preserve a question/conditional's scope; do not join unrelated sentences."""
    return [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+', text.replace('’', "'")) if part.strip()]


def current_coverage_propositions(text):
    """Recognize affirmative personal current-coverage claims with typed values.

    The subject must be the reader's actual coverage. Discussion of a possible
    route, a question, a conditional, or an older arrangement is not such a claim.
    """
    result = []
    for clause in clauses(text):
        lower = clause.casefold()
        if '?' in lower or re.search(r'\b(?:if|whether|suppose|previously|formerly|used to|might|could|would)\b', lower):
            continue
        # A possessive coverage phrase inside a generic route explanation is
        # not the subject of an actual coverage assertion. Require that same
        # proposition boundary before comparing its category with user reports.
        explicit_none = re.search(r"\byou(?: currently| now)? have no (?:health )?(?:insurance|coverage)\b|\byou(?:'re| are)(?: currently| now)? uninsured\b", lower)
        if not explicit_none and not personal_insurance_assertion(clause):
            continue
        personal = re.search(
            r"\byou(?: currently| now)? (?:have|receive)\b|"
            r"\byou(?:'re| are)(?: currently| now)? (?:covered|uninsured)\b|"
            r'\byour ' + _PERSONAL_COVERAGE_NOUN + r'\b', lower)
        if not personal:
            continue
        statement = lower[personal.start():]
        # A future start/end, coverage question or stated preference is not a
        # present assertion that the person has this coverage category.
        if re.search(r'\b(?:insurance|coverage|health plan) (?:question|options?|choices?|preference|goal)\b', statement):
            continue
        if re.search(r'\b(?:no (?:health )?(?:insurance|coverage)|uninsured)\b', statement):
            result.append(frozenset({'none'}))
            continue
        if re.search(r"\b(?:not|don't|do not|no longer)\b", statement):
            continue  # Negated category claims need their own proposition type.
        values = {key for key, pattern in _COVERAGE.items() if re.search(pattern, statement)}
        if 'retiree' in values:
            values.discard('employer')
        if values:
            result.append(frozenset(values))
        elif re.search(r"\byou(?: currently| now)? (?:have|receive) (?:current |health |medical )?(?:insurance|coverage)\b|\byou(?:'re| are)(?: currently| now)? covered\b", statement):
            result.append(frozenset({'__some_coverage__'}))
    return result


def coverage_matches_reports(text, referenced_reports):
    claims = current_coverage_propositions(text)
    if not claims:
        return True
    values = set()
    for report in referenced_reports:
        if report.get('status') in _INACTIVE:
            continue
        value = report.get('value')
        if report.get('id') == 'guide.coverage.current':
            values.update(value if isinstance(value, list) else [value] if isinstance(value, str) else [])
        elif report.get('id', '').startswith('readiness.RC09.'):
            if value in {'my_job', 'spouse_job', 'family_job'}:
                values.add('employer')
            elif value in {'cobra', 'retiree'}:
                values.add(value)
    return all(bool(values - {'none', 'unknown', 'deferred'}) if claim == {'__some_coverage__'}
               else claim <= values for claim in claims)


def personal_insurance_assertion(text):
    """Bind coverage assertions to their personal subject, not the paragraph.

    Generic category teaching stays generic even beside conversational "you".
    A bare follow-on "Coverage is ..." can inherit only an immediately preceding
    factual personal statement, not an invitation, hypothetical or category.
    """
    noun = _PERSONAL_COVERAGE_NOUN
    factual_person = False
    for sentence in clauses(text):
        lower = sentence.casefold()
        if '?' in sentence or re.match(r'\s*(?:if|suppose|whether|hypothetically)\b', lower):
            factual_person = False
            continue
        direct = re.search(r"\b(?:you|they|he|she)\s+(?:(?:currently|already|now)\s+)?(?:have|has|receive|receives)\s+(?:a\s+)?" + noun + r'\b(?!\s+(?:option|choice|question)s?\b)', lower)
        covered = re.search(r"\b(?:you|they|he|she)(?:'re| are| is| remain| remains| stay| stays)\s+(?:currently\s+)?covered\b", lower)
        possessed = re.search(r'\b(?:your|their|his|her)\s+' + noun + r'\b(?!\s+(?:option|choice|question)s?\b)', lower)
        if direct or covered:
            return True
        if possessed:
            rest = lower[possessed.end():]
            # Permit relative/parenthetical clauses while retaining the explicit
            # possessive subject. Potential/conditional coverage is not actual.
            predicate = (r'\A\s*(?:,\s*(?:which|that)\s+|,\s*[^,]{1,80},\s*)?'
                         r'(?:(?:currently|already|now|still)\s+)?'
                         r'(?:is|comes|ends|will|through|from|under|via|active)\b')
            if re.search(predicate, rest) and not re.search(r'\b(?:would|could|might)\b', rest):
                return True
        if factual_person and re.match(r'\s*(?:the\s+)?(?:insurance|coverage|health plan)\s+(?:is|comes|ends|will)\b', lower):
            return True
        factual_person = bool(re.search(r"\b(?:you|they|he|she)(?:'re| are| is| have| has)\s+(?:currently\s+)?(?:retired|retiring|working|employed|enrolled|covered)\b", lower))
    return False


def asserted_coverage_text(text):
    """Project asserted coverage propositions for the :8895 coverage checks only.

    This is a grammatical scope boundary, not an intent/topic recognizer. Keep
    the original text for every other factual check. Embedded whether-questions
    and epistemic status predicates do not assert the answer to that question.
    Independent adversative clauses must still be checked in their own scope.
    """
    unresolved = re.compile(
        r'\b(?:your|their|his|her)\s+' + _PERSONAL_COVERAGE_NOUN +
        r'\s+(?:is|remains|seems|appears)(?:\s+to be)?\s+'
        r'(?:(?:still|currently|presently|as yet)\s+)?'
        r'(?:unknown|unclear|unconfirmed|unreported|undetermined|unspecified|'
        r'(?:not(?:\s+yet)?|never)\s+(?:known|confirmed|reported|established|determined|specified))\b', re.I)
    asserted = []
    for sentence in clauses(text):
        sentence = unresolved.sub('', sentence)
        for part in re.split(r'\s*(?:,\s*)?\b(?:but|yet|however|nevertheless)\b\s*|'
                             r'\s*\b(?:and|so)\s+(?=(?:you|your|they|their|he|his|she|her)\b)',
                             sentence, flags=re.I):
            part = part.strip()
            if not part or '?' in part or re.match(r'^(?:if|suppose|hypothetically)\b', part, re.I):
                continue
            # The prefix may contain an independent assertion; retain it.
            embedded = re.search(r'\bwhether\b', part, re.I)
            if embedded:
                part = part[:embedded.start()]
            # "... know/check/ask if ..." is an embedded question, not coverage.
            embedded = re.search(r'\b(?:know|understand|check|confirm|ask|learn|clarify|determine|establish|find out|see)\b'
                                 r'[^.!?;]{0,60}?\bif\b', part, re.I)
            if embedded:
                part = part[:embedded.start()]
            asserted.append(unresolved.sub('', part))
    return '\n'.join(asserted)


def worker_relationship_assertion(text):
    """A question about a worker is not a report identifying that worker.

    Keep independent assertions after a hypothetical antecedent. The existing
    scope projection also keeps assertions beside embedded questions/uncertainty.
    This changes no profile value and grants no Medicare eligibility authority.
    """
    scopes=[]
    for clause in clauses(text):
        if re.match(r'^(?:if|suppose|hypothetically)\b',clause,re.I):
            clause=clause.split(',',1)[1] if ',' in clause else ''
        scopes.append(clause)
    return bool(re.search(r"\b(?:your|their|his|her) (?:wife|husband|spouse)'s\s+"
        r"(?:\w+\s+){0,2}(?:job|employer|employment|work|workplace)\b",
        asserted_coverage_text('\n'.join(scopes)),re.I))


def application_status(text):
    """Return only an asserted personal application status, never topic mention."""
    statuses = []
    for clause in clauses(text):
        if '?' in clause or re.search(r'\b(?:if|whether|suppose|might|could|would)\b', clause, re.I):
            continue
        if re.search(r"\b(?:you|they|he|she)\s+(?:haven't|have not|hasn't|has not|never)\s+(?:yet\s+)?applied\b", clause, re.I):
            statuses.append('not_applied')
        elif re.search(r"\b(?:you|they|he|she)(?:'ve| have| has)?\s+(?:already\s+)?(?:applied|submitted (?:your |their |an? |the )?application)\b|\byour application\s+(?:is|has been|was)\s+(?:pending|submitted|received)\b", clause, re.I):
            statuses.append('pending')
    return statuses


def personal_result_assertion(text):
    """Passive personal coverage results still belong to checked software cards.

    The existing action guard catches "a plan covers your ...". The grammatical
    inverse must not gain authority merely because the covered item is first.
    Use the same question/conditional scope boundary, not a task-name exception.
    """
    return bool(re.search(
        r'\b(?:your|their|his|her)\s+(?:doctors?|providers?|hospitals?|'
        r'medicines?|medications?|prescriptions?|drugs?|care|procedures?|services?)\s+'
        r'(?:is|are|will be)\s+(?:not\s+)?(?:covered|included|paid for|in (?:the |a )?network)\b',
        asserted_coverage_text(text), re.I))


def provider_access_supported(text, evidence):
    """Check evidence topic and preserved scope for explicit provider-access claims.

    A general Medicare definition cannot support a statement about doctor access.
    Universal doctor access is not an authorized Advantage proposition; Original
    Medicare's public proposition retains the accepts-Medicare qualification.
    This is deliberately a bounded claim family, not general source entailment.
    """
    for clause in clauses(text):
        if '?' in clause:
            continue
        lower = clause.casefold()
        # Bind the asserted subject before considering incidental route names,
        # such as "Unlike Medicare Advantage, Original Medicare lets ...".
        subject = re.search(r'\b(original medicare|medicare advantage)(?: plans?)?'
            r'(?:\s+(?:generally|typically|usually|often|can|may|does|not))*\s+'
            r'(?:covers?|lets?|allows?|provides?|accepts?|has|is)\b', lower)
        mentioned = {kind for name, kind in [('medicare advantage', 'advantage'),
                     ('original medicare', 'original')] if name in lower}
        route = (('advantage' if subject[1] == 'medicare advantage' else 'original') if subject
                 else next(iter(mentioned)) if len(mentioned) == 1 else None)
        if not route or not re.search(r'\b(?:doctors?|providers?|hospitals?|networks?)\b', lower):
            continue
        if not re.search(r'\b(?:covers?|accepts?|access|see|use|choose|networks?|vary|varies|limited|restrict\w*)\b', lower):
            continue
        # Pure research/process language does not claim the access result.
        if re.search(r'\b(?:compare|check|discuss|ask about|look at)\b', lower) and not re.search(r'\b(?:covers?|accepts?|can see|can use)\b', lower):
            continue
        supporting = [item for item in evidence
                      if re.search(r'\b(?:doctors?|providers?|hospitals?|networks?)\b', item.get('text', ''), re.I)
                      and (('medicare advantage' in item.get('text', '').casefold() or item.get('id') == 'advantage')
                           if route == 'advantage' else
                           ('original medicare' in item.get('text', '').casefold() or item.get('id') in {'original', 'parts'}))]
        if not supporting:
            return False
        universals = list(re.finditer(r'\b(?:every|any|all) (?:u\.s\. )?(?:doctors?|providers?|hospitals?)\b|\bno (?:network )?restrictions\b', lower))
        # Negation must govern this access predicate/quantifier. A different
        # proposition such as "is not free and covers every doctor" cannot
        # weaken the universal-access guard.
        negative_access = re.compile(
            r"(?:\bnot\s+|\b(?:does not|do not|doesn't|don't|cannot|can't|will not|won't|not)\s+"
            r"(?:(?:necessarily|always|automatically|universally)\s+)?"
            r"(?:(?:cover|accept|include|see|use|choose|have)\s+|"
            r"(?:let|allow)\s+you\s+(?:to\s+)?(?:see|use|choose)\s+))\Z")
        unqualified_universal = any(not negative_access.search(lower[:match.start()]) for match in universals)
        if unqualified_universal:
            if route == 'advantage' or not re.search(r'\b(?:accepts?|takes?|participat\w* in) medicare\b', lower):
                return False
    return True


def question_scope_valid(text, question):
    """Check atomic request shape and the supported coverage/prescription scopes.

    Coupled fields in an approved question remain coupled. The remaining
    question meanings retain the caller's existing guards; this is not a claim
    of exhaustive semantic verification for all 41 meanings.
    """
    identifier = question.get('canonical_id', question.get('id'))
    fields = question.get('fields', [])
    allowed_requests = max(1, question.get('atomicRequests', 1), len(fields))
    requests = max(text.count('?'), 1 + len(re.findall(
        r'\b(?:and|also)\s+(?:what|which|when|where|who|how|do you|are you)\b', text, re.I)))
    if requests > allowed_requests:
        return False
    if identifier == 'T07':
        subject = re.sub(r'\b(?:prescription(?: drug)?|drug) (?:coverage|plans?|insurance)\b', '', text, flags=re.I)
        return bool(re.search(r'\b(?:prescriptions?|medicines?|medications?|meds|drugs?)\b', subject, re.I))
    return True


def personal_intake_question(text):
    """Recognize direct requests for personal coverage/medicine/timing reports.

    Educational invitations (what would help, shall we explore, how does X work)
    remain free. A detected intake request needs an explicit approved target;
    the service does not guess that target from this wording.
    """
    for clause in clauses(text):
        lower = clause.casefold()
        # Desired-start questions remain personal intake even when politely
        # phrased as "Would you like ..." or presented as an ASAP/month choice.
        # Keep invitations to explain timing free: they do not ask for a date.
        if re.search(r'\b(?:do|would) you (?:want|like|prefer)\s+(?:your\s+)?'
                     r'(?:medicare(?: coverage)?|coverage|insurance)\s+to\s+(?:start|begin)\b', lower):
            return True
        if re.match(r'(?:would you like|want me to|should we|shall we)\b', lower) or re.search(r'\b(?:help (?:you )?understand|help clarify)\b', lower):
            continue
        if re.search(r'\b(?:what|which|when|where|whose|how much|how many|do you|are you|have you|did you|tell me|tell us)\b', lower) and re.search(
                r'\b(?:you (?:currently |already |now )?(?:have|take|use|live|pay|retir\w*|work\w*|enrol\w*|appl\w*)|your (?:current )?(?:insurance|coverage|prescriptions?|medicines?|medications?|doctors?|birthday|job|zip|income|premium))\b', lower):
            return True
        if re.search(r'\b(?:what|which)\s+(?:[a-z]+\s+){0,2}(?:doctors?|hospitals?|prescriptions?|medicines?|medications?|meds)\b.{0,100}\b(?:you|your|we include)\b|\bhow old are you\b', lower):
            return True
    return False


def explicit_defer_request(quote):
    """A present request to postpone this detail, not a hypothetical or refusal."""
    for clause in clauses(quote):
        if re.search(r"\b(?:if|suppose|hypothetically|used to|don't|do not|not)\b", clause, re.I):
            continue
        if re.search(r'\b(?:leave|save|keep|hold)\b.{0,100}\b(?:for later|until later|for another time)\b|\b(?:come|go|get) back to\b.{0,100}\blater\b', clause, re.I):
            return True
    return False


def named_defer_targets(quote):
    """Named question objects in a present postponement request.

    These aliases identify approved meanings, not new profile fields. Mentions
    in an adjacent educational question do not determine the postponed target.
    """
    found = set()
    for clause in clauses(quote):
        if not explicit_defer_request(clause):
            continue
        if re.search(r'\b(?:job|employment|medicine|medication|prescription) start[- ](?:month|date)\b', clause, re.I):
            # An embedded start-date alias is not the coverage-start meaning.
            # This sentinel can only reject a mismatched disposition; it never
            # creates or routes to an unapproved field.
            found.add('non_coverage_start')
        elif re.search(r'\b(?:start[- ]month|start[- ]date|(?:desired|coverage) start)(?:\s+question)?\b', clause, re.I):
            found.add('T04')
        if re.search(r'\b(?:doctor|provider|hospital)(?:s| names?| list)?\s+questions?\b', clause, re.I):
            found.add('T06')
        if re.search(r'\b(?:prescription|medicine|medication)(?:s| names?| list)?\s+questions?\b', clause, re.I):
            found.add('T07')
    return found


_START_QUESTION = r'(?:start[- ]month|start[- ]date|(?:desired|coverage) start)(?:\s+question)?'
_START_OBJECT = r'(?:(?:the|my|our|this|that)\s+)?' + _START_QUESTION
_REQUEST_PREFIX = r"(?:(?:please|let's|let us|can we|could we|I(?:'d| would) like to)\s+)?"
_START_DEFERRAL = re.compile(
    r'\A\s*' + _REQUEST_PREFIX + r'(?:'
    r'(?:leave|save|keep|hold)\s+' + _START_OBJECT + r'\s+(?:for later|until later|for another time)'
    r'|(?:come|go|get) back to\s+' + _START_OBJECT + r'\s+later'
    r')\s*[.!?;]?\s*\Z', re.I)


def explicit_named_start_deferral(message):
    """One bounded conversation control, independent of extraction labels.

    Match a complete leading current request, preserving its exact original
    quote. Never search an inner phrase of quoted/attributed speech, a conditional,
    or an employment/medicine start question. A second mention of this target
    leaves its current intention ambiguous and remains semantic interpretation.
    This creates only a conversational disposition, never a date or other fact.
    """
    if not isinstance(message, str):
        return None
    parts = [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+', message) if part.strip()]
    if (not parts or not _START_DEFERRAL.fullmatch(parts[0].replace('’', "'"))
            or any(re.search(_START_QUESTION, part, re.I) for part in parts[1:])):
        return None
    return {'id':'T04', 'entity':'profile', 'fields':[{'key':'choice','value':'deferred'}],
            'quote':parts[0], 'scope':'intended', 'subject':'beneficiary',
            'uncertain':False, 'correction':False}


def canonical_named_start_deferral(update, message):
    """Correct a disposition-only proposal for an independently explicit control."""
    if (not isinstance(update, dict) or update.get('entity') != 'profile'
            or update.get('subject') != 'beneficiary' or update.get('scope') not in {'current', 'intended'}
            or update.get('fields') not in ([{'key':'choice','value':'later'}],
                                          [{'key':'choice','value':'deferred'}],
                                          [{'key':'choice','value':'check later'}],
                                          [{'key':'choice','value':'unknown'}],
                                          [{'key':'choice','value':'not sure'}])):
        return None
    control = explicit_named_start_deferral(message)
    if control is None or update.get('quote') != control['quote']:
        return None
    return {**update, **control}


def normalize_named_start_deferral(updates, message):
    """Merge the explicit navigation control before ordinary report validation.

    Omission or a mislabeled disposition cannot change the control's meaning.
    Only disposition proposals for its exact clause are replaced. Other fields,
    quotes and reports retain their original validators and the 24-update bound.
    """
    control = explicit_named_start_deferral(message)
    if control is None:
        return updates
    remaining = [update for update in updates if canonical_named_start_deferral(update, message) is None]
    if len(remaining) >= 24:
        return updates
    return [*remaining, control]
