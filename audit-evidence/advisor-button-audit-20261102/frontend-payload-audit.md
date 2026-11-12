# Frontend button-to-payload audit

Scope: :8893's production question descriptors and `advisor.js` form/draft/submit functions. This check starts no server, operates no browser, and calls no model. The synthetic client throws if any model transport is attempted.

`question-button-registry.json` is generated from `NaturalConversation.question`, the retained 41-meaning inventory, and service-created conditional field variants. It contains 88 descriptor variants: default and all-field presentations for every inventory entry, plus a real multi-county ZIP reference selector and partial RC11/RC16/RC23 questions. The three documented child aliases remain mapped to their parent question IDs.

The executable production renderer matrix covers:

- All 98 distinct precise choice IDs: select, deselect, reselect, then deliberate Send with the exact choice and beneficiary/item entity.
- All 16 distinct finite field options: scoped key/value submission, numeric days-supply choices, and the non-report “Another amount” affordance.
- Unknown, defer, and clear for every descriptor; empty submission does not create a report.
- Every multi-select exclusive option in both selection orders.
- Full assistance-program draft seeding, with a later decline displayed separately from retained historical reports.
- The approved three-priority cap, including replacement after deselection.
- Typed draft protection across all question choices, field options, and local disclosures.
- Every direct insurance choice against both expanded insurance families; unrelated subtype controls close without inventing or discarding the precise selection.

Confirmed problems found in the pre-fix production path were the stale insurance-family expansion, stale finite fields after whole-question disposition, invalid numeric `daysSupply='other'`, assistance-program decline combined with named programs, incomplete assistance-program draft seeding, and loss of the three-priority limit. The implementation and the backend-specific verification are recorded by the parent audit packet; this matrix verifies the renderer and request-construction side rather than replacing backend acceptance tests.

Run with `python3 -m unittest discover -s alternatives/advisor-first/tests -p test_button_payload_matrix.py`. The Python wrapper executes the production JavaScript functions directly, using descriptors from the Python service, and nests 192 Node checks. It does not reproduce the form or payload implementation in a separate test fixture.

Final scoped result: the Python wrapper and all 192 nested Node checks passed. See `frontend-payload-tests.log` and `frontend-payload-node.log`. No model calls or browser actions were made.
