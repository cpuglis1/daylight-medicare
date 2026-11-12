# Security and privacy official (HP-01)

Designation record · November 7, 2026 · Part of Daylight's security program. Read with the [launch security spec](../LAUNCH_SECURITY_SPEC_2026-11-06.md) §7 and the [data classification policy](HP-02_DATA_CLASSIFICATION_POLICY_2026-11-07.md). Not legal advice.

## Designation

Effective on signature, **Chris Puglisi**, founder, is Daylight's:

- **Security official.** Responsible for developing and carrying out Daylight's security policies and procedures. HIPAA's Security Rule requires one named person in this role (45 CFR 164.308(a)(2)).
- **Privacy official.** Responsible for Daylight's privacy policies, privacy notice and the handling of people's privacy requests. HIPAA's Privacy Rule requires a privacy official (45 CFR 164.530(a)). Daylight names one now because it protects health information to the HIPAA standard from the first message (HP-02), whether or not HIPAA strictly applies yet.

One person holds both roles at launch. That is normal for a one-person company, and it is why the outside checks below exist.

## What the role covers

| Area | Responsibility |
| --- | --- |
| Security program | Own and keep current: data classification (HP-02), vendor register (HP-03), risk analysis (HP-10), breach notification matrix (HP-11) and the written information security program (HP-14). |
| Vendors | Approve every vendor before it touches health information; confirm its contract (BAA or equivalent) and record it in the register. |
| Changes | Approve any change to a health-data path: model provider, storage, logging, analytics or exports (OP-09 code-owner review). |
| Access | Grant least-privilege access, remove it the day someone leaves, and review the access audit log monthly (spec §6.3). |
| Incidents | Receive reports of suspected incidents, decide on containment, and work with counsel on notification (spec §5.4 and §7). |
| People's requests | Answer access, correction and deletion requests from participants and customers (HP-15). |
| Notices and consent | Keep the privacy notice (HP-12) and pilot consent (HP-13) accurate to what the system actually does. |
| Training | Brief anyone before they are given access to health information. |
| Stop authority | Pause any feature or data flow that breaks policy, using the kill switches (spec §3.7), and block a release that fails a privacy gate. |

## Contact

`security@` and `privacy@` on the Daylight domain, delivered to a mailbox covered by a BAA (set up with ES-01). Until then, the founder's direct contact.

## Outside checks while one person holds the role

- Counsel reviews the privacy notice, the consent step and the HIPAA-status questions (LG-06, HP-16).
- People other than the founder run the pen test and LLM red-team before public launch (spec §7).
- When a second person with security responsibility joins, decide whether to separate the two roles and name a backup. Until then, the incident runbook lists counsel as the first outside contact if the founder is unavailable.

## Records to update

- Assign the `privacy_security_review` role in [owners.json](../../project/owners.json) to Chris Puglisi. It is currently unassigned.
- Reference this designation in the written information security program when HP-14 is adopted.

## Sign-off

Signed: ______________________ Chris Puglisi, founder

Date: ________________

Effective on signature (target November 10, 2026). Review at Gate 2, before AEP 2027 (HP-24), or when staffing changes.
