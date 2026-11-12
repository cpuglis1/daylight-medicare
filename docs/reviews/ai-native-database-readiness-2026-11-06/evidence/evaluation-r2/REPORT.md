# Evaluation report · 2026-11-06T14:18:39+00:00

Python 3.14.7. Offline; 0 paid model calls.

| Suite | Result | Known gaps |
| --- | --- | --- |
| persona_journeys | passed | Injected responses: says nothing about real-model conversation quality. |
| checklist_coverage | passed | The advisor does not emit checklist receipts yet, so no real decision is scored. This suite tests the scorer and receipt format only. |
| factual_grounding | passed | Checks the statements and verifiers, not each sentence a live model writes. |
| commission_counterfactual | passed | Covers the ranking functions and decision records. Model-request serialization (rest of I02) is not yet checked with canaries. |
| abstention | passed | Offline fault injection; does not observe a live model choosing to abstain. |
