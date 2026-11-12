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
        personal = re.search(
            r"\byou(?: currently| now)? (?:have|receive)\b|"
            r"\byou(?:'re| are)(?: currently| now)? (?:covered|uninsured)\b|"
            r'\byour (?:current |present )?(?:insurance|coverage|health plan)\b', lower)
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
    noun = r'(?:(?:current|medical|health|drug|prescription|medicare)\s+){0,3}(?:insurance|coverage|health plan)'
    factual_person = False
    for sentence in clauses(text):
        lower = sentence.casefold()
        if '?' in sentence or re.match(r'\s*(?:if|suppose|whether|hypothetically)\b', lower):
            factual_person = False
            continue
        direct = re.search(r"\b(?:you|they|he|she)\s+(?:(?:currently|already|now)\s+)?(?:have|has|receive|receives)\s+(?:a\s+)?" + noun + r'\b(?!\s+(?:options|choices|questions)\b)', lower)
        covered = re.search(r"\b(?:you|they|he|she)(?:'re| are| is| remain| remains| stay| stays)\s+(?:currently\s+)?covered\b", lower)
        possessed = re.search(r'\b(?:your|their|his|her)\s+' + noun + r'\b(?!\s+(?:options|choices|questions)\b)', lower)
        if direct or covered:
            return True
        if possessed:
            rest = lower[possessed.end():]
            # Permit relative/parenthetical clauses while retaining the explicit
            # possessive subject. Potential/conditional coverage is not actual.
            if re.search(r'\b(?:is|comes|ends|will|through|from|under|via|active)\b', rest) and not re.search(r'\b(?:would|could|might)\b', rest):
                return True
        if factual_person and re.match(r'\s*(?:the\s+)?(?:insurance|coverage|health plan)\s+(?:is|comes|ends|will)\b', lower):
            return True
        factual_person = bool(re.search(r"\b(?:you|they|he|she)(?:'re| are| is| have| has)\s+(?:currently\s+)?(?:retired|retiring|working|employed|enrolled|covered)\b", lower))
    return False


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
        if re.search(r'\b(?:start[- ]month|start[- ]date|(?:desired|coverage) start)(?:\s+question)?\b', clause, re.I):
            found.add('T04')
        if re.search(r'\b(?:doctor|provider|hospital)(?:s| names?| list)?\s+questions?\b', clause, re.I):
            found.add('T06')
        if re.search(r'\b(?:prescription|medicine|medication)(?:s| names?| list)?\s+questions?\b', clause, re.I):
            found.add('T07')
    return found


def canonical_named_start_deferral(update, message):
    """Normalize an explicit named T04 postponement; never infer another report.

    Only a sole choice proposal, exact current quote, present direct request and
    unambiguous named start question qualify. A third person's or hypothetical
    question, mixed targets, dates, another field, or a negation cannot be remapped.
    """
    if (not isinstance(update, dict) or update.get('entity') != 'profile'
            or update.get('subject') != 'beneficiary' or update.get('scope') not in {'current', 'intended'}
            or update.get('fields') not in ([{'key':'choice','value':'later'}],
                                          [{'key':'choice','value':'deferred'}],
                                          [{'key':'choice','value':'check later'}])):
        return None
    quote = update.get('quote')
    if (not isinstance(quote, str) or not quote.strip() or quote not in message
            or len(clauses(quote)) != 1
            or re.search(r"\b(?:if|suppose|hypothetically|used to|yesterday|previously|mother|father|mom|dad|spouse|wife|husband|their|his|her|and|or|both)\b", quote, re.I)
            or named_defer_targets(quote) != {'T04'}):
        return None
    # Only a current imperative/first-person request can resolve model uncertainty.
    request = re.compile(r"\A\s*(?:(?:please|let's|let us|can we|could we|I(?:'d| would) like to)\s+)?(?:leave|save|keep|hold|come back to|go back to|get back to)\b", re.I)
    if not request.search(quote):
        return None
    return {**update, 'id':'T04', 'fields':[{'key':'choice','value':'deferred'}],
            'uncertain':False, 'scope':'intended'}
