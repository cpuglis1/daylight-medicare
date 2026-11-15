# Working on Daylight

Read these, in order, before changing anything:

1. [PRINCIPLES.md](PRINCIPLES.md): independence (D64), comprehensiveness and
   control. Commercial economics never enter plan inclusion, eligibility,
   filtering, ranking, explanation or personal fit.
2. [docs/project/CURRENT_STATE.md](docs/project/CURRENT_STATE.md): what is
   current, where to work, open decisions and the rules that hold in every task.
3. The scoped `AGENTS.md` for the surface you are changing, such as
   [alternatives/advisor-first/AGENTS.md](alternatives/advisor-first/AGENTS.md).
4. Before app changes: `PRODUCT.md`, `DAYLIGHT_REQUIREMENTS.md`, `DESIGN.md` and
   `docs/product/MASTER_DESIGN.md`. Name the requirement IDs a change addresses.
5. Before interface or conversation changes, read the Daylight Brain's
   `02 UX playbook.md` (path in CURRENT_STATE) and
   [conversation implementation rules](docs/product/CONVERSATION_IMPLEMENTATION.md).

For company context (strategy, licensing, pilot, partners, business decisions),
read the Daylight Brain's `AGENTS.md`; its path is in CURRENT_STATE under
"How work runs".

Older dated directives are in [docs/project/DIRECTIVE_HISTORY.md](docs/project/DIRECTIVE_HISTORY.md).
They remain binding where not superseded. Read the entries covering an area
before changing it.

## Hard rules

- Preserve source evidence, sealed revisions, review and acceptance gates,
  source STOPs, the 41 conditional meanings and the protected variants
  (:8890, :8891, :8896) and their stores.
- Acquisition, tests, sealing or model agreement are not acceptance.
- Use fictional data. No agent-run live conversation tests or paid probes.
- The workspace has substantial uncommitted work: targeted patches only; never
  reset, stash or discard unrelated changes.
- Report what you actually ran and what remains open.

## Interface work

- Deliver the user story through the existing conversation: reuse known reports,
  ask only consequential missing details, perform the supported work and continue
  in the same visit. A standalone panel or a new launch button is not integration.
- Keep useful content, user-entered answers and notes, adaptive branches and
  factual safeguards.
- One prominent Continue per guided page; text-labeled choices, Back, edit and
  help. No preselected answers, hidden gestures or decorative animation.
- Keep the main task and Continue near the top; Ask Daylight below Continue and
  Back, not duplicated in the header.
- Inspect desktop, tablet and phone rendering. A passing test count is not
  owner approval.

## Recording new owner direction

Follow "Changing direction" in [CURRENT_STATE.md](docs/project/CURRENT_STATE.md).
Do not prepend dated paragraphs to this file.
