# Advisor input allowance removal · November 4, 2026

Owner requested removing the reviewed input allowance encountered while trying Opus 5.5. This is a local :8893 backend change under D86/D90. It does not establish conversational quality.

The former 16,000-token check applied to the whole model request, including instructions, schema and context. `request_limits.INPUT_TOKENS` is now `None`, exposed as `maxInputTokens: null` by the active service. All selectable models use the same policy. Counting retains supplied exchanges instead of deleting older ones to meet that ceiling; existing context permissions and packing of duplicate presentation data remain.

The ledger first reserves each stage's configured output allowance, then atomically funds its counted input before submission. Settlement validates usage against that actual reservation. Cache-write pricing remains included where applicable. A later stage can encounter the daily cap after an earlier stage succeeds; existing accepted work and the earlier receipt remain. Unissued work is released; submitted requests with uncertain usage stay held, including across midnight and any authorized connection recovery.

The shared $5/UTC-day cap, pricing review, output allowances, 96,000-byte request bound, provider limits and usage validation remain. No existing budget receipt was reset or reconciled. The protected variants were not edited. All 38 UI files match their before hashes, and the composition prompt is byte-for-byte unchanged.

Verification: 22 temporary-ledger accounting tests and five isolated token-count/settlement tests passed. These cover requests above the former ceiling for every selectable model, exact settlement, concurrent funding, the exact daily boundary, later-stage rejection and separately funded recovery. Seven edited Python files compile. Fixture tests emitted existing unclosed SQLite connection ResourceWarnings. No conversations or paid provider probes were run. The historical sample runner was adjusted to handle an absent input ceiling; it was not executed.

Activated November 4 at 17:10:05 America/New_York. Launch agent `com.daylight.advisor-first.8893` is running with PID 63802. GET `/` and `/api/ai/usage` returned 200; the live status reported no input ceiling, the unchanged $5 cap, AI enabled and $0.8279738 remaining at that moment. See [activation.json](activation.json), [checks.json](checks.json) and [count-and-settlement-tests.txt](count-and-settlement-tests.txt). `before/` retains the exact pre-change files and `before.json` retains the UI hashes.

The owner continues conversational review. This change removes the named application input block; provider availability and conversational naturalness were not evaluated here.
