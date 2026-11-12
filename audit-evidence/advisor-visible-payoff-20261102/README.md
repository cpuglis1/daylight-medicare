# Advisor visible payoff refinement

Scope: D86/D73, the advisor-first :8893 variant only. The owner requested a reassuring opening; a useful first response with balanced explanation and progress; contextual coverage pictures, reported-date timelines and editable preparation checklists; at most two relevant educational suggestions; and occasional grounded progress with a recap only on explicit saved resume.

## Composition changes and verification

`alternatives/advisor-first/natural_agent.py` replaces redundant composition guidance with a substantive first response, natural acknowledgment, one relevant teaching point when useful, occasional progress grounded in resolved reports or changes, and optional followups about a specific unanswered aspect of the current explanation. It preserves direct answers, optional consequential questions, the successful comparison-preparation ordering, and the prohibition on treating learning receipts as comprehension or verified coverage.

The four existing targeted suites passed: `test_natural_agent.py` (95), `test_education_contract.py` (30), `test_education_followups.py` (7), and `test_decision_guidance.py` (18), totaling **150 tests**. Each ran with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s alternatives/advisor-first/tests -p '<suite>.py'`. [Captured output](prompt-tests.log) includes expected fixed-code diagnostics from injected failure cases. Tests used synthetic transports; no provider calls were made for this prompt check.

[Prompt size](prompt-size.json) decreased from 14,087 to 13,790 characters and from 2,088 to 2,021 whitespace-delimited words. This does not measure actual token usage. The 8,000-input-token limit, model, stage count, schema, budget, privacy and real evidence/recommendation gates are unchanged.

The initial broader run also found seven test expectations tied to the prior timing-first comparison order. [Test-only corrections and retained invariants](ordering-regression-notes.md) explain the changes; the four affected suites then passed **84 tests**, with [captured output](ordering-regression-tests.log). Backend flow was unchanged by this correction. Localhost-dependent checks from the broader run require separate verification.

## Frontend scope and limits

The accompanying frontend work is separate from these prompt tests: a reassuring opening, contextual artifacts with reported dates and local correction, an optional ZIP/doctors/prescriptions preparation milestone, and a category-only recap on explicit saved resume. Displayed reports are not verified findings; neither a reported date nor a learning receipt establishes an actual coverage start or comprehension. Suggestions remain optional drafts for deliberate Send. No synthetic plan catalog is introduced.

## Interface and activation verification

Follow-up verification closed the initial suite failures: **66 HTTP/lifecycle checks pass** with temporary localhost binding permitted ([output](http-tests.log)); all **84 checks in the four affected ordering suites pass** after correcting stale test assumptions ([rationale](ordering-regression-notes.md), [output](ordering-regression-tests.log)). No backend behavior was changed for those test corrections. The initial full run is retained; it was not rerun wholesale after these focused closures. The disposable preview server was stopped after inspection.

All **332 Node checks pass**: 140 ordinary checks plus the 192-case button payload matrix with its required registry input. [Actual output](ui-tests.txt). New tests cover partial and corrected reported dates, snapshot isolation, explicit saved recap categories, no inferred dates, unresolved reports, deliberate review/checklist actions, milestone transitions and duplicate timeline suppression. The original full Python attempt is retained in [full-suite-initial.log](full-suite-initial.log); sandbox-blocked HTTP cases and obsolete pre-comparison-order test expectations are tracked in follow-up logs rather than hidden.

The disposable [UI fixture](preview_server.py) used synthetic responses, a separate temporary database and zero model calls. Browser inspection covered desktop 1280×800, tablet 768×1024 and phone 390×844. Tablet/phone page widths matched their viewports. The new date review displayed both editable date rows; returning preserved the conversation. The optional Make a checklist action opened the existing review, and deliberate Prepare opened the editable checklist with copy/print/return controls. [Desktop](ui-desktop.png), [tablet](ui-tablet.png), and [phone](ui-phone.png) captures retain the mock preview label. The viewport override was reset afterward.

Only the :8893 service was restarted. [Activation receipt](activation.json) records source hashes, the new helper served byte-for-byte, live AI enabled on GPT-5.4 and unchanged no-retry/recommendation-hold status. The real service's [opening](live-opening.png) was separately checked in the browser. Existing user tabs and saved profiles were not changed. Start a fresh visit after refresh to load the new script and visit state.

These checks establish controlled behavior and rendering, not consumer comprehension or live-model conversation quality. No paid model evaluation was run for this refinement. No new analytics or persistent transcript history were added. Useful answers, understanding, correction and next-step clarity remain the intended evaluation outcomes; message count or elapsed chat time is not treated as success.
