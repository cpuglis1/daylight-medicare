# Isolated readiness wireframe

October 22, 2026. Design/research only; **not connected to guest profiles, a model or matching**. Uses fictional examples in memory. Refresh resets the example. Do not enter personal information.

- [Open interactive wireframe](index.html)
- [Review captured screens](review.html)
- [Design contract](../READINESS_DESIGN.md)
- [Trigger matrix](../READINESS_TRIGGERS.md), [source notes](../READINESS_SOURCES.md), [future acceptance scenarios](../READINESS_ACCEPTANCE.md)
- [Delivery and verification](../READINESS_DELIVERY.md)

Verified local URL: http://127.0.0.1:8898/readiness-preview/

To restart this static server from the project root, if needed:

```sh
python3 -m http.server 8898 --bind 127.0.0.1 --directory docs/product
```

The live application is independently served at http://127.0.0.1:8890/. This server does not start, reconfigure or modify that service.

## Review paths

Open **Preview scenarios and documents** to switch synthetic fixtures. Job-coverage transition demonstrates three short follow-ups. All relevant facts already confirmed demonstrates zero follow-ups. Missing baseline facts / defer demonstrates unresolved inputs without an endless retry. Other fixtures illustrate conflicts, exact provider/drug needs and unavailable sources. Choose **Check what we can compare** first. Because plan-data acceptance is held, the first result states that boundary; **Prepare my details** is an explicit optional intake choice.

Ask opens optional source-linked context; its draft never sends. The free-text example is hardcoded and labeled scripted. Arbitrary text is left unresolved, not interpreted by a local rule pretending to be AI. AI example unavailable demonstrates the manual fallback. This is not the production rule engine or a comprehensive demonstration of all 30 research triggers.

## Incumbent visual system

This narrow extension reuses the Daylight sun, paper/sage/olive palette, Fraunces headings, Atkinson Hyperlegible body, explicit controls, stable four phases and two-path coverage context. No new hero, photography, tagline, visual world or approved system change. The single contextual readiness introduction explains the task; it is not marketing copy. Existing DESIGN.md and .impeccable/design.json are preserved.

Assets come from ../visual-preview/assets/ (daylight.svg and existing font files); their existing provenance/license notes and LICENSE.txt remain authoritative. No new stock purchase or image generation. Prototype-only workbench controls, source links, notice rows and capability summary are development review surfaces. Do not copy the workbench into production. A few compact prototype type sizes differ from the root token table and require integration mapping rather than treating this file as a new design system.

## Checks and limits

13 Node model/registry tests pass. Browser observations cover 1440×1000 desktop, 390×844 phone and a 768×1024 tablet summary, plus proposal, Ask and route behaviors recorded in the delivery report. A fresh finish reviewer scored the three material interaction findings resolved and shipped the artifact **only as an isolated design wireframe**. These checks are not assistive-technology testing, older-adult comprehension evidence, production persistence validation or licensed Medicare/Florida review.

Run the scoped tests:

```sh
node --test docs/product/readiness-preview/model.test.cjs
```
