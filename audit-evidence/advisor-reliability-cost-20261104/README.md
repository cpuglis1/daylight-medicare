# D86/D90 connection recovery and cost · November 4, 2026

The latest observed failure was a receive interruption (curl 56) during composition. Ledger row 564 settled extraction at $0.059348; row 565 retained its $0.112 uncertain generation hold. A missing receipt is not a confirmed bill.

Recent measured examples: Claude rows 557–558 total $0.135508 for the typed opening; row 559 is $0.070288 for the one-call COBRA answer. Sol rows 552–553 total $0.0407701. These are historical examples, not estimates for the new prompt.

Production :8893 now permits one separately funded recovery for a dropped connection in each generation stage. It preserves original uncertain receipts and settled extraction. Repeated disconnections stop after two attempts; cap denial starts no replacement. HTTP rejection, invalid output, factual rejection and billing failures receive no paid retry. Exact token counting can reconnect once, without a generation charge. The $5 UTC-day cap and provider selection are unchanged. The status endpoint accurately reports bounded automatic recovery.

Composition instructions were condensed from 19,188 to 7,850 characters before the unchanged response-length section. The prior instructions are retained in composer-before.py.txt. Both canonical reports and learning records, all question meanings, referenced evidence, factual validation and source/purpose gates remain. Prompt length reduction is not a measured percentage price reduction.

Verification: the 913-test suite completed with one obsolete literal wording assertion in the comparison instruction test. That assertion now checks the equivalent new wording. A subsequent 58-test affected run passed, including network recovery, cap denial, premium-provider settlement, exact-count recovery, education and comparison gates. These tests inject failures and provider replies; they do not establish full real-model conversational quality. No full production-context live conversation was executed in this change.

The local launchd advisor was restarted and inspected: both premium models are configured, automatic recovery is enabled with one retry per stage, the daily cap is $5, and $2.8335686 remained available at activation. There is no claim that any network API can guarantee every request.
