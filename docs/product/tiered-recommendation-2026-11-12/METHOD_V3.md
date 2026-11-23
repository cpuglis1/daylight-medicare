# V3 implementation addendum — November 14, 2026

Method ID: `daylight-tiered-v3-20261114`. D167 implementation, not method acceptance.
The earlier method and its evidence remain intact.

On a :8895 cross-plan drug-cost investigation, server-reconciled comparison results
may provide the within-fit-group order for Part D or drug-bearing Medicare Advantage
plans. The comparable key is the supported sum of plan premiums and drug spending
for the user's selected refill dates. The existing estimator and its exact-input,
source, eligibility and receipt checks determine whether an estimate exists.
A held/missing estimate has no numerical rank. It remains in the list and cannot
be called more expensive than a ranked plan. Pharmacy listing is a separate dated
observation; unknown listing evidence stays unknown. No commercial input is used.

These estimates use published retail averages, not an exact-store quotation.
They exclude medical spending and must not be labeled an all-in cheapest Medicare
plan. Existing no-recommendation gates for unresolved drug evidence remain in force.
The client cannot supply prices to this method. With no comparison result, existing
criteria apply. This addendum does not accept sources, release recommendations,
change plan inclusion, or establish a preferred coverage path.

See [D167 verification](../../../audit-evidence/profile-replay-20261114/README.md).
