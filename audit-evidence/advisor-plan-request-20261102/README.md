# Actual plan requests and repeated desired-start questions

November 2, 2026 (America/New_York), owner-authorized repair within five minutes. D86/D73: respect the requested task and avoid collecting information that cannot unlock the result. Astra independently inspected the routing and question guard; the primary agent implemented and verified the scoped repair.

## Causes and changes

The composer could substitute a coverage-route lesson for an actual plan-list request. Its existing source holds prohibit personal results, but its conversational instruction did not directly distinguish these requests. The prompt now states the unavailable capability plainly, stops offering an overview the person declined and permits a complete answer with no follow-up question. Personal plan availability is unchanged; no source/recommendation gate is weakened.

The existing desired-start instruction protected soonest/after-coverage preferences but omitted explicit month/year. The personal-question detector also failed to recognize a null-target question phrased as “Do you want Medicare to start…?” or “Would you like coverage to begin…?” The revised instruction covers resolved month/year; the narrow detector now recognizes those personal requests before the general educational-invitation exception. The validator removes an exact trailing copy from the reply as well as suppressing the untargeted question. Approved targeted questions and invitations to explain timing remain available.

Runtime changes are limited to `natural_agent.py` and `conversation_claims.py`. No frontend, profile store, model/stage/budget policy, protected variant or sealed research changes. The supplied customer transcript was read locally, not saved in this packet or sent to a provider.

## Verification

191 focused tests pass: 37 conversation-claim tests (including three new regressions with positive/negative controls), 95 natural-agent, 30 education-contract, 16 decision-guidance and 13 COBRA-conversation tests. Exact output is in `claim-tests.log` and `tests.log`. The new regression confirms the resolved month removes T04 from eligible questions and that rephrasing it with no target cannot bypass that decision, including when duplicated in the reply.

`live-plan-request.json` records one successful fictional request, two model calls and $0.03525 measured/accounted cost, with no automatic retry. The delivered response states that the app cannot yet show a verified personal list of actual Medicare plans; question is null, with no route lesson. Personal output holds remain enforced. `activation.json` records the :8893 restart and source hashes.

This targeted check does not establish whole-journey conversation quality or repair paragraph duplication in copied/rendered text. Read-only inspection found that `web/advisor.js` deliberately contains both clipped screen-reader text and visible reveal text, which can explain duplication in extracted/copied text; the renderer appends each reply once. Actual browser appearance was not checked. No full browser/responsive replay was performed; no layout changes were made. Restart clears unsaved server visit continuity; saved profiles are unchanged.
