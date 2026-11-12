# Direct AI Send — October 30, 2026

The owner requested removing :8893's AI send-confirmation warning. The extra dialog and its 428-triggered resubmission are removed. A deliberate typed-message Send now supplies the existing `aiConsent: true` and `natural-context-v1` fields directly. Navigation/choices do not grant that permission, and nothing is sent merely on typing or page load.

A brief inline OpenAI disclosure describes Send, with the data categories and context limits retained in privacy details. Saving and sensitive saving remain separate. No backend guard, recipient, context allowlist, budget, reveal behavior or source/recommendation gate changes.

Four new free renderer tests exercise the actual request helper/turn function: scoped Send payload, navigation without AI permission, one Send/one request, and unexpected 428 retaining the draft without a popup or retry. The full suite passes **194 tests in 6.570 seconds**; existing SQLite ResourceWarnings were emitted, with no test failures. JavaScript syntax passes. No paid model requests were made.

A labeled fixture with a temporary store verified one Send reaches the next question without a dialog; phone width390 had no document overflow and retained one Send. The active :8893 page shows the concise disclosure. Existing user tabs were not reloaded, and the fixture was stopped. Files changed: `web/advisor.js`, `web/index.html`, the new frontend tests, and scoped requirement/interaction documentation. :8891 and backend code remain untouched.
