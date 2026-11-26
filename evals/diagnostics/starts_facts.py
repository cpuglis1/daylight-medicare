"""Bind held-out fact and coverage prompts to ordinary local advisor visits.

The runner admits only pinned source lines. Setup records the shopper’s
goal and relationship. The prompt supplies the rest of the question. Evidence
comes from the advisor's normal retrieval and Plans projection.
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

# These rows can run with the normal advisor source or Plans context below.
# Cases that need evidence from a verified earlier lookup are outside this adapter.
LINE_HASHES = {
    'medicare_factual_support-work_cobra-1': '538242c19469c60f2674eaef9775d545ff1d34f27c91aa47fb16a34fa5b2cb17',
    'medicare_factual_support-work_cobra-2': 'dc91817103ff8a6342c5d5f84d86b9cf747487683eb7242bf68e8146a4e1b0a3',
    'medicare_factual_support-work_cobra-3': '3a86be35db2922d6a90bb5ee2646d2e207378f4502a4659a0200a73d2161931c',
    'medicare_factual_support-work_cobra-4': '6818af7f8d613c0999d9d02b56d6c9bd8a9150da100aeb29294ccbaaba07e1da',
    'medicare_factual_support-work_cobra-5': 'f469c8f14fd2a8e3c8688c4b20ede1b4c2b8ff955a9cdb1e6dc4950050dea95e',
    'medicare_factual_support-hsa_spend-1': '1b01684bceddd276a6e178c91cf729b1469d491319d51d31f81531a62309cdcb',
    'medicare_factual_support-hsa_spend-2': '1159fb65629c5b1e4da3a128377cdad73b2fa7acc2d11a14e8301fbe7fb08838',
    'medicare_factual_support-hsa_spend-3': 'c00490e50258703fb2dc4a1f1adb8a842d73959a6ce0224425fc14b0a899397b',
    'medicare_factual_support-hsa_spend-5': '0c7020bd6af731292e9212368474117938b683c285c6827845759a90e36eb68f',
    'medicare_factual_support-drug_delay-1': 'fc6c0f0ad7223d0ef3d322f2a9ddd5cf88acbf7d7ea11ac5d5f7d7b4a09e80e0',
    'medicare_factual_support-drug_delay-2': '08451132b76b14526875d64f1ead64de559586ef96bc57780d89925ea4506bfd',
    'medicare_factual_support-drug_delay-3': '525bc3f3c25c831f45ca26c80a89650caf63e3ca7c5e6d4ddd46b9775c3b2e8a',
    'medicare_factual_support-drug_delay-5': '6b061ff58d78ad2c9a31d7aca48542e3278e38876ee45d80f3d588c0a03eb1b6',
    'medicare_factual_support-drug_basis-1': '4fa42bc28e2730af52b3afad0f05c9e953425fe0e2d9fa143f9a6808505200e5',
    'medicare_factual_support-drug_basis-2': 'ef282baf1f6838e90732062a5e724f30530c468037fb7413efdab134cad21ef8',
    'medicare_factual_support-drug_basis-3': '64d6b8669717dfb49bf2a5ae028f86ddd7279b741dfe154e68e97cd43a4fadad',
    'medicare_factual_support-drug_basis-4': 'b11f019a08147590f99c568dcdb778bdeca4c6f2790a4e5437f44c3c561d7e20',
    'medicare_factual_support-drug_basis-5': '67bbd64264b19921ef2571c8d08db5c508a2579901a4c939e49e57ea45299157',
    'medicare_factual_support-help_penalty-1': '1d6272d14b0ebf93eb3ddc252e32e12aa1c2f2505f0d769750f1d7169511778e',
    'medicare_factual_support-help_penalty-2': 'd17cc09364cb83037e4f49395f81376a3c5f49a5265fb45c9f83dbb0552b13d5',
    'medicare_factual_support-help_penalty-3': 'a6de9c61d41977c147d6e883985adf9897d01fbc04bc2d23e52916d1f4c005ec',
    'medicare_factual_support-help_penalty-4': 'df14254494f88a06c9e82b7cc27234e11363971e7950c9f7a622f853d18372ac',
    'medicare_factual_support-help_penalty-5': 'ba697c8ee3e4a1e60022adbeb79892a6dfbb6070e18317eccc37c3e486ab9e9c',
    'medicare_factual_support-switch_period-1': 'c3d6ade3225e143eab6c8099138040facc0c92f1e7e601d9537760572b30be26',
    'medicare_factual_support-switch_period-2': '2e29449ae4f468241e43a10bed206c770e0fc5f485992de025b22b9155fba79c',
    'medicare_factual_support-switch_period-3': '2c3abcc62b2bc1d8e47793e7539ca93949b9494f66c46e659930a86c38d54e27',
    'medicare_factual_support-switch_period-5': 'dab119fd513d75e1e318e73035cb242d9b8b9641efe117a8d0192286a1c4cbaf',
    'required_coverage-annual_date-1': '5c337da5ef5ce3972c6622e63a1aec0a8b3c9344e2b63c29251d60df8ebb3405',
    'required_coverage-annual_date-2': 'd4c32ba51c89dff6f092247ed27a5ba574759328446a5f88c18329a20a105880',
    'required_coverage-annual_date-3': '70caf6238e91a1a7d8fc4205ccdd8b6e098c76999441ef1b1021e65bff2993a7',
    'required_coverage-annual_date-4': 'd71878d729348d6ca0989ed78aea764a71d1f02419456c819f9948c6983d8e7f',
    'required_coverage-annual_date-5': '782889f76ad54925a554a475c6f9052080b1bba8e6aa0ea52174dae7309e7bee',
    'required_coverage-plan_year-1': 'f65c8336710d2144789ac1c4f43ae286e924995398a65e3ba52aca4d47dbe575',
    'required_coverage-plan_year-2': 'd9c520ef4d00fe5bd81961b96818abc6654dce82be39dfadf0cb64d0d692e353',
    'required_coverage-plan_year-3': '02bda8f1a7cacba6f26f5cbc53b090f4aa32c22b7c9d1c1f1d64643490e4aeb2',
    'required_coverage-plan_year-4': 'adc30a34c351cd9f4e5073956db52d70f03e98d26aa6c4587edecd8339d95898',
    'required_coverage-plan_year-5': '6c83f04cca8d00627ff58a9fbb73f65e3f9d3cac963f58d29e63b4ee827859de',
    'required_coverage-program-1': '6f7d3ea09bdd62431a2aae0fa99c5883ad8a4be1f2b23079baa86393d261f82e',
    'required_coverage-program-2': 'c82b5546f569e5ce71fcc89c1aa22007ab0850041b1e14e90d77d1693f6d47d2',
    'required_coverage-program-3': '87905f600b687c6cb76704c498e467c047e78d0546522fe3468d89c45eb20c23',
    'required_coverage-program-4': '2a91b07353cb8981a1c66a7a053fc6ed306624eaaf6493911332ac8c151981f6',
    'required_coverage-program-5': '1ef1b816316fc432e54a4636e91aeca3431d98c2f82abea4e71ad4f2a62b60ab',
    'required_coverage-handoff_yes-1': 'a9df3ab30d1151d065e19015daac18c8bf45d14efd5011d24de3f81be26fbfc7',
    'required_coverage-handoff_yes-2': 'fdfa29531cda8eb49941c7eedeeb277b0147161ecf38b574f7c8173fb593743e',
    'required_coverage-handoff_yes-3': '6f6bde60bf211f27c7238fb28a19cd1e05021efa5de5e47f362baf38e119cd47',
    'required_coverage-handoff_yes-4': '91dc988d0e16a52b0e3792cc6b406df51bae90fd5e74a68ba7b24fb3c0d7a037',
    'required_coverage-handoff_yes-5': 'c70d5a5f58910304d62f7fb97c8def2649a279d0eab4449f3c841471937bd525',
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
        relationship = 'someone' if case['journey'] == 'caregiver' else 'self'
        goal = 'review' if family == 'plan_year' else 'learn'
        setup = [
            {'type': 'choice', 'id': 'T01', 'fields': {'choice': goal}},
            {'type': 'choice', 'id': 'RC01', 'fields': {'choice': relationship}},
        ]
        starts[case_id] = {
            'lineHash': line_hash, 'setup': setup, 'history': [],
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
