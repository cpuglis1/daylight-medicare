# Name grounding at text boundaries

November 4, 2026 · D86/D90 reliability; D73 conversation continuity · advisor-first :8893

The owner reported a name-verification notice after naming two fictional doctors, practices and cities. This is a composition-validation failure, separate from the previously repaired session recovery. The original rejected model reply is not retained in ordinary logs, so its exact wording cannot be reconstructed from the visible transcript.

## Reproduced defect and change

The validator concatenated the answer and next question before looking for proper names. An answer ending in `Tampa` followed by `What ZIP code do you live in?` became the unsupported name `Tampa What`. A paragraph break could similarly join `Tampa` to `These`. Adding a period made the same supported answer pass.

[Before/after replay](boundary-replay.json) uses the retained old validation method and the changed method on identical fictional inputs. Both false rejections now pass, the already valid punctuated answer remains valid, and an invented doctor remains rejected.

The name detector now scans the reply, question and paragraphs separately. Full multiword names remain checked inside each paragraph, including soft line wraps. Names in questions are checked too. There are no new name allowlists, caregiver branches, prompt rules, canned answers or model calls. Other source, amount, personal-finding and coverage checks are unchanged.

## Verification

Nine added regression tests cover the two text boundaries, varied source-grounded names, invented or extended identities, names in later paragraphs/questions, unsupported participation assertions and the four-turn fictional sequence supplied by the owner. The journey test exercises the ordinary interpreter/composer controller with scripted transport: it retains both doctor/practice/city pairs, two distinct medicine strengths and current coverage; preserves the generated acknowledgment; and advances without the validation notice. ZIP is the fixture's chosen valid next question, not a new forced dialogue rule. Recommendation and external-verification gates remain false. There are still exactly two model stages per typed turn, with no repair call.

The full advisor suite result and local activation are recorded in [completion.json](completion.json) and [regression.log](regression.log). Checks use the project virtual environment and disposable local test fixtures. No paid model calls or new live-model journey were performed. Passing these checks establishes this reproduced validation correction, not that all generated wording or provider failures are eliminated.

## Scope and preservation

The source change is limited to `natural_agent.py`; regression coverage is in `test_name_grounding_boundaries.py` and `test_provider_capture_regression.py`. [Before copies](before/) preserve the prior implementation. [Source hashes](source-manifest.json) identify the resulting files.

For D73 review, the change preserves useful conversation content and supported next steps instead of discarding them at a formatting boundary. It changes no intake meanings, coverage paths, learner assessment, plan filtering, personal verification, saving permission or source acceptance. UI assets and protected variants remain unchanged. Existing session recovery and fixed-category diagnostics are retained; raw user/model text is not newly logged. No public deployment or consumer release is asserted.
