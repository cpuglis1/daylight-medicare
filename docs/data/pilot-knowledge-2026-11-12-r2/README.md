# Pilot Medicare fact base: social-insurance extension

November 12, 2026 · D162 · 2026 pilot general education

**74 indexed facts: 40 already accepted, 31 new candidates, three unchanged
Florida legal holds.** The live :8895 app still uses the accepted r1 catalog;
this additive revision does not activate new wording or change the app.

- [Exact wording review](REVIEW.md): the 31 additions with conditions, official sources and approval digests.
- [Enrollment by situation](ENROLLMENT.md): 16 situations separating windows, actions and coverage starts.
- [Guide coverage and corrections](COVERAGE.md): every substantive topic in the supplied pages.
- [Source evidence and limitations](SOURCES.md): new captures, STOPs, year exclusions and one unresolved precise closing-date detail.
- [Verification](../../../audit-evidence/pilot-knowledge-social-insurance-20261112/README.md): actual checks and preservation evidence.

The additions cover A/B/C/D benefits and premiums, eligibility, custodial versus
skilled care, enrollment timing, penalty formulas, payer order, drug tiers and
exceptions, the 2026 Part D cap, Medicaid administration and Social Security's
adult disability definition. Existing source records and all 43 original facts
are retained exactly. The study guide is a coverage prompt, not authority.

The same small local `PilotKnowledge` reader can load this revision. There is no
new service, embedding store, model request, intake, runtime calculator or Brain
update. The machine-readable [situation map](enrollment-situations.json) references
catalog facts and is review material, not an executable personal eligibility rule.

## Acceptance and activation

D159 accepted the exact original 40 facts. The 31 additions have source comparison
and offline verification, but no acceptance receipt. Under the existing D158
wording gate, review [REVIEW.md](REVIEW.md) and explicitly accept the desired new
facts for general education on :8895 before they enter answers. No extra blanket
independent-review requirement has been introduced. The specific Florida holds
remain independent and disabled.

`review-controls.json` is a portable review fixture containing only the unchanged
40 existing receipts and a matching r2 revision identifier. It is not the running
app's controls file and does not approve the additions. Synthetic receipts used
for tests exist only in temporary directories. A later activation should bind
the exact accepted digests, point the :8895 reader and controls to the same
revision, and verify the running surface while preserving other ports and data.

`build.py` uses local retained evidence only and refuses to overwrite a sealed
manifest. `verify.py` checks source bytes/passages, unchanged approvals, topic
retrieval, situation references, year/expiry/surface restrictions and withdrawal.
The raw captures are immutable snapshots, not a remote-change monitor. Review
again by December 31, 2026 or earlier if a source changes.
