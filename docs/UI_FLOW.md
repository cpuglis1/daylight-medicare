# Simple Medicare intake and discussion

> The original starter questions below have been restored at the owner’s request. The chat now uses a free local welcome, bounded live conversation and local text logging; see [Milkman chat implementation](MILKMAN_CHAT_IMPLEMENTATION.md) for the current architecture. The reference review below is historical.

Implemented in `cms-slice/apps/chat/`, served by the existing Python demo. The question definitions are in `app.js`; conversational discovery prompts and routing are in `scripts/conversation.py`.

## Reference review — October 18, 2026

- [Chapter’s public intake](https://askchapter.org/flow/default): inspected in the browser using a sample Naples ZIP. Both Medicare-coverage branches proceed to prescription coverage, hearing, vision, dental, optional date of birth, first name, and then a phone-number/contact-consent gate. Stopped before providing contact information or submitting consent. The separate [booking form](https://askchapter.org/book/cta-medicare) also requests retirement timing and discussion plan types.
- [Healthpilot](https://www.healthpilot.com/medicare-plans/compare/): self-directed plan comparison centered on doctors, prescriptions, budget and preferences.
- [ANA](https://anahealth.us/): conversational exploration with context carried through questions.
- [MedicareCopilot](https://www.medicarecopilot.ai/ai-plan-intelligence): intake includes providers, medicines, pharmacy, budget and coverage priorities. Its advertised ranking capabilities are not capabilities of this prototype.

## Implemented flow

The landing page explains the tool in one sentence and has one **Get started** button. No model toggle, technical status banner or promotional sections.

One question per screen:

1. Who is the coverage for: myself or someone else?
2. Home ZIP code.
3. Have Medicare: yes, no, or unsure?
4. Only if no: coverage needed within three months, later, or unsure?
5. Need prescription drug coverage: yes, no, or unsure?
6. Want hearing benefits: yes, no, or unsure?
7. Want vision benefits: yes, no, or unsure?
8. Want dental benefits: yes, no, or unsure?

The default branch has seven questions; the new-to-Medicare branch has eight. The Chapter coverage questions are retained, with a caregiver entry and conditional timing question. Birth date, name and contact collection are omitted from this research flow. Back navigation retains answers. Edit answers starts a fresh discussion with the revised intake and clears old product selections.

Completing the last answer automatically opens **Let’s discuss your options**, shows two source-backed coverage paths, and asks what matters most. The discussion now uses a viewport-height chat layout: the title and reply box remain visible while the transcript scrolls. New replies follow the latest message; scrolling back reveals a **Latest message** control. Opening coverage paths remain available at the start of the transcript. These are educational starting points, not a personalized shortlist. The conversation collects current coverage, doctors/hospitals, prescriptions, pharmacy, cost preferences, travel and timing. People may type their own replies, use suggested replies, defer a question or ask for factual research.

## Connection and evidence

`POST /api/conversation` receives the intake, up to 16 recent messages and explicit medicine/pharmacy/plan selections. State exists only in the tab and request, without browser persistence or server-side conversation storage. The same local-origin, size and rate guards apply as for the evidence chat.

When `OPENAI_API_KEY` and `OPENAI_MODEL` are supplied in the server environment, the existing Responses adapter automatically selects the next discovery topic from bounded prompts using recent context. It selects question topics rather than authoring coverage facts. Factual questions go through the existing source-backed chat, preserving exact-product confirmation, source ordering, sources and limitations. Requests use `store: false`. The adapter follows [official structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

Without a model connection, guided follow-ups and the local evidence lookup work. A failed configured connection falls back to guided questions with a short notice. No live model was configured or exercised during this UI change; its routing contract was verified with a controlled transport.

Local plan evidence remains limited to the existing 2027 Collier County release. ZIP collection does not create a national lookup or establish county membership. Personal prices, suitability ranking, exact clinical network confirmation and enrollment remain outside this demo. The question set and discovery wording are deliberately provisional.

## Verification

Browser-checked the landing page, invalid ZIP handling, automatic discussion start, doctor-priority follow-up, a real NCH source answer, caregiver wording, new-to-Medicare timing branch, and editing intake answers. JavaScript syntax and 60 Python tests passed: existing evidence/model/HTTP boundaries (45), discovery and HTTP boundaries (9), and portable release behavior (6). Rebuilt the immutable current release to include the new UI and conversation module.

The [ZIP 34102 demo plan](ZIP_34102_DEMO_PLAN.md) distinguishes current capabilities from the natural model conversation, confirmed session profile and local plan comparison needed for a useful resident demonstration.
