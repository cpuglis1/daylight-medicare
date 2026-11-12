# Daylight: does each next screen follow from the user's last action?

No, not consistently. The app has a coherent topic sequence, but its transitions often follow that fixed sequence more strongly than the user's answer. This is a separate problem from the broken backend. Fixing plan loading would leave the sequencing problems below.

This second Chrome pass focused on the relationship between the last click, the immediate response, and the next requested decision. No application code changed.

| Last user action | What follows | Flow judgment | A more natural response |
|---|---|---|---|
| Let's get started → Me / someone I'm helping | A question about existing Medicare coverage | Sensible first branch | Keep it; explain unfamiliar A/B labels at the question |
| A beginner reaches “Do you have Medicare yet?” | Choices require distinguishing A/B and whether they will need to sign up themselves | The form partly asks for the conclusion it should help establish | Ask observable facts: what their card says, whether they receive Social Security, and whether they know their coverage |
| “Yes, I have Parts A and B” → Continue | A full lesson about A and B, then assertions about three gaps | Weak personalization. The user has not been asked whether additional coverage already fills those gaps | Ask how they get coverage now and what they want to review; make the A/B refresher optional |
| “Only Part A so far” → birthday → Continue | “We need to know whether you have Part B” | Direct contradiction of the selected answer | “You have Part A and haven't added Part B. Let's work out what affects your next step.” |
| Birthday supplied before work coverage is known | A personalized-looking timetable appears | The app presents an answer before collecting the facts needed to support it | Resolve the relevant work/coverage situation first; then explain confirmed dates and unresolved facts |
| “Yes, coverage from a current job” | Explanation that Part B may wait, followed by the ordinary prescription/extra/path sequence if Continue is chosen | The next task is ambiguous: preparing for a future change, or comparing plans now? | Offer those two explicit goals, with the relevant checklist or comparison route |
| “Yes” to regular medicines | “When we get to plans” the user can check them; Continue leads to dental/vision/hearing | A deferred payoff. This can be reasonable, but the transition does little to connect the tasks | Collect the list now, or clearly say that the next short questions build the comparison criteria before checking exact medicines |
| Dental → That's everything | “What this means for you: Noted,” a generic qualification, then another Continue | A low-value intermediate state. The button feels as if it should finish the question, but requires another click without useful new reasoning | Confirm the chosen extras and advance, or explain an actual consequence of that choice |
| Doctors and low monthly cost selected → That's what matters | “Which matters most?” repeats the selected choices | The distinction is valid, but both questions sound like “most” | First ask what to consider; then ask which criterion takes priority when they conflict |
| Doctors selected as the top priority | A relevant doctors-versus-cost table, alongside an admission that networks cannot be checked | The trade-off explanation is well placed. The earlier ranking promise needs qualification | Explain immediately which criteria can affect results and which need external verification |
| A coverage-path leaning is selected | The card marks that leaning; See my plans leads to location questions | Recording a tentative leaning is reasonable; some users still need concrete costs/options before leaning | Keep “show both” prominent and let users compare before committing to a preference |
| See my plans → ZIP → county | The first explicit Collier-only limitation appears late in the full journey | The user has already invested effort before learning whether the promised results exist | Establish service area near the beginning and explain what the app can provide there |
| “I'm not sure” about prescriptions or county | No medicines / outside the service area | The next content does not follow from the answer | Use an unresolved branch that helps the user find out |
| On to next steps, including after a failed comparison | A generic map, completion checkmarks, and “Your shortlist” | The ending implies more progress than the user made | Summarize actual decisions, remaining questions, and the next executable action |

**Information sometimes arrives before its explanation.**

The date step displays a Medigap window before Medigap has been introduced. The prescription lesson refers to separate versus all-in-one drug coverage before the two coverage paths are explained. The extras lesson mentions Medigap before its definition in the path lesson. A beginner has to carry unfamiliar terms through several screens before getting the framework that makes them useful. Introduce a small, plain-language overview first, then explain a term when it helps the decision currently on screen.

**The interaction pattern is inconsistent.**

Some answer clicks advance immediately; others reveal another question; others add an explanation and require Continue. “That's everything” can be followed by a thin acknowledgement and another Continue. The quick route changes some of those behaviors again. Choose a clear pattern: select an answer, see its immediate consequence, then take one clearly labeled next action. Use a separate screen or a reliable scroll/focus transition when the task changes.

The visibility issue is concrete: after selecting “Yes, I have Parts A and B,” the answer stays near the middle of the viewport while the explanation and Continue are below the fold. A user can see the selection change without seeing the useful response. [Screenshot](flow-01-answer-result-below-fold.jpg).

The extras acknowledgement illustrates the low-value extra click: [Screenshot](flow-02-extras-thin-payoff.jpg).

**The map mixes lessons with the person's actual situation.**

“Your foundation” displays A and B even after the person has said Part A only. The map can mark skipped lessons and unperformed comparison work complete. It should distinguish facts about current coverage, concepts explained, preferences collected, and unresolved tasks. Otherwise the visual map teaches the user a situation they do not actually have.

**What I would preserve.**

The who-is-this-for opener, the basic coverage-versus-gap explanation, the contextual glossary, the trade-off table tied to selected priorities, and a caution about future switching immediately before a path choice all have useful roles. The fresh quick entry also genuinely skips to the path/preference stage. The issue is how these components are sequenced and adapted.

**A more natural overall flow.**

Start with the user's goal, who coverage is for, and service area. Ask what coverage they have now. Branch into timing questions only when their situation requires them. Give the short explanation needed for the next decision. Collect personal comparison needs, show the relevant trade-offs and actual options, then record a preference or shortlist. End with an honest map of what is known, what was chosen, what remains unresolved, and how to take the next step.

For an already-enrolled user, the next question after A/B should concern their current coverage and what they want to change. For someone preparing to leave job coverage, the next task should establish the transition they are planning. A beginner can receive more teaching along the route. Those users should not all be carried through an almost identical lesson sequence.

Each transition should answer three questions for the user: “Did you understand what I just told you?”, “Why does this information matter now?”, and “Why is this the next question?” Several current transitions fail one or more of those checks.
