"""D79 navigation coaching. These milestones are not insurance readiness gates."""

LESSONS = ['basics', 'parts', 'routesintro', 'drugbasics', 'medigap', 'costs', 'checks']
FACT_IDS = {'basics', 'routesintro', 'drugbasics', 'options', 'parts', 'parta',
            'partb', 'original', 'advantage', 'drugs', 'medigap', 'extras',
            'costs', 'checks', 'dates', 'next', 'medical_limit', 'switching'}
LESSON_LABELS = {'basics': 'Start with what Medicare is',
                 'parts': 'Learn about Parts A and B',
                 'routesintro': 'Learn how the coverage options fit together',
                 'drugbasics': 'Learn about prescription coverage',
                 'medigap': 'Learn about Medicare supplements',
                 'costs': 'Learn how Medicare costs work',
                 'checks': 'Learn what to compare in a plan'}


def initial():
    return {'learningSeen': [], 'samplesVisible': False}


def valid(value):
    return (isinstance(value, dict) and set(value) == {'learningSeen', 'samplesVisible'}
            and type(value['samplesVisible']) is bool
            and isinstance(value['learningSeen'], list)
            and len(value['learningSeen']) <= len(FACT_IDS)
            and all(isinstance(x, str) and x in FACT_IDS for x in value['learningSeen'])
            and len(value['learningSeen']) == len(set(value['learningSeen'])))


def remember(meta, facts):
    for fact in facts:
        if fact['id'] not in meta['journey']['learningSeen']:
            meta['journey']['learningSeen'].append(fact['id'])


def next_lesson(meta):
    return next((x for x in LESSONS if x not in meta['journey']['learningSeen']), None)


def offer(flow, guide, record, question):
    """A small contextual next step, never the old seven-task hub."""
    meta = record['conversation']
    task = meta['task']
    if question or meta['journey']['samplesVisible']:
        return None
    if not task and flow.value(guide,'intent.goal')=='unresolved':
        return {'question':'What would you like help with? You can type it below.',
                'choices':[], 'signature':'goal.other'}
    if task == 'learn' or not task:
        lesson = next_lesson(meta)
        choices = [{'value': 'explore', 'label': 'Explore my coverage options'}]
        choices.append({'value': 'learn_next', 'label': LESSON_LABELS[lesson]} if lesson
                       else {'value': 'samples', 'label': 'See sample plans'})
        return {'question': 'Would you like to explore options for your situation, or keep learning first?',
                'choices': choices, 'signature': 'learning.' + (lesson or 'done')}
    if task in {'compare', 'review'} and not meta['preparing']:
        return {'question': 'Would you like to build a picture of your situation, or see the sample plans first?',
                'choices': [{'value': 'explore', 'label': 'Help me explore my options'},
                            {'value': 'samples', 'label': 'See sample plans first'}],
                'signature': 'comparison.start'}
    if task in {'browse', 'compare', 'review'}:
        return {'question': 'Ready to see how plan options are presented?',
                'choices': [{'value': 'samples', 'label': 'See sample plans'},
                            {'value': 'review', 'label': 'Review my information first'}],
                'signature': 'options.preview'}
    return {'question': 'Would you like to continue exploring your coverage options?',
            'choices': [{'value': 'explore', 'label': 'Continue to my coverage options'},
                        {'value': 'samples', 'label': 'See sample plans first'}],
            'signature': 'return.' + task}


SUMMARIES = {
    'browse': 'The current plan cards are samples. They can show you what to compare, but cannot establish which plans are available for your location and date.',
    'compare': 'Your information is ready to review below. The current plan cards are samples, so a personal match still needs verified plan information.',
    'review': 'We can use these details to review your options, including keeping your current coverage. The current plan cards are samples, not a recommendation to change plans.',
    'timing': 'We have the dates you know together. Any dates left open still need checking before an enrollment deadline or coverage start can be confirmed.',
    'providers': 'Your doctor preferences are together. Whether a doctor accepts a particular plan still needs checking with the exact office and plan.',
    'drug_coverage': 'Your prescription information is together. Coverage still needs checking against the exact medicine and plan.',
    'drug_pricing': 'Your prescription and fill details are together. A personal price still needs the plan, pharmacy and pricing checks.',
    'medigap': 'Your Medicare supplement questions are organized. Any buying or return rights still need the applicable rules and your actual coverage history checked.',
    'snp': 'We can explain these plan types. Whether a specific plan is available to you still needs its exact requirements checked.',
    'costs': 'We can keep your cost questions together. A personal total still needs the relevant plan, care and prescription costs checked.'}


def presentation(flow, guide, record, question):
    meta = record['conversation']
    samples = meta['journey']['samplesVisible']
    phase = (3 if samples else 0 if not meta['task'] or meta['task'] == 'learn'
             else 1 if question or meta['task'] not in {'browse','compare','review'} or not meta['preparing'] and meta['task'] in {'compare', 'review'}
             else 2)
    fields = {q['field'] for q in flow.baseline if flow.value(guide, q['field']) is not None}
    if flow.value(guide,'subject.role') is not None:fields.add('subject.role')
    reports = {key for key, fact in record['facts'].items() if not fact.get('stale')}
    return {'phase': phase, 'labels': ['Your goal', 'Your situation', 'Your options', 'Your next step'],
            'meaning': 'Conversation milestones, not verified eligibility or a recommendation.',
            'reportedGroups': len(fields) + len(reports - {'RC01'}),
            'samplesVisible': samples,
            'summary': SUMMARIES.get(meta['task'], '') if not question else '',
            'nextStep': offer(flow, guide, record, question)}
