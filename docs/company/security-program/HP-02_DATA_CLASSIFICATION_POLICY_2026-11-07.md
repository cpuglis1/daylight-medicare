# Data classification and handling policy (HP-02)

Policy · November 7, 2026 · Daylight security program. Owner: the security and privacy official ([HP-01](HP-01_SECURITY_PRIVACY_OFFICIAL_2026-11-07.md)). Read with the [launch security spec](../LAUNCH_SECURITY_SPEC_2026-11-06.md) §5 and the [vendor register](HP-03_VENDOR_REGISTER_2026-11-07.md). Not legal advice.

## 1. The rule

Daylight protects health information to the HIPAA standard from the first message a person types, whatever law strictly applies at that moment.

Whether HIPAA applies before checkout is an open counsel question (spec Q1 and Q2), and the Collier pilot sells nothing, so it may not apply yet. Applying the standard anyway means nothing has to be rebuilt at checkout, and every privacy statement Daylight makes stays true. The cost is small: the two BAAs the pilot needs are self-serve and free (HP-04, HP-05).

Two working rules follow:

- When unsure which class something belongs to, treat it as Class 2.
- Classify every new field, store, export or vendor before it ships. The security official approves.

## 2. Classes

| Class | What it is | Examples | Where it may go |
| --- | --- | --- | --- |
| **1. Restricted identifiers** | Numbers that enable identity theft or enrollment fraud | Medicare number (MBI), Social Security number, full date of birth, card or bank numbers, driver's license or passport numbers, passwords | Not collected before checkout, and never in the pilot. If someone types one by accident, it is removed before the model call and before anything is saved (HP-07). After checkout (Gate 2): field-level encryption (SA-20). |
| **2. Health information** (HIPAA standard) | Anything about a person's health, coverage or Medicare situation, and anything that identifies the person alongside it | Every profile report (section 3), chat messages and model replies, decision and recommendation records, saved profiles, pilot transcripts, observation notes, feedback stored with a session | Only systems the vendor register approves for Class 2. See section 4. |
| **3. Contact details** | Who a person is and how to reach them, kept apart from health information | Participant name, email, phone, invite status, participant code | The invite list and the founder's scheduling email and phone. Never written next to Class 2 content outside approved systems. |
| **4. Content-free metadata** | Numbers and opaque references that reveal nothing about a person's health | Turn counts, tokens, cost, durations, event counts (PX-11), friction level, hashed session reference, error codes | Traces, metrics, logs and dashboards (HP-09). No free text, no drug, doctor or plan names, no ZIP. |
| **5. Public reference data** | Published facts not about any one person | CMS plan files, formularies, Star Ratings, NPPES, public provider directories | Research database, object archive, and the public repository after rights review. |
| **6. Confidential business data** | Commercial terms | Commission schedules, the commission-status table, carrier and FMO contracts, acquisition costs | `dl_fulfillment` only. Never in model context or any recommendation input (D64, A07). |

Fictional test data (personas, golden cases) carries no restrictions, but it must be written from scratch, never copied from a real participant.

Two traps:

- **A public fact becomes Class 2 once it is attached to a person.** "Eliquis is on this formulary" is Class 5. "This participant takes Eliquis" is Class 2. Sending a person's medicine or doctor to an outside lookup service (RxNav, NPPES, a carrier directory) discloses Class 2 to that service. Prefer local copies of public data; any live per-person lookup needs a vendor register entry first (DQ-13, DQ-16, DQ-20).
- **Free text is always Class 2.** People type anything into chat, so every message is treated as health information, even one about the weather.

## 3. Pre-checkout fields

Every report the advisor captures is Class 2. The current report set maps as follows. Any field added later is Class 2 unless the security official records otherwise.

| Report | What it holds |
| --- | --- |
| RC01 | Who the help is for |
| RC02 | ZIP and county |
| RC03 | Coverage year |
| RC04–RC06 | Part A and B enrollment, Part B effective date, age and its basis |
| RC07–RC08 | Current Original Medicare or Advantage arrangement; relevant events and dates |
| RC09–RC14 | Work insurance, employer size, job and coverage end dates, creditable drug coverage, family or retiree benefits, HSA contributions |
| RC15–RC17 | Medigap rights, change notices, replacing a Medigap policy |
| RC18–RC19 | Cost assistance, special-needs plan type |
| RC20 | Routine travel location |
| RC21 | Doctors and hospitals |
| RC22–RC23 | Medicines, strength, fill quantity and pharmacy |
| RC24 | Clinic or pharmacy problems |
| RC25 | Budget and premium preferences |
| RC26 | Military or VA program |

Also Class 2: birth month and year, plan preferences, comparisons viewed, the recommendation shown, and the "was this useful?" (PX-22) and end-of-session answers (MV-10) when stored with the session.

## 4. Where Class 2 may and may not go

| Allowed, once the contract in the vendor register is in place | Not allowed |
| --- | --- |
| Daylight's verified AWS accounts in `us-east-1` and services covered by the applicable BAA | GitHub |
| The D101 OpenAI GPT API project, after verification of the covered organization, endpoints and effective data controls | Coding agents and anything in their context: Claude Code, Codex, Paperclip, Copilot |
| The founder's browser, viewing through Daylight's own admin pages | Development and evaluation model accounts, unapproved API features and the Console playground |
| | Email, text messages, Google Drive, Docs or Sheets, Slack, notes apps, unless the register later approves one under a BAA |
| | Error tracking, analytics, session replay, ad pixels, and third-party scripts on any page that shows health information |
| | Downloads or exports to the laptop. If one is ever unavoidable: FileVault on, deleted the same day, and logged. |
| | JSON schema definitions, tool names, enum values, file names and database object names |

## 5. Handling rules for Class 2

- **Minimum necessary.** Ask for medicines and doctors only when a check needs them, and say why. Age or birth month and year are enough before checkout (spec §5.3). Send the model only what the current turn needs.
- **Encryption.** TLS in transit; encryption at rest with managed keys.
- **Access.** Founder only during the pilot, through named accounts with phishing-resistant MFA. Every read of a person's records goes to the access audit log (SA-01).
- **No content in logs or traces.** Logs and traces carry Class 4 only (HP-09).
- **Retention.** Raw chat stays visit-only unless the person agrees to a saved transcript under section 6. Saved profiles follow the existing saving permission. Deletion on request (HP-15).
- **Separate permissions.** AI transfer, saving, transcript saving, family sharing, human handoff and enrollment are separate choices (existing rule; HP-13).

## 6. Pilot study transcripts

**D101 decision, November 8, 2026:** detailed numeric usage records may be kept
for 90 days and non-identifying cohort totals for 12 months. Raw chat remains
visit-only for the approved pilot. The earlier transcript study below remains a
historical proposal with separate consent and approval requirements.

**Owner direction, November 7, 2026:** save pilot chat transcripts for evaluation and study of how people use the tool.

This changes the standing "no new raw-transcript persistence" rule for the invite-only Collier pilot only. Record it as a numbered owner decision before it is built, and update the places that state the old rule: the privacy rule in `docs/project/CURRENT_STATE.md`, the P12 exit evidence in `docs/project/COLLIER_MVP.md`, and the privacy line in `alternatives/advisor-first/AGENTS.md`.

Proposed conditions, to confirm before building:

1. **Opt-in.** A separate yes or no in the consent step (HP-13). People who say no still take part, and their chat stays visit-only.
2. **Pseudonymous.** Stored under a participant code. The code-to-name key lives only in the invite list (Class 3), never with the transcript.
3. **Scrubbed.** Class 1 identifiers are removed before saving (HP-07).
4. **Sealed store.** A separate table in the operations database on the AWS BAA account: encrypted, founder-only, every read logged. Not in traces, logs or the repository.
5. **Fixed retention.** Deleted on a set date, proposed as June 30, 2027 (six months after the go/no-go), or sooner at the person's request.
6. **Use.** The founder reads and annotates. Any automated analysis runs only through the Anthropic HIPAA organization. Findings enter evaluation suites as rewritten fictional personas, never as copied text (spec §5.2.6).
7. **Disclosed.** The privacy notice (HP-12) and consent step (HP-13) say plainly that transcripts are saved, why, for how long, who reads them, and how to withdraw.

## 7. Review

Review this policy when counsel answers spec Q1–Q3 (HP-16), before Gate 2 (checkout data), before AEP 2027 (HP-24), and whenever a new data store or vendor is added.

Approved: ______________________ Chris Puglisi, security and privacy official

Date: ________________
