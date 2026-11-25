"""Bind held-out fact and coverage prompts to ordinary local advisor visits.

Only manually reviewed source-line hashes are admitted. Setup records visitor
reports and prior visitor turns. Current-turn evidence must come from the
advisor's normal retrieval and Plans projection.
"""

import hashlib
import json

# These are prerequisites for running the trials, never requested tool
# outputs. Evidence is fetched through the ordinary composer and may differ.
RULES = {
    'work_cobra': 'working_coverage_sep',
    'hsa_spend': 'hsa_medicare',
    'drug_delay': 'partd_penalty',
    'drug_basis': 'partd_penalty',
    'help_penalty': 'extra_help',
    'switch_period': 'annual_enrollment',
    'annual_date': 'annual_enrollment',
    'program': 'extra_help',
}

# The selected hypothetical plan is a checked-in 2026 Collier browsing entry.
PLAN = '2026:H1032:198:000'

PRIOR_TOPIC = {
    'work_cobra': 'Suppose someone’s former employer offers them COBRA.',
    'hsa_spend': 'Suppose someone saved money in an HSA before starting Medicare.',
    'drug_delay': 'I’m asking generally about a gap after someone first had a chance to enroll in drug coverage.',
    'drug_basis': 'I have a question about how the Part D penalty is calculated when it applies. I might want to speak with an advisor after this.',
    'help_penalty': 'I’m asking about the Part D late-enrollment penalty.',
    'annual_date': 'I’m asking about the yearly Medicare plan change period.',
    'plan_year': 'I’m looking at a 2026 plan listing.',
    'program': 'I’d like to understand Extra Help for prescription costs.',
    'handoff_yes': 'I’d like the option to speak with someone.',
}

PRIOR_PREFERENCE = {
    2: 'Plain language, please.',
    4: 'I want to make this decision for myself.',
    5: 'Let’s take this one step at a time.',
}

# Earlier-turn-only tool conditions require a real prior tool turn. An exact
# office assignment and a displayed Medigap price need their native sources.
LINE_HASHES = {
    'medicare_factual_support-work_cobra-1': '2c80b8becddf9cacd7132264eb55e63a01a9ac5e5a933196d44b3a8285edbd99',
    'medicare_factual_support-work_cobra-2': '0a60b09a207958f1e4a901ddb43e73c83269aae657c52f61eeff7a0bed30da7e',
    'medicare_factual_support-work_cobra-3': '43e6ef68ddd012a7a807a3db91719013fb4f063f57b8cf7d391581242d21bf51',
    'medicare_factual_support-work_cobra-4': '99a5aa06df66025015ae495b8bdfcbde8b21cb00390be7deaed8102e1891fb3a',
    'medicare_factual_support-work_cobra-5': '85c65059624fc971d9020f2c89af45837f4edb1625d619557a61b10c9112f98b',
    'medicare_factual_support-hsa_spend-1': '9fa8a1cb9b8b3e755a67c76ca7097b6148e3e0e9a4f00b4f8117c893e2a84410',
    'medicare_factual_support-hsa_spend-2': 'ed897b31e57dd51f2b09ed5e77d7be54e782cffd18edd48fd23603c669d55521',
    'medicare_factual_support-hsa_spend-3': 'f75f5db2c5aeba26b025b5cdde6e57498fa71a130021ff7b34e622a3b637c2c7',
    'medicare_factual_support-hsa_spend-5': '3feee482e61cbbf4ede3a67abee56a0da1114839072b203561af4e7e1f895283',
    'medicare_factual_support-drug_delay-1': '1bcf5d936d247ba6181bfed06e3ecf05dccdb0c95163eaf640d1ecec9edbc851',
    'medicare_factual_support-drug_delay-2': '8fb1d0ce44650a7ef0d0e3ce3c12add39aa35dc4c5f0fca6164056c48a7a37c4',
    'medicare_factual_support-drug_delay-3': 'd781902c4853435d0850c6eac8c61465ca703b67c68c013b21c687ec5e4f6fff',
    'medicare_factual_support-drug_delay-5': '81c929364339699bf23bf34b7f58dbdaa616cfd5aa8eb80c2f0c00f774f9e4e4',
    'medicare_factual_support-drug_basis-1': '60c9091622db15034affb06dd418fc285ad1827987e750b5a4c40d5aa3242486',
    'medicare_factual_support-drug_basis-2': '7f514a09fe17dc0db85d8b1b3fd5e0f996de08d44073eff9787828a51233815c',
    'medicare_factual_support-drug_basis-3': '3fed7bdc8853981e3b03d9cc3564d6124b95d3528f2243ac8a01323dc7a3f2ef',
    'medicare_factual_support-drug_basis-4': 'e739ed43a0a684870b7ca4db5277c4ce5a4c99aa73c377e5bdecd324521ebfda',
    'medicare_factual_support-drug_basis-5': 'f6a0784631a5c81769e735e95e42e2ba981870d851d0aa75e78518653a8b2779',
    'medicare_factual_support-help_penalty-1': 'a4d8a9c0d7a367e3a4bcef27be503342d3c013855e20cc77ca93871fed5a9125',
    'medicare_factual_support-help_penalty-2': '3ddfeeeb9a2f55178a159bdddbc53159db865ffbf2b001a7621f5a359289a9e6',
    'medicare_factual_support-help_penalty-3': 'b98f7d7e755f5939f0c32cd64f35518d5cf8222ba52c719bfbced1ab5b4d369e',
    'medicare_factual_support-help_penalty-4': '9978250498741aa58732fdc77e4d56467e94f8578ee12f5c27a033eeec7b3519',
    'medicare_factual_support-help_penalty-5': '5d13729d80b87bb7073751c20e905632daec74482105f92c80a372f62bdae35b',
    'medicare_factual_support-switch_period-1': '9c8d92d60a9f85a4f60542bf544856fa0f25b258bc8d23aa86f959ba74813098',
    'medicare_factual_support-switch_period-2': '855efd369b47aef0ae4626555958dcd4569f57c8bc6aa1448807fbdb45beb39e',
    'medicare_factual_support-switch_period-3': 'e9a2b056aac25f9265d49019cdbd9dbda6bdab95ed0e97bd95fcd50899345d6d',
    'medicare_factual_support-switch_period-5': '08c34cc92a1041dde5a7c2e91870d81d53b585174c5408b4b246bd4cb72c6231',
    'required_coverage-annual_date-1': '0996e00ac1378b8113524cf6de5228b462beaed0e798f582822b28176319a340',
    'required_coverage-annual_date-2': '251418c054950c4f5b3e7a50037941dd6972851cd33f15a72c405d239c5fb5cb',
    'required_coverage-annual_date-3': 'd09432f2b64684c0fcd0d4b09dfbc2bb7d27f847d38bc25bea4482475d28ebfb',
    'required_coverage-annual_date-4': '16fa72549aa89db06886f45d66a2fba6751836597f32e2da2557e10689af28fb',
    'required_coverage-annual_date-5': 'cb8a0671ee89164c578e471bceb317aae9587e99871bde39da1fc752bffe26c8',
    'required_coverage-plan_year-1': 'b81b5e39b7bf52c4ad3cfc2081042d97c3d088cd9904a7fdfccd636ea5d0f38f',
    'required_coverage-plan_year-2': '6824004fa34ff51b6698c847c7156947dbeb180969864a92240ae9c7da6fbc36',
    'required_coverage-plan_year-3': '71cfda3f8ef963417b7ae6921113d31a2005a29049a3b7aaed59b9f2a6e677e6',
    'required_coverage-plan_year-4': '4a3b1fa26493e893fd90f55b7f7f3e11e6cc061d9f07cccf9df530581f7bbe23',
    'required_coverage-plan_year-5': 'afd4f0a713178e8463ca62dcbaaa0e69d66c7e7589e7b97866fcc8c6f605bee4',
    'required_coverage-program-1': '0b3996d70520aadd3575d1ec5275ca67c43759c716316d7089a0c610ee60822c',
    'required_coverage-program-2': '17aba9acf092daf5bb59bb47696d46727451623c589109b3a6550cc009fad39f',
    'required_coverage-program-3': '25555b2871fa5451e37ceba0cbdb93d186c9650b736d088c3105a23e383e3a55',
    'required_coverage-program-4': '7f4803611d075a0bfe02f67204111a83a2060abadeda4d8e07a46c1231207787',
    'required_coverage-program-5': '957009434a53ce891ddbaf26175c9986b55a913da5ff94d40b66d4600b07dd8f',
    'required_coverage-handoff_yes-1': 'c5884f6c948b5a3b904aff266fe50b4f4750483ce8277c0445535f794d3ad0ab',
    'required_coverage-handoff_yes-2': '06c1a3ac98740ed7d2e1043dea1e8683f13438da1d63d4c02bdde1fd42de3df9',
    'required_coverage-handoff_yes-3': '00669e7ce4602a227337e099fa36980e1d917643e223b834f539b0515e2a222f',
    'required_coverage-handoff_yes-4': 'dde9a09e14003cbef9bafee101d63713ee52c60fb579d48772a4f5b8c4f22cb5',
    'required_coverage-handoff_yes-5': 'b7abdb3063d9e56ffc56763df2bef1efc3bf5303c3a14226c1218225280268c5',
}

RULE_TEXT_HASHES = {
    'working_coverage_sep': '0d9f7593bea46dbec180cdfe18d356f27c863be907aadcfd606c59c30826659a',
    'hsa_medicare': '7fe9d7f4182b4386830f911d744edc57bee12feb98f0dded18834b065c09142d',
    'partd_penalty': '0854cd22600119ec8651bc904ea0fbe71048a2b4bfcdc79f4336f5fa2665c025',
    'extra_help': 'a0b79d02991eb0edb56f84e4496a546ddabab0222876c2a22ab9daa3ffcda39e',
    'annual_enrollment': '47ef8a6112fb4f337cb4c2e0f8aa66bcbdfa211b26e02c5fc8b05f72b3a25a13',
}


def build_starts(rows):
    """Return typed starts for pinned fictional cases in the supplied corpus.

    Args:
        rows: Mapping from case ID to its decoded row and source-line digest.
    Returns:
        Visit actions, assertions and separately scoped Plans bindings by ID.
    """
    starts = {}
    for case_id, line_hash in LINE_HASHES.items():
        if case_id not in rows:
            continue
        case, _ = rows[case_id]
        family = case['scenario_family']
        variant = int(case_id.rsplit('-', 1)[1])
        relationship = 'someone' if case['journey'] == 'caregiver' else 'self'
        goal = 'review' if family == 'plan_year' else 'learn'
        setup = [
            {'type': 'choice', 'id': 'T01', 'fields': {'choice': goal}},
            {'type': 'choice', 'id': 'RC01', 'fields': {'choice': relationship}},
        ]
        history = []
        if variant in PRIOR_PREFERENCE:
            history.append((PRIOR_PREFERENCE[variant], '', ''))
        if family in PRIOR_TOPIC:
            history.append((PRIOR_TOPIC[family], '', ''))
        starts[case_id] = {
            'lineHash': line_hash, 'setup': setup, 'history': history,
            'relationship': relationship, 'fields': {'intent.goal': goal},
            'source_id': RULES.get(family),
            'requires_source_lookup': case['judge'] == 'medicare_factual_support',
            **({'selected_plan': PLAN} if family == 'plan_year' else {}),
        }
    return starts


def verify_start(flow, state, start):
    """Verify the accepted rule prerequisite without adding it to model context.

    Args:
        flow: The ordinary advisor conversation with loaded accepted rules.
        state: The signed visit state checked by the caller.
        start: The pinned fixture defining the exact prerequisite.
    Raises:
        ValueError: If the accepted source is absent or has changed.
    """
    source = start.get('source_id')
    if source:
        text = flow.rule_facts.get(source, {}).get('text', '')
        if hashlib.sha256(text.encode()).hexdigest() != RULE_TEXT_HASHES[source]:
            raise ValueError('The accepted Medicare rule for this trial is unavailable.')


def prepare_trial(service, owner, state, start):
    """Resolve a real 2026 browsing selection using Send-bound Plans permission.

    Args:
        service: The built local advisor service.
        owner: This trial's isolated visit owner.
        state: The signed visit state checked by the caller.
        start: The pinned fixture with an optional catalog selection.
    Returns:
        Additional normal turn permissions for the selected catalog entry.
    Raises:
        ValueError: If the scoped catalog or selected browsing entry is absent.
    """
    selected = start.get('selected_plan')
    if selected is None:
        return {}
    from plans_context import POLICY, rehydrate

    plans = service.adaptive.plans_service
    view = plans.for_handoff(owner, None)
    if view['scope']['year'] != 2026 or view['scope']['county_fips'] != '12021':
        raise ValueError('The 2026 Collier browsing catalog is unavailable.')
    request = {'version': POLICY, 'reviewToken': None, 'viewDigest': view['view_digest'],
               'visibleIds': [selected], 'comparedIds': [], 'selectedId': selected,
               'field': None, 'mode': 'all', 'navigation': 'advantage'}
    rehydrate(plans, owner, request, None)
    return {'plansContext': request, 'plansContextPolicy': POLICY}


def verify_observation(trace, start):
    """Check first-compose prerequisites independently of the model's behavior.

    Args:
        trace: The local trial trace or None if no trace was recorded.
        start: The pinned typed start.
    Returns:
        Whether the initial request had the required lookup or catalog route.
    """
    selected = start.get('selected_plan')
    needs_lookup = start['requires_source_lookup']
    if not (needs_lookup or selected):
        return True
    compose = next((call['request'] for call in (trace or {}).get('modelCalls', [])
                    if call.get('kind') == 'compose' and isinstance(call.get('request'), dict)), {})
    if selected:
        try:
            context = json.loads(compose['input'][0]['content'])['resolved_context']['plans_context']
            return context.get('selected_id') == selected and context.get('scope', {}).get('year') == 2026
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            return False
    for tool in compose.get('tools', []):
        if tool.get('type') == 'function' and tool.get('name') == 'lookup_medicare_sources':
            source_ids = tool.get('parameters', {}).get('properties', {}).get('source_ids', {})
            return start['source_id'] in source_ids.get('items', {}).get('enum', [])
    return False
