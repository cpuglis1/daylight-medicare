"use strict";
/* Daylight Medicare: adapt the next question to the entered coverage and goal.
   Personal guide notes are session-only. The catalog API remains authoritative
   for published records; typed chat is a separate, explicitly submitted action. */

/* ------------------------------------------------------------------ helpers */
const el = id => document.getElementById(id);
const node = (tag, text, className) => {
  const n = document.createElement(tag);
  if (text !== undefined && text !== null) n.textContent = text;
  if (className) n.className = className;
  return n;
};
const markup = (tag, html, className) => { const n = node(tag, undefined, className); n.innerHTML = html; return n; };
const escapeHtml = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/* ================================================================== reviewed content ================================================================== */
const SOURCES = {
  options: "https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options",
  joining: "https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan",
  costs: "https://www.medicare.gov/basics/costs/medicare-costs",
  medigap: "https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy",
  compare: "https://www.medicare.gov/plan-compare/",
  shine: "https://www.floridashine.org/Counseling-Sites/Collier.aspx",
  signup: "https://www.ssa.gov/medicare/sign-up",
};
const HELP = [
  {name: "SHINE, free, unbiased Medicare counseling (Collier County)", detail: "Serving Health Insurance Needs of Elders. One-on-one help. No sales.", phone: "1-800-963-5337", href: SOURCES.shine},
  {name: "1-800-MEDICARE", detail: "The official Medicare helpline, open 24 hours a day, 7 days a week.", phone: "1-800-633-4227", tty: "TTY 1-877-486-2048"},
  {name: "Medicare.gov", detail: "Compare health and drug plans on the official Medicare website.", href: SOURCES.compare},
];
const GLOSSARY = {
  premium: "The amount you pay each month to have coverage, whether or not you use any care.",
  deductible: "An amount you pay before coverage pays its share, under the relevant benefit rules. Part B has an annual deductible; Part A uses benefit periods.",
  "your 20% share": "Coinsurance: after the deductible, you usually pay about 20% of the Medicare-approved amount for Part B care. Original Medicare puts no yearly cap on this.",
  "late penalty": "If you wait too long to sign up after you're first eligible, your monthly cost can be higher for as long as you have that coverage.",
  "Part A": "Hospital insurance: inpatient hospital care, skilled nursing facility care, hospice and some home health care.",
  "Part B": "Medical insurance: doctors, outpatient care, tests, equipment and many preventive services.",
  "Original Medicare": "Parts A and B together, run by the federal government and accepted by any U.S. doctor who takes Medicare.",
  "Part D": "Medicare prescription drug coverage, a separate drug plan, or built into most all-in-one plans.",
  "drug list": "A plan's list of covered drugs (also called a formulary). Being listed doesn't by itself confirm the cost or approval for one person.",
  "drug deductible": "What you pay for covered drugs before the plan pays its share under its deductible rules. Some drugs may be exempt; the deductible is not the total cost of your medicines.",
  "add-ons": "The extra coverage you can buy to go with Original Medicare: a drug plan (Part D) and a Medigap policy. They fill the gaps Original Medicare leaves.",
  "Medicare Advantage": "Medicare hospital and medical coverage through a private insurance company’s plan instead of Original Medicare. Most plans include drug coverage. Doctors, costs, and rules vary by plan.",
  Medigap: "Medicare Supplement Insurance, a private policy that helps pay your share of costs under Original Medicare. Same thing as a Supplement.",
  network: "The providers and pharmacies a plan works with. Routine care outside a network can cost more or be uncovered, depending on the plan and service.",
  HMO: "A plan type that generally keeps you in its network, often needing a referral to see a specialist.",
  PPO: "A plan type that lets you go outside the network, but usually at a higher cost.",
  "yearly out-of-pocket limit": "A Medicare Advantage limit on covered medical cost sharing. Premiums and drug costs are separate. Original Medicare A/B has no yearly medical spending cap on its own.",
  "Medigap window": "The federal six-month age-65 Medigap period depends on both age and Part B enrollment. Insurers cannot use medical underwriting to refuse a policy or charge more because of health during this period; other conditions and special rights may still matter.",
  "star rating": "Medicare's 1-to-5 quality rating for a company's plans. More stars means higher measured quality.",
  "special needs plan": "An Advantage plan only for people who qualify, for example, with Medicaid or certain health conditions.",
};
const V5_ROWS = [
  ["Who runs it", "The federal government", "Private companies approved by Medicare"],
  ["Doctors and hospitals", "Any in the U.S. that accept Medicare", "Usually a network; going outside it can cost more or not be covered, except emergencies"],
  ["Prescription drugs", "Add a separate Part D plan", "Usually included"],
  ["What you pay when you get care", "Usually 20% for most Part B services after the Part B deductible. Part A has separate costs. Medigap may help with covered cost sharing.", "Copays or coinsurance, with a yearly out-of-pocket limit"],
  ["Monthly cost", "Part B premium + Part D premium + Medigap premium (if you buy one)", "Part B premium + the plan premium; amounts vary by plan"],
  ["Dental, vision, hearing", "Generally not covered", "Many plans include some"],
  ["Care away from home", "Works the same anywhere in the U.S.", "Mostly local network; check each plan's travel rules"],
  ["Changing later", "Switch to Advantage each fall. Buying Medigap later may need health questions outside your 6-month window.", "Change plans each fall (Oct 15 - Dec 7)"],
];
const PRIORITY_LABELS = {keep_doctors: "Keeping my current doctors", travel: "Care when away from home", low_premium: "A low monthly cost", predictable: "Predictable bills, fewer surprises"};
const EXTRA_LABELS = {dental: "Dental", vision: "Vision", hearing: "Hearing"};

function visBox(wrap, caption) { const v = node("figure", undefined, "visual"); v.append(wrap); if (caption) v.append(node("figcaption", caption, "visual-caption")); return v; }
function visualV0() {
  const grid = node("div", undefined, "v-two");
  grid.append(markup("div", "<span class='v-ico' aria-hidden='true'>✉</span><strong>Already getting Social Security?</strong><p>Your Medicare card arrives automatically around your 65th birthday.</p>", "v-card"),
    markup("div", "<span class='v-ico' aria-hidden='true'>🖊</span><strong>Not yet?</strong><p>You sign up yourself during your 7-month window.</p>", "v-card"));
  return visBox(grid, "Two ways people get Medicare at 65.");
}
function visualV2() {
  const grid = node("div", undefined, "v-two");
  grid.append(markup("div", "<strong>Part A, Hospital</strong><ul><li>Inpatient hospital care</li><li>Skilled nursing facility care</li><li>Hospice care</li></ul>", "v-card"),
    markup("div", "<strong>Part B, Medical</strong><ul><li>Doctors and outpatient care</li><li>Tests and medical equipment</li><li>Preventive services</li></ul>", "v-card"));
  return visBox(grid, "Part A and Part B together are called Original Medicare.");
}
function visualV3() {
  const wrap = node("div", undefined, "v-bar-wrap");
  const bar = node("div", undefined, "v-bar");
  const m = node("div", undefined, "v-bar-seg v-bar-medicare"); m.style.width = "80%"; m.append(markup("span", "Medicare pays<strong>$80</strong>"));
  const y = node("div", undefined, "v-bar-seg v-bar-you"); y.style.width = "20%"; y.append(markup("span", "You pay<strong>$20</strong>"));
  bar.append(m, y);
  wrap.append(node("p", "On an example $100 Part B bill, after the deductible:", "v-bar-lead"), bar);
  return visBox(wrap, "Example only. A Medigap policy can pay some or all of your $20 share.");
}
function visualFoundation() {
  const wrap = node("div", undefined, "coverage-foundation");
  wrap.append(node("h2", "How Original Medicare fits together"));
  const base = node("div", undefined, "fdn-blocks");
  for (const [part, label] of [["Part A", "Hospital care"], ["Part B", "Medical care"]]) {
    const block = node("div", undefined, "fdn-block"); block.append(spot(part === "Part A" ? "hospital" : "stethoscope"), node("strong", part), node("span", label)); base.append(block);
  }
  wrap.append(base, node("p", "These two parts are the foundation. Three things still need a closer look:", "diagram-lede"));
  const gaps = node("dl", undefined, "coverage-gaps");
  for (const [label, detail] of [["Prescription medicines", "Separate drug coverage may be needed."], ["Dental, vision, and hearing", "Routine services are generally not covered."], ["Your share of care costs", "Original Medicare has no yearly medical spending limit."]]) { gaps.append(node("dt", label), node("dd", detail)); }
  wrap.append(gaps); return visBox(wrap, "A picture of the coverage parts, not a statement that you are enrolled in them.");
}
function visualV4() {
  const wrap = node("div", undefined, "coverage-routes"); wrap.append(node("h2", "Two ways to arrange coverage"));
  const grid = node("div", undefined, "coverage-route-grid");
  for (const [title, steps] of [["Original Medicare", [["Parts A + B", "Hospital and medical care"], ["Separate Part D plan", "Prescription drug coverage"], ["Optional Medigap policy", "Helps with certain A/B costs"]]], ["Medicare Advantage", [["Hospital + medical through a private plan", "Instead of Original Medicare"], ["Drug coverage", "Included in many plans"], ["Other benefits", "Coverage and limits vary by plan"]]]]) {
    const col = node("section", undefined, "coverage-route"); col.append(node("h3", title)); const list = node("ol");
    for (const [label, detail] of steps) { const li = node("li"); li.append(node("strong", label), node("span", detail)); list.append(li); }
    col.append(list); grid.append(col);
  }
  wrap.append(grid, node("p", "Medigap works with Original Medicare, not Medicare Advantage. You still pay the Part B premium with either route.", "diagram-note"));
  return visBox(wrap, "Compare the same coverage needs across the two routes. Neither route is selected for you.");
}
// D25–D28: the small teaching picture is shared by the task and its chat answer.
function guidePicture(kind) {
  const picture = node("div", undefined, "guide-picture"); picture.dataset.kind = kind;
  if (kind === "basics") { picture.append(pictureBlock("Medicare", "Health insurance to help pay for care", "basics")); return picture; }
  if (kind === "drugbasics") { picture.append(pictureBlock("Part D", "Coverage for prescription medicines", "drugbasics")); return picture; }
  if (kind === "routesintro") { picture.append(progressivePicture({id:"routesintro", concepts:["medicare", "parts", "routes"]})); return picture; }
  if (kind === "costs") { picture.append(visualV3()); return picture; }
  if (kind === "costtypes") {
    const list = node("dl", undefined, "guide-checks");
    for (const [label, detail] of [["Premium", "Paid each month for coverage."], ["Deductible", "Paid before coverage pays its share, under the benefit rules."], ["Care costs", "Copays or coinsurance when you use care."]]) list.append(node("dt", label), node("dd", detail));
    picture.append(list, node("p", "The monthly premium alone is not your total cost.", "guide-diagram-note")); return picture;
  }
  if (kind === "dates") { picture.append(visualV6()); return picture; }
  if (kind === "drugs") {
    const routes = node("div", undefined, "guide-drug-routes");
    for (const [route, label, detail, topic] of [["Original Medicare", "Separate Part D plan", "Drug coverage you can add", "original"], ["Medicare Advantage", "Part D in most plans", "Drug coverage included in most plans", "advantage"]]) {
      const branch = node("section"), heading = node("h3"), explain = secondary(route, () => answerGuideTopic(topic)); explain.className = "guide-route-button"; explain.setAttribute("aria-label", `Explain ${route}`); heading.append(explain);
      const block = secondary("", () => answerGuideTopic("drugs")); block.className = "guide-piece guide-piece-topic"; block.setAttribute("aria-label", `Explain ${label}`); block.append(spot("pill"), node("strong", label), node("span", detail)); branch.append(heading, block); routes.append(branch);
    }
    picture.append(routes, node("p", "Check the exact medicine, drug list, pharmacy, and costs for each plan.", "guide-diagram-note")); return picture;
  }
  if (kind === "checks") {
    const list = node("dl", undefined, "guide-checks");
    for (const [label, value] of [["Doctors", "Check the exact plan and office."], ["Medicines", "Check the drug list and pharmacy costs."], ["Costs", "Compare monthly payments and care costs."]]) list.append(node("dt", label), node("dd", value));
    picture.append(list); return picture;
  }
  if (kind === "extras") {
    const grid = node("div", undefined, "guide-extras");
    for (const label of ["Dental", "Vision", "Hearing"]) grid.append(node("strong", label));
    picture.append(grid, node("p", "Check the covered services, limits, costs, and providers for each plan.", "guide-diagram-note")); return picture;
  }
  const base = node("div", undefined, "guide-base");
  for (const [part, label, icon, topic] of [["Part A", "Hospital care", "hospital", "parta"], ["Part B", "Medical care", "stethoscope", "partb"]]) { const item = node("button", undefined, "guide-part"); item.type = "button"; item.setAttribute("aria-label", `Explain ${part}: ${label.toLowerCase()}`); item.addEventListener("click", () => answerGuideTopic(topic)); item.append(spot(icon), node("strong", part), node("span", label)); base.append(item); }
  picture.append(base);
  if (kind === "parts") { picture.append(node("p", "Together: Original Medicare", "guide-diagram-note")); return picture; }
  const routes = node("div", undefined, "guide-branches");
  for (const [title, pieces] of [["Original Medicare", [["Parts A + B", "Hospital and medical"], ["Separate Part D plan", "Drug coverage you can add"], ["Optional Medigap", "Helps with your share of A/B costs"]]], ["Medicare Advantage", [["A + B in a private plan", "Hospital and medical"], ["Part D usually included", "Drug coverage in most plans"], ["Other benefits vary", "Check each plan's details"]]]]) {
    const route = node("section", undefined, "guide-branch"), head = node("h3"), routeButton = secondary(title, () => answerGuideTopic(title === "Original Medicare" ? "original" : "advantage")); routeButton.className = "guide-route-button"; routeButton.setAttribute("aria-label", `Explain ${title}`); head.append(routeButton); route.append(head);
    for (const [label, detail] of pieces) { const topic = label.includes("Part D") ? "drugs" : label.includes("Medigap") ? "medigap" : label === "Parts A + B" ? "parts" : label.includes("private plan") ? "advantage" : "extras"; const block = node("button", undefined, "guide-piece"); block.type = "button"; block.setAttribute("aria-label", `Explain ${label}`); block.addEventListener("click", () => answerGuideTopic(topic)); block.append(node("strong", label), node("span", detail)); route.append(block); }
    routes.append(route);
  }
  picture.append(routes, node("p", "Medigap goes with Original Medicare. You still pay the Part B premium with either route.", "guide-diagram-note"));
  return picture;
}
// D29–D30: concepts enter only when the current question needs them.
function lessonFor(n = state.journey.stop) {
  if (window.DaylightFlow?.active) return window.DaylightFlow.helpLesson;
  const start = state.screen.start || "goal", coverage = state.screen.coverage || "context", priority = state.screen.priorities || "priorities", p = person();
  const make = (id, relevance, concepts, summary) => ({id, ...GUIDE_TOPICS[id], topics: id === "basics" ? ["basics"] : [id, "basics"], relevance, concepts: ["medicare", ...concepts], ...(summary ? {summary} : {})});
  if (n === 0) {
    const reason = {basics: "Medicare is the starting point. The picture will grow as you explore.", recipient: "We ask so the next questions refer to the person who will receive coverage.", goal: "Your goal helps us choose which questions and explanations come next.", location: `Medicare is national, but the plans available can depend on where ${p.you} live.`, county: "Some ZIP codes cross county lines. We ask only when the location lookup needs clarification.", compareKind: "Different types of coverage do different jobs. Choose what you want to explore.", compareExplain: "First, see how the two coverage routes fit together.", learnNext: "Choose what you would like to understand. You can finish without entering personal details.", learnParts: "Hospital care and medical care are two parts of Medicare.", learnRoutes: "The two routes arrange hospital and medical coverage differently.", learnSupplement: "Supplements work with the Original Medicare route.", supplementResult: "You wanted to understand supplements. They work with Original Medicare; they do not go with Medicare Advantage."}[start];
    if (["learnParts"].includes(start)) return make("parts", reason, ["parts"]);
    if (["learnRoutes", "compareExplain"].includes(start)) return make("routesintro", reason, ["parts", "routes"]);
    if (["learnSupplement", "supplementResult"].includes(start)) return make("medigap", reason, ["parts", "routes", "medigap"]);
    if (state.quick || state.intake.goal === "compare") return make("checks", reason, ["parts", "drugs", "extras", "costs", "routes", "medigap"], "You’re taking the comparison shortcut. The full picture is here if you need a reference.");
    return make("basics", reason, [], ["location", "county"].includes(start) ? "Medicare is a national program. Later, we’ll use the location you enter to find local plan records." : "Medicare is health insurance. We’ll add the coverage pieces to this picture as you meet them.");
  }
  if (n === 1) return make(state.screen.timing === "social" ? "dates" : "parts", state.screen.timing === "social" ? "These benefits can affect whether Medicare enrollment starts automatically. We still need to check the actual notice." : "What is already in place helps us choose the relevant next questions. It is fine to be unsure.", ["parts"]);
  if (n === 2) {
    if (coverage === "routesIntro") return make("routesintro", "You’ve told us A and B are in place. First, let’s see the two ways that coverage can be arranged.", ["parts", "routes"]);
    if (coverage === "supplementIntro") return make("medigap", `This is one kind of extra insurance ${p.you} might already have. We’ll ask about ${p.your} current coverage next.`, ["parts", "routes", "medigap"]);
    if (["timing", "transition", "jobGoal"].includes(coverage)) return make("dates", coverage === "timing" ? "Birth timing helps us explain sign-up windows. It never substitutes for an actual coverage start date." : coverage === "jobGoal" ? "Your next task tells us whether to prepare a job-coverage checklist or explore future plan options." : "Work and insurance end dates help identify the enrollment questions to confirm before changing coverage.", ["parts"], "Parts A and B are the coverage foundation. When they start depends on the person’s situation.");
    if (coverage === "review") return make("routesintro", "Your current coverage and the change you want are separate facts. We keep both in view.", ["parts", "routes"]);
    if (coverage === "jobContext" && reviewMode()) return make("parts", "A and B are already reported in place. We ask about job insurance to understand what other benefits may be changing.", ["parts"]);
    return make(reviewMode() ? "routesintro" : "parts", reviewMode() ? "This helps us explain what would change, or understand the coverage already in place." : "Insurance from a current job can affect when to add Part B. That is why we ask before discussing dates.", reviewMode() ? ["parts", "routes", ...(state.intake.currentCoverage === "supplement" ? ["medigap"] : [])] : ["parts"], reviewMode() ? "The two routes provide A and B differently. Medigap is an optional policy used with Original Medicare." : "Keep A and B in view. Job coverage is separate, and may affect the next enrollment step.");
  }
  if (n === 3) return make("drugbasics", `The medicines ${p.you} take become a checklist for drug coverage. Names alone do not confirm coverage or prices.`, ["parts", "drugs"]);
  if (n === 4) return make("extras", "Routine dental, vision, and hearing services need their own check. We’ll keep the needs you select on your list.", ["parts", "drugs", "extras"]);
  if (n === 5) {
    const known = ["parts", "drugs", "extras", "costs"];
    if (priority === "routesIntro") return make("routesintro", "Now connect the coverage pieces you’ve learned to the two ways of getting Medicare.", [...known, "routes"]);
    if (priority === "medigapIntro") return make("medigap", "One more piece: extra insurance that can help with your share of Original Medicare costs.", [...known, "routes", "medigap"]);
    if (priority === "route") return make("options", "These are the pieces we’ve built together. Your answer chooses the first plan list to open; it does not enroll you.", [...known, "routes", "medigap"]);
    return make("costs", priority === "top" ? "When priorities conflict, this tells us what to check first. Some needs cannot be scored from published plan facts." : "A monthly payment and what you pay when you get care are different. Your priorities help us decide what to compare.", known);
  }
  return make(n === 6 ? "checks" : "next", n === 6 ? "Use the published records to compare facts, then verify doctors, medicines, costs, and enrollment requirements." : "This brings together the answers you entered and the checks that remain open.", ["parts", "drugs", "extras", "costs", "routes", "medigap"]);
}
function learnedConcepts(lesson) { return new Set([...(state.learned || []), ...lesson.concepts]); }
function teachLesson(lesson) { state.learned = learnedConcepts(lesson); }
function pictureBlock(title, detail, topic, current = false) {
  const b = secondary("", () => el("ask-panel").hidden ? explainPictureTopic(topic) : answerGuideTopic(topic)); b.className = "map-piece" + (current ? " map-piece-current" : ""); b.setAttribute("aria-label", `Explain ${title}`);
  b.append(node("strong", title), node("span", detail)); return b;
}
function progressivePicture(lesson) {
  const known = learnedConcepts(lesson), wrap = node("div", undefined, "learning-picture"); wrap.dataset.concepts = [...known].join(" ");
  const root = pictureBlock("Medicare", "Health insurance to help pay for care", "basics", lesson.id === "basics"); root.classList.add("map-root"); wrap.append(root);
  if (known.has("parts")) {
    const base = node("div", undefined, "map-foundation");
    base.append(pictureBlock("Part A", "Hospital care", "parta", lesson.id === "parts"), pictureBlock("Part B", "Medical care", "partb", lesson.id === "parts")); wrap.append(base);
  }
  if (known.has("routes")) {
    const branches = node("div", undefined, "map-routes");
    for (const [label, id, detail] of [["Original Medicare", "original", "A + B through the federal program"], ["Medicare Advantage", "advantage", "A + B through a private plan"]]) {
      const branch = node("section", undefined, "map-route"); branch.append(pictureBlock(label, detail, id, ["routesintro", "options"].includes(lesson.id)));
      if (known.has("drugs")) branch.append(pictureBlock(id === "original" ? "Separate Part D plan" : "Part D in most plans", "Prescription medicines", "drugs", ["drugs", "drugbasics"].includes(lesson.id)));
      if (known.has("medigap") && id === "original") branch.append(pictureBlock("Optional Medigap", "Helps with your share of A/B costs", "medigap", lesson.id === "medigap"));
      if (known.has("extras") && id === "advantage") branch.append(pictureBlock("Other benefits vary", "Check dental, vision, and hearing", "extras", lesson.id === "extras"));
      branches.append(branch);
    }
    wrap.append(branches);
    if (known.has("medigap")) wrap.append(node("p", "Medigap goes with Original Medicare.", "map-note"));
  } else {
    if (known.has("parts")) wrap.append(node("p", "A + B together are Original Medicare.", "map-note"));
    if (known.has("drugs")) wrap.append(pictureBlock("Part D", "Coverage for prescription medicines", "drugbasics", lesson.id === "drugbasics"));
    if (known.has("extras")) wrap.append(pictureBlock("Dental, vision, and hearing", "Routine services need a separate check", "extras", lesson.id === "extras"));
  }
  if (known.has("costs")) {
    const costs = node("div", undefined, "map-costs" + (lesson.id === "costs" ? " map-costs-current" : ""));
    costs.append(node("strong", "Two kinds of cost")); const grid = node("dl"); grid.append(node("dt", "Each month"), node("dd", "Your premium"), node("dt", "When you get care"), node("dd", "Your share of the bill")); costs.append(grid); wrap.append(costs);
  }
  if (lesson.id === "dates") { const context = node("div", undefined, "map-timing"); context.append(node("strong", "When coverage starts"), node("p", "Dates depend on age, actual coverage, and job insurance. Unknown dates stay open.")); wrap.append(context); }
  return wrap;
}
function lessonGuide(n, prefix = "stage") {
  const lesson = lessonFor(n), aside = node("aside", undefined, "lesson-guide"); aside.dataset.lesson = lesson.id;
  const title = node("h2", "Your Medicare picture", "lesson-title"); title.id = `${prefix}-lesson-title`; aside.setAttribute("aria-labelledby", title.id);
  const toggle = secondary(state.guideOpen ? "Hide Medicare guide" : "Show Medicare guide", () => {
    state.guideOpen = !state.guideOpen; state.guidePreference = state.guideOpen;
    state.pictureTopic = null; renderStop(n); requestAnimationFrame(() => el(`${prefix}-guide-toggle`)?.focus({preventScroll:true}));
  });
  toggle.id = `${prefix}-guide-toggle`; toggle.setAttribute("aria-expanded", String(state.guideOpen)); toggle.setAttribute("aria-controls", `${prefix}-guide-content`);
  const content = node("div", undefined, "guide-content"); content.id = `${prefix}-guide-content`; content.hidden = !state.guideOpen;
  if (state.pictureTopic && GUIDE_TOPICS[state.pictureTopic]) {
    const topic = GUIDE_TOPICS[state.pictureTopic], answer = node("section", undefined, "picture-explanation"), heading = node("h3", topic.question);
    heading.tabIndex = -1; answer.append(secondary("Back to picture", () => { state.pictureTopic = null; renderStop(n); requestAnimationFrame(() => el(`${prefix}-guide-toggle`)?.focus({preventScroll:true})); }), heading, node("p", topic.answer));
    answer.append(secondary("Ask more about this", () => { const id = state.pictureTopic; answerGuideTopic(id); })); content.append(answer);
  } else content.append(node("p", lesson.summary, "lesson-summary"), progressivePicture(lesson), node("p", "Select a named piece to read its explanation.", "map-instruction"));
  const source = state.pictureTopic ? GUIDE_TOPICS[state.pictureTopic]?.source || lesson.source : lesson.source;
  aside.append(title, toggle, content, link(source.includes("ssa.gov") ? "Source: Social Security" : "Source: Medicare.gov", source, "lesson-source"));
  return aside;
}
function explainPictureTopic(id) {
  if (!GUIDE_TOPICS[id]) return;
  state.pictureTopic = id; state.guideOpen = true; renderStop(state.journey.stop);
  requestAnimationFrame(() => document.querySelector(".picture-explanation h3")?.focus({preventScroll:true}));
}
function mobileConcept(lesson) {
  const box = node("div", undefined, "mobile-concept");
  const pairs = lesson.id === "basics" ? [["Medicare", "Health insurance", "basics"]] : lesson.id === "parts" ? [["Part A", "Hospital care", "parta"], ["Part B", "Medical care", "partb"]] : lesson.id === "drugbasics" ? [["Part D", "Prescription medicines", "drugbasics"]] : lesson.id === "medigap" ? [["Medigap", "Extra insurance for Original Medicare costs", "medigap"]] : lesson.id === "extras" ? [["Dental, vision, hearing", "Check routine services separately", "extras"]] : lesson.id === "costs" ? [["Each month", "Your premium", "costs"], ["When you get care", "Your share of the bill", "costs"]] : ["routesintro", "options"].includes(lesson.id) ? [["Original Medicare", "Federal program", "original"], ["Medicare Advantage", "Private plan", "advantage"]] : lesson.id === "dates" ? [["Coverage dates", "Confirm the actual start", "dates"]] : [["Doctors + medicines", "Check the exact plan", "checks"]];
  for (const [title, detail, id] of pairs) box.append(pictureBlock(title, detail, id));
  return box;
}
function visualV5() {
  const table = node("table", undefined, "v-compare"), thead = node("thead"), head = node("tr");
  head.append(node("th", ""), node("th", "Original Medicare"), node("th", "Medicare Advantage")); thead.append(head); table.append(thead);
  const body = node("tbody");
  for (const [l, o, a] of V5_ROWS) { const tr = node("tr"); const th = node("th", l); th.scope = "row"; const d1 = node("td", o); d1.setAttribute("data-col", "Original Medicare"); const d2 = node("td", a); d2.setAttribute("data-col", "Medicare Advantage"); tr.append(th, d1, d2); body.append(tr); }
  table.append(body);
  const wrap = node("div", undefined, "v-compare-wrap"); wrap.append(table);
  return visBox(wrap, "A side-by-side, not a scorecard. Neither column is “better.”");
}
function visualV8() {
  const wrap = node("div", undefined, "v8");
  wrap.append(markup("p", "Most states use standardized lettered Medigap plans, such as Plan G or Plan N. The same letter has the same basic benefits across insurers. These policy letters are different from Medicare Parts A and B. Massachusetts, Minnesota, and Wisconsin standardize policies differently.", "v8-lead"));
  const grid = node("div", undefined, "v8-grid");
  for (const [l, n] of [["A", "Basic benefits"], ["G", "Helps with covered A/B cost sharing; the Part B deductible is separate"], ["N", "Some office and emergency-room copays; other cost sharing can apply"], ["K / L", "You pay a share of covered costs, with a yearly limit"]]) grid.append(markup("div", `<span class='v8-letter'>Plan ${l}</span><span>${n}</span>`, "v8-card"));
  wrap.append(grid, node("p", "Prices aren't available in Daylight yet. Compare the lettered benefits, then request insurer quotes. An independent Medicare counselor can help.", "v8-note"));
  wrap.append(link("Compare official Medigap benefits", "https://www.medicare.gov/health-drug-plans/medigap/basics/compare-plan-benefits"));
  return visBox(wrap, "Benefits and insurer quotes are separate. Prices are not available here yet.");
}

function stamp(kind, text) {
  const icon = kind === "checked" ? "✓" : "◌";
  return markup("span", `<span class="stamp-ico" aria-hidden="true">${icon}</span> ${escapeHtml(text || (kind === "checked" ? "Checked" : "Not checked yet"))}`, "stamp " + (kind === "checked" ? "stamp-checked" : "stamp-notyet"));
}
function sourceTag(name, href) {
  const t = node("span", undefined, "source-tag"); t.append(markup("span", "▣", "st-ico"));
  if (href) { const a = node("a", name); Object.assign(a, {href, target: "_blank", rel: "noopener noreferrer"}); t.append(a); } else t.append(node("span", name));
  return t;
}
const SPOTS = {
  hospital: '<rect class="s-fill" x="16" y="22" width="32" height="34" rx="2"/><path class="s-line" d="M16 22v34h32V22zM32 28v14M25 35h14"/>',
  stethoscope: '<path class="s-line" d="M22 14v14a10 10 0 0 0 20 0V14"/><circle class="s-line-fill" cx="22" cy="13" r="3"/><circle class="s-line-fill" cx="42" cy="13" r="3"/><path class="s-line" d="M32 38v6a7 7 0 0 0 14 0v-3"/><circle class="s-fill s-line" cx="46" cy="39" r="4"/>',
  pill: '<rect class="s-fill s-line" x="22" y="14" width="20" height="10" rx="2"/><path class="s-line" d="M26 24v6a6 6 0 0 0 12 0v-6"/><path class="s-line" d="M24 44h16v8H24zM32 30v14"/>',
  umbrella: '<path class="s-fill s-line" d="M10 32a22 22 0 0 1 44 0z"/><path class="s-line" d="M32 32v16a5 5 0 0 1-10 0"/>',
  calendar: '<rect class="s-fill s-line" x="12" y="16" width="40" height="34" rx="3"/><path class="s-line" d="M12 26h40M22 12v8M42 12v8"/><circle class="s-sun" cx="40" cy="40" r="4"/>',
  bundle: '<rect class="s-fill s-line" x="16" y="20" width="32" height="28" rx="3"/><path class="s-line" d="M16 30h32M32 20v28"/><path class="s-line" d="M28 14h8l2 6H26z"/>',
  tooth: '<path class="s-fill s-line" d="M20 18c-6 0-8 6-6 14s3 16 7 16 3-10 7-10 3 10 7 10 5-8 7-16-0-14-6-14c-4 0-5 3-8 3s-4-3-9-3z"/>',
  phone: '<rect class="s-fill s-line" x="20" y="12" width="24" height="40" rx="5"/><path class="s-line" d="M28 17h8"/>',
  map: '<path class="s-fill s-line" d="M12 18l14-4 12 4 14-4v34l-14 4-12-4-14 4z"/><path class="s-line" d="M26 14v34M38 18v34"/><path class="s-dash" d="M18 40c6-10 18-6 20-18"/>',
};
function spot(name) { const f = node("span", undefined, "spot"); f.innerHTML = `<svg viewBox="0 0 64 64" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">${SPOTS[name] || ""}</svg>`; return f; }

function termChips(terms) {
  if (!terms || !terms.length) return null;
  const wrap = node("p", undefined, "term-chips"); wrap.append(node("span", "Tap to define: ", "term-lead"));
  for (const t of terms) { const b = node("button", t, "term-chip"); b.type = "button"; b.addEventListener("click", () => openGlossary(t)); wrap.append(b); }
  return wrap;
}
function openGlossary(term) {
  const d = el("glossary-dialog") || buildGlossaryDialog();
  el("glossary-term").textContent = term; el("glossary-def").textContent = GLOSSARY[term] || "Definition coming soon.";
  d.showModal();
}
function buildGlossaryDialog() {
  const d = node("dialog"); d.setAttribute("aria-labelledby", "glossary-term"); d.setAttribute("aria-describedby", "glossary-def"); d.id = "glossary-dialog"; d.className = "glossary-dialog";
  const t = node("h2", "", "glossary-head"); t.id = "glossary-term";
  const p = node("p", "", "glossary-def"); p.id = "glossary-def";
  const c = node("button", "Close", "primary-button"); c.type = "button"; c.addEventListener("click", () => d.close());
  d.append(t, p, c); d.addEventListener("click", e => { if (e.target === d) d.close(); }); document.body.append(d);
  return d;
}

/* ================================================================== input controls ================================================================== */
function renderChips(options, selected, onPick, opts = {}) {
  const wrap = node("div", undefined, "choices" + (opts.multi ? " choices-multiple" : ""));
  for (const [value, label] of options) {
    const b = node("button", label, "choice" + (opts.multi ? " multi" : ""));
    b.type = "button";
    b.dataset.value = value;
    b.setAttribute("aria-pressed", String(opts.multi ? (selected || []).includes(value) : selected === value));
    b.addEventListener("click", () => onPick(value, b));
    wrap.append(b);
  }
  return wrap;
}
function primary(label, onClick) { const b = node("button", label, "primary-button"); b.type = "button"; b.addEventListener("click", onClick); return b; }


/* Session-only answers. Only an explicitly submitted chat question leaves the tab. */
const GOALS = {learn: "Understand Medicare", compare: "Compare plans", review: "Review or change my coverage", job: "My job coverage is ending"};
const GOAL_NOTES = {learn: "Or work out where to start.", compare: "Look at plans or options you already have in mind.", review: "Including adding coverage.", job: "Work out the next steps for a transition."};
const COMPARE_KINDS = {advantage: "Medicare Advantage plans", medigap: "Medicare Supplement (Medigap)", drugs: "Separate drug plans (Part D)", named: "Plans I already have in mind", unsure: "Help me understand the difference"};
const ADVANTAGE_EXPLANATION = "With Medicare Advantage, you get your Medicare hospital and medical coverage through a private insurance company's plan instead of Original Medicare.";
const MEDIGAP_EXPLANATION = "With Original Medicare, you pay part of some care bills. Medicare Supplement insurance, also called Medigap, can help pay some of that share.";
const COVERAGE = {original: "Original Medicare only", supplement: "Original Medicare + Medigap", advantage: "Medicare Advantage", employer: "Employer, retiree, VA or other coverage", unsure: "Not sure yet"};
const STOP_NAMES = ["Your goal", "Parts A & B", "Your coverage", "Medicines", "Other benefits", "Your options", "Compare plans", "Next steps"];
const STATUS_WORD = {done: "answered", skipped: "not answered", blocked: "needs attention", locked: "not reached", current: "you are here", visited: "viewed"};
const CATEGORY_LABELS = {all: "All plan types", "MA-PD": "Advantage with drugs", MA: "Advantage without drugs", PDP: "Separate drug plans", SNP: "Special needs plans"};
function freshIntake() { return {priorities: [], priorityOrder: [], extras: [], medicines: "", doctor: ""}; }
const state = {intake: freshIntake(), journey: {stop: 0, reached: 0, visited: new Set(), finished: new Set()}, screen: {}, quick: false, guideOpen: true, guidePreference: null, pictureTopic: null, personalReview: false, learned: new Set(["medicare"]),
  conversationId: crypto.randomUUID(), history: [], busy: false, controller: null, connection: "checking", live: false,
  plansLoaded: false, plansError: null, catalog: null, category: "all", sort: null, selected: new Map(), comparison: null, compareError: null, compareBusy: false, plansLimit: 6, planQuery: "", requestId: 0};
const person = () => state.intake.recipient === "someone" ? {you: "they", your: "their", title: "Their"} : {you: "you", your: "your", title: "Your"};
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const reviewMode = () => state.intake.medicare === "yes_ab";
const decidingPartB = () => ["only_a", "no"].includes(state.intake.medicare);
const announce = text => { el("sr-live").textContent = text; };
function addMonths(my, count) { const n = my.year * 12 + my.month - 1 + count; return {year: Math.floor(n / 12), month: ((n % 12) + 12) % 12 + 1}; }
const monthNumber = my => my.year * 12 + my.month - 1;
const fmtMY = my => `${MONTHS[my.month - 1]} ${my.year}`;
function parseMonth(value) { const m = /^(\d{4})-(\d{2})$/.exec(value || ""); return m && +m[2] >= 1 && +m[2] <= 12 && +m[1] >= 1900 && +m[1] <= 2150 ? {year: +m[1], month: +m[2]} : null; }
function computeDates(i = state.intake, today = new Date()) {
  const now = {year: today.getFullYear(), month: today.getMonth() + 1};
  // New intake asks for the birth year. Legacy age-65 fields remain readable.
  const turn65 = i.dobMonth && i.dobYear ? {month: +i.dobMonth, year: +i.dobYear + 65} : i.birthMonth && i.birthYear ? {month: +i.birthMonth, year: +i.birthYear} : null;
  const known = !i.birthSkipped && !!turn65 && ["yes", "no"].includes(i.birthdayFirst);
  const effective65 = known ? addMonths(turn65, i.birthdayFirst === "yes" ? -1 : 0) : null;
  const iepStart = known ? addMonths(effective65, -3) : null, iepEnd = known ? addMonths(effective65, 3) : null;
  const b = parseMonth(i.partBStart);
  // The birthday never substitutes for an actual/confirmed Part B effective month.
  const medigapStart = effective65 && b && i.medicare === "yes_ab" ? (monthNumber(b) > monthNumber(effective65) ? b : effective65) : null;
  const employmentEnd = parseMonth(i.employmentEnd), coverageEnd = parseMonth(i.coverageEnd);
  const earliestEnd = employmentEnd && coverageEnd ? (monthNumber(employmentEnd) < monthNumber(coverageEnd) ? employmentEnd : coverageEnd) : null;
  return {known, turn65, iepStart, iepEnd, period: known ? (monthNumber(now) < monthNumber(iepStart) ? "upcoming" : monthNumber(now) > monthNumber(iepEnd) ? "past" : "current") : "unknown",
    medigapStart, medigapEnd: medigapStart ? addMonths(medigapStart, 5) : null, employmentEnd, coverageEnd, earliestEnd};
}
function dateItems() {
  const i = state.intake, d = computeDates(), items = [];
  if (reviewMode()) items.push(["2027 coverage review", "October 15 – December 7, 2026", "The fall window concerns health and drug plans. Buying or changing Medigap follows separate rules."]);
  if (["yes", "ended"].includes(i.job)) {
    if (d.employmentEnd) items.push(["Employment end month", fmtMY(d.employmentEnd), "The actual or expected month entered; confirm the exact date with the employer."]);
    if (d.coverageEnd) items.push(["Job health coverage end month", fmtMY(d.coverageEnd), "The actual or expected month entered; ask the benefits office to confirm the last covered day."]);
    items.push(reviewMode() ? ["Replacement coverage", "Confirm with the plan or SHINE", "Parts A and B are already reported in place. Check the drug and supplemental coverage changes and their enrollment timing before the job benefits end."] : ["Part B enrollment", "Confirm with Social Security", "Qualifying current-employment coverage can create an eight-month special enrollment period. Employment or coverage ending first matters; do not wait eight months to arrange continuous coverage."]);
  } else if (!reviewMode() && d.known && i.job === "no" && ["no", "auto", "signup", "only_a"].includes(i.medicare)) {
    items.push([d.period === "past" ? "Past initial enrollment window" : "Initial enrollment window", `${fmtMY(d.iepStart)} – ${fmtMY(d.iepEnd)}`, d.period === "past" ? "This window has passed. Social Security can check a special or general enrollment period; this is not a current sign-up deadline." : "This is the age-65 initial window. Social Security confirms eligibility and the actual coverage start."]);
  } else if (!reviewMode()) items.push(["Personal enrollment dates", "Still to confirm", i.medicare === "unsure" ? "Check the Medicare card or Social Security record before choosing an enrollment route." : "Age-65 timing and current coverage need to be established before showing a personal window."]);
  // Introduce this only once the user has reached the explanation of the two paths.
  if (state.journey.visited.has(5) && i.leaning === "original") items.push(d.medigapStart ? ["Age-65 Medigap enrollment window", `${fmtMY(d.medigapStart)} – ${fmtMY(d.medigapEnd)}`, "Based on the age-65 month and Part B effective month you entered. Confirm any special rights or exceptions before acting."] : ["Medigap enrollment dates", "Still to confirm", "We need the age-65 month and actual Part B effective month. We do not infer this window from a birthday alone."]);
  return items;
}
function visualV6() {
  const wrap = node("div", undefined, "v-timeline"), list = node("ol", undefined, "v-timeline-list");
  for (const [label, when, detail] of dateItems()) { const li = node("li", undefined, "v-tl-item"), body = node("div", undefined, "v-tl-body"), head = node("p", undefined, "v-tl-head"); head.append(node("strong", label), node("span", when, "v-tl-when")); body.append(head, node("p", detail, "v-tl-detail")); li.append(node("span", "", "v-tl-dot"), body); list.append(li); }
  wrap.append(list); return visBox(wrap, "Dates reflect the facts entered in this tab. Unresolved dates stay unresolved.");
}
function stageHead(title, lede) { const h = node("div", undefined, "stage-head"); h.append(node("h1", title, "stage-title")); if (lede) h.append(node("p", lede, "stage-lede")); return h; }
function questionBlock(prompt, note) { const q = node("div", undefined, "question"); q.append(node("h2", prompt, "question-prompt")); if (note) q.append(node("p", note, "question-note")); return q; }
function feedback(text, cls = "") { const p = node("div", undefined, "payoff answer-feedback " + cls); p.tabIndex = -1; p.setAttribute("role", "status"); p.append(node("p", text)); return p; }
function secondary(label, action) { const b = node("button", label, "secondary-button"); b.type = "button"; b.addEventListener("click", action); return b; }
function link(label, href, cls = "action-link") { const a = node("a", label, cls); a.href = href; if (!href.startsWith("tel:")) { a.target = "_blank"; a.rel = "noopener noreferrer"; } return a; }
function details(title, ...children) { const d = node("details", undefined, "v5-details"); d.append(node("summary", title), ...children); return d; }
// D06/D15: descriptions at existing call sites never replace the visible Continue label.
function actions(stage, _nextDescription, onNext, enabled = true, onBack) { const row = node("div", undefined, "continue-bar flow-actions"); const b = primary("Continue", onNext); b.disabled = !enabled;
  const form = stage.querySelector("form.single-field-form"); if (form) form.addEventListener("submit", event => { event.preventDefault(); if (!event.isComposing && !b.disabled && el("ask-panel").hidden) onNext(); }); row.append(b); if (onBack) { const back = secondary("Back", onBack); back.className = "text-button back-action"; row.append(back); } stage.append(row); }
function nextScreen(key, value) { state.pictureTopic = null; state.screen[key] = value; renderStop(state.journey.stop, "top"); }
function pick(field, value, invalidate = false) { const previous = state.intake[field]; state.intake[field] = value;
  if (field === "medicare" && previous !== value) { delete state.intake.partBStart; delete state.intake.currentCoverage; state.intake.coverageReviewed = false; state.intake.timingReviewed = false; state.screen.coverage = "context"; delete state.dateReturn; }
  if (field === "goal" && previous !== value) { delete state.intake.jobGoal; delete state.dateReturn; state.screen.coverage = "context"; state.intake.coverageReviewed = false; state.personalReview = ["review", "job"].includes(value); state.pictureTopic=null; state.quick = false; if (state.guidePreference === null) state.guideOpen = value === "learn"; invalidatePlans(); }
  if (field === "compareKind" && previous !== value) { state.category = value === "advantage" ? "MA-PD" : value === "drugs" ? "PDP" : "all"; state.sort = null; state.planQuery = ""; invalidatePlans(); }
  if (field === "job" && previous !== value) { for (const key of ["jobGoal", "employerSize", "employmentEnd", "coverageEnd"]) delete state.intake[key]; }
  if (field === "topPriority") state.intake.priorityOrder = [value, ...state.intake.priorities.filter(k => k !== value)]; if (invalidate) invalidatePlans(); renderStop(state.journey.stop, "feedback:" + field); }
function invalidatePlans(clearSelections = false) { if (state.selected.size) state.comparisonStale = true; state.requestId++; state.controller?.abort(); state.plansLoaded = false; state.plansError = null; state.catalog = null; state.comparison = null; state.compareError = null; if (clearSelections) state.selectionContext = null; }
function answeredStop(n) { const i = state.intake; return [!!i.goal && (i.goal !== "compare" || (!!i.zip && !!i.county)),
  !!i.timingReviewed, !!i.coverageReviewed, !!i.drugsReviewed, !!i.extrasAnswered, !!i.prioritiesAnswered, state.plansLoaded, state.journey.visited.has(7)][n]; }
function unresolvedStop(n) { const i = state.intake; return (n === 0 && i.county === "unsure") || (n === 1 && (["unsure", "yes_unknown_parts", "different"].includes(i.medicare) || (i.medicare === "no" && i.social === "unsure"))) || (n === 2 && ((!reviewMode() && i.job === "unsure") || i.currentCoverage === "unsure" || i.birthSkipped || i.birthdayFirst === "unsure")) || (n === 3 && i.drugs === "unsure") || (n === 4 && i.extrasUnsure); }
function journeyStatus(n) { if (n === 6 && state.plansError) return "blocked"; if (unresolvedStop(n)) return "blocked"; if (n === state.journey.stop) return "current"; if (n > state.journey.reached) return "locked"; if (n === 7 && state.journey.visited.has(7)) return "visited"; if (answeredStop(n)) return "done"; return state.journey.visited.has(n) ? "visited" : "skipped"; }
function routeStops() {
  const i = state.intake;
  const planned = i.goal === "compare" && !state.personalReview ? [0,6,7] : i.goal === "learn" && !state.personalReview ? [0,7] : i.goal === "job" && i.jobGoal !== "compare" ? [0,1,2,7] : [0,1,2,3,4,5,6,7];
  return [...new Set([...planned, ...state.journey.visited, state.journey.stop])].sort((a,b) => a-b);
}
function renderPhases(current) {
  const nav=el("journey-map"),strip=node("ol",undefined,"phase-track");
  for(const [index,label] of ["Your goal","Your situation","Your options","Your next step"].entries()){
    const li=node("li",undefined,index===current?"phase-current":"");if(index===current)li.setAttribute("aria-current","step");
    li.append(node("span",String(index+1),"phase-number"),node("span",label));strip.append(li);
  }
  nav.replaceChildren(strip);
}
function legacyPhase(){const n=state.journey.stop;return n===7?3:n>=5?2:n>0?1:["compareKind","compareExplain","supplementResult","location","county"].includes(state.screen.start)?2:["basics","learnNext","learnParts","learnRoutes","learnSupplement"].includes(state.screen.start)?1:0;}
function renderJourneyMap() {renderPhases(legacyPhase());}

function goToStop(n) { if (n > state.journey.reached) return; if (n === 7 && state.journey.stop !== 7) state.finishReturn = {stop: state.journey.stop, screen: {...state.screen}}; if (n !== state.journey.stop) state.pictureTopic = null; if (n !== 6) { state.requestId++; state.controller?.abort(); } state.journey.stop = n; state.journey.visited.add(n); renderStop(n, "top"); }
function advance(n = Math.min(state.journey.stop + 1, 7)) { state.journey.finished.add(state.journey.stop); state.journey.reached = Math.max(state.journey.reached, n); goToStop(n); }
function renderStop(n, focus = "none") {
  const selectedValue = document.activeElement?.closest?.(".choice")?.dataset.value;
  const disclosureKey = d => (d.closest("[data-plan-id]")?.dataset.planId || "") + ":" + d.firstElementChild?.textContent; const previous = state.renderedStop; state.openDetails ||= {}; if (previous !== undefined) state.openDetails[previous] = new Set([...el("stage").querySelectorAll("details[open]")].map(disclosureKey));
  state.journey.stop = n; state.journey.visited.add(n); renderJourneyMap(); const stage = el("stage"); stage.replaceChildren();
  [stop0, stop1, stop2, stop3, stop4, stop5, stop6, stop7][n](stage);
  teachLesson(lessonFor(n));
  arrangeStage(stage, n);
  for (const d of stage.querySelectorAll("details")) if (state.openDetails[n]?.has(disclosureKey(d))) d.open = true; state.renderedStop = n; if (!el("ask-panel").hidden) renderAskCanned();
  requestAnimationFrame(() => { if (document.activeElement !== stage && stage.contains(document.activeElement)) return; if (focus.startsWith("feedback") && selectedValue) { [...stage.querySelectorAll(".choice")].find(b => b.dataset.value === selectedValue)?.focus({preventScroll: true}); } else if (focus === "top") { stage.focus({preventScroll: true}); window.scrollTo({top: 0, behavior: "instant"}); } });
  announce(`${["Your goal","Your situation","Your options","Your next step"][legacyPhase()]}: ${stage.querySelector("h1")?.textContent || STOP_NAMES[n]}.`);
}
function arrangeStage(stage, n) {
  const lesson = lessonFor(n);
  if (n === 7) {
    const head = stage.querySelector(".stage-head"), actions = stage.querySelector(".next-actions"), top = node("div", undefined, "finish-head"), controls = node("div", undefined, "finish-controls");
    controls.append(actions, askBottom()); top.append(head, controls);
    const content = [...stage.children].filter(child => child !== head && child !== actions);
    stage.replaceChildren(top, ...content); return;
  }
  if (n === 6) {
    const head = stage.querySelector(".stage-head"), main = node("div", undefined, "catalog-main"), layout = node("div", undefined, "decision-layout");
    main.append(head, node("p", lesson.relevance, "task-relevance"));
    for (const child of [...stage.children]) if (child !== head) main.append(child);
    main.append(askBottom()); layout.classList.toggle("reference-collapsed",!state.guideOpen); layout.append(main, lessonGuide(n)); stage.replaceChildren(layout); return;
  }
  const head = stage.querySelector(".stage-head"), task = node("div", undefined, "task-area"), explanation = node("section", undefined, "supporting-content");
  explanation.setAttribute("aria-label", "Explanation and visual guide");
  const lede = head?.querySelector(".stage-lede");
  const question = stage.querySelector(".birth-card > h2, .question > h2"), heading = head?.querySelector("h1");
  if (question && heading) { explanation.append(node("p", heading.textContent, "stage-context")); heading.textContent = question.textContent; question.remove(); }
  task.append(head, node("p", lesson.relevance || "Choose what would help today. You can change your goal later.", "task-relevance"));
  for (const child of [...stage.children]) {
    if (child === head) continue;
    if (child.matches(".question, .form-field, .birth-card, .flow-actions, .next-actions, .teaching-copy")) {
      task.append(child);
    } else explanation.append(child);
  }
  if (lede) explanation.prepend(lede);
  task.append(askBottom());
  const layout = node("div", undefined, "decision-layout"); layout.append(task, lessonGuide(n));
  if (head) stage.replaceChildren(layout, explanation);
}
function askBottom() { const box = node("div", undefined, "ask-bottom"), b = secondary("Ask Daylight", openAsk); b.className = "ask-open-btn"; box.append(b, node("p", "Questions about this step? Your place stays here.")); return box; }
function showLanding() { document.body.classList.add("landing-mode"); el("landing").hidden = false; ["stage", "journey-map", "restart"].forEach(id => el(id).hidden = true); el("ask-open").hidden = false; if(document.querySelector(".header-note"))document.querySelector(".header-note").hidden = false; closeAsk(false); window.scrollTo({top: 0, behavior: "instant"}); requestAnimationFrame(() => el("get-started").focus({preventScroll: true})); }
function beginJourney(quick = false) { if(window.DaylightFlow) return window.DaylightFlow.start(quick); state.quick = quick; state.screen.start = quick ? "compareKind" : "goal"; state.personalReview = false; if (state.guidePreference === null) state.guideOpen = !quick; if (quick) state.intake.goal = "compare"; document.body.classList.remove("landing-mode"); el("landing").hidden = true; ["stage", "journey-map", "restart"].forEach(id => el(id).hidden = false); renderStop(0, "top"); }
function startOver() { window.DaylightFlow?.reset(); state.controller?.abort(); state.requestId++; Object.assign(state, {intake: freshIntake(), journey: {stop: 0, reached: 0, visited: new Set(), finished: new Set()}, screen: {}, quick: false, guideOpen: true, guidePreference: null, pictureTopic: null, personalReview: false, learned: new Set(["medicare"]), catalog: null, plansLoaded: false, plansError: null, category: "all", sort: null, selected: new Map(), comparison: null, compareError: null, compareBusy: false, plansLimit: 6, planQuery: "", openDetails: {}, renderedStop: undefined, dateReturn: null, conversationId: crypto.randomUUID(), history: [], busy: false, chatWelcomed: false, chatTurns: 0, preparationDrafts: {}, preparationContexts: {}, previousPreparationDrafts: [], activePreparation: null, finishReturn: null, comparisonStale: false, selectionContext: null, locationReturn: null, locationBusy: false, locationIssue: null}); el("ask-thread").replaceChildren(); askCurrentExchange = null; el("ask-input").value = ""; setAskStatus(""); showLanding(); }
function requestStartOver() {
  if (window.DaylightFlow?.requestStartOver) return window.DaylightFlow.requestStartOver();
  let dialog = el("restart-confirm");
  if (!dialog) {
    dialog = node("dialog", undefined, "restart-confirm"); dialog.id = "restart-confirm"; dialog.setAttribute("aria-labelledby", "restart-title"); dialog.setAttribute("aria-describedby", "restart-consequence");
    const title = node("h2", "Start a new guide?"); title.id = "restart-title";
    const explanation = node("p", "This clears this tab’s guide answers, notes, saved comparisons, conversation, and unsent question. Your current guide will be lost."); explanation.id = "restart-consequence";
    const row = node("div", undefined, "reset-actions"), keep = primary("Keep my guide", () => dialog.close()); keep.autofocus = true;
    row.append(keep, secondary("Clear and start over", () => { dialog.close(); startOver(); })); dialog.append(title, explanation, row); document.body.append(dialog);
  }
  dialog.showModal();
}

function stop0(stage) {
  const i = state.intake, page = state.screen.start || "goal";
  stage.append(stageHead("Let's start with your situation."));
  if (page === "goal") {
    const q = questionBlock("What would you like help with today?");
    const choices = renderChips(Object.entries(GOALS), i.goal, v => pick("goal",v));
    for (const b of choices.children) { b.append(node("span", GOAL_NOTES[b.dataset.value], "choice-detail")); }
    q.append(choices); stage.append(q);
    actions(stage,"Continue",() => { if(i.recipient && goalStart() === "personal")advance(1);else nextScreen("start",i.recipient?goalStart():"recipient"); },!!i.goal,showLanding); return;
  }
  if (page === "recipient") {
    const q = questionBlock("Who is this for?"); q.append(renderChips([["self","Me"],["someone","Someone I'm helping"]],i.recipient,v=>pick("recipient",v))); stage.append(q);
    actions(stage,"Continue",()=> { const next=goalStart(); if(next === "personal") advance(1); else nextScreen("start",next); },!!i.recipient,()=>nextScreen("start","goal")); return;
  }
  if (page === "personal") { actions(stage,"Continue",()=>advance(1)); return; }
  if (page === "basics") {
    stage.querySelector("h1").textContent = "What is Medicare?";
    stage.append(teachingCopy([["Health insurance from the federal government","Medicare helps pay for health care. It is mainly for people 65 or older. Some younger people qualify because of a disability or certain health conditions. Eligibility rules still apply."]]));
    actions(stage,"Continue",()=>nextScreen("start","learnNext"),true,()=>nextScreen("start","recipient")); return;
  }
  if (page === "learnNext") {
    const q=questionBlock("What would you like to understand next?"); q.append(renderChips([["parts","How the Medicare parts fit together"],["personal","Connect Medicare to my situation"],["finish","Keep what I've learned and see next steps"]],i.learningNext,v=>pick("learningNext",v))); stage.append(q);
    actions(stage,"Continue",()=>{ if(i.learningNext === "personal") {state.personalReview=true;advance(1);} else if(i.learningNext === "finish") advance(7); else nextScreen("start","learnParts"); },!!i.learningNext,()=>nextScreen("start","basics"));return;
  }
  if (["learnParts","learnRoutes","learnSupplement","compareExplain"].includes(page)) {
    const parts=page === "learnParts", supplement=page === "learnSupplement";
    stage.querySelector("h1").textContent=parts?"Hospital care and medical care":supplement?"Where supplements fit":"Two ways to get Medicare";
    stage.append(teachingCopy(parts?[["Part A","Hospital insurance, including inpatient hospital care."],["Part B","Medical insurance, including doctors and outpatient care."]]:supplement?[["Help with your share of the bill",MEDIGAP_EXPLANATION],["A separate decision","Medigap works with Original Medicare, not Medicare Advantage. Drug coverage is separate. Enrollment and switching rights need checking."]]:[["Original Medicare","Parts A and B through the federal program. Drug coverage can be added separately."],["Medicare Advantage",ADVANTAGE_EXPLANATION]]));
    if (page === "learnRoutes") {
      stage.append(secondary("Explain supplements with Original Medicare",()=>nextScreen("start","learnSupplement")));
      actions(stage,"Continue",()=>advance(7),true,()=>nextScreen("start","learnParts"));
    } else actions(stage,"Continue",()=>nextScreen("start",parts?"learnRoutes":supplement?"learnNext":"compareKind"),true,()=>nextScreen("start",parts?"learnNext":supplement?"learnRoutes":"compareKind"));return;
  }
  if(page === "compareKind") {
    const q=questionBlock("Which plans or options would you like to compare?");q.append(renderChips(Object.entries(COMPARE_KINDS),i.compareKind,v=>pick("compareKind",v)));stage.append(q);
    actions(stage,"Continue",()=>{ if(i.compareKind === "unsure") nextScreen("start","compareExplain"); else if(i.compareKind === "medigap") nextScreen("start","supplementResult"); else nextScreen("start","location"); },!!i.compareKind,state.quick?showLanding:()=>nextScreen("start",i.goal === "compare"?"goal":"recipient"));return;
  }
  if(page === "supplementResult") {
    stage.querySelector("h1").textContent="Understand Medicare Supplement plans";
    stage.append(teachingCopy([["Where Medigap fits",MEDIGAP_EXPLANATION],["Benefits and quotes are different","You can compare standardized benefits here. Insurer prices and personal eligibility need a separate quote. This catalog does not include Medigap quotes."]]));
    stage.append(visualV8(),node("p","Changing from Medicare Advantage to Original Medicare does not guarantee you can buy Medigap. Check your purchasing rights before dropping current coverage.","question-note"),link("Find Medigap policies on Medicare.gov","https://www.medicare.gov/medigap-supplemental-insurance-plans/"));
    actions(stage,"Continue",()=>advance(7),true,()=>nextScreen("start","compareKind"));return;
  }
  if(page === "location") {
    stage.append(renderLocation()); if(state.locationIssue)stage.append(feedback(state.locationIssue));
    actions(stage,"Continue",resolveLocation,!state.locationBusy && /^\d{5}$/.test(i.zip||""),()=> {if(state.locationReturn) {const n=state.locationReturn;state.locationReturn=null;goToStop(n);}else nextScreen("start","compareKind");});
    if(state.locationBusy) stage.append(node("p","Checking location…","loading-text"));return;
  }
  const matches=state.locationMatches || [];
  const q=questionBlock(matches.length>1?"Which county do you live in?":"Which county is your ZIP code in?","The lookup could not establish one county. Choose what you know; it is fine to be unsure.");
  const opts=matches.length ? matches.map(m=>[m.fips,m.name+", "+m.state]) : [["12021","Collier County, Florida"],["outside","A different county"]];
  q.append(renderChips([...opts,["unsure","I'm not sure"]],i.countyFips || i.county,v=>{i.countyFips=v;i.county=v === "12021"?"Collier County":v === "unsure"?"unsure":"outside";i.locationMethod="reported";pick("county",i.county,true);}));stage.append(q);
  if(i.county && i.county !== "Collier County")stage.append(feedback(i.county === "unsure"?"Location stays unresolved. Education and official comparison remain available.":"Local records here cover Collier County only. Medicare.gov can show plans for your area."));
  actions(stage,"Continue",finishLocation,!!i.county,()=>nextScreen("start","location"));
}
function goalStart() { return state.personalReview ? "personal" : state.intake.goal === "learn" ? "basics" : state.intake.goal === "compare" ? "compareKind" : "personal"; }
let geographyPromise;
async function resolveLocation() {
  const zip=state.intake.zip,session=state.conversationId;if(!/^\d{5}$/.test(zip||"") || state.locationBusy)return;
  state.locationBusy=true;state.locationIssue=null;renderStop(0);
  try {
    geographyPromise ||= requestJSON("/zip-counties.json").catch(error=>{geographyPromise=null;throw error;});
    const data=await geographyPromise;
    if(session !== state.conversationId || zip !== state.intake.zip || state.journey.stop !== 0 || state.screen.start !== "location")return;
    const rows=data.zips?.[zip];state.locationSource=data.source_url;state.locationPeriod=data.period;
    state.locationMatches=Array.isArray(rows)? rows.map(([fips,name,region])=>({fips,name,state:region})):[];
    state.intake.checkedZip=zip;
    if(state.locationMatches.length === 1) {
      const m=state.locationMatches[0];Object.assign(state.intake,{county:m.fips === "12021"?"Collier County":"outside",countyFips:m.fips,countyName:m.name,locationState:m.state,locationMethod:"lookup"});finishLocation();
    } else nextScreen("start","county");
  } catch(_) {if(session === state.conversationId && zip === state.intake.zip && state.journey.stop === 0 && state.screen.start === "location"){state.locationMatches=[];state.locationIssue="The location lookup is unavailable. You can tell us the county or keep it unknown.";nextScreen("start","county");}}
  finally {if(session === state.conversationId){state.locationBusy=false;if(state.journey.stop === 0)renderStop(0);}}
}
function finishLocation() { state.locationReturn=null;advance(6); }
function catalogBack() { if(state.intake.prioritiesAnswered)goToStop(5);else {state.screen.start="location";goToStop(0);} }
function editPersonalCoverage() { state.personalReview=true; if(!state.intake.recipient){state.screen.start="recipient";goToStop(0);}else {state.journey.reached=Math.max(state.journey.reached,1);goToStop(1);} }
function editLocation() {state.locationReturn=state.journey.stop;state.screen.start="location";goToStop(0);}
function renderLocation() {
  const form=node("form",undefined,"question single-field-form");form.append(node("h2",state.intake.recipient === "someone"?"What is their ZIP code?":"What is your ZIP code?","question-prompt"));
  const label=node("label","ZIP code","field-label"),input=node("input");input.id="zip-in";label.htmlFor=input.id;Object.assign(input,{type:"text",inputMode:"numeric",maxLength:5,pattern:"[0-9]{5}",required:true,placeholder:"e.g. 34102",className:"zip-input",value:state.intake.zip||""});
  input.addEventListener("input",()=>{state.intake.zip=input.value.trim();if(state.intake.zip !== state.intake.checkedZip){state.intake.county=null;state.intake.countyFips=null;invalidatePlans(true);}const next=el("stage").querySelector(".flow-actions .primary-button");if(next)next.disabled=state.locationBusy || !/^\d{5}$/.test(state.intake.zip);});
  input.addEventListener("keydown",e=>{if(e.isComposing && e.key === "Enter")e.preventDefault();});
  const submit=node("button","Continue");submit.type="submit";submit.hidden=true;submit.tabIndex=-1;form.append(label,input,submit);return form;
}
function monthPicker(title, monthKey, yearKey) {
  const card = node("div", undefined, "birth-card"), row = node("div", undefined, "month-row"); card.append(node("h2", title, "question-prompt"));
  const m = node("select"), y = node("input"); m.id = monthKey; m.setAttribute("aria-label", "Birth month"); m.append(new Option("Choose a month", "")); MONTHS.forEach((mo, n) => m.append(new Option(mo, String(n + 1)))); m.value = String(state.intake.dobMonth || "");
  Object.assign(y, {type: "number", min: "1900", max: String(new Date().getFullYear()), placeholder: "Birth year, e.g. 1962", value: state.intake.dobYear || ""}); y.setAttribute("aria-label", "Birth year");
  const err = node("p", "", "field-error"); err.setAttribute("role", "alert");
  const remember = () => { state.intake.dobMonth = m.value ? +m.value : null; state.intake.dobYear = y.value ? +y.value : null; delete state.intake[monthKey]; delete state.intake[yearKey]; };
  m.addEventListener("change", remember); y.addEventListener("input", remember);
  const save = () => { const now = new Date(); if (!m.value || !y.value || !Number.isInteger(+y.value) || +y.value < 1900 || +y.value > now.getFullYear() || (+y.value === now.getFullYear() && +m.value > now.getMonth() + 1)) { err.textContent = "Choose the birth month and enter the birth year, or select that you don't know the date."; y.focus(); return false; } remember(); state.intake[monthKey] = +m.value; state.intake[yearKey] = +y.value + 65; state.intake.birthSkipped = false; return true; };
  const month = node("label", "Birth month", "field-label"), year = node("label", "Birth year", "field-label"); month.append(m); year.append(y); row.append(month, year); card.append(row, err); return {card, save};
}
function stop1(stage) {
  const i = state.intake, {you, your, title} = person(), page = state.screen.timing || "coverage";
  stage.append(stageHead(page === "coverage" ? `${title} Medicare status.` : "How will enrollment start?", page === "coverage" ? "What is already in place will determine the next question." : `${cap(you)} said Medicare is not in place yet. Receiving benefits can affect whether enrollment is automatic.`));
  if (page === "coverage") {
    const q = questionBlock(i.recipient === "someone" ? "Do they have Medicare yet?" : "Do you have Medicare yet?");
    q.append(renderChips([["yes_ab","Yes, Parts A and B"],["only_a","Yes, Part A only"],["yes_unknown_parts","Yes, but I'm not sure which parts"],["no","No"],["unsure","I'm not sure"],["different","My situation is different"]],i.medicare,v=>pick("medicare",v,true)));stage.append(q);
    if(i.medicare)stage.append(feedback({yes_ab:"Parts A and B are reported in place. Their effective dates are separate facts.",only_a:"Part A is reported in place. Current job coverage can affect the next Part B questions.",yes_unknown_parts:"Medicare enrollment is reported; the parts stay unknown until checked.",no:"We'll check what affects enrollment and the next steps.",unsure:"Whether Medicare has started remains an open question.",different:"We won't assume Parts A and B. Describe the situation or keep it open for a counselor."}[i.medicare]));
    if(["yes_ab","only_a","yes_unknown_parts","different"].includes(i.medicare)) stage.append(secondary("Help me check my Medicare card",()=>{state.screen.cardHelp=!state.screen.cardHelp;renderStop(1); }));
    if(state.screen.cardHelp && ["yes_ab","only_a","yes_unknown_parts","different"].includes(i.medicare))stage.append(feedback('If you have your Medicare card nearby, look for “Hospital (Part A)” and “Medical (Part B).” Their start dates are listed separately. A private plan card is different. Reading the card is optional; no number or upload is needed.'));
    if(i.medicare === "different")stage.append(localNotes("medicareDetails","What would you like us to know? (optional)","For example: Part B only",400));
    actions(stage,"Continue",()=>{if(i.medicare === "no")nextScreen("timing","social");else {i.timingReviewed=true;state.screen.coverage=reviewMode() && i.goal === "learn"?"routesIntro":"context";advance(2);}},!!i.medicare,()=>goToStop(0));return;
  }

  const q = questionBlock(`Do ${you} already receive Social Security or Railroad Retirement benefits?`, "This helps establish whether enrollment may be automatic. It does not establish a coverage start date."); q.append(renderChips([["yes", "Yes"], ["no", "No"], ["unsure", "I'm not sure"]], i.social, v => pick("social", v))); stage.append(q);
  if (i.social) stage.append(feedback(i.social === "yes" ? "Enrollment is usually automatic at 65 for people already receiving these benefits. Check the actual Medicare notice or card, especially if delaying Part B or living outside the usual enrollment area." : i.social === "no" ? "People not receiving these benefits generally apply through Social Security. We'll establish current coverage before discussing dates." : "Whether enrollment is automatic remains unresolved. Check with Social Security; the guide will keep this question open."));
  actions(stage, "Continue to current health coverage →", () => { i.timingReviewed = true; advance(2); }, !!i.social, () => nextScreen("timing", "coverage"));
}

function coverageOverview() {
  const box = node("div", undefined, "coverage-overview"); box.append(visualV4(), sourceTag("Medicare: coverage options", SOURCES.options)); return box;
}
function stop2(stage) {
  const i = state.intake, p = person(), page = state.screen.coverage || "context";
  if (["routesIntro", "supplementIntro"].includes(page)) {
    const isRoutes = page === "routesIntro"; stage.append(stageHead(isRoutes ? "Two ways to get Medicare." : "What is Medigap?"));
    stage.append(teachingCopy(isRoutes ? [["Original Medicare", "Parts A and B through the federal program."], ["Medicare Advantage", ADVANTAGE_EXPLANATION]] : [["Extra insurance for Original Medicare", "Medigap can help pay your share of certain A/B costs. It works with Original Medicare, not Medicare Advantage."]]));
    actions(stage, "Continue", () => nextScreen("coverage", isRoutes && ["supplement"].includes(i.currentCoverage) ? "supplementIntro" : "context"), true, () => isRoutes ? goToStop(1) : nextScreen("coverage", "routesIntro")); return;
  }
  if (reviewMode() && page !== "timing" && !["jobContext", "jobGoal", "transition"].includes(page)) {
    stage.append(stageHead("Build on the coverage already in place.", "Having A and B doesn't tell us what other coverage you have. We won't assume there are gaps."));
    if (page === "context") {
      const q = questionBlock(i.recipient === "someone" ? "Which coverage do they have now?" : "Which coverage do you have now?",i.goal === "review"?"This helps us explain what would change.":"This helps us understand the coverage already in place."); q.append(renderChips(Object.entries(COVERAGE), i.currentCoverage, v => pick("currentCoverage", v, true))); stage.append(q);
      if (i.currentCoverage) stage.append(feedback({original: "We'll consider separate drug and supplemental coverage without assuming either is required.", supplement: "Your existing supplement may already address some costs. Compare its benefits and renewal premium before replacing it.", advantage: "We'll review an existing Advantage arrangement. Changing a plan and moving to Original Medicare with a supplement are different decisions.", employer: "Check how that coverage coordinates with Medicare before replacing it. Employer, retiree and military coverage have different rules.", unsure: "We'll keep the current arrangement unresolved. A plan card or benefits notice can help identify it; you don't need to upload it."}[i.currentCoverage]));
      stage.append(termChips(["Part A", "Part B", "Original Medicare", "Medigap", "Medicare Advantage"]));
      actions(stage, "Continue to what you want to review →", () => { if(i.goal === "job") nextScreen("coverage","jobContext"); else if(i.goal === "review") nextScreen("coverage","review"); else {i.coverageReviewed=true;advance(3);} }, !!i.currentCoverage, () => goToStop(1)); return;
    }
    const q=questionBlock("What would you like to do with this coverage?");q.append(renderChips([["keep","Understand or review what I have"],["replace","Compare replacing it"],["add","Explore adding coverage"],["unsure","I'm not sure yet"]],i.changeIntent,v=>pick("changeIntent",v,true)));stage.append(q);
    if(i.currentCoverage === "advantage" && i.changeIntent === "replace")stage.append(feedback("Moving to Original Medicare and buying Medigap are separate decisions. The fall plan-change period does not guarantee you can buy a supplement. Check those rights before dropping coverage."));
    actions(stage,"Continue",()=>{i.coverageReviewed=true;if(["replace","add"].includes(i.changeIntent)){state.screen.start="compareKind";goToStop(0);}else if(i.changeIntent === "keep"){advance(7);}else advance(3);},!!i.changeIntent,()=>nextScreen("coverage","context"));return;
  }

  const head = page === "jobContext" ? ["Plan for the other coverage ending.", "Parts A and B are already in place. These questions concern the job coverage and benefits that may be changing."] : state.dateReturn ? ["Confirm the dates for Medigap.", "The month you turned 65 and the Part B effective month are separate facts. Together, they help establish the federal age-65 supplement window."] : page === "timing" ? ["Check the age-65 timing.", i.job === "no" ? "There is no current-employment coverage reported. These dates describe the age-65 initial window; other eligibility or enrollment rights may still apply." : "The type of current insurance is unresolved. We can record age-based dates while keeping the enrollment decision open."] : page === "jobGoal" ? ["What are you planning for?", "Choose the next task for the current job coverage."] : page === "transition" ? ["Record the work-coverage transition.", "Employer size and the expected end months will shape the questions for the benefits office and Social Security."] : [i.medicare === "only_a" ? "Part A is in place. Let's establish the next step." : "What affects the enrollment decision?", "Current employment and the kind of health insurance help establish the next enrollment questions."];
  stage.append(stageHead(...head));
  if (page === "timing" && i.birthSkipped) stage.querySelector("h1").textContent = "You can continue without a birth date.";
  if (page === "context" || page === "jobContext") {
    if (i.medicare === "unsure") stage.append(node("p", "Enrollment status is still unknown. Use this as general guidance while checking the Medicare card or Social Security record.", "question-note"));
    const q = questionBlock(`Does ${p.your} health insurance come from ${p.your} own or a spouse's current job?`, "COBRA and retiree coverage are different from insurance based on a current job."); q.append(renderChips([["yes", "Yes, insurance from a current job"], ["ended", "The employment or its health coverage recently ended"], ["no", "No current-employment coverage"], ["unsure", "I'm not sure which kind of coverage it is"]], i.job, v => { i.coverageReviewed = false; pick("job", v); })); stage.append(q);
    if (i.job) stage.append(feedback(reviewMode() && ["yes", "ended"].includes(i.job) ? "Parts A and B are already in place. We will record what job coverage is ending and the dates, then identify the drug and other benefits to review." : i.job === "ended" ? "The employment and insurance end dates can affect the next enrollment questions. We will record both, rather than assume a current window." : i.job === "yes" ? "Employer size and the type of group coverage matter. Check with the benefits office before delaying Part B. Next, choose whether you are preparing for a future change or exploring plans now." : i.job === "no" ? "We'll look at age-65 timing, or keep it open if a different eligibility route applies. Past enrollment windows won't be presented as current deadlines." : "Ask whether this is group coverage based on active employment, and how it works with Medicare. Until confirmed, we won't tell you to delay Part B."));
    actions(stage, ["yes", "ended"].includes(i.job) ? "Continue to your work-coverage goal →" : reviewMode() ? "Continue to what you want to review →" : "Continue to timing details →", () => { if(["yes","ended"].includes(i.job) && i.goal === "job"){i.jobGoal="plan";nextScreen("coverage","transition");}else nextScreen("coverage",["yes","ended"].includes(i.job)?"jobGoal":reviewMode()?"review":"timing"); }, !!i.job, () => page === "jobContext" ? nextScreen("coverage", "context") : goToStop(1)); return;
  }
  if (page === "jobGoal") {
    const q = questionBlock("What would help with the job coverage?", "The guide can prepare a transition checklist or help you explore future options."); q.append(renderChips([["plan", "Make a work-coverage transition checklist"], ["compare", "Explore Medicare plans now"]], i.jobGoal, v => pick("jobGoal", v))); stage.append(q);
    if (i.jobGoal) stage.append(feedback(i.jobGoal === "plan" ? "Next we'll record the expected end months and questions for the benefits office. The checklist will show what still needs confirmation." : "We'll collect the same timing facts first, then continue to needs and plan options. Browsing does not establish that you can enroll now."));
    actions(stage, "Continue to transition facts →", () => nextScreen("coverage", "transition"), !!i.jobGoal, () => nextScreen("coverage", reviewMode() ? "jobContext" : "context")); return;
  }
  if (page === "transition") {
    stage.append(node("p", "Enter what is known; leave uncertain dates blank. We won't turn planned dates into a confirmed enrollment deadline.", "question-note"));
    const q = questionBlock("How many employees does the employer have?"); q.append(renderChips([["20plus", "20 or more"], ["under20", "Fewer than 20"], ["unsure", "I don't know"]], i.employerSize, v => pick("employerSize", v))); stage.append(q);
    if (i.employerSize) stage.append(feedback(reviewMode() ? "Parts A and B are already reported in place. Ask the benefits office how the job benefits coordinate with Medicare and what replacement drug or supplemental coverage needs review." : i.employerSize === "under20" ? "With fewer than 20 employees, job insurance may not pay fully without Medicare. Ask the benefits office and Social Security about Part B now, before waiting for retirement." : i.employerSize === "20plus" ? "Confirm that the coverage is a qualifying employer group plan and ask how it coordinates with Medicare. The guide does not verify that from employer size alone." : "Employer size and coordination rules remain open questions for the benefits office."));
    for (const [field, label] of [["employmentEnd", "Employment end month, actual or expected (optional)"], ["coverageEnd", "Job health coverage end month, actual or expected (optional)"]]) stage.append(monthField(field, label));
    stage.append(link("Medicare: working past 65 and changing job coverage", "https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65"));
    actions(stage, i.jobGoal === "plan" ? "Build my transition checklist →" : "Continue to medicines →", () => { if (!validMonthFields(stage)) return; i.coverageReviewed = true; if (i.jobGoal === "plan") { state.journey.reached = 7; advance(7); } else advance(3); }, !!i.employerSize, () => nextScreen("coverage", i.goal === "job" ? (reviewMode()?"jobContext":"context") : "jobGoal")); return;
  }
  const picker = monthPicker(`What month and year were ${p.you} born?`, "birthMonth", "birthYear"); if (!i.birthSkipped) stage.append(picker.card);
  const unknown = node("div", undefined, "form-field"), unknownLabel = node("label", undefined, "unknown-date"), checkbox = node("input"); checkbox.type = "checkbox"; checkbox.checked = !!i.birthSkipped;
  unknownLabel.append(checkbox, node("span", "I don't know the birth date, or Medicare eligibility is for another reason.")); unknown.append(unknownLabel); stage.append(unknown);
  checkbox.addEventListener("change", () => { i.birthSkipped = checkbox.checked; if (checkbox.checked) for (const key of ["birthMonth", "birthYear", "dobMonth", "dobYear", "birthdayFirst"]) delete i[key]; renderStop(2); });
  if (!i.birthSkipped) { const q = questionBlock(`Is ${p.your} birthday on the first day of the month?`, "This can shift the age-65 sign-up dates by one month."); q.append(renderChips([["yes", "Yes, the first"], ["no", "No"], ["unsure", "I'm not sure"]], i.birthdayFirst, v => { if (picker.save()) pick("birthdayFirst", v); })); stage.append(q); }
  if (i.birthSkipped || i.birthdayFirst === "unsure") stage.append(feedback("Age-based dates stay unresolved. Medicare can check disability, ESRD, or other eligibility and enrollment situations. The rest of the guide can still help you compare coverage roles."));
  else if (computeDates().known) stage.append(feedback(state.dateReturn ? "The age-65 month is recorded. The preview below uses the actual Part B month where entered; special or state rights still need confirmation." : `The age-65 initial enrollment window is ${computeDates().period}. Special enrollment rights and the actual Part B start need separate confirmation.`), visualV6());
  stage.append(sourceTag("Medicare: when to sign up", "https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-can-i-sign-up-for-medicare"));
  actions(stage, state.dateReturn === 5 ? "Return to priorities →" : "Continue to medicines →", () => { if (!i.birthSkipped && (!picker.save() || !i.birthdayFirst)) { announce("Enter the birth month and year and answer the first-day question, or select that you don't know the date."); return; } i.coverageReviewed = true; const next = state.dateReturn || 3; delete state.dateReturn; advance(next); }, true, () => { if (state.dateReturn) { delete state.dateReturn; goToStop(5); } else nextScreen("coverage", "context"); });
}
function monthField(key, labelText) { const wrap = node("div", undefined, "form-field"), l = node("label", labelText, "field-label"), input = node("input"); l.htmlFor = key; Object.assign(input, {id: key, type: "month", min: "1900-01", max: "2150-12", value: state.intake[key] || ""}); input.addEventListener("input", () => { state.intake[key] = input.value; }); wrap.append(l, input); return wrap; }
function validMonthFields(stage) { const invalid = [...stage.querySelectorAll('input[type="month"]')].find(input => input.value && (!parseMonth(input.value) || !input.validity.valid)); if (invalid) { invalid.reportValidity(); invalid.focus(); return false; } return true; }
function foundationCard() { const i = state.intake, box = node("div", undefined, "card foundation"); box.append(node("h2", "What we know about current coverage"), node("p", i.medicare === "yes_ab" ? `Parts A and B: in place. Coverage arrangement: ${COVERAGE[i.currentCoverage] || "not yet established"}.` : i.medicare === "only_a" ? "Part A: in place. Part B: not yet added. These are the facts entered, not a completed A/B foundation." : i.medicare === "no" ? "Medicare enrollment: not yet in place." : "Medicare enrollment: not yet confirmed.")); return box; }

function localNotes(field, label, placeholder, max = 1000) { const wrap = node("div", undefined, "form-field"), l = node("label", label, "field-label"), input = node("textarea"); input.id = field; l.htmlFor = field; Object.assign(input, {rows: 3, maxLength: max, placeholder, value: state.intake[field] || ""}); input.addEventListener("input", () => { state.intake[field] = input.value; }); wrap.append(l, input, node("p", "Saved in this tab for your checklist. This entry is not sent to chat or logged.", "question-note")); return wrap; }
function stop3(stage) {
  const i = state.intake, p = person(); stage.append(stageHead("Make a medicine-checking list.", "Part D is Medicare coverage for prescription medicines. Keep a list of what needs checking; we’ll connect this piece to your coverage options later."));
  const q = questionBlock(`Do ${p.you} take prescription medicines regularly?`); q.append(renderChips([["yes", "Yes"], ["no", "No"], ["unsure", "I'm not sure"]], i.drugs, v => { i.drugsReviewed = false; pick("drugs", v, true); })); stage.append(q);
  if (i.drugs === "yes") { stage.append(feedback("Add names, strengths and how often they are taken if known. We'll carry the list to your checklist. Personal coverage and pharmacy prices still need verification for each plan."), localNotes("medicines", "Medicines to check (optional)", "Example: medicine name, strength, frequency")); }
  if (i.drugs === "no") stage.append(feedback("No regular prescriptions today. That does not by itself mean drug coverage is unnecessary. Current creditable drug coverage and enrollment timing affect whether a late penalty could apply."));
  if (i.drugs === "unsure") { stage.append(feedback("The medicine list still needs to be gathered. The pharmacy can help identify current prescriptions. We'll keep this as an open task."), localNotes("medicines", "Notes for gathering the medicine list (optional)", "What needs to be confirmed?")); }
  if (i.drugs) stage.append(node("p", "Next we'll collect dental, vision and hearing needs, then use your priorities to explain the coverage trade-offs. We do not verify medicine coverage from this list.", "question-note"));
  actions(stage, "Continue", () => { i.drugsReviewed = true; advance(4); }, !!i.drugs, () => goToStop(2));
  stage.append(details("More about drug coverage and penalties", node("p", "Other coverage may count as creditable drug coverage. Ask the existing plan before changing it; taking no medicines does not settle the enrollment decision."), termChips(["Part D", "drug list", "drug deductible", "late penalty"]), link("Medicare: avoiding late enrollment penalties", "https://www.medicare.gov/basics/costs/medicare-costs/avoid-penalties")));
}
function stop4(stage) {
  const i = state.intake, p = person(); stage.append(stageHead("Which extras should stay on the checklist?", "Routine dental, vision and hearing coverage varies. Original Medicare generally does not cover these routine services; some Advantage plans include benefits with conditions and limits."));
  const q = questionBlock(`Which dental, vision, or hearing needs should we check?`, `Select any that matter for ${p.your} care. Or choose “None of these” or “I'm not sure yet.”`);
  const options = [["dental", "Dental"], ["vision", "Vision"], ["hearing", "Hearing"], ["none", "None of these"], ["unsure", "I'm not sure yet"]];
  const choices = renderChips(options, [], v => { if (["none", "unsure"].includes(v)) { i.extras = []; i.extrasNone = v === "none"; i.extrasUnsure = v === "unsure"; } else { i.extras = i.extras.includes(v) ? i.extras.filter(x => x !== v) : [...i.extras, v]; i.extrasNone = i.extrasUnsure = false; } i.extrasAnswered = false; invalidatePlans(); renderStop(4, "feedback"); }, {multi: true});
  const alternatives = node("div", undefined, "choice-alternatives"); alternatives.setAttribute("role", "group"); alternatives.setAttribute("aria-label", "No needs selected or not sure");
  [...choices.children].slice(3).forEach(b => alternatives.append(b)); q.append(choices, node("p", "Or", "choice-or"), alternatives);
  const chosen = i.extrasNone ? ["none"] : i.extrasUnsure ? ["unsure"] : i.extras; [...q.querySelectorAll(".choice")].forEach((b, n) => b.setAttribute("aria-pressed", String(chosen.includes(options[n][0])))); stage.append(q);
  const hasAnswer = chosen.length > 0;
  if (hasAnswer) stage.append(feedback(i.extrasUnsure ? "Extras remain undecided. We'll include a reminder to check routine care needs before choosing." : i.extrasNone ? "No extras requested. We'll still show what needs verification, without treating extra benefits as a match." : `We'll keep ${i.extras.map(k => EXTRA_LABELS[k].toLowerCase()).join(", ")} on the checklist. A benefit label does not establish what treatment, provider or annual allowance is covered.`));
  if (i.extras.length) stage.append(localNotes("extraNotes", "Specific needs to verify (optional)", "Example: dental work planned, glasses, hearing aids", 600));
  actions(stage, "Save extras and continue to priorities →", () => { i.extrasAnswered = true; advance(5); }, hasAnswer, () => goToStop(3));
}
const TRADEOFFS = {
  keep_doctors: ["Keeping doctors", "Any U.S. doctor accepting Medicare; check acceptance and assignment.", "Check the exact 2027 plan's network and referral rules.", "Daylight cannot confirm individual doctor participation. This does not affect plan ordering."],
  travel: ["Care away from home", "Medicare-accepting providers across the U.S.", "Routine out-of-area care depends on the plan; emergency protections differ from routine travel coverage.", "Travel coverage is not scored. Check the plan's Evidence of Coverage."],
  low_premium: ["Monthly costs", "Part B plus any drug-plan and supplement premiums.", "Part B plus the plan premium; care can have copays and coinsurance.", "We can sort published plan premiums. This excludes total care costs and Medigap quotes."],
  predictable: ["Costs when using care", "A Medigap policy may cover some Original Medicare cost sharing.", "Copays and coinsurance, with a limit for covered medical services.", "We can sort the published medical limit. It is not a prediction of your yearly bill and does not include every expense."],
};
function stop5(stage) {
  const i = state.intake, page = state.screen.priorities || "priorities";
  if (["routesIntro", "medigapIntro"].includes(page)) {
    const isRoutes = page === "routesIntro"; stage.append(stageHead(isRoutes ? "Two ways to get Medicare." : "What is Medigap?"));
    stage.append(teachingCopy(isRoutes ? [["Original Medicare", "Parts A and B through the federal program. Drug coverage can be added separately."], ["Medicare Advantage", ADVANTAGE_EXPLANATION + " Most plans include drug coverage."]] : [["Help with your share of the bill", "Medigap is extra insurance you may be able to buy for certain costs under Original Medicare. It does not go with Medicare Advantage."], ["A separate decision", "It does not replace drug coverage. Availability and enrollment rights need checking before changing existing coverage."]]));
    actions(stage, "Continue", () => completeRouteLesson(page), true, () => nextScreen("priorities", !isRoutes ? "routesIntro" : i.priorities.length > 1 ? "top" : "priorities")); return;
  }
  stage.append(stageHead(page === "route" ? "Compare the two ways to get coverage." : page === "top" ? "Put your priorities in order." : "What matters most to you?", "Doctors, travel, medicine prices and extra benefits still need checking. Only published financial fields can change the plan order."));
  if (page === "priorities") {
    const q = questionBlock("What is most important to you?", "Select any that matter to you. You can also continue without choosing a priority.");
    q.append(renderChips(Object.entries(PRIORITY_LABELS), i.priorities, v => { i.priorities = i.priorities.includes(v) ? i.priorities.filter(k => k !== v) : [...i.priorities, v]; if (!i.priorities.includes(i.topPriority)) delete i.topPriority; i.prioritiesAnswered = false; i.priorityOrder = []; invalidatePlans(); renderStop(5, "feedback"); }, {multi: true})); stage.append(q);
    actions(stage, "Continue", () => i.priorities.length > 1 ? nextScreen("priorities", "top") : openOptions("priorities"), true, () => goToStop(4));
  } else if (page === "top") {
    const most = questionBlock("If these conflict, which matters most?"); most.append(renderChips(i.priorities.map(k => [k, PRIORITY_LABELS[k]]), i.topPriority, v => pick("topPriority", v, true))); stage.append(most);
    if (i.topPriority) stage.append(feedback(["keep_doctors", "travel"].includes(i.topPriority) ? "This stays your first checking task. It cannot be scored; the order of published plan fields will be explained separately." : "This published financial field will come first when ordering plans within a category. It does not establish total cost or personal fit."));
    actions(stage, "Continue", () => openOptions("top"), !!i.topPriority, () => nextScreen("priorities", "priorities"));
  } else {
    const lq = questionBlock("Which options would you like to see?", "You can change the plan list later.");
    lq.append(renderChips([["unsure", "Show all options before I decide"], ["original", "Original Medicare with separate coverage"], ["advantage", "Medicare Advantage plans"]], i.leaning, v => { state.category = v === "original" ? "PDP" : v === "advantage" ? "MA-PD" : "all"; pick("leaning", v, true); })); stage.append(lq);
    if (i.leaning) stage.append(feedback({unsure: "We'll show all plan categories in their published order. Each category serves a different purpose. No coverage route has been selected.", original: "We'll start with separate drug plans. Supplement prices still need separate quotes. Check Medigap enrollment rights before dropping existing coverage.", advantage: "We'll start with Advantage plans that include drugs. Plans without drugs and special needs plans remain available in the other categories."}[i.leaning]));
    actions(stage, "Continue", () => { if (!validMonthFields(stage)) return; i.priorityOrder = i.topPriority ? [i.topPriority, ...i.priorities.filter(k => k !== i.topPriority)] : [...i.priorities]; i.prioritiesAnswered = true; state.sort = null; state.plansLimit = 6; state.planQuery = ""; if(!/^\d{5}$/.test(i.zip||"") || !i.county){state.locationReturn=5;state.screen.start="location";goToStop(0);}else advance(6); }, !!i.leaning, () => nextScreen("priorities", state.screen.routeBack || (i.priorities.length > 1 ? "top" : "priorities")));
  }
  if (page !== "route") { stage.append(details("How Medicare pays for care", visualV2(), visualV3(), sourceTag("Medicare: costs", SOURCES.costs))); return; }
  stage.append(termChips(["Medicare Advantage", "Medigap", "Part D", "network", "HMO", "PPO"]));
  if (i.priorities.length) {
    const rows = node("table", undefined, "v-compare"); const head = node("tr"); head.append(node("th", "Priority"), node("th", "Original Medicare + optional supplement"), node("th", "Medicare Advantage")); const th = node("thead"); th.append(head); rows.append(th); const tbody = node("tbody");
    for (const key of i.priorities) { const t = TRADEOFFS[key], tr = node("tr"), label = node("th", t[0]); label.scope = "row"; const a = node("td", t[1]), b = node("td", t[2]); a.dataset.col = "Original Medicare"; b.dataset.col = "Medicare Advantage"; tr.append(label, a, b); tbody.append(tr); }
    rows.append(tbody); const f = feedback("Here are the trade-offs for the priorities selected."); f.append(rows); i.priorities.forEach(k => f.append(node("p", TRADEOFFS[k][3], "question-note"))); stage.append(f);
  }
  stage.append(visualFoundation(), coverageOverview(), visualV5(), sourceTag("Medicare: coverage options", SOURCES.options));
  const rights = node("section", undefined, "medigap-rights"); rights.append(node("h2", "Before changing to a supplement"), node("p", "Medigap works with Original Medicare, not Medicare Advantage. The federal six-month age-65 enrollment window depends on being 65 or older and having Part B. Later applications can face underwriting, though special and state rights may apply. Check those rights before dropping existing coverage."), sourceTag("Medicare: buying Medigap", SOURCES.medigap)); stage.append(rights);
  if (i.leaning === "original") {
    stage.append(node("p", "The catalog can show separate drug plans. Medigap premiums and standalone dental quotes are not included, so a drug-plan premium is not the price of the whole Original Medicare route.", "question-note"));
    const dates = details("Optional: establish the Medigap date inputs", node("p", "Use the actual or confirmed Part B effective month, not an assumed 65th-birthday date."), monthField("partBStart", "Part B effective month (optional)"));
    if (!i.birthMonth || !i.birthYear || !["yes", "no"].includes(i.birthdayFirst)) { dates.append(node("p", "Age-65 timing is also unresolved. Edit Your coverage to enter it, or confirm the window with SHINE. No Medigap dates will be guessed."), secondary("Edit birth date", () => { state.screen.coverage = "timing"; state.dateReturn = 5; goToStop(2); })); }
    dates.append(secondary("Update date preview", () => { if (validMonthFields(stage)) renderStop(5, "feedback"); })); stage.append(dates, visualV6());
  }
}
function nextRouteLesson() { return !state.learned.has("routes") ? "routesIntro" : "route"; }
function openOptions(from) { const next = nextRouteLesson(); if (next === "route") state.screen.routeBack = from; nextScreen("priorities", next); }
function completeRouteLesson(from) { state.screen.routeBack = from; nextScreen("priorities", "route"); }
function teachingCopy(items) { const box = node("div", undefined, "teaching-copy"); for (const [title, copy] of items) { const item = node("section", undefined, "teaching-item"); item.append(node("h2", title), node("p", copy)); box.append(item); } return box; }

/* The application API remains authoritative. No static file or unreviewed data fallback. */
async function requestJSON(path, options = {}) {
  let r;
  try { r = await fetch(path, {...options, signal: options.signal || AbortSignal.timeout(12000)}); }
  catch (error) { if (["AbortError", "TimeoutError"].includes(error.name)) throw error; throw new Error("The service couldn't be reached. Please retry; your guide and notes are still in this tab."); }
  if (!(r.headers.get("content-type") || "").includes("application/json")) throw new Error("The plan service isn't connected right now. Your guide and notes are still available.");
  let data; try { data = await r.json(); } catch (_) { throw new Error("The service couldn't provide a usable response. Please try again."); }
  if (!r.ok || data.validation_status === "pending") { const error = new Error(data.validation_status === "pending" ? "Plan data is awaiting validation. No plan facts are available yet; your checklist and official comparison links still work." : r.status === 429 ? "The service is busy. Please try again shortly." : "The service couldn't complete that request. Your answers and saved notes are still in this tab."); error.pending = data.validation_status === "pending"; throw error; }
  return data;
}
async function checkConnection() { try { const s = await requestJSON("/api/status"); state.live = !!s.live_conversation_available; state.connection = s.consumer_ready === false ? "pending" : "available"; } catch (e) { state.live = false; state.connection = e.pending ? "pending" : "offline"; } updateChatAvailability(); return state.connection; }
function intakeToPriorities() { const i = state.intake, order = i.priorityOrder?.length ? i.priorityOrder : i.priorities, scored = []; for (const k of order || []) { const name = {low_premium: "monthly_premium", predictable: "medical_limit"}[k]; if (name) scored.push(name); } return {priorities: scored, unscored: [...(i.priorities || []).filter(k => ["keep_doctors", "travel"].includes(k)), ...(i.extras || []), ...(["yes", "unsure"].includes(i.drugs) ? ["medicines"] : [])]}; }
function stop6(stage) {
  const i = state.intake; stage.append(stageHead(`Comparing ${state.category === "all" ? "published plans" : state.category === "MA-PD" ? "Medicare Advantage plans with drug coverage" : state.category === "MA" ? "Medicare Advantage plans without drug coverage" : state.category === "PDP" ? "separate drug plans" : "special needs plans"} for 2027`, "These are published plan facts, not confirmed personal matches. A plan's monthly premium is only one part of Medicare costs."));
  if (!/^\d{5}$/.test(i.zip || "") || i.county !== "Collier County") {
    stage.append(feedback(i.county === "unsure" ? "The county is still unknown. Confirm it to view Collier County plans; this is not an out-of-area conclusion." : i.county === "outside" ? "This location is outside the current Collier County catalog. Use Medicare.gov for local plans, or keep building your guide." : "Confirm a ZIP code and county before opening local plan records."), secondary("Change or confirm location", editLocation), link("Compare plans for any area on Medicare.gov", SOURCES.compare));
    actions(stage, "Continue with unresolved plan search →", () => advance(7), true, catalogBack); return;
  }
  const context=node("div",undefined,"comparison-context");context.append(node("p",`ZIP ${i.zip} · Collier County${i.locationMethod === "reported" ? " (reported)" : ""} · Plan year 2027`,"question-note"),secondary("Change location",editLocation),secondary("Edit comparison goal",()=>{state.screen.start="compareKind";goToStop(0);}));stage.append(context);
  if(i.locationMethod === "lookup")stage.append(link(`Location source: HUD crosswalk${state.locationPeriod ? " · "+state.locationPeriod : ""}`,state.locationSource || "https://www.huduser.gov/portal/datasets/usps_crosswalk.html","lesson-source"));
  if(i.currentCoverage)stage.append(feedback(`Current coverage reported: ${COVERAGE[i.currentCoverage] || "still to confirm"}. Keeping current coverage is an option. Published records are not a comparison of its full personal costs or benefits.`));
  if(state.comparisonStale)stage.append(feedback("Your context changed. Saved candidates are retained for reference; load a new comparison before treating them as current."));
  if (!i.medicare) stage.append(feedback("You chose direct browsing. You can add current coverage and personal needs at any time using the journey above. No personal match has been established."), secondary("Review a possible personal change",editPersonalCoverage));
  const cats = node("div", undefined, "pref-row"); cats.setAttribute("aria-label", "Plan category");
  for (const [value, label] of Object.entries(CATEGORY_LABELS)) { const b = secondary(label, () => { if (state.category === value && state.plansLoaded) return; state.category = value; state.plansLimit = 6; state.planQuery = ""; state.sort = null; state.catalog = null; state.plansLoaded = false; state.plansError = null; state.comparison = null; renderStop(6, "none"); }); b.setAttribute("aria-pressed", String(state.category === value)); cats.append(b); } stage.append(cats);
  stage.append(node("p", "These categories serve different roles. Special needs plans have eligibility restrictions; seeing a record does not establish eligibility. Medigap quotes and standalone dental plans are not in this catalog.", "question-note"));
  if (i.leaning === "original" || state.category === "PDP") stage.append(details("Where Medigap fits alongside a drug plan", visualV8(), link("Find Medigap policies on Medicare.gov", "https://www.medicare.gov/medigap-supplemental-insurance-plans/")));
  const tasks = intakeToPriorities().unscored; if (tasks.length) stage.append(feedback(`Still to verify: ${tasks.map(k => ({keep_doctors: "doctor participation", travel: "routine care away from home", medicines: "medicine coverage and pharmacy prices", dental: "dental benefits", vision: "vision benefits", hearing: "hearing benefits"}[k])).join(", ")}. These do not determine this order.`));
  const host = node("div", undefined, "plans-host"); host.id = "stop6-plans"; stage.append(host);
  if (state.plansError) renderPlanError(host);
  else if (state.catalog) renderCatalog(host, state.catalog);
  else { host.append(node("p", "Checking the published plan service…", "loading-text")); loadCatalog(); }
  actions(stage, state.selected.size ? "Continue with my saved comparisons →" : state.plansLoaded ? "Continue to my next actions →" : "Continue with plan search unresolved →", () => advance(7), true, catalogBack);
}
function renderPlanError(host) { const box = node("div", undefined, "card info-card"); box.setAttribute("role", "alert"); box.append(node("h2", "Plan records are unavailable"), node("p", state.plansError), secondary("Try loading plan records again", () => { state.catalog = null; state.plansError = null; state.plansLoaded = false; renderStop(6); }), link("Use official Medicare plan comparison", SOURCES.compare)); host.replaceChildren(box); }
async function loadCatalog() {
  const requestId = ++state.requestId; state.controller?.abort(); const controller = new AbortController(); state.controller = controller; const timeout = setTimeout(() => controller.abort(), 12000);
  const priorities = state.category === "all" ? [] : state.sort !== null ? (state.sort ? [state.sort] : []) : intakeToPriorities().priorities;
  try {
    const result = await requestJSON("/api/catalog", {method: "POST", headers: {"Content-Type": "application/json"}, signal: controller.signal, body: JSON.stringify({conversation_id: state.conversationId, action: "list", category: state.category, priorities, year: "2027", county_fips: "12021"})});
    if (!Array.isArray(result.plans)) throw new Error("The catalog response was incomplete. Please retry; no comparison was completed.");
    if (requestId !== state.requestId || state.journey.stop !== 6) return;
    state.catalog = result; state.plansLoaded = true; state.plansError = null; renderStop(6); announce(`${result.plans.length} published records loaded. Personal fit remains unverified.`);
  } catch (e) { if (requestId !== state.requestId || state.journey.stop !== 6) return; state.plansLoaded = false; state.catalog = null; state.plansError = e.name === "AbortError" ? "The service took too long. Please retry; your notes are still available." : e.message; renderStop(6); }
  finally { clearTimeout(timeout); }
}
const metricNames = {monthly_premium: "Monthly plan premium", medical_limit: "In-network yearly medical limit", drug_deductible: "Drug deductible"};
function moneyLabel(m) { return m?.state === "value" && Number.isFinite(m.value_cents) ? new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(m.value_cents / 100) : m?.state === "not_applicable" ? "Not applicable" : "Not available"; }
function sourceLinks(facts) { const urls = new Set(); for (const f of facts || []) for (const s of (Array.isArray(f.evidence) ? f.evidence : [f.evidence]).filter(Boolean)) { const url = s.requested_url || s.url; if (url?.startsWith("https://")) urls.add(url); } if (!urls.size) return null; const d = details(`Sources (${urls.size})`); for (const url of urls) d.append(link(new URL(url).hostname, url)); return d; }
function renderCatalog(host, result) {
  host.replaceChildren(); const criteria = result.scored_criteria || [], first = criteria[0];
  const order = state.category === "all" ? "All categories are in source order. Their different roles make premium-only comparisons misleading." : first ? `Ordered by ${metricNames[first]?.toLowerCase() || "the selected published field"}, low to high. Unknown, inapplicable and conflicting values follow known values. This is not a personal-fit ranking.` : "Source order. No personal-fit ranking or best-plan designation.";
  host.append(node("p", `${result.plans.length} records · ${order}`, "rank-head"));
  const sorts = node("div", undefined, "pref-row"); sorts.append(node("span", "Order by", "chips-lead"));
  for (const [v, label] of [["", "Source order"], ["monthly_premium", "Plan premium"], ["medical_limit", "Medical limit"], ["drug_deductible", "Drug deductible"]]) { const b = secondary(label, () => { state.sort = v; state.plansLimit = 6; state.catalog = null; state.plansError = null; state.plansLoaded = false; renderStop(6); }); b.disabled = (state.category === "all" && !!v) || (state.category === "PDP" && v === "medical_limit") || (state.category === "MA" && v === "drug_deductible"); b.setAttribute("aria-pressed", String(v === (first || ""))); sorts.append(b); } host.append(sorts);
    const search = node("div", undefined, "form-field"), label = node("label", "Find a plan by name, company or ID", "field-label"), input = node("input"); label.htmlFor = "plan-search"; Object.assign(input, {id: "plan-search", type: "search", value: state.planQuery || "", placeholder: "Search this category"}); search.append(label, input); host.append(search);
  const list = node("div"); host.append(list);
  const paintPlans = () => {
    list.replaceChildren(); const query = (state.planQuery || "").toLowerCase(), filtered = result.plans.filter(p => [p.name, p.carrier, p.id].filter(Boolean).join(" ").toLowerCase().includes(query)), count = state.plansLimit || 6;
    const info = node("p", `Showing ${Math.min(count, filtered.length)} of ${filtered.length} matching records${query ? ` (${result.plans.length} in this category)` : ""}.`, "question-note"); info.setAttribute("role", "status"); list.append(info);
    const grid = node("div", undefined, "plan-card-grid"); filtered.slice(0,count).forEach((plan,index)=>grid.append(renderPlanCard(plan,index+1))); list.append(grid);
    if (!filtered.length) list.append(node("p", query ? "No names or IDs match this search. Clear the search or choose another category; this is not an eligibility result." : "No records were returned for this category. Try another category or use official Medicare comparison; this is not an eligibility result."));
    if (filtered.length > count) list.append(secondary(`Show ${Math.min(6,filtered.length-count)} more ${filtered.length-count === 1 ? "record" : "records"}`, () => { state.plansLimit = count + 6; paintPlans(); }));
  };
  input.addEventListener("input",()=>{state.planQuery=input.value;state.plansLimit=6;paintPlans();}); paintPlans();
  host.append(node("p", result.scope || "Published records do not establish personal eligibility or a complete live market.", "question-note"));
  host.append(renderSavedComparison());
  const lineages = sourceLinks(result.facts || []); if (lineages) host.append(lineages);
}
function renderPlanCard(plan, position) {
  const card = node("article", undefined, "plan-card"); card.dataset.planId = plan.id; card.append(node("p", `${CATEGORY_LABELS[plan.category] || plan.category} · ${plan.plan_type || ""}`, "plan-kind"), node("h3", plan.name), node("p", `${plan.id} · 2027 · Collier County, Florida`, "question-note"));
  const dl = node("dl", undefined, "plan-fields"); for (const [key, label] of Object.entries(metricNames)) dl.append(node("dt", label), node("dd", `${moneyLabel(plan.metrics?.[key])}${key === "monthly_premium" ? " / month" : ""}`)); card.append(dl, node("p", "Doctor participation, exact medicine coverage and personal total costs are not confirmed.", "question-note"));
  if (plan.premium_source_conflict) card.append(node("p", "Published premium sources disagree. See the preserved amounts and conditions below; this record is not treated as a known premium for ordering.", "catalog-warning"));
  if (plan.eligibility === "restricted_unconfirmed") card.append(node("p", `Restricted eligibility: ${plan.snp_type || "special needs criteria"}. Personal eligibility has not been established.`, "plan-eligibility"));
  const d = details("Plan details and source conditions");
  if (plan.star_rating?.state === "rated") d.append(node("p", `CMS rating: ${plan.star_rating.value} of 5. A contract-level quality measure, not a personal-fit score.`)); else d.append(node("p", "CMS rating: not available as a numeric rating in this record."));
  for (const note of plan.notes || []) d.append(node("p", note));
  for (const observation of plan.premium_basis?.observations || []) d.append(node("p", `${observation.label}: ${moneyLabel(observation.value)}`));
  const sources = sourceLinks([{evidence: [plan.source, ...(plan.star_rating?.evidence ? [plan.star_rating.evidence] : [])]}]); if (sources) d.append(sources); card.append(d);
  const saved = state.selected.has(plan.id), save = secondary(saved ? `Remove ${plan.name} from comparison` : `Save ${plan.name} for comparison`, () => { if (state.selected.has(plan.id)) state.selected.delete(plan.id); else if (state.selected.size < 3) { state.selected.set(plan.id, {...plan,savedContext:{zip:state.intake.zip,county:"Collier County",year:"2027"}}); state.selectionContext = `${state.intake.county}:${state.intake.zip}:2027`; } else { announce("Choose up to three records. Remove one before adding another."); const note = card.querySelector(".selection-error") || node("p", "", "selection-error field-error"); note.setAttribute("role", "alert"); note.textContent = "Up to three records can be compared. Remove one to add this plan."; card.append(note); return; } state.comparison = null; state.compareError = null; renderStop(6); announce(`${state.selected.size} records saved for comparison.`); }); save.setAttribute("aria-pressed", String(saved)); card.append(save);
  card.append(secondary(`Ask about ${plan.name}`, () => { openAsk(); askTyped(`Explain the published record for plan ${plan.id}, including its limitations.`); })); return card;
}
function renderSavedComparison() {
  const wrap = node("section", undefined, "card saved-comparison"); wrap.id = "saved-comparison"; wrap.append(node("h2", `${state.selected.size} records saved for comparison`), node("p", "Save two or three records. The comparison shows their different roles and published fields; it does not establish eligibility or choose a plan."));
  if (state.comparisonStale) wrap.append(node("p","Context changed. These are earlier candidates; request a new comparison before relying on them.","catalog-warning"));
  if (state.selected.size) { const ul = node("ul"); for (const p of state.selected.values()) { const li = node("li", `${p.name} (${p.id}) `); li.append(secondary(`Remove ${p.name}`, () => { state.selected.delete(p.id); state.comparison = null; renderStop(6); })); ul.append(li); } wrap.append(ul); }
  const b = primary(state.compareBusy ? "Loading comparison…" : "Compare saved records", compareSelected); b.disabled = state.selected.size < 2 || state.compareBusy; wrap.append(b);
  if (state.compareError) { const e = node("p", state.compareError, "field-error"); e.setAttribute("role", "alert"); wrap.append(e); }
  if (state.intake.currentCoverage) wrap.append(node("p",`Current coverage reported: ${COVERAGE[state.intake.currentCoverage]}. The exact current policy, renewal price, and benefits must be checked for a complete current-versus-proposed review. Keeping it remains an option.`,"question-note"));
  if (state.comparison) { wrap.append(node("p",`Published records · 2027 · Collier County, Florida · ZIP ${state.intake.zip}`,"question-note")); const plans = state.comparison.plans, table = node("table", undefined, "v-compare"), head = node("tr"); head.append(node("th", "Published field")); plans.forEach(p => head.append(node("th", p.name))); const thead = node("thead"); thead.append(head); table.append(thead); const body = node("tbody"); for (const [key, label] of [["category", "Coverage role"], ...Object.entries(metricNames), ["verification", "Personal checks"]]) { const row = node("tr"), title = node("th", label); title.scope = "row"; row.append(title); plans.forEach(p => { const text = key === "category" ? CATEGORY_LABELS[p.category] : key === "verification" ? "Doctors, drugs, total costs and eligibility still to verify" : key === "monthly_premium" && p.premium_source_conflict ? "Source conflict — see conditions" : moneyLabel(p.metrics?.[key]); const cell = node("td", text); cell.dataset.col = p.name; row.append(cell); }); body.append(row); } table.append(body); wrap.append(table, node("p", state.comparison.scope || "Different plan roles are not interchangeable.", "question-note")); for (const plan of plans) { const conditions = details(`Conditions and sources for ${plan.name}`); for (const note of plan.notes || []) conditions.append(node("p", note)); const source = sourceLinks([{evidence: plan.source}]); if (source) conditions.append(source); wrap.append(conditions); } }
  return wrap;
}
async function compareSelected() {
  if (state.compareBusy || state.selected.size < 2 || state.intake.county !== "Collier County") return; const ids = [...state.selected.keys()].sort(), id = state.requestId; state.compareBusy = true; state.compareError = null; renderStop(6);
  try { const r = await requestJSON("/api/catalog", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action: "compare", plan_ids: ids, conversation_id: state.conversationId})}); if (!Array.isArray(r.plans) || r.plans.length !== ids.length || r.plans.some(p => !ids.includes(p.id))) throw new Error("The comparison did not return the selected records. Retry before using it."); if (id === state.requestId && ids.join() === [...state.selected.keys()].sort().join()) { state.comparison = r; state.comparisonStale = false; } }
  catch (e) { if (id === state.requestId) state.compareError = e.message; }
  finally { state.compareBusy = false; if (id === state.requestId && state.journey.stop === 6) { renderStop(6); requestAnimationFrame(() => el("saved-comparison")?.scrollIntoView({block: "start", behavior: "instant"})); } }
}

function buildMap() {
  const i = state.intake, p = person(), steps = [];
  const arrangementUnknown = i.medicare === "yes_ab" && (!i.currentCoverage || i.currentCoverage === "unsure");
  steps.push({title: "Current coverage", status: !i.medicare || ["unsure","different","yes_unknown_parts"].includes(i.medicare) ? "Open question" : arrangementUnknown ? "A/B reported; arrangement unknown" : "Entered, not independently verified", sentence: !i.medicare ? "Medicare enrollment status was not entered." : i.medicare === "yes_ab" ? `Parts A and B are reported in place. ${arrangementUnknown ? "The coverage arrangement is still to confirm" : COVERAGE[i.currentCoverage]}.` : i.medicare === "only_a" ? "You reported Part A. Part B has not been added." : i.medicare === "no" ? "Not enrolled in Medicare yet." : i.medicare === "yes_unknown_parts" ? "You reported Medicare enrollment. Which parts are in place remains unknown." : i.medicare === "different" ? `A different Medicare situation was reported${i.medicareDetails ? ": " + i.medicareDetails : ""}. Confirm the parts and effective dates before a change.` : "Check the A/B lines and effective dates on the Medicare card or contact Social Security."});
  if (["yes", "ended"].includes(i.job)) steps.push({title: "Work-coverage transition", status: "Confirm before acting", sentence: `Ask the benefits office how Medicare coordinates with the current coverage${i.employerSize === "under20" ? "; fewer than 20 employees can change how claims are paid" : ""}. Confirm the last day of employment and health coverage. ${reviewMode() ? "Parts A and B are already in place; review the replacement drug and other benefits with the plan or SHINE." : "Contact Social Security before coverage ends; an eight-month Part B special period does not mean waiting eight months avoids a gap."}`});
  else if (!reviewMode()) steps.push({title: "Enrollment timing", status: "Still to confirm", sentence: i.job === "unsure" || !i.job ? "Establish whether coverage is based on current employment before deciding whether Part B can wait." : "Use Social Security's enrollment guidance to confirm the applicable window and coverage effective date. No Part B start has been inferred."});
  steps.push({title: "Comparison needs", status: i.drugsReviewed || i.extrasAnswered || i.prioritiesAnswered ? "Recorded where answered" : "Not yet collected", sentence: `Medicines: ${{yes: "regular prescriptions; coverage and pharmacy costs need checking", no: "no regular prescriptions reported", unsure: "unknown; gather the list"}[i.drugs] || "not answered"}. Extras: ${i.extrasUnsure ? "undecided" : i.extrasNone ? "none requested" : i.extras.length ? i.extras.map(k => EXTRA_LABELS[k]).join(", ") : "not answered"}.`});
  steps.push({title: "Plan comparison", status: state.plansError ? "Blocked" : state.plansLoaded ? "Records viewed; fit unverified" : "Not completed", sentence: state.plansError ? "The plan service did not provide usable records. No plan comparison was completed." : state.plansLoaded ? `${state.selected.size} records saved for comparison. ${state.comparison ? "A published-field comparison was loaded." : "No saved-record comparison has been completed."} Doctor participation, medicine coverage, eligibility and total costs remain unverified.` : "No local plan records have been viewed. Unanswered or skipped stages are not completed work."});
  return steps;
}
function checklistItems() {
  const i = state.intake, items = [];
  if (i.medicare === "no" && i.social === "yes") items.push("Check the automatic-enrollment notice or Medicare card and confirm the A/B effective dates with Social Security before assuming coverage has started.");
  if (i.medicare === "no" && i.social !== "yes") items.push(i.social === "unsure" ? "Ask Social Security whether enrollment will be automatic or requires an application; confirm the applicable timing." : "Contact Social Security to confirm the enrollment period and apply for Parts A and B, as appropriate to the current coverage situation.");
  if (i.medicare === "only_a" && i.job !== "yes") items.push("Ask Social Security about adding Part B and the applicable initial, special or general enrollment period; Part A alone does not establish a Part B start date.");
  if (!i.medicare || ["unsure","yes_unknown_parts","different"].includes(i.medicare)) items.push("Check the Medicare card or Social Security record for Parts A and B and their effective dates.");
  if (i.medicare === "yes_ab" && (!i.currentCoverage || i.currentCoverage === "unsure")) items.push("Use the current plan card or benefits notice to identify how coverage is arranged. A Medicare counselor can help; the guide has not confirmed the arrangement.");
  if (["yes", "ended"].includes(i.job)) { items.push("Benefits office: confirm employer group-plan status, employer size, coordination with Medicare, and the last covered day."); if (!reviewMode()) items.push("Social Security: confirm the Part B enrollment route and effective date before job coverage ends. Ask whether CMS-40B and employer evidence on CMS-L564 are needed."); else items.push("The plan or SHINE: review which drug, supplemental or other benefits need replacement when job coverage ends. Parts A and B are already reported in place."); items.push("Current drug plan: request the notice of creditable prescription coverage. Keep a copy.", "Confirm replacement drug and other coverage enrollment periods separately; one enrollment window does not establish every deadline."); }
  else if (i.goal === "job") items.push("Clarify what health coverage will end: no current-employment insurance has been confirmed in the guide.");
  if (i.drugs !== "no") items.push(i.medicines ? `Verify this medicine list against the exact plan and pharmacy: ${i.medicines}` : "Gather medicine names, strengths and frequency, then verify the exact plan's drug list and pharmacy costs.");
  if (i.doctor || i.priorities.includes("keep_doctors") || i.reviewFocus === "doctors") items.push(`Ask ${i.doctor || "each doctor's office"} about the exact 2027 plan, location and provider. Confirm with the plan too; no network match is established here.`);
  if (i.priorities.includes("travel")) items.push("Check routine care away from home, out-of-network costs and referral requirements in the plan's Evidence of Coverage.");
  if (i.extras.length) items.push(`Verify ${i.extras.map(k => EXTRA_LABELS[k].toLowerCase()).join(", ")} services, exclusions, provider rules and benefit limits.${i.extraNotes ? " Notes: " + i.extraNotes : ""}`);
  if (i.extrasUnsure) items.push("Decide which dental, vision or hearing needs should be checked.");
  if (!state.plansLoaded) items.push(i.jobGoal === "plan" ? "Once transition timing is confirmed, compare replacement coverage on Medicare.gov or return to this guide." : "Complete the local plan search when records are available, or use Medicare.gov for an official comparison.");
  if (i.leaning === "original" || i.currentCoverage === "supplement" || i.reviewFocus === "change") items.push("Check Medigap enrollment or switching rights and obtain actual supplement quotes before replacing coverage.");
  return items;
}
function helpLinks() { const box = node("div", undefined, "card"); box.append(node("h2", "People and official tools that can help")); const ul = node("ul", undefined, "help-list"); for (const h of (state.intake.county === "Collier County" ? HELP : [{name: "Free local Medicare counseling (SHIP)", detail: "Find the State Health Insurance Assistance Program where the person lives.", href: "https://www.shiphelp.org/"}, ...HELP.slice(1)])) { const li = node("li", undefined, "help-item"); li.append(node("strong", h.name), node("p", h.detail)); if (h.phone) li.append(link(h.phone, "tel:" + h.phone.replace(/[^+\d]/g, ""))); if (h.tty) li.append(node("p", h.tty)); if (h.href) li.append(link(h.name.startsWith("SHINE") ? "Find a SHINE counselor" : h.name.includes("SHIP") ? "Find local Medicare counseling" : "Open Medicare.gov plan comparison", h.href)); ul.append(li); } box.append(ul, link(state.intake.medicare === "only_a" ? "Social Security: add Part B" : reviewMode() ? "Social Security: Medicare records and enrollment questions" : "Social Security: sign up for Medicare", state.intake.medicare === "only_a" ? "https://www.ssa.gov/medicare/sign-up/part-b-only" : "https://www.ssa.gov/medicare/sign-up"), link("Medicare: help with costs", "https://www.medicare.gov/basics/costs/help")); return box; }
function supportTasks() {
  const i=state.intake, tasks=[];
  if (["yes","ended"].includes(i.job) || i.goal === "job") tasks.push({id:"benefits",title:"Check how the job coverage will end",action:"Prepare questions for the benefits office",reason:"These details help establish which enrollment and replacement-coverage questions need confirming."});
  if(i.medicare && i.medicare !== "yes_ab")tasks.push({id:"enrollment",title:i.medicare === "only_a"?"Confirm the next Part B step":"Confirm Medicare enrollment and timing",action:"Prepare a Social Security call script",reason:"The reported coverage and dates leave an enrollment question to confirm."});
  if(i.goal === "learn" && !state.personalReview)tasks.push({id:"learning",title:"Keep a clear picture of what you explored",action:"Prepare my learning summary",reason:"You can stop with understanding. Comparing or changing a plan is optional."});
  if(i.compareKind === "medigap" || i.leaning === "original" || i.currentCoverage === "supplement")tasks.push({id:"supplement",title:"Check supplement rights and request quotes",action:"Prepare supplement questions",reason:"Benefits, insurer prices, and the right to buy a policy are separate questions."});
  if(["yes","ended"].includes(i.job))tasks.push({id:"drugNotice",title:"Request the drug-coverage notice",action:"Prepare a request for the coverage notice",reason:"Ask the current coverage provider whether the drug coverage is creditable."});
  if(i.drugs === "yes" || i.medicines || i.doctor || i.priorities.includes("keep_doctors"))tasks.push({id:"care",title:"Check doctors and medicines for the exact plan",action:"Prepare doctor and medicine questions",reason:"A published plan record does not confirm these personal details."});
  if(!tasks.length)tasks.push({id:"review",title:i.changeIntent === "keep"?"Review the coverage you already have":"Review the published facts and open checks",action:"Prepare my comparison questions",reason:"Keeping current coverage is a valid outcome. Compare tradeoffs before deciding."});
  return tasks;
}
function preparationText(kind) {
  const i=state.intake, who=i.recipient === "someone"?"the person I’m helping":"me", dates=[];
  if(i.employmentEnd)dates.push("Employment end month reported: "+i.employmentEnd);
  if(i.coverageEnd)dates.push("Job health coverage end month reported: "+i.coverageEnd);
  const intro=`Prepared with Daylight for ${who}. These are questions, not verified answers. No one has been contacted.`;
  const prompts={
    benefits:["Questions for the benefits office",...dates,"Is this group health coverage based on current employment?","How many employees does the employer have, and how does this coverage coordinate with Medicare?","What are the exact last days of employment and health coverage?","Which drug and other benefits will end, and what will continue?","Can you provide written confirmation of these details?"],
    enrollment:["Call script for Social Security",`Medicare status reported: ${{yes_ab:"Parts A and B",only_a:"Part A only",yes_unknown_parts:"enrolled; parts unknown",no:"not enrolled",unsure:"unknown",different:"another situation"}[i.medicare] || "not entered"}.`,...(i.medicareDetails?[i.medicareDetails]:[]),...dates,"Please help confirm the parts of Medicare in place and their effective dates.",...(i.medicare !== "yes_ab"?["Which enrollment period or other eligibility route applies to this situation?","What application or evidence is needed, and when would coverage start?"]:[]),...(["yes","ended"].includes(i.job) && !reviewMode()?["Are CMS-40B and employer evidence on CMS-L564 needed? What should be done before job coverage ends?"]:[]),"I do not want to assume a start date or miss a separate drug-coverage deadline."],
    drugNotice:["Draft request to the current coverage provider","Please provide the notice stating whether my current prescription drug coverage is creditable for Medicare Part D.","Please confirm which dates the notice covers and when that coverage will end.","I would like a copy to keep with my records."],
    care:["Questions for the plan, doctor’s office, and pharmacy",...(i.doctor?["Doctor / office to check: "+i.doctor]:[]),...(i.medicines?["Medicine list reported: "+i.medicines]:["Gather medicine names, strengths, and frequency."]),"For each exact plan and year: does this doctor at this location participate? Confirm with both the office and plan.","For each exact medicine and pharmacy: is it covered, are there restrictions, and what costs apply?","Do referral, travel, or benefit rules affect the care needed?"],
    supplement:["Questions about Medicare Supplement insurance (Medigap)",MEDIGAP_EXPLANATION,"Is Original Medicare in place or being considered?","Which enrollment or guaranteed-issue rights apply? What dates or health questions matter?","What are the actual insurer quotes for the same lettered benefits?","If leaving Medicare Advantage, what must be arranged before changing coverage?","Drug coverage is a separate check. Do not drop existing coverage based on this draft."],
    learning:["What I explored",...[...state.learned].map(k=>({medicare:"Medicare: federal health insurance that helps pay for care.",parts:"Part A: hospital care. Part B: medical care.",routes:ADVANTAGE_EXPLANATION,medigap:MEDIGAP_EXPLANATION,drugs:"Part D: prescription drug coverage.",costs:"Monthly premiums and costs when using care are different.",extras:"Routine dental, vision, and hearing services need their own check."}[k])).filter(Boolean),"My next question: ","I can keep learning, connect this to my situation, or compare options later."],
    review:["Questions for reviewing coverage",...(i.currentCoverage?["Current coverage reported: "+COVERAGE[i.currentCoverage]]:[]),...(state.selected.size?["Saved candidates, not enrollment choices:",...[...state.selected.values()].map(p=>p.name+" · "+p.id)]:[]),"What changes compared with the coverage already in place?","Which costs are published, and which personal costs remain unknown?","Are the doctors, medicines, pharmacies, and other benefits needed covered under the exact plan?","What enrollment periods or switching rights apply?","Would keeping current coverage meet my needs?"],
  };
  return [intro,"",...(prompts[kind] || prompts.review)].join("\n\n");
}
function openPreparation(kind) {
  state.activePreparation=kind;state.preparationDrafts ||= {};state.preparationContexts ||= {};if(state.preparationDrafts[kind] === undefined){state.preparationDrafts[kind]=preparationText(kind);state.preparationContexts[kind]=JSON.stringify(state.intake);}
  renderStop(7);requestAnimationFrame(()=>{el("preparation-draft")?.focus();el("preparation-workspace")?.scrollIntoView({block:"start",behavior:"instant"});});
}
function preparationWorkspace() {
  const section=node("section",undefined,"preparation-workspace");section.id="preparation-workspace";
  const title=node("h2","Your draft — ready to edit"),label=node("label","Questions or message to use","field-label"),draft=node("textarea");draft.id="preparation-draft";label.htmlFor=draft.id;draft.rows=12;draft.value=state.preparationDrafts[state.activePreparation];
  draft.addEventListener("input",()=>{state.preparationDrafts[state.activePreparation]=draft.value;});
  const status=node("p","Prepared only. Nothing has been sent.","preparation-status");status.setAttribute("role","status");
  const row=node("div",undefined,"preparation-actions");
  if(state.preparationContexts?.[state.activePreparation] !== JSON.stringify(state.intake)){
    status.textContent="Your answers changed after this draft was prepared. Review it before use.";
    row.append(secondary("Create an updated draft",()=>{const kind=state.activePreparation;state.previousPreparationDrafts ||= [];state.previousPreparationDrafts.push(state.preparationDrafts[kind]);state.preparationDrafts[kind]=preparationText(kind);state.preparationContexts[kind]=JSON.stringify(state.intake);renderStop(7);}));
  }
  row.append(secondary("Copy draft",async()=>{try{await navigator.clipboard.writeText(draft.value);status.textContent="Copied. You can paste and use this draft yourself.";}catch(_){draft.focus();draft.select();status.textContent="Select and copy the draft using your device’s Copy command.";}}),secondary("Print or save this draft",printMap),secondary("Back to my next steps",()=>{state.activePreparation=null;renderStop(7,"top");}));
  section.append(title,node("p","This draft stays in this tab. Edit it before using it; Daylight has not contacted anyone.","question-note"),label,draft,status,row);return section;
}
function checklistGroups() {
  if(state.intake.goal === "learn" && !state.personalReview)return [{title:"Keep exploring when you want",items:["Use the Medicare picture to revisit the concepts you explored.","Write down a question for Daylight or an independent Medicare counselor. No plan change is required."]}];
  const groups=[{title:"Enrollment and current coverage",items:[]},{title:"Job coverage and transition",items:[]},{title:"Coverage, doctors, and medicines",items:[]}];
  for(const text of checklistItems()) {
    const index=/Benefits office|Current drug plan|replacement drug|job coverage|transition timing|health coverage will end/.test(text)?1:/Social Security|Medicare card|enrollment notice|identify how coverage/.test(text)?0:2;
    // Work-transition SSA action already covers the generic enrollment instruction.
    if(["yes","ended"].includes(state.intake.job) && /^Contact Social Security to confirm the enrollment period/.test(text))continue;
    groups[index].items.push(text);
  }
  return groups.filter(g=>g.items.length);
}
function summaryContent(interactive = false) {
  const wrap=node("div",undefined,"summary-content"),i=state.intake,tasks=supportTasks();
  wrap.append(node("p",`${i.recipient === "someone"?"For the person you're helping":i.recipient === "self"?"For you":"Your research"} · ${GOALS[i.goal]||"Goal not entered"}${i.zip?` · ZIP ${i.zip}`:""}${i.county?` · ${i.county === "Collier County"?"Collier County":i.county === "outside"?(i.countyName || "Outside Collier County"):"County unresolved"}`:""}`,"finalmap-sub"));
  const grid=node("div",undefined,"summary-grid"),next=node("section",undefined,"checklist-primary"),recorded=node("section",undefined,"recorded-summary");
  next.append(node("h2","Your next step: "+tasks[0].title.toLowerCase()),node("p",tasks[0].reason,"checklist-intro"));
  if(interactive)next.append(secondary("Help me with this step",()=>openPreparation(tasks[0].id)));
  for(const group of checklistGroups()) { const list=node("ul",undefined,"todo-list");group.items.forEach(text=>list.append(node("li",text)));next.append(node("h3",group.title),list); }
  if(interactive && tasks.length>1){next.append(node("h3","Prepare another step"));for(const task of tasks.slice(1))next.append(secondary(task.action,()=>openPreparation(task.id)));}
  recorded.append(node("h2","What you entered"),node("p","Reported facts and open questions; these are not verified or completed service actions.","checklist-intro"));
  if(i.goal === "learn" && !state.personalReview) {
    recorded.append(node("h3","Concepts explored"));const list=node("ul");for(const concept of state.learned)list.append(node("li",{medicare:"Medicare",parts:"Parts A and B",routes:"The two coverage routes",medigap:"Medicare Supplement insurance",drugs:"Prescription coverage",costs:"Monthly and care costs",extras:"Other benefits"}[concept]||concept));recorded.append(list);
  } else {const list=node("ul",undefined,"finalmap-route");for(const step of buildMap()){const li=node("li"),body=node("div");body.append(node("h3",step.title),node("p",step.status,"summary-status"),node("p",step.sentence));li.append(body);list.append(li);}recorded.append(list);}
  if(interactive){const edits=node("div",undefined,"summary-edits");edits.append(secondary("Edit coverage answers",editPersonalCoverage),secondary(state.plansError?"Retry the plan search":"Explore plan comparisons",()=>{state.screen.start="compareKind";goToStop(0);}));recorded.append(edits);}
  grid.append(next,recorded);wrap.append(grid);
  if(i.medicare || i.job)wrap.append(visualV6());
  if(i.priorities.length)wrap.append(node("p","Priorities: "+(i.priorityOrder.length?i.priorityOrder:i.priorities).map(k=>PRIORITY_LABELS[k]).join("; ")));
  if(i.leaning)wrap.append(node("p",`Your stated preference when preparing this guide: ${i.leaning === "original"?"Original Medicare with separate coverage":i.leaning === "advantage"?"Medicare Advantage":"still exploring"}. This is your preference, not a Daylight recommendation.`));
  if(i.doctor)wrap.append(node("p","Doctor / office to check: "+i.doctor));
  if(i.medicines)wrap.append(node("p","Medicines reported: "+i.medicines));
  if(i.extraNotes)wrap.append(node("p","Other benefit notes: "+i.extraNotes));
  if(state.selected.size){wrap.append(node("h2","Saved for comparison, not chosen for enrollment"));for(const plan of state.selected.values())wrap.append(node("p",`${plan.name} · ${plan.id} · ${CATEGORY_LABELS[plan.category]||plan.category} · ${plan.savedContext?.year||"2027"} · saved for ${plan.savedContext?.county||"Collier County"}${state.comparisonStale?" · recheck after context change":""}`));}
  if(!interactive && state.preparationDrafts)for(const [kind,text] of Object.entries(state.preparationDrafts)){wrap.append(node("h2","Prepared draft · "+(supportTasks().find(t=>t.id===kind)?.title||kind)),node("p",text,"printed-draft"));}
  wrap.append(helpLinks());return wrap;
}
function returnFromFinish() {const target=state.finishReturn || {stop:0,screen:{start:"goal"}};state.screen={...target.screen};goToStop(target.stop);}
function stop7(stage) {
  stage.append(stageHead(state.intake.goal === "learn" && !state.personalReview?"Your Medicare learning summary":"Your next steps","Keep what is useful, confirm the open questions, and decide what to do next."));
  const row=node("div",undefined,"next-actions"),task=supportTasks()[0];row.append(primary(task.action,()=>openPreparation(task.id)),secondary("Back",returnFromFinish),secondary("Print or save my summary",printMap));stage.append(row);
  if(state.activePreparation)stage.append(preparationWorkspace());
  const summary=node("div");summary.id="summary-live";summary.append(summaryContent(true));stage.append(summary);
  if(state.personalReview || state.intake.goal !== "learn") {const notes=localNotes("doctor","Add a doctor or office to check (optional)","Name and location; no ID numbers",240);notes.querySelector("textarea").addEventListener("input",()=>summary.replaceChildren(summaryContent(true)));stage.append(notes);}
  stage.append(node("p","Daylight explains available information and prepares drafts. It does not contact others, enroll you, or confirm eligibility, provider participation, or personal prices.","question-note"));
}
function buildPrintContent() { const wrap = node("div"); wrap.append(node("h1", "Your coverage, plain as day.", "print-h1"), node("p", "Daylight Medicare · " + new Date().toLocaleDateString("en-US"), "print-meta"), summaryContent(), node("p", "General information, not a personal recommendation or enrollment. Published-field ordering is not a personal-fit ranking. Unknown items above must be confirmed.", "print-disclaimer")); return wrap; }
function printMap() { const v = el("print-view"); v.replaceChildren(buildPrintContent()); let d = el("print-preview"); if (!d) { d = node("dialog", undefined, "print-preview"); d.id = "print-preview"; d.setAttribute("aria-label", "Printable coverage map"); document.body.append(d); } d.replaceChildren(); const row = node("div", undefined, "preview-actions"); row.append(secondary("Close preview", () => d.close()), primary("Print or save PDF", () => { v.replaceChildren(buildPrintContent()); window.print(); })); d.append(row, buildPrintContent()); d.showModal(); }

const ASK = {
  0: [["What can Daylight help with?", "The guide explains coverage roles, records your questions and can display published 2027 Collier County plan records when the plan service is available. Enrollment and personal fit still require verification."], ["What happens to my answers?", "Guide answers and medicine/doctor notes stay in this tab. Questions with an existing guide explanation are answered in this tab. Other submitted questions and recent conversation messages are sent to the local server and, when connected, its conversation service. Submitted chat may be logged. Tab notes are not attached automatically."]],
  1: [["What do the A and B letters mean?", "Part A is hospital insurance; Part B is medical insurance, including doctors and outpatient care. Check the card's effective dates to establish what is in place."], ["Is enrollment automatic?", "People already receiving Social Security or Railroad Retirement benefits are usually enrolled automatically at 65. Check the actual notice. Others generally apply through Social Security; special situations can differ."]],
  2: [["What should I ask the benefits office?", "Ask whether coverage is based on current active employment, whether it is a qualifying group plan, employer size, how Medicare coordinates with it, and the exact employment and health-coverage end dates. Ask separately about creditable drug coverage."], ["Why aren't you showing a Part B start date?", "A birthday and current work coverage do not establish when Part B actually starts. Social Security confirms the enrollment route and effective date. Unknown dates stay unknown."]],
  3: [["Does taking no medicines settle the drug-plan decision?", "No. Drug needs can change, and current creditable coverage and enrollment timing affect penalties. Ask your current insurer whether its drug coverage is creditable before changing it."], ["Does my list confirm drug coverage?", "No. The list is a checklist. Verify the exact medicine, strength, plan drug list, restrictions and pharmacy prices. Daylight does not establish personal drug coverage or cost from a name alone."]],
  4: [["Does a dental benefit mean all dental work is covered?", "No. Check the covered services, exclusions, yearly limits, costs and provider requirements for the exact plan. A benefit label is not confirmation for your treatment."], ["Can extras be separate from Medicare?", "Standalone dental and vision coverage exists. Those quotes are not included in this catalog; free local Medicare counseling can help identify what to compare."]],
  5: [["How will my priorities affect results?", "Published plan premiums and medical limits can affect numeric ordering. Doctor participation, travel rules, extras and personal medicine prices are not scored. Those remain verification tasks, even if they are your top priority."], ["When does the Medigap window begin?", "The federal age-65 six-month period depends on both age and having Part B. A birthday alone is insufficient. Special or state protections may also apply; verify rights before dropping other coverage."]],
  6: [["Is the first record the best plan for me?", "No. Records are in source order or ordered by explicit published fields. Eligibility, doctor participation, exact medicines and personal total cost have not been established."], ["What is a special needs plan?", "An Advantage plan restricted to people meeting particular criteria, such as certain Medicaid or clinical circumstances. Listing it does not determine anyone's eligibility."], ["Why might plan records be unavailable?", "The plan service may be disconnected, busy, or waiting for data validation. Retry or use official Medicare comparison. The guide will not substitute unverified records or mark that search complete."]],
  7: [["Who can help me take the next step?", "SHINE offers free, unbiased counseling in Florida at 1-800-963-5337. Medicare is available at 1-800-633-4227. Social Security handles Parts A and B enrollment. Links and phone numbers are included in your map."], ["What remains unresolved?", "The map identifies unanswered coverage facts, unverified doctors and medicines, missing dates and any failed plan search. Saved records are comparison candidates, not enrollment choices."]],
};
function askSource() { return [SOURCES.options, SOURCES.signup, "https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65", "https://www.medicare.gov/health-drug-plans/part-d", SOURCES.costs, SOURCES.medigap, SOURCES.compare, state.intake.county === "Collier County" ? SOURCES.shine : "https://www.shiphelp.org/"][state.journey.stop]; }
const GUIDE_TOPICS = {
  basics: {title: "What Medicare is", summary: "Medicare is federal health insurance. We’ll build the rest of the picture one piece at a time.", question: "What is Medicare?", aliases: ["Explain Medicare", "Medicare basics"], answer: "Medicare is health insurance from the federal government. It helps pay for health care. It is mainly for people 65 or older who meet the program’s eligibility rules. Some younger people qualify because of a disability, End-Stage Renal Disease, or ALS. You can learn the coverage pieces one at a time.", visual: "basics", source: "https://www.medicare.gov/basics/get-started-with-medicare"},
  routesintro: {title: "The two coverage routes", summary: "You can get Parts A and B through the federal program or through a private Medicare Advantage plan.", question: "What are the two ways to get Medicare?", aliases: ["Explain the two coverage routes"], answer: "Original Medicare is Parts A and B through the federal program. Medicare Advantage is a private plan approved by Medicare that provides Parts A and B. Both routes provide Medicare coverage, with different rules and costs. We can add the other coverage pieces after this distinction is clear.", visual: "routesintro", source: SOURCES.options},
  drugbasics: {title: "The piece for prescription medicines", summary: "Part D is Medicare coverage for prescription medicines. Your medicine list helps identify what to check.", question: "What does Part D do?", aliases: ["What is prescription coverage?"], answer: "Part D helps pay for prescription medicines. Each drug plan has a list of covered medicines and its own costs and rules. A medicine list is a starting point for checking those details; it does not establish personal coverage or pharmacy prices.", visual: "drugbasics", source: "https://www.medicare.gov/health-drug-plans/part-d"},
  options: {title: "How your options fit together", summary: "Start with hospital and medical care. Then compare the two ways to get your coverage.", question: "How do my Medicare options fit together?", aliases: ["Explain my options", "What are my Medicare options?", "Original Medicare vs Medicare Advantage", "How is Original Medicare different from Medicare Advantage?"], answer: "There are two main routes. Original Medicare is Parts A and B; you can add a separate drug plan and may be able to buy Medigap to help with your share of costs. Medicare Advantage provides A and B through a private plan, and most plans include drug coverage. Medigap goes with Original Medicare, not Medicare Advantage. You still pay the Part B premium with either route.", visual: "routes", source: SOURCES.options},
  parts: {title: "The two parts to start with", summary: "Part A is hospital insurance. Part B is medical insurance. Together, they are Original Medicare.", question: "What do Parts A and B cover?", aliases: ["What are A and B?", "Explain Parts A and B"], answer: "Part A: " + GLOSSARY["Part A"] + "\n\nPart B: " + GLOSSARY["Part B"] + "\n\n" + GLOSSARY["Original Medicare"], visual: "parts", source: SOURCES.options},
  parta: {title: "Part A: hospital care", summary: "Hospital insurance is one part of Medicare.", question: "What is Part A?", aliases: ["Explain Part A", "What does Part A cover?"], answer: "Part A is hospital insurance. It covers inpatient hospital care, skilled nursing facility care, hospice, and some home health care. Together, Part A and Part B are Original Medicare.", visual: "parts", source: SOURCES.options},
  partb: {title: "Part B: medical care", summary: "Medical insurance is one part of Medicare.", question: "What is Part B?", aliases: ["Explain Part B", "What does Part B cover?"], answer: "Part B is medical insurance. It covers doctors, outpatient care, tests, equipment, and many preventive services. Together, Part A and Part B are Original Medicare.", visual: "parts", source: SOURCES.options},
  original: {title: "Original Medicare", summary: "Parts A and B are the foundation. Other coverage can help with drugs and some costs.", question: "What is Original Medicare?", aliases: ["Explain Original Medicare"], answer: GLOSSARY["Original Medicare"] + " You can add separate drug coverage (Part D) and may be able to buy a Medigap policy for certain A/B costs.", visual: "routes", source: SOURCES.options},
  advantage: {title: "Medicare Advantage", summary: "A private plan provides Parts A and B. Most plans also include drug coverage.", question: "What is Medicare Advantage?", aliases: ["What is Part C?", "Explain Medicare Advantage"], answer: GLOSSARY["Medicare Advantage"] + " You still pay the Part B premium. Check each plan's doctors, drug coverage, costs, and rules.", visual: "routes", source: SOURCES.options},
  drugs: {title: "Where prescription coverage fits", summary: "Drug coverage is called Part D. Where it sits depends on the coverage route.", question: "How do I get prescription drug coverage?", aliases: ["What is Part D?", "Explain Part D", "What is drug coverage?", "How does prescription coverage work?"], answer: "Part D helps pay for prescription medicines. With Original Medicare, you can join a separate Medicare drug plan. Most Medicare Advantage plans include Part D. Check the exact drug list, restrictions, pharmacy, and costs before relying on coverage for a particular medicine.", visual: "drugs", source: "https://www.medicare.gov/health-drug-plans/part-d"},
  medigap: {title: "What a supplement does", summary: "Medigap can help pay your share of certain Original Medicare costs.", question: "What is Medigap?", aliases: ["What is a supplement?", "What is Medicare Supplement Insurance?", "Explain Medigap"], answer: GLOSSARY.Medigap + " It works with Original Medicare, not Medicare Advantage. Drug coverage is separate. Check your enrollment rights before changing existing coverage.", visual: "routes", source: SOURCES.medigap},
  extras: {title: "Dental, vision, and hearing", summary: "Routine services need a separate check. Benefits can differ from plan to plan.", question: "How do dental, vision, and hearing benefits work?", aliases: ["Is dental covered?", "Is vision covered?", "Is hearing covered?"], answer: "Original Medicare generally does not cover routine dental, vision, and hearing services. Some Medicare Advantage plans include benefits, with conditions and limits. Check covered services, costs, yearly limits, and providers for the exact plan.", visual: "extras", source: SOURCES.options},
  costs: {title: "Monthly cost and care costs", summary: "A monthly premium and what you pay when you use care are different costs.", question: "What costs should I compare?", aliases: ["What is a premium?", "What is a deductible?", "Explain Medicare costs"], answer: "A premium is the amount you pay each month for coverage. A deductible is an amount you pay before coverage pays its share under the benefit's rules. Copays and coinsurance are costs when you use care. A plan's premium alone is not your total cost.", visual: "costtypes", source: SOURCES.costs},
  checks: {title: "What to check for each plan", summary: "A plan list is the starting point. Check doctors, medicines, and costs for your situation.", question: "What should I check before choosing a plan?", aliases: ["Is the first plan best for me?", "How do I compare plans?"], answer: ASK[6][0][1] + " Compare the exact plan's providers, drug coverage, costs, and enrollment requirements before making a decision.", visual: "checks", source: SOURCES.compare},
  dates: {title: "Dates depend on your situation", summary: "Your birth date, actual coverage, and job insurance can affect which dates need checking.", question: "Why do these dates matter?", aliases: ["Explain the timeline"], answer: ASK[2][1][1] + " The timeline uses the facts entered in this tab. An unknown date stays an open check; special enrollment rights may need separate confirmation.", visual: "dates", source: SOURCES.signup},
  next: {title: "Turn your map into next steps", summary: "Keep the facts you entered and work through the checks that remain open.", question: "How do I use my checklist?", aliases: ["What do I do with my map?"], answer: "Use the checklist to confirm open coverage questions, dates, doctor participation, and medicine costs. It includes official tools and help contacts. Saving a plan for comparison does not enroll you or establish that it fits your needs.", visual: "checks", source: SOURCES.compare},
};
const normalizeGuideQuestion = text => String(text).toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9]+/g, " ").trim();
function findGuideTopic(message) {
  const q = normalizeGuideQuestion(message);
  for (const [id, topic] of Object.entries(GUIDE_TOPICS)) if ([topic.question, ...topic.aliases].some(alias => normalizeGuideQuestion(alias) === q)) return {id, ...topic};
  const entry = ASK[state.journey.stop].find(([question]) => normalizeGuideQuestion(question) === q);
  return entry ? stepGuideQuestion(entry[0], entry[1]) : null;
}
let askReturnFocus = null, askReturnScroll = {top: 0, left: 0}, askCurrentExchange = null;
const askContextKey = () => `${state.journey.stop}:${lessonFor().id}`;
function setAskStatus(text, quiet = false) { const status = el("ask-status"); status.textContent = text; if (quiet) status.classList.add("sr-only"); else status.classList.remove("sr-only"); }
function updateChatAvailability() {
  el("ask-availability").textContent = state.connection === "checking" ? "Guide explanations are ready. Checking live answers…" : state.live ? "AI requests are enabled. Transfer requires permission; this service does not log chat." : "Guide explanations work here. Other live replies are unavailable right now.";
}
function syncAskLayout() {
  const open=!el("ask-panel").hidden;el("ask-panel").setAttribute("aria-modal","true");
  [el("main"),el("journey-map"),document.querySelector(".site-header"),document.querySelector(".site-footer"),document.querySelector(".skip-link")].forEach(n=>{if(n)n.inert=open;});
  const viewport=window.visualViewport,available=viewport?.height || window.innerHeight;
  if(open && Number.isFinite(available)) {
    const phone=matchMedia("(max-width: 760px)").matches;
    const height=Math.min(phone?736:710,available-32);
    el("ask-panel").style.height=`${height}px`;
    const reference=document.querySelector(".flow-picture,.guide-panel");const anchor=reference?.getBoundingClientRect().top || (available-height)/2;
    el("ask-panel").style.top=`${(viewport?.offsetTop || 0)+(phone?available-height-12:Math.max(16,Math.min(anchor,available-height-16)))}px`;
  }
}
function revealAskExchange(exchange = askCurrentExchange, focus = true) {
  if (!exchange || el("ask-panel").hidden) return;
  requestAnimationFrame(() => {
    if (el("ask-panel").hidden || !exchange.isConnected) return;
    const reading = el("ask-reading");
    reading.scrollTop += exchange.querySelector("h3").getBoundingClientRect().top - reading.getBoundingClientRect().top - 24;
    if (focus) exchange.querySelector("h3").focus({preventScroll: true});
  });
}
function openAsk() {
  if(state.pictureTopic){state.pictureTopic=null;renderStop(state.journey.stop);}
  const opening = el("ask-panel").hidden;
  if (opening) { askReturnFocus = document.activeElement; askReturnScroll = {top: window.scrollY || 0, left: window.scrollX || 0}; }
  el("ask-panel").hidden = false; el("ask-scrim").hidden = false; document.body.classList.add("ask-active"); syncAskLayout();
  if (opening) el("ask-thread").hidden = !!askCurrentExchange && askCurrentExchange.dataset.context !== askContextKey();
  renderAskCanned(); updateChatAvailability();
  if (opening) { if (askCurrentExchange && !el("ask-thread").hidden) revealAskExchange(); else { el("ask-reading").scrollTop = 0; el("ask-title").focus({preventScroll: true}); } }
}
function closeAsk(focus = true) {
  const wasOpen = !el("ask-panel").hidden;
  el("ask-panel").hidden = true; el("ask-scrim").hidden = true; document.body.classList.remove("ask-active"); syncAskLayout();
  if (focus && wasOpen) {
    window.scrollTo({...askReturnScroll, behavior: "instant"});
    (askReturnFocus?.isConnected ? askReturnFocus : document.querySelector("#stage .ask-bottom button") || el("ask-open")).focus({preventScroll: true});
  }
}
function addGuideAnswer(topic) {
  const msg = addAsk("daylight", topic.answer, topic.source, topic.sourceLabel); msg.dataset.guideTopic = topic.id || "guide";
  // A short, relevant picture follows the explanation; it never displaces the question.
  if (["parts", "routesintro", "options", "drugs", "costs"].includes(topic.id)) msg.append(guidePicture(topic.visual));
  renderAskCanned(); revealAskExchange(); return msg;
}
function rememberChat(question, answer) { state.history.push({role: "user", content: question}, {role: "assistant", content: answer}); state.history = state.history.slice(-8); }
function answerGuideTopic(id) {
  const topic = GUIDE_TOPICS[id]; if (!topic || state.busy) return;
  openAsk(); addAsk("you", topic.question); addGuideAnswer({id, ...topic}); rememberChat(topic.question, topic.answer);
}
function stepGuideQuestion(question, answer) {
  const local = state.journey.stop === 0;
  return {id: "step-question", question, answer, source: local ? null : askSource(), visual: null, sourceLabel: local ? question === "What happens to my answers?" ? "Daylight · about your answers" : "Daylight · about this guide" : null};
}
function renderAskCanned() {
  const lesson = lessonFor(), box = el("ask-canned"); el("ask-context").textContent = el("landing").hidden ? document.querySelector("#stage h1")?.textContent || lesson.title : "Your Medicare questions";
  const readingAnswer = state.chatTurns && !el("ask-thread").hidden;
  el("ask-intro").hidden = !!readingAnswer;
  box.replaceChildren(node("h3", readingAnswer ? "You can also ask" : "Questions about this step"));
  const currentQuestion = readingAnswer ? askCurrentExchange?.dataset.question || "" : "", current = normalizeGuideQuestion(currentQuestion);
  const candidates = [...lesson.topics.filter(id => id !== "basics" || lesson.id === "basics").map(id => ({id, ...GUIDE_TOPICS[id]})), ...ASK[state.journey.stop].map(([q, a]) => stepGuideQuestion(q, a)), {id: "basics", ...GUIDE_TOPICS.basics}];
  const seen = new Set([current]); let shown = 0;
  for (const topic of candidates) {
    const key = normalizeGuideQuestion(topic.question);
    if (seen.has(key) || findGuideTopic(currentQuestion)?.id === topic.id && topic.id !== "step-question") continue;
    seen.add(key);
    const button = secondary(topic.question, () => { if (state.busy) return; addAsk("you", topic.question); addGuideAnswer(topic); rememberChat(topic.question, topic.answer); });
    button.className = "ask-canned-q"; button.disabled = state.busy; box.append(button);
    if (++shown === 2) break;
  }
  const earlier = readingAnswer ? state.chatTurns - 1 : state.chatTurns;
  if (earlier > 0) box.append(secondary(`Read earlier questions (${earlier})`, () => { el("ask-thread").hidden = false; renderAskCanned(); revealAskExchange(readingAnswer ? el("ask-thread").children[0] : askCurrentExchange); }));
}
function addAsk(who, text, source, sourceLabel) {
  const thread = el("ask-thread");
  if (who === "you") {
    state.chatTurns = (state.chatTurns || 0) + 1;
    const exchange = node("section", undefined, "ask-exchange"), question = node("h3", text, "ask-question"); question.id = `ask-question-${state.chatTurns}`; question.tabIndex = -1;
    exchange.setAttribute("aria-labelledby", question.id); exchange.dataset.question = text; exchange.dataset.context = askContextKey(); exchange.append(question); thread.append(exchange); thread.hidden = false; askCurrentExchange = exchange;
    setAskStatus(""); el("ask-intro").hidden = true; revealAskExchange(); return exchange;
  }
  const msg = node("div", undefined, "ask-msg ask-daylight");
  msg.append(node("p", sourceLabel || (source ? "Daylight · guide explanation" : "Daylight · live AI reply"), "ask-who"), node("p", text, "ask-text"));
  if (source) msg.append(link("Read the official source", source));
  (askCurrentExchange || thread).append(msg); setAskStatus("Daylight’s answer is ready below your question.", true); revealAskExchange(askCurrentExchange, document.activeElement !== el("ask-input")); return msg;
}
async function askTyped(message) {
  if (window.DaylightFlow?.askTyped) return window.DaylightFlow.askTyped(message);
  if (state.busy || !message?.trim()) return; const conversationId = state.conversationId; state.busy = true; el("ask-send").disabled = true; addAsk("you", message); renderAskCanned();
  try {
    const topic = findGuideTopic(message); if (topic) { addGuideAnswer(topic); rememberChat(message, topic.answer); return; }
    setAskStatus("Checking live answers…"); await checkConnection(); updateChatAvailability();
    if (conversationId !== state.conversationId) return;
    if (!state.live) throw new Error("Live answers are unavailable right now. The guide questions still work. Your question has not been sent to the conversation service.");
    const result = await requestJSON("/api/live-chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message, history: state.history.slice(-8), conversation_id: conversationId})});
    if (conversationId !== state.conversationId) return;
    addAsk("daylight", [result.text || "The service returned no explanation. Try a more specific question.", result.question].filter(Boolean).join("\n\n")); rememberChat(message, result.text || "");
  } catch (e) {
    if (conversationId === state.conversationId) {
      const msg = addAsk("daylight", ["AbortError", "TimeoutError"].includes(e.name) ? "The conversation service took too long. You can retry or use a guide question below." : e.message);
      msg.querySelector(".ask-who").textContent = "Daylight · reply unavailable";
      msg.append(secondary("Retry this question", () => askTyped(message))); setAskStatus("Live reply unavailable. Your question is shown above.");
    }
  } finally { if (conversationId === state.conversationId) { state.busy = false; el("ask-send").disabled = false; renderAskCanned(); } }
}
el("get-started").addEventListener("click", () => beginJourney());
el("fast-start").addEventListener("click", () => beginJourney(true));
el("restart").addEventListener("click", requestStartOver);
el("ask-open").addEventListener("click", openAsk);
el("ask-close").addEventListener("click", () => closeAsk());
el("ask-scrim").addEventListener("click", () => closeAsk());
el("ask-form").addEventListener("submit", e => { e.preventDefault(); const message = el("ask-input").value.trim(); if (message && !state.busy) { el("ask-input").value = ""; askTyped(message); } });
el("ask-input").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); el("ask-form").requestSubmit(); } });
window.addEventListener?.("resize", syncAskLayout);
window.visualViewport?.addEventListener("resize", syncAskLayout);
window.visualViewport?.addEventListener("scroll", syncAskLayout);
document.addEventListener("keydown", e => {
  const panel = el("ask-panel"); if (panel.hidden || document.querySelector("dialog[open]")) return;
  if (e.key === "Escape") { e.preventDefault(); closeAsk(); return; }
  if (e.key !== "Tab") return;
  const controls = [...panel.querySelectorAll("button:not(:disabled),a[href],textarea,input,select,[tabindex='0']")].filter(n => n.getClientRects().length);
  const first = controls[0], last = controls.at(-1);
  if (e.shiftKey && (document.activeElement === first || document.activeElement === el("ask-title"))) { e.preventDefault(); last?.focus(); }
  else if ((!e.shiftKey && document.activeElement === last) || !panel.contains(document.activeElement)) { e.preventDefault(); first?.focus(); }
});
el("about-answers").addEventListener("toggle", () => document.body.classList.toggle("privacy-expanded", el("about-answers").open));
document.querySelector(".skip-link").addEventListener("click", e => { e.preventDefault(); (el("stage").hidden ? el("landing-title") : el("stage")).focus(); });
checkConnection();
showLanding();
