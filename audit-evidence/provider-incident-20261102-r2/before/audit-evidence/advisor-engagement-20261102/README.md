# Conversational pacing and education follow-ups

November 2, 2026 · D49 / D54 / D55 / D57 / D73 / D86 · :8893 only

The owner requested visibly moving pending dots, immediate clearing on Send, a clearer way to find a question below the visible chat, and judgment about balancing substantive teaching with practical discovery. This increment preserves one practical next question and adds optional contextual exploration without a mandatory learning/intake fork.

## Implemented behavior

- **Immediate Send feedback:** the submitted raw draft is copied locally and cleared before transport starts. The submitted bubble and three assistant-side dots remain in the reading pane. A successful response does not clear a newer draft, even if it repeats the same text. A failure restores the submitted draft when the composer is empty; with a newer draft present, the earlier one remains available through the existing Restore draft control. No automatic retry or profile change occurs on transport failure.
- **Actual pending motion:** dots move vertically in a staggered 1.1-second wave. Browser inspection identified the retained base stylesheet's unconditional `animation:none!important` as the reason the earlier dots stayed still. A specific pending-only override fixes the cascade, including stagger and offscreen/hidden pause. Reduced motion retains static visible dots. The existing accessible status and validated word reveal remain.
- **Optional contextual questions:** the existing C2 composition response may include `education_followups`, zero to two questions of at most 120 characters. Instructions usually prefer an empty list; substantive current teaching with a meaningful unresolved tradeoff can warrant suggestions. Current referenced reviewed evidence, recent dialogue, the practical target and remembered return point remain available. There is no third call or model-setting change. Ordinary acknowledgements, missing teaching, pause and required clarification suppress suggestions. Malformed/unsafe optional suggestions are discarded independently so they cannot block a valid main reply.
- **Simple presentation:** suggested questions appear in one collapsed More about this disclosure with the explanation. Choosing one fills and focuses the existing composer; it does not send, replace another draft, infer understanding, write a profile detail or displace the pending practical question. Typing remains available at every point. Contextual inline visuals and the single expandable Sources footer remain.
- **Finding the next question:** a 44px downward arrow appears only when lower content is out of view. Its accessible name/title distinguishes Go to next question from Go to latest message. It scrolls only the reading pane, focuses a newly reached question when applicable and hides at the bottom. Opening disclosures and growing the composer update its position/state. Reduced motion uses immediate scrolling.

## Verification and activation

- [Final full suite](tests-final.log): **489 Python tests passed in 46.045 seconds**. This includes the two wrappers containing **87 Node checks**; counts are nested, not additive. Seven new backend optional-question tests and a planning integration test cover the output contract, suppression, unsafe supplemental recovery, unchanged practical target, retained memory and unchanged call counts.
- The initial [sandboxed run](tests.log) could not bind the HTTP fixtures and ran during the final CSS/test-regex adjustment. The final run used local socket permission and passed. No test uses a paid model call.
- [Browser measurements](browser-checks.json) and screenshots use a disposable fixture server and fictional input. They confirm the composer was empty during the pending request, all three dots had `daylight-typing` running with distinct nonzero vertical transforms, and a failed request preserved the newer draft while exposing the earlier draft for restoration.
- Choosing an optional question left the current health-insurance question unchanged, filled only the composer and created no pending request. The arrow reached the question/lower choices and disappeared at the bottom. Desktop 1280×720, tablet 768×1024 and phone 390×844 retained viewport-sized document bounds and zero outer scrolling. Guides remained adjacent on wider screens and stacked on phone; one Sources footer remained.
- [Activation](activation.json): restarted only the existing :8893 job, preserving its infrastructure virtualenv and `--local-research` arguments. All three served UI assets returned 200 and matched workspace bytes; the service reported GPT-5.4 available and automatic retries disabled. The user-owned live tab was not reloaded. Copy unsent text before refreshing to load the new frontend.
- [Preservation inventory](preservation.json), compared with the preceding increment, shows only the intended advisor adapter CSS changed among the retained stylesheets and engine lock. No protected variant, shared engine, guest-store schema, budget policy, evidence acceptance or recommendation release changed.
- **Paid AI calls for this increment: 0.** No model, reasoning setting, daily allowance, permission scope, automatic saving or persistent transcript was added.

| Mocked browser proof | Capture |
| --- | --- |
| Empty composer and pending dots | [pending-desktop.png](pending-desktop.png) |
| Newer draft preserved after failure | [recovery-desktop.png](recovery-desktop.png) |
| Optional questions beside the explanation | [education-desktop.png](education-desktop.png) |
| Next practical question reached | [next-question-desktop.png](next-question-desktop.png) |
| Teaching, optional questions and practical question, tablet | [education-tablet.png](education-tablet.png) |
| Stacked contextual visuals and optional questions, phone | [education-phone.png](education-phone.png) |

## Strategic review and limits

This change improves control over reading, continuation and error recovery while preserving consequential minimal intake. It neither assumes an explanation was understood nor promotes a learner's optional question into a preference. Commercial economics do not enter the new prompts or controls. Reported-input completeness and independent source/personal-output gates remain separate; suggestions do not unlock plan recommendations or unsupported actions.

The backend contract is tested with controlled transports, and browser response content is explicitly mocked using retained reviewed teaching. No new live-model dialogue, physical-device keyboard test, assistive-technology certification or consumer comprehension/retention experiment was run. The proposed engagement balance should be assessed with actual users; it is not an established retention improvement. The separate previously reported PCP-submission incident is not diagnosed or claimed fixed by this increment.
