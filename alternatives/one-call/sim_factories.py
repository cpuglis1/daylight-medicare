"""Flow factories for the bake-off harness (``python3 -m sim.run --flow-factory``).

Two factories with the same switches and the same data wiring, so the two
loops are compared like for like:

- ``make_two_call_flow`` : advisor-first's ``NaturalConversation``, configured
  the way the :8895 demo configures it;
- ``make_one_call_flow`` : ``OneCallConversation``, configured the way the 8897
  server configures it.

With an injected client (a scripted transport) the conversation is constructed
directly: no server, no database, no key, no network. That path is tested.

With no client the factory builds the real server wiring on an unbound port
and returns its conversation, which uses the live model client, the shared
daily budget ledger and the local display database. That path makes paid model
calls, has never been run, and is for an owner-cleared bake-off only.

Pilot knowledge: neither factory claims an acceptance surface unless the caller
names one (``pilot_knowledge_surface``). The owner's acceptance of the reviewed
pilot facts covers ``unified-8895`` and ``hosted-demo`` only, so by default both
loops teach from the same library without those facts.
"""
import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

import json

from natural_flow import NaturalConversation

from one_call_flow import OneCallConversation
import one_call_server

ADVISOR = _paths.ADVISOR
LIVE_TWO_CALL_DATABASE = ADVISOR / 'var/demo-8895/bakeoff-two-call.sqlite3'


def _direct(conversation, client, budget, count_tokens):
    """The conversation as advisor-first's server constructs it, without a server."""
    flow = conversation(None, None,
                        json.loads((ADVISOR / 'web/guide-contract.json').read_text()),
                        json.loads((ADVISOR / 'web/teaching-facts.json').read_text()),
                        json.loads((ADVISOR / 'web/readiness-content.json').read_text()),
                        client, True, budget, count_tokens, fixture=False)
    # What server.build sets on a live conversation: the reviewed model policy and one recovery slot.
    policy = json.loads((ADVISOR / 'model-policy.json').read_text())
    flow.agent.reasoning_effort = policy['reasoning_effort']
    flow.agent.composition_reasoning_effort = policy.get('composition_reasoning_effort', 'none')
    flow.agent.connection_retries = 1
    flow.agent.composition_recovery = True
    flow.model_agents = {client.model: flow.agent}
    return flow


def _make(one_call, client, *, budget=None, count_tokens=None, medigap_repository=None, part_d_repository=None,
          doctor_service=None, prescription_service=None, pilot_knowledge_surface=None, reconcile=None,
          inline_reconcile=None, tool_outputs=True, **server_options):
    if client is None:
        if budget is not None or count_tokens is not None:
            raise ValueError('The live wiring uses the server’s own budget ledger and token counter.')
        checks = doctor_service is not None or prescription_service is not None
        options = {'database': None if one_call else LIVE_TWO_CALL_DATABASE, **server_options}
        service = one_call_server.build_one_call(
            0, one_call=one_call, medigap_repository=medigap_repository, part_d_repository=part_d_repository,
            conversation_checks=checks, doctor_service=doctor_service, prescription_service=prescription_service,
            reconcile=reconcile if one_call else None, **options)
        flow = service.adaptive
        flow.sim_service = service          # the conversation's data services live on the server object
    else:
        if server_options:
            raise ValueError('Server options apply to the live wiring only.')
        flow = _direct(OneCallConversation if one_call else NaturalConversation, client, budget, count_tokens)
        one_call_server.configure(flow, medigap_repository=medigap_repository, part_d_repository=part_d_repository)
        if doctor_service is not None or prescription_service is not None:
            one_call_server.attach_checks(flow, doctor_service=doctor_service,
                                          prescription_service=prescription_service,
                                          part_d_repository=part_d_repository)
        if one_call and reconcile is not None:
            flow.reconciler.enabled = bool(reconcile)
    flow.pilot_knowledge.surface = pilot_knowledge_surface
    if one_call:
        if inline_reconcile if inline_reconcile is not None else client is not None:
            # A scripted run is repeatable only when the record pass finishes before the next turn.
            flow.reconciler.executor = lambda work: work()
        # The graders read code-made tool values to tell a relayed amount from an invented one.
        flow.one_call_eval = bool(tool_outputs)
    return flow


def make_two_call_flow(client=None, **options):
    """advisor-first's two-call conversation with the :8895 switches.

    Options: ``budget``, ``count_tokens``, ``medigap_repository``, ``part_d_repository``,
    ``doctor_service``, ``prescription_service``, ``pilot_knowledge_surface``.
    """
    for name in ('reconcile', 'inline_reconcile', 'tool_outputs'):
        if name in options:
            raise ValueError('That option belongs to the one-call flow.')
    return _make(False, client, **options)


def make_one_call_flow(client=None, **options):
    """The one-call conversation with the same switches.

    Options: those of ``make_two_call_flow``, plus ``reconcile`` (None follows the
    ``DAYLIGHT_ONE_CALL_RECONCILE`` switch), ``inline_reconcile`` (run the record pass
    before the turn returns; the default with an injected client) and ``tool_outputs``
    (publish this turn's tool outputs under ``metrics.oneCall.toolOutputs``).
    """
    return _make(True, client, **options)
