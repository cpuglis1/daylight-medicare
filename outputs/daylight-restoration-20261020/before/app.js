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
  "Medicare Advantage": "Part C: a private plan approved by Medicare that provides Parts A and B. Many include drugs and some extras. Networks, cost sharing and covered medical spending limits vary.",
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
  wrap.append(markup("p", "Medigap policies come in standardized lettered plans, like Plan G or Plan N. Every company must offer the same benefits for the same letter, so a Plan G is a Plan G wherever you buy it.", "v8-lead"));
  const grid = node("div", undefined, "v8-grid");
  for (const [l, n] of [["A", "Basic benefits"], ["G", "Covers nearly all gaps except the Part B deductible"], ["N", "Lower premium; small copays for some visits"], ["K / L", "Lower premium; you pay a share up to a yearly limit"]]) grid.append(markup("div", `<span class='v8-letter'>Plan ${l}</span><span>${n}</span>`, "v8-card"));
  wrap.append(grid, node("p", "Prices aren't available in Daylight yet. Compare the lettered benefits, then get quotes from free SHINE counseling or several companies.", "v8-note"));
  return visBox(wrap, "Benefits are standardized by letter. Prices are not available here yet.");
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
  const wrap = node("div", undefined, "choices");
  for (const [value, label] of options) {
    const b = node("button", label, "choice" + (opts.multi ? " multi" : ""));
    b.type = "button";
    b.setAttribute("aria-pressed", String(opts.multi ? (selected || []).includes(value) : selected === value));
    b.addEventListener("click", () => onPick(value, b));
    wrap.append(b);
  }
  return wrap;
}
function primary(label, onClick) { const b = node("button", label, "primary-button"); b.type = "button"; b.addEventListener("click", onClick); return b; }


/* Session-only answers. Only an explicitly submitted chat question leaves the tab. */
const GOALS = {learn: "Understand my choices", review: "Review my current coverage", job: "Prepare for job coverage ending", compare: "Compare published plans"};
const COVERAGE = {original: "Original Medicare only", supplement: "Original Medicare + Medigap", advantage: "Medicare Advantage", employer: "Employer, retiree, VA or other coverage", unsure: "Not sure yet"};
const STOP_NAMES = ["Start", "Medicare status", "Your coverage", "Medicines", "Extras", "Your priorities", "Your plans", "Next steps"];
const STATUS_WORD = {done: "answered", skipped: "not answered", blocked: "needs attention", locked: "not reached", current: "you are here", visited: "viewed"};
const CATEGORY_LABELS = {all: "All plan types", "MA-PD": "Advantage with drugs", MA: "Advantage without drugs", PDP: "Separate drug plans", SNP: "Special needs plans"};
function freshIntake() { return {priorities: [], priorityOrder: [], extras: [], medicines: "", doctor: "", leaning: "unsure"}; }
const state = {intake: freshIntake(), journey: {stop: 0, reached: 0, visited: new Set(), finished: new Set()}, screen: {}, quick: false,
  conversationId: crypto.randomUUID(), history: [], busy: false, controller: null, connection: "checking", live: false,
  plansLoaded: false, plansError: null, catalog: null, category: "all", sort: null, selected: new Map(), comparison: null, compareError: null, compareBusy: false, plansLimit: 6, planQuery: "", requestId: 0};
const person = () => state.intake.recipient === "someone" ? {you: "they", your: "their", title: "Their"} : {you: "you", your: "your", title: "Your"};
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const reviewMode = () => state.intake.medicare === "yes_ab";
const decidingPartB = () => state.intake.medicare && !reviewMode();
const isPhone = () => matchMedia("(max-width: 860px)").matches;
const announce = text => { el("sr-live").textContent = text; };
function addMonths(my, count) { const n = my.year * 12 + my.month - 1 + count; return {year: Math.floor(n / 12), month: ((n % 12) + 12) % 12 + 1}; }
const monthNumber = my => my.year * 12 + my.month - 1;
const fmtMY = my => `${MONTHS[my.month - 1]} ${my.year}`;
function parseMonth(value) { const m = /^(\d{4})-(\d{2})$/.exec(value || ""); return m && +m[2] >= 1 && +m[2] <= 12 && +m[1] >= 1900 && +m[1] <= 2150 ? {year: +m[1], month: +m[2]} : null; }
function computeDates(i = state.intake, today = new Date()) {
  const now = {year: today.getFullYear(), month: today.getMonth() + 1};
  const turn65 = i.birthMonth && i.birthYear ? {month: +i.birthMonth, year: +i.birthYear} : null;
  const known = !!turn65 && ["yes", "no"].includes(i.birthdayFirst);
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
function actions(stage, label, onNext, enabled = true, onBack) { const row = node("div", undefined, "continue-bar flow-actions"); if (onBack) row.append(secondary("Back", onBack)); const b = primary(label, onNext); b.disabled = !enabled; row.append(b); stage.append(row); }
function nextScreen(key, value) { state.screen[key] = value; renderStop(state.journey.stop, "top"); }
function pick(field, value, invalidate = false) { const previous = state.intake[field]; state.intake[field] = value;
  if (field === "medicare" && previous !== value) { delete state.intake.partBStart; delete state.intake.currentCoverage; state.intake.coverageReviewed = false; state.intake.timingReviewed = false; state.screen.coverage = "context"; delete state.dateReturn; }
  if (field === "goal" && previous !== value) { delete state.intake.jobGoal; delete state.dateReturn; state.screen.coverage = "context"; state.intake.coverageReviewed = false; if (value !== "compare") state.quick = false; }
  if (field === "job" && previous !== value) { for (const key of ["jobGoal", "employerSize", "employmentEnd", "coverageEnd"]) delete state.intake[key]; }
  if (field === "topPriority") state.intake.priorityOrder = [value, ...state.intake.priorities.filter(k => k !== value)]; if (invalidate) invalidatePlans(); renderStop(state.journey.stop, "feedback:" + field); }
function invalidatePlans(clearSelections = false) { state.requestId++; state.controller?.abort(); state.plansLoaded = false; state.plansError = null; state.catalog = null; state.comparison = null; state.compareError = null; if (clearSelections) state.selected.clear(); }
function answeredStop(n) { const i = state.intake; return [!!i.recipient && !!i.goal && !!i.zip && !!i.county,
  !!i.timingReviewed, !!i.coverageReviewed, !!i.drugsReviewed, !!i.extrasAnswered, !!i.prioritiesAnswered, state.plansLoaded, state.journey.visited.has(7)][n]; }
function unresolvedStop(n) { const i = state.intake; return (n === 0 && i.county === "unsure") || (n === 1 && (i.medicare === "unsure" || (i.medicare === "no" && i.social === "unsure"))) || (n === 2 && ((!reviewMode() && i.job === "unsure") || i.currentCoverage === "unsure")) || (n === 3 && i.drugs === "unsure") || (n === 4 && i.extrasUnsure); }
function journeyStatus(n) { if (n === 6 && state.plansError) return "blocked"; if (unresolvedStop(n)) return "blocked"; if (n === state.journey.stop) return "current"; if (n > state.journey.reached) return "locked"; if (n === 7 && state.journey.visited.has(7)) return "visited"; if (answeredStop(n)) return "done"; return state.journey.visited.has(n) ? "visited" : "skipped"; }
function renderJourneyMap() {
  const nav = el("journey-map"), strip = node("ol", undefined, "jmap-strip"); nav.replaceChildren();
  for (let n = 0; n < STOP_NAMES.length; n++) { const st = journeyStatus(n), li = node("li", undefined, `jmap-stop jmap-${st}${n === state.journey.stop ? " jmap-active" : ""}`), b = node("button", undefined, "jmap-btn"); b.type = "button"; b.disabled = st === "locked"; b.setAttribute("aria-current", n === state.journey.stop ? "step" : "false"); b.setAttribute("aria-label", `${n ? `Step ${n}` : "Start"}: ${STOP_NAMES[n]} (${STATUS_WORD[st]})`); b.title = STATUS_WORD[st]; b.append(node("span", st === "done" ? "✓" : st === "blocked" ? "!" : n === 0 ? "☀" : String(n), "jmap-num"), node("span", STOP_NAMES[n], "jmap-name")); b.addEventListener("click", () => goToStop(n)); li.append(b); strip.append(li); }
  const current = journeyStatus(state.journey.stop); nav.append(node("p", `${state.journey.stop ? `Step ${state.journey.stop} of 7` : "Getting started"} · ${STOP_NAMES[state.journey.stop]}${current === "blocked" ? " · needs attention" : ""}`, "jmap-count"), strip);
}
function goToStop(n) { if (n > state.journey.reached) return; if (n !== 6) { state.requestId++; state.controller?.abort(); } state.journey.stop = n; state.journey.visited.add(n); renderStop(n, "top"); }
function advance(n = Math.min(state.journey.stop + 1, 7)) { state.journey.finished.add(state.journey.stop); state.journey.reached = Math.max(state.journey.reached, n); goToStop(n); }
function renderStop(n, focus = "none") {
  const disclosureKey = d => (d.closest("[data-plan-id]")?.dataset.planId || "") + ":" + d.firstElementChild?.textContent; const previous = state.renderedStop; state.openDetails ||= {}; if (previous !== undefined) state.openDetails[previous] = new Set([...el("stage").querySelectorAll("details[open]")].map(disclosureKey));
  state.journey.stop = n; state.journey.visited.add(n); renderJourneyMap(); const stage = el("stage"); stage.replaceChildren();
  if (n > 0) stage.append(secondary("Edit goal or location", () => { state.screen.start = "location"; goToStop(0); }));
  [stop0, stop1, stop2, stop3, stop4, stop5, stop6, stop7][n](stage); stage.append(askBottom()); for (const d of stage.querySelectorAll("details")) if (state.openDetails[n]?.has(disclosureKey(d))) d.open = true; state.renderedStop = n; if (!el("ask-panel").hidden) renderAskCanned();
  requestAnimationFrame(() => { if (focus.startsWith("feedback")) { const field = focus.split(":")[1]; const target = (field ? stage.querySelector(`[data-feedback="${field}"]`) : null) || stage.querySelector(".answer-feedback") || stage.querySelector(".reveal-target"); if (target) { target.focus({preventScroll: true}); target.scrollIntoView({block: "nearest", behavior: "instant"}); } } else if (focus === "top") { stage.focus({preventScroll: true}); window.scrollTo({top: 0, behavior: "instant"}); el("journey-map").querySelector('[aria-current="step"]')?.scrollIntoView({block: "nearest", inline: "center"}); } });
  announce(`${n ? `Step ${n} of 7` : "Getting started"}: ${STOP_NAMES[n]}.`);
}
function askBottom() { const box = node("div", undefined, "ask-bottom"); box.append(secondary("Have a question? Ask Daylight", openAsk)); return box; }
function showLanding() { document.body.classList.add("landing-mode"); el("landing").hidden = false; ["stage", "journey-map", "ask-open", "restart"].forEach(id => el(id).hidden = true); document.querySelector(".header-note").hidden = true; closeAsk(false); window.scrollTo({top: 0, behavior: "instant"}); requestAnimationFrame(() => el("get-started").focus({preventScroll: true})); }
function beginJourney(quick = false) { state.quick = quick; if (quick) state.intake.goal = "compare"; document.body.classList.remove("landing-mode"); el("landing").hidden = true; ["stage", "journey-map", "ask-open", "restart"].forEach(id => el(id).hidden = false); renderStop(0, "top"); }
function startOver() { state.controller?.abort(); state.requestId++; Object.assign(state, {intake: freshIntake(), journey: {stop: 0, reached: 0, visited: new Set(), finished: new Set()}, screen: {}, quick: false, catalog: null, plansLoaded: false, plansError: null, category: "all", sort: null, selected: new Map(), comparison: null, compareError: null, compareBusy: false, plansLimit: 6, planQuery: "", openDetails: {}, renderedStop: undefined, dateReturn: null, conversationId: crypto.randomUUID(), history: [], busy: false}); el("ask-thread").replaceChildren(); el("ask-input").value = ""; showLanding(); }

function stop0(stage) {
  const i = state.intake, page = state.screen.start || "recipient";
  stage.append(stageHead("Let's start with your situation.", "2027 plan comparisons cover Collier County, Florida. You can use the guide elsewhere too."));
  if (page === "recipient") { const q = questionBlock("Who are we looking at Medicare for?"); q.append(renderChips([["self", "Me"], ["someone", "Someone I'm helping"]], i.recipient, v => pick("recipient", v))); stage.append(q); if (i.recipient) stage.append(feedback(i.recipient === "self" ? "We'll build the guide around your situation." : "We'll refer to the person you're helping. Use their coverage and location.")); actions(stage, state.quick && i.goal === "compare" ? "Continue to location →" : "Continue to your goal →", () => nextScreen("start", state.quick && i.goal === "compare" ? "location" : "goal"), !!i.recipient); return; }
  if (page === "goal") { const q = questionBlock("What would help most today?", "This decides which questions we ask next."); q.append(renderChips(Object.entries(GOALS), i.goal, v => pick("goal", v))); stage.append(q); if (i.goal) stage.append(feedback({learn: "We'll explain the two coverage routes and connect each question to your situation.", review: "We'll ask about existing coverage before discussing any gaps or changes.", job: "We'll build a work-coverage transition checklist before looking at replacement coverage.", compare: "We'll open the catalog after checking the service area. Earlier questions stay optional and won't be marked complete."}[i.goal])); actions(stage, "Continue to location →", () => nextScreen("start", "location"), !!i.goal, () => nextScreen("start", "recipient")); return; }
  stage.append(renderLocation(), secondary("Change my goal", () => nextScreen("start", "goal")));
  const valid = /^\d{5}$/.test(i.zip || "") && !!i.county;
  if (valid) {
    stage.append(feedback(i.county === "Collier County" ? "We have a Collier County catalog for 2027. Published records still need to be available from the plan service before we can show them." : i.county === "unsure" ? "The county is unresolved. We can continue with general guidance; we won't assume you live outside Collier County or show local plans until you confirm." : "We don't have local plan records for that county. You can continue with general guidance and use Medicare.gov for local comparisons."));
    if (i.county === "unsure") stage.append(link("Check location with Medicare.gov", SOURCES.compare)); if (i.county === "outside") stage.append(link("Compare plans in your area on Medicare.gov", SOURCES.compare));
  }
  const direct = i.goal === "compare" && i.county === "Collier County";
  actions(stage, direct ? "Browse published plans →" : "Continue to current Medicare status →", () => { if (direct) { state.journey.reached = 7; advance(6); } else advance(1); }, valid, () => nextScreen("start", state.quick && i.goal === "compare" ? "recipient" : "goal"));
}
function renderLocation() {
  const q = questionBlock("Where does the person receiving coverage live?", "ZIP codes can cross county boundaries. Confirm the county separately.");
  const label = node("label", "ZIP code", "field-label"), input = node("input"); input.id = "zip-in"; label.htmlFor = input.id; Object.assign(input, {type: "text", inputMode: "numeric", maxLength: 5, placeholder: "e.g. 34102", className: "zip-input", value: state.intake.zip || ""});
  const err = node("p", "", "field-error"); err.setAttribute("role", "alert"); input.addEventListener("input", () => { state.intake.zip = input.value.trim(); if (state.intake.zip !== state.intake.checkedZip) { state.intake.county = null; invalidatePlans(true); q.querySelector(".county-choices")?.setAttribute("hidden", ""); const next = el("stage").querySelector(".flow-actions .primary-button"); if (next) next.disabled = true; const payoff = el("stage").querySelector(".answer-feedback"); if (payoff) payoff.textContent = "Check the updated ZIP and confirm its county before continuing."; } });
  q.append(label, input, primary("Check location →", () => { if (!/^\d{5}$/.test(input.value.trim())) { err.textContent = "Enter a 5-digit ZIP code."; input.focus(); return; } state.intake.zip = input.value.trim(); state.intake.checkedZip = state.intake.zip; state.intake.county = null; invalidatePlans(true); renderStop(0, "feedback"); }), err);
  if (/^\d{5}$/.test(state.intake.zip || "") && state.intake.checkedZip === state.intake.zip) { const county = node("div", undefined, "county-choices reveal-target"); county.tabIndex = -1; county.append(node("h2", `Is ZIP ${state.intake.zip} in Collier County, Florida?`, "question-prompt"), renderChips([["Collier County", "Yes, Collier County"], ["outside", "A different county"], ["unsure", "I'm not sure"]], state.intake.county, v => { state.intake.county = v; invalidatePlans(true); renderStop(0, "feedback"); })); q.append(county); }
  return q;
}
function monthPicker(title, monthKey, yearKey) {
  const card = node("div", undefined, "card"), row = node("div", undefined, "month-row"); card.append(node("h2", title, "question-prompt"));
  const m = node("select"), y = node("input"); m.id = monthKey; m.setAttribute("aria-label", "Month of 65th birthday"); m.append(new Option("Month…", "")); MONTHS.forEach((mo, n) => m.append(new Option(mo, String(n + 1)))); m.value = String(state.intake[monthKey] || "");
  Object.assign(y, {type: "number", min: "1900", max: "2150", placeholder: "Year, e.g. 2027", value: state.intake[yearKey] || ""}); y.setAttribute("aria-label", "Year of 65th birthday");
  const err = node("p", "", "field-error"); err.setAttribute("role", "alert");
  const save = () => { if (!m.value || !y.value || !Number.isInteger(+y.value) || +y.value < 1900 || +y.value > 2150) { err.textContent = "Choose a month and enter a year from 1900 to 2150, or choose 'I don't know the date'."; return false; } state.intake[monthKey] = +m.value; state.intake[yearKey] = +y.value; state.intake.birthSkipped = false; return true; };
  row.append(m, y); card.append(row, err); return {card, save};
}
function stop1(stage) {
  const i = state.intake, {you, your, title} = person(), page = state.screen.timing || "coverage";
  stage.append(stageHead(page === "coverage" ? `${title} Medicare status.` : "How will enrollment start?", page === "coverage" ? "What is already in place will determine the next question." : `${cap(you)} said Medicare is not in place yet. Receiving benefits can affect whether enrollment is automatic.`));
  if (page === "coverage") {
    const q = questionBlock(`What Medicare coverage do ${you} have?`, "Part A is hospital insurance. Part B is medical insurance for doctors and outpatient care. Look for the letters and effective dates on the Medicare card; no numbers or documents are needed.");
    q.append(renderChips([["yes_ab", "Both Part A and Part B"], ["only_a", "Part A only"], ["no", "Not enrolled in Medicare yet"], ["unsure", "I'm not sure what the card shows"]], i.medicare, v => pick("medicare", v, true))); stage.append(q);
    if (i.medicare) stage.append(feedback({yes_ab: `${cap(you)} already have A and B. Next we'll ask how that coverage is arranged, rather than assume anything is missing.`, only_a: `${cap(you)} have Part A and haven't added Part B. The next question is about current job coverage, because that affects what to do next.`, no: `We'll ask whether ${you} receive Social Security benefits, then check what affects enrollment timing.`, unsure: `Keep this marked unknown. Check the A and B lines and effective dates on the card, or ask Social Security. We'll make that an open task rather than assume enrollment.`}[i.medicare]));
    actions(stage, i.medicare === "no" ? "Continue to Social Security benefits →" : "Continue to your coverage situation →", () => { if (i.medicare === "no") nextScreen("timing", "social"); else { i.timingReviewed = true; advance(2); } }, !!i.medicare, () => goToStop(0)); return;
  }
  const q = questionBlock(`Do ${you} already receive Social Security or Railroad Retirement benefits?`, "This helps establish whether enrollment may be automatic. It does not establish a coverage start date."); q.append(renderChips([["yes", "Yes"], ["no", "No"], ["unsure", "I'm not sure"]], i.social, v => pick("social", v))); stage.append(q);
  if (i.social) stage.append(feedback(i.social === "yes" ? "Enrollment is usually automatic at 65 for people already receiving these benefits. Check the actual Medicare notice or card, especially if delaying Part B or living outside the usual enrollment area." : i.social === "no" ? "People not receiving these benefits generally apply through Social Security. We'll establish current coverage before discussing dates." : "Whether enrollment is automatic remains unresolved. Check with Social Security; the guide will keep this question open."));
  actions(stage, "Continue to current health coverage →", () => { i.timingReviewed = true; advance(2); }, !!i.social, () => nextScreen("timing", "coverage"));
}

function coverageOverview() {
  const box = node("div", undefined, "card"); box.append(node("h2", "The framework for the next questions"), node("p", "Part A covers hospital care; Part B covers medical care. Together they form Original Medicare."), node("p", "There are two ways to arrange coverage: keep Original Medicare and consider separate drug coverage (Part D) and a supplement (Medigap), or receive A and B through a private Medicare Advantage plan. Many Advantage plans include Part D."), node("p", "We will ask about medicines, extras and priorities before comparing those routes. These are concepts, not a statement that you have every part or need every add-on.")); return box;
}
function stop2(stage) {
  const i = state.intake, p = person(), page = state.screen.coverage || "context";
  if (reviewMode() && page !== "timing" && !["jobContext", "jobGoal", "transition"].includes(page)) {
    stage.append(stageHead("Build on the coverage already in place.", "Having A and B doesn't tell us what other coverage you have. We won't assume there are gaps."));
    if (page === "context") {
      const q = questionBlock(`How do ${p.you} get coverage today?`); q.append(renderChips(Object.entries(COVERAGE), i.currentCoverage, v => pick("currentCoverage", v, true))); stage.append(q);
      if (i.currentCoverage) stage.append(feedback({original: "We'll consider separate drug and supplemental coverage without assuming either is required.", supplement: "Your existing supplement may already address some costs. Compare its benefits and renewal premium before replacing it.", advantage: "We'll review an existing Advantage arrangement. Changing a plan and moving to Original Medicare with a supplement are different decisions.", employer: "Check how that coverage coordinates with Medicare before replacing it. Employer, retiree and military coverage have different rules.", unsure: "We'll keep the current arrangement unresolved. A plan card or benefits notice can help identify it; you don't need to upload it."}[i.currentCoverage]));
      stage.append(details("Optional: refresh the A/B and coverage-path basics", coverageOverview(), termChips(["Part A", "Part B", "Original Medicare", "Part D", "Medigap", "Medicare Advantage"])));
      actions(stage, "Continue to what you want to review →", () => nextScreen("coverage", i.goal === "job" ? "jobContext" : "review"), !!i.currentCoverage, () => goToStop(1)); return;
    }
    const q = questionBlock("What do you want to review first?", "You can change these priorities later."); const opts = {costs: "Monthly costs and what I pay for care", doctors: "Doctors, medicines and benefits", change: "A different way to get coverage", understand: "Understand what I already have"}; q.append(renderChips(Object.entries(opts), i.reviewFocus, v => pick("reviewFocus", v))); stage.append(q);
    if (i.reviewFocus) stage.append(feedback({costs: "We'll keep published plan premium, drug deductible and medical spending limit separate. None is your total yearly cost.", doctors: "We'll make a verification list. Daylight cannot confirm personal doctor participation or medicine prices, so these stay open checks.", change: "We'll compare the roles of the two routes before recording a preference. A change to Medigap may involve separate enrollment rights.", understand: "We'll explain the parts relevant to your current arrangement, with optional detail when you need it."}[i.reviewFocus]));
    actions(stage, "Continue to medicines →", () => { i.coverageReviewed = true; advance(3); }, !!i.reviewFocus, () => nextScreen("coverage", "context")); return;
  }
  const head = page === "jobContext" ? ["Plan for the other coverage ending.", "Parts A and B are already in place. These questions concern the job coverage and benefits that may be changing."] : state.dateReturn ? ["Confirm the dates for Medigap.", "The month you turned 65 and the Part B effective month are separate facts. Together, they help establish the federal age-65 supplement window."] : page === "timing" ? ["Check the age-65 timing.", i.job === "no" ? "There is no current-employment coverage reported. These dates describe the age-65 initial window; other eligibility or enrollment rights may still apply." : "The type of current insurance is unresolved. We can record age-based dates while keeping the enrollment decision open."] : page === "jobGoal" ? ["What are you planning for?", "Choose the next task for the current job coverage."] : page === "transition" ? ["Record the work-coverage transition.", "Employer size and the expected end months will shape the questions for the benefits office and Social Security."] : [i.medicare === "only_a" ? "Part A is in place. Let's establish the next step." : "What affects the enrollment decision?", "Current employment and the kind of health insurance help establish the next enrollment questions."];
  stage.append(stageHead(...head));
  if (page === "context" || page === "jobContext") {
    if (i.medicare === "unsure") stage.append(node("p", "Enrollment status is still unknown. Use this as general guidance while checking the Medicare card or Social Security record.", "question-note"));
    const q = questionBlock(`Does ${p.your} health insurance come from ${p.your} own or a spouse's current job?`, "COBRA and retiree coverage are different from insurance based on a current job."); q.append(renderChips([["yes", "Yes, insurance from a current job"], ["ended", "The employment or its health coverage recently ended"], ["no", "No current-employment coverage"], ["unsure", "I'm not sure which kind of coverage it is"]], i.job, v => { i.coverageReviewed = false; pick("job", v); })); stage.append(q);
    if (i.job) stage.append(feedback(reviewMode() && ["yes", "ended"].includes(i.job) ? "Parts A and B are already in place. We will record what job coverage is ending and the dates, then identify the drug and other benefits to review." : i.job === "ended" ? "The employment and insurance end dates can affect the next enrollment questions. We will record both, rather than assume a current window." : i.job === "yes" ? "Employer size and the type of group coverage matter. Check with the benefits office before delaying Part B. Next, choose whether you are preparing for a future change or exploring plans now." : i.job === "no" ? "We'll look at age-65 timing, or keep it open if a different eligibility route applies. Past enrollment windows won't be presented as current deadlines." : "Ask whether this is group coverage based on active employment, and how it works with Medicare. Until confirmed, we won't tell you to delay Part B."));
    actions(stage, ["yes", "ended"].includes(i.job) ? "Continue to your work-coverage goal →" : reviewMode() ? "Continue to what you want to review →" : "Continue to timing details →", () => nextScreen("coverage", ["yes", "ended"].includes(i.job) ? "jobGoal" : reviewMode() ? "review" : "timing"), !!i.job, () => page === "jobContext" ? nextScreen("coverage", "context") : goToStop(1)); return;
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
    actions(stage, i.jobGoal === "plan" ? "Build my transition checklist →" : "Continue to medicines →", () => { if (!validMonthFields(stage)) return; i.coverageReviewed = true; if (i.jobGoal === "plan") { state.journey.reached = 7; advance(7); } else advance(3); }, !!i.employerSize, () => nextScreen("coverage", "jobGoal")); return;
  }
  const picker = monthPicker(`When is, or was, ${p.your} 65th birthday?`, "birthMonth", "birthYear"); stage.append(picker.card);
  const q = questionBlock(`Is ${p.your} birthday on the first day of the month?`, "This can shift the age-65 initial enrollment window by one month."); q.append(renderChips([["yes", "Yes, the first"], ["no", "No"], ["unsure", "I'm not sure"]], i.birthdayFirst, v => { picker.save(); pick("birthdayFirst", v); })); stage.append(q);
  stage.append(secondary("I don't know the date / a different eligibility situation applies", () => { delete i.birthMonth; delete i.birthYear; i.birthSkipped = true; i.birthdayFirst = "unsure"; renderStop(2, "feedback"); }));
  if (i.birthSkipped || i.birthdayFirst === "unsure") stage.append(feedback("Age-based dates stay unresolved. Medicare can check disability, ESRD, or other eligibility and enrollment situations. The rest of the guide can still help you compare coverage roles."));
  else if (computeDates().known) stage.append(feedback(state.dateReturn ? "The age-65 month is recorded. The preview below uses the actual Part B month where entered; special or state rights still need confirmation." : `The age-65 initial enrollment window is ${computeDates().period}. Special enrollment rights and the actual Part B start need separate confirmation.`), visualV6());
  stage.append(sourceTag("Medicare: when to sign up", "https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-can-i-sign-up-for-medicare"));
  actions(stage, state.dateReturn === 5 ? "Return to priorities →" : "Continue to medicines →", () => { if (!i.birthSkipped && (!picker.save() || !i.birthdayFirst)) { announce("Complete the birthday fields and first-day question, or choose that you don't know the date."); return; } i.coverageReviewed = true; const next = state.dateReturn || 3; delete state.dateReturn; advance(next); }, true, () => { if (state.dateReturn) { delete state.dateReturn; goToStop(5); } else nextScreen("coverage", "context"); });
}
function monthField(key, labelText) { const wrap = node("div", undefined, "form-field"), l = node("label", labelText, "field-label"), input = node("input"); l.htmlFor = key; Object.assign(input, {id: key, type: "month", min: "1900-01", max: "2150-12", value: state.intake[key] || ""}); input.addEventListener("input", () => { state.intake[key] = input.value; }); wrap.append(l, input); return wrap; }
function validMonthFields(stage) { const invalid = [...stage.querySelectorAll('input[type="month"]')].find(input => input.value && (!parseMonth(input.value) || !input.validity.valid)); if (invalid) { invalid.reportValidity(); invalid.focus(); return false; } return true; }
function foundationCard() { const i = state.intake, box = node("div", undefined, "card foundation"); box.append(node("h2", "What we know about current coverage"), node("p", i.medicare === "yes_ab" ? `Parts A and B: in place. Coverage arrangement: ${COVERAGE[i.currentCoverage] || "not yet established"}.` : i.medicare === "only_a" ? "Part A: in place. Part B: not yet added. These are the facts entered, not a completed A/B foundation." : i.medicare === "no" ? "Medicare enrollment: not yet in place." : "Medicare enrollment: not yet confirmed.")); return box; }

function localNotes(field, label, placeholder, max = 1000) { const wrap = node("div", undefined, "form-field"), l = node("label", label, "field-label"), input = node("textarea"); input.id = field; l.htmlFor = field; Object.assign(input, {rows: 3, maxLength: max, placeholder, value: state.intake[field] || ""}); input.addEventListener("input", () => { state.intake[field] = input.value; }); wrap.append(l, input, node("p", "Saved in this tab for your checklist. This entry is not sent to chat or logged.", "question-note")); return wrap; }
function stop3(stage) {
  const i = state.intake, p = person(); stage.append(stageHead("Make a medicine-checking list.", "Drug coverage is called Part D. It can be separate alongside Original Medicare (Parts A and B), or included in many Medicare Advantage plans (private plans providing A and B). The exact medicines and pharmacy affect what needs checking."));
  stage.append(details("Optional: how the coverage choices fit together", coverageOverview()));
  const q = questionBlock(`Do ${p.you} take prescription medicines regularly?`); q.append(renderChips([["yes", "Yes"], ["no", "No"], ["unsure", "I'm not sure"]], i.drugs, v => { i.drugsReviewed = false; pick("drugs", v, true); })); stage.append(q);
  if (i.drugs === "yes") { stage.append(feedback("Add names, strengths and how often they are taken if known. We'll carry the list to your checklist. Personal coverage and pharmacy prices still need verification for each plan."), localNotes("medicines", "Medicines to check (optional)", "Example: medicine name, strength, frequency")); }
  if (i.drugs === "no") stage.append(feedback("No regular prescriptions today. That does not by itself mean drug coverage is unnecessary. Current creditable drug coverage and enrollment timing affect whether a late penalty could apply."));
  if (i.drugs === "unsure") { stage.append(feedback("The medicine list still needs to be gathered. The pharmacy can help identify current prescriptions. We'll keep this as an open task."), localNotes("medicines", "Notes for gathering the medicine list (optional)", "What needs to be confirmed?")); }
  if (i.drugs) { stage.append(node("p", "Next we'll collect dental, vision and hearing needs, then use your priorities to explain the coverage trade-offs. We do not verify medicine coverage from this list.", "question-note")); actions(stage, "Save medicine needs and continue to extras →", () => { i.drugsReviewed = true; advance(4); }, true, () => goToStop(2)); }
  stage.append(details("More about drug coverage and penalties", node("p", "Other coverage may count as creditable drug coverage. Ask the existing plan before changing it; taking no medicines does not settle the enrollment decision."), termChips(["Part D", "drug list", "drug deductible", "late penalty"]), link("Medicare: avoiding late enrollment penalties", "https://www.medicare.gov/basics/costs/medicare-costs/avoid-penalties")));
}
function stop4(stage) {
  const i = state.intake, p = person(); stage.append(stageHead("Which extras should stay on the checklist?", "Routine dental, vision and hearing coverage varies. Original Medicare generally does not cover these routine services; some Advantage plans include benefits with conditions and limits."));
  const q = questionBlock(`Which would ${p.you} like to check?`, "Select any, or explicitly choose none or unsure. These needs are not used to infer verified benefits.");
  const options = [["dental", "Dental"], ["vision", "Vision"], ["hearing", "Hearing"], ["none", "None of these"], ["unsure", "I'm not sure yet"]];
  q.append(renderChips(options, [], v => { if (["none", "unsure"].includes(v)) { i.extras = []; i.extrasNone = v === "none"; i.extrasUnsure = v === "unsure"; } else { i.extras = i.extras.includes(v) ? i.extras.filter(x => x !== v) : [...i.extras, v]; i.extrasNone = i.extrasUnsure = false; } i.extrasAnswered = false; invalidatePlans(); renderStop(4, "feedback"); }, {multi: true}));
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
  const i = state.intake; stage.append(stageHead("Connect your priorities to the two routes.", "Compare first; a preference is optional. Doctors, travel, medicine prices and extras stay verification tasks. Only published financial fields can change the catalog order."));
  const paths = node("div", undefined, "path-cards");
  for (const [title, body] of [["Original Medicare", "Keep Parts A and B. A separate Part D plan can cover prescriptions; Medigap is a separate supplement for certain A/B costs. Dental or other routine extras may need separate coverage."], ["Medicare Advantage", "A private plan provides A and B, usually through a network. Many include Part D and some extras. You still pay copays or coinsurance up to the plan's covered medical spending limit."]]) { const c = node("div", undefined, "path-card"); c.append(node("h2", title, "path-title"), node("p", body)); paths.append(c); }
  stage.append(paths, termChips(["Medicare Advantage", "Medigap", "Part D", "network", "HMO", "PPO"]));
  const q = questionBlock("What should we consider?", "Select any. We'll explain the trade-offs for those choices.");
  q.append(renderChips(Object.entries(PRIORITY_LABELS), i.priorities, v => { i.priorities = i.priorities.includes(v) ? i.priorities.filter(k => k !== v) : [...i.priorities, v]; if (!i.priorities.includes(i.topPriority)) delete i.topPriority; i.prioritiesAnswered = false; i.priorityOrder = []; invalidatePlans(); renderStop(5, "feedback"); }, {multi: true})); stage.append(q);
  if (i.priorities.length) {
    const rows = node("table", undefined, "v-compare"); const head = node("tr"); head.append(node("th", "Priority"), node("th", "Original Medicare + optional supplement"), node("th", "Medicare Advantage")); const th = node("thead"); th.append(head); rows.append(th); const tbody = node("tbody");
    for (const key of i.priorities) { const t = TRADEOFFS[key], tr = node("tr"), label = node("th", t[0]); label.scope = "row"; const a = node("td", t[1]), b = node("td", t[2]); a.dataset.col = "Original Medicare"; b.dataset.col = "Medicare Advantage"; tr.append(label, a, b); tbody.append(tr); }
    rows.append(tbody); const f = feedback("Here are the trade-offs for the priorities selected."); f.append(rows); i.priorities.forEach(k => f.append(node("p", TRADEOFFS[k][3], "question-note"))); stage.append(f);
  }
  if (i.priorities.length > 1) { const most = questionBlock("If those conflict, which takes priority?", "An unverified priority stays unverified, even when it matters most."); most.append(renderChips(i.priorities.map(k => [k, PRIORITY_LABELS[k]]), i.topPriority, v => pick("topPriority", v, true))); stage.append(most); if (i.topPriority) { const top = feedback(["keep_doctors", "travel"].includes(i.topPriority) ? "That stays your first verification task. It cannot be scored; any published-field order will be explained separately." : "That published financial field will be considered first when ordering records within a category. It still does not establish total cost or personal fit."); top.dataset.feedback = "topPriority"; stage.append(top); } }
  stage.append(details("Before switching to a supplement: Medigap enrollment rights", node("p", "Medigap works with Original Medicare, not Medicare Advantage. The federal six-month age-65 enrollment window depends on being 65 or older and having Part B. Later applications can face underwriting, though special and state rights may apply. Check those rights before dropping existing coverage."), sourceTag("Medicare: buying Medigap", SOURCES.medigap)));
  const lq = questionBlock("Which options should we look at?", "This changes the initial catalog view, not an enrollment decision. You can change it in the results."); lq.append(renderChips([["unsure", "Show all options before I decide"], ["original", "Original Medicare add-ons"], ["advantage", "Medicare Advantage options"]], i.leaning, v => { state.category = v === "original" ? "PDP" : v === "advantage" ? "MA-PD" : "all"; pick("leaning", v, true); })); stage.append(lq);
  const viewFeedback = feedback({unsure: "We'll start with all published categories in source order. Each category has a different role; no coverage route has been selected.", original: "We'll start with separate drug-plan records and explain the supplement quote work still needed. Before moving from Advantage, check Medigap enrollment rights before dropping coverage.", advantage: "We'll start with Advantage plans that include drugs. Plans without drugs and special needs plans remain visible as separate categories with their own conditions."}[i.leaning]); viewFeedback.dataset.feedback = "leaning"; stage.append(viewFeedback);
  if (i.leaning === "original") {
    stage.append(node("p", "The catalog can show separate drug plans. Medigap premiums and standalone dental quotes are not included, so a drug-plan premium is not the price of the whole Original Medicare route.", "question-note"));
    const dates = details("Optional: establish the Medigap date inputs", node("p", "Use the actual or confirmed Part B effective month, not an assumed 65th-birthday date."), monthField("partBStart", "Part B effective month (optional)"));
    if (!i.birthMonth || !i.birthYear || !["yes", "no"].includes(i.birthdayFirst)) { dates.append(node("p", "Age-65 timing is also unresolved. Edit Your coverage to enter it, or confirm the window with SHINE. No Medigap dates will be guessed."), secondary("Edit age-65 timing", () => { state.screen.coverage = "timing"; state.dateReturn = 5; goToStop(2); })); }
    dates.append(secondary("Update date preview", () => { if (validMonthFields(stage)) renderStop(5, "feedback"); })); stage.append(dates, visualV6());
  }
  stage.append(details("Full side-by-side comparison", visualV5()));
  actions(stage, "Save priorities and view available plans →", () => { if (!validMonthFields(stage)) return; i.priorityOrder = i.topPriority ? [i.topPriority, ...i.priorities.filter(k => k !== i.topPriority)] : [...i.priorities]; i.prioritiesAnswered = true; state.sort = null; state.plansLimit = 6; state.planQuery = ""; advance(6); }, i.priorities.length <= 1 || !!i.topPriority, () => goToStop(4));
}

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
async function checkConnection() { try { const s = await requestJSON("/api/status"); state.live = !!s.live_conversation_available; state.connection = s.consumer_ready === false ? "pending" : "available"; } catch (e) { state.live = false; state.connection = e.pending ? "pending" : "offline"; } return state.connection; }
function intakeToPriorities() { const i = state.intake, order = i.priorityOrder?.length ? i.priorityOrder : i.priorities, scored = []; for (const k of order || []) { const name = {low_premium: "monthly_premium", predictable: "medical_limit"}[k]; if (name) scored.push(name); } return {priorities: scored, unscored: [...(i.priorities || []).filter(k => ["keep_doctors", "travel"].includes(k)), ...(i.extras || []), ...(["yes", "unsure"].includes(i.drugs) ? ["medicines"] : [])]}; }
function stop6(stage) {
  const i = state.intake; stage.append(stageHead("Compare published plan records.", "These are plan options, not confirmed personal matches. A plan's premium is only one part of Medicare costs."));
  if (!/^\d{5}$/.test(i.zip || "") || i.county !== "Collier County") {
    stage.append(feedback(i.county === "unsure" ? "The county is still unknown. Confirm it to view Collier County plans; this is not an out-of-area conclusion." : i.county === "outside" ? "This location is outside the current Collier County catalog. Use Medicare.gov for local plans, or keep building your guide." : "Confirm a ZIP code and county before opening local plan records."), secondary("Change or confirm location", () => { state.screen.start = "location"; goToStop(0); }), link("Compare plans for any area on Medicare.gov", SOURCES.compare));
    actions(stage, "Continue with unresolved plan search →", () => advance(7), true, () => goToStop(5)); return;
  }
  stage.append(node("p", `Location: ZIP ${i.zip}, Collier County · Plan year 2027`, "question-note"));
  if (!i.medicare) stage.append(feedback("You chose direct browsing. You can add current coverage and personal needs at any time using the journey above. No personal match has been established."));
  const cats = node("div", undefined, "pref-row"); cats.setAttribute("aria-label", "Plan category");
  for (const [value, label] of Object.entries(CATEGORY_LABELS)) { const b = secondary(label, () => { if (state.category === value && state.plansLoaded) return; state.category = value; state.plansLimit = 6; state.planQuery = ""; state.sort = null; state.catalog = null; state.plansLoaded = false; state.plansError = null; state.comparison = null; renderStop(6, "none"); }); b.setAttribute("aria-pressed", String(state.category === value)); cats.append(b); } stage.append(cats);
  stage.append(node("p", "These categories serve different roles. Special needs plans have eligibility restrictions; seeing a record does not establish eligibility. Medigap quotes and standalone dental plans are not in this catalog.", "question-note"));
  if (i.leaning === "original" || state.category === "PDP") stage.append(details("Where Medigap fits alongside a drug plan", visualV8(), link("Find Medigap policies on Medicare.gov", "https://www.medicare.gov/medigap-supplemental-insurance-plans/")));
  const tasks = intakeToPriorities().unscored; if (tasks.length) stage.append(feedback(`Still to verify: ${tasks.map(k => ({keep_doctors: "doctor participation", travel: "routine care away from home", medicines: "medicine coverage and pharmacy prices", dental: "dental benefits", vision: "vision benefits", hearing: "hearing benefits"}[k])).join(", ")}. These do not determine this order.`));
  const host = node("div", undefined, "plans-host"); host.id = "stop6-plans"; stage.append(host);
  if (state.plansError) renderPlanError(host);
  else if (state.catalog) renderCatalog(host, state.catalog);
  else { host.append(node("p", "Checking the published plan service…", "loading-text")); loadCatalog(); }
  actions(stage, state.selected.size ? "Continue with my saved comparisons →" : state.plansLoaded ? "Continue to my next actions →" : "Continue with plan search unresolved →", () => advance(7), true, () => goToStop(5));
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
  if (state.selected.size) { const toolbar = node("div", undefined, "comparison-toolbar"); toolbar.append(node("strong", `${state.selected.size} saved for comparison`), secondary(`Compare ${state.selected.size} saved records`, compareSelected)); toolbar.lastElementChild.disabled = state.selected.size < 2 || state.compareBusy; host.append(toolbar); }
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
  const card = node("article", undefined, "plan-card"); card.dataset.planId = plan.id; card.append(node("p", `${CATEGORY_LABELS[plan.category] || plan.category} · ${plan.plan_type || ""}`, "plan-kind"), node("h3", plan.name), node("p", plan.id, "question-note"));
  const dl = node("dl", undefined, "plan-fields"); for (const [key, label] of Object.entries(metricNames)) dl.append(node("dt", label), node("dd", `${moneyLabel(plan.metrics?.[key])}${key === "monthly_premium" ? " / month" : ""}`)); card.append(dl, node("p", "Doctor participation, exact medicine coverage and personal total costs are not confirmed.", "question-note"));
  if (plan.premium_source_conflict) card.append(node("p", "Published premium sources disagree. See the preserved amounts and conditions below; this record is not treated as a known premium for ordering.", "catalog-warning"));
  if (plan.eligibility === "restricted_unconfirmed") card.append(node("p", `Restricted eligibility: ${plan.snp_type || "special needs criteria"}. Personal eligibility has not been established.`, "plan-eligibility"));
  const d = details("Plan details and source conditions");
  if (plan.star_rating?.state === "rated") d.append(node("p", `CMS rating: ${plan.star_rating.value} of 5. A contract-level quality measure, not a personal-fit score.`)); else d.append(node("p", "CMS rating: not available as a numeric rating in this record."));
  for (const note of plan.notes || []) d.append(node("p", note));
  for (const observation of plan.premium_basis?.observations || []) d.append(node("p", `${observation.label}: ${moneyLabel(observation.value)}`));
  const sources = sourceLinks([{evidence: [plan.source, ...(plan.star_rating?.evidence ? [plan.star_rating.evidence] : [])]}]); if (sources) d.append(sources); card.append(d);
  const saved = state.selected.has(plan.id), save = secondary(saved ? `Remove ${plan.name} from comparison` : `Save ${plan.name} for comparison`, () => { if (state.selected.has(plan.id)) state.selected.delete(plan.id); else if (state.selected.size < 3) state.selected.set(plan.id, plan); else { announce("Choose up to three records. Remove one before adding another."); const note = card.querySelector(".selection-error") || node("p", "", "selection-error field-error"); note.setAttribute("role", "alert"); note.textContent = "Up to three records can be compared. Remove one to add this plan."; card.append(note); return; } state.comparison = null; state.compareError = null; renderStop(6); announce(`${state.selected.size} records saved for comparison.`); }); save.setAttribute("aria-pressed", String(saved)); card.append(save);
  card.append(secondary(`Ask about ${plan.name}`, () => { openAsk(); askTyped(`Explain the published record for plan ${plan.id}, including its limitations.`); })); return card;
}
function renderSavedComparison() {
  const wrap = node("section", undefined, "card saved-comparison"); wrap.id = "saved-comparison"; wrap.append(node("h2", `${state.selected.size} records saved for comparison`), node("p", "Save two or three records. The comparison shows their different roles and published fields; it does not establish eligibility or choose a plan."));
  if (state.selected.size) { const ul = node("ul"); for (const p of state.selected.values()) { const li = node("li", `${p.name} (${p.id}) `); li.append(secondary(`Remove ${p.name}`, () => { state.selected.delete(p.id); state.comparison = null; renderStop(6); })); ul.append(li); } wrap.append(ul); }
  const b = primary(state.compareBusy ? "Loading comparison…" : "Compare saved records", compareSelected); b.disabled = state.selected.size < 2 || state.compareBusy; wrap.append(b);
  if (state.compareError) { const e = node("p", state.compareError, "field-error"); e.setAttribute("role", "alert"); wrap.append(e); }
  if (state.comparison) { const plans = state.comparison.plans, table = node("table", undefined, "v-compare"), head = node("tr"); head.append(node("th", "Published field")); plans.forEach(p => head.append(node("th", p.name))); const thead = node("thead"); thead.append(head); table.append(thead); const body = node("tbody"); for (const [key, label] of [["category", "Coverage role"], ...Object.entries(metricNames), ["verification", "Personal checks"]]) { const row = node("tr"), title = node("th", label); title.scope = "row"; row.append(title); plans.forEach(p => { const text = key === "category" ? CATEGORY_LABELS[p.category] : key === "verification" ? "Doctors, drugs, total costs and eligibility still to verify" : key === "monthly_premium" && p.premium_source_conflict ? "Source conflict — see conditions" : moneyLabel(p.metrics?.[key]); const cell = node("td", text); cell.dataset.col = p.name; row.append(cell); }); body.append(row); } table.append(body); wrap.append(table, node("p", state.comparison.scope || "Different plan roles are not interchangeable.", "question-note")); for (const plan of plans) { const conditions = details(`Conditions and sources for ${plan.name}`); for (const note of plan.notes || []) conditions.append(node("p", note)); const source = sourceLinks([{evidence: plan.source}]); if (source) conditions.append(source); wrap.append(conditions); } }
  return wrap;
}
async function compareSelected() {
  if (state.compareBusy || state.selected.size < 2) return; const ids = [...state.selected.keys()].sort(), id = state.requestId; state.compareBusy = true; state.compareError = null; renderStop(6);
  try { const r = await requestJSON("/api/catalog", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({action: "compare", plan_ids: ids, conversation_id: state.conversationId})}); if (!Array.isArray(r.plans) || r.plans.length !== ids.length || r.plans.some(p => !ids.includes(p.id))) throw new Error("The comparison did not return the selected records. Retry before using it."); if (id === state.requestId && ids.join() === [...state.selected.keys()].sort().join()) state.comparison = r; }
  catch (e) { if (id === state.requestId) state.compareError = e.message; }
  finally { state.compareBusy = false; if (id === state.requestId && state.journey.stop === 6) { renderStop(6); requestAnimationFrame(() => el("saved-comparison")?.scrollIntoView({block: "start", behavior: "instant"})); } }
}

function buildMap() {
  const i = state.intake, p = person(), steps = [];
  steps.push({title: "Current coverage", status: !i.medicare || i.medicare === "unsure" ? "Open question" : "Entered fact", sentence: !i.medicare ? "Medicare enrollment status was not entered." : i.medicare === "yes_ab" ? `Parts A and B are in place. ${COVERAGE[i.currentCoverage] || "The coverage arrangement is not yet confirmed"}.` : i.medicare === "only_a" ? "Part A is in place. Part B has not been added." : i.medicare === "no" ? "Not enrolled in Medicare yet." : "Check the A/B lines and effective dates on the Medicare card or contact Social Security."});
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
  if (!i.medicare || i.medicare === "unsure") items.push("Check the Medicare card or Social Security record for Parts A and B and their effective dates.");
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
function summaryContent() { const wrap = node("div", undefined, "summary-content"), i = state.intake; wrap.append(node("p", `${i.recipient === "someone" ? "For the person you're helping" : "For you"} · ${GOALS[i.goal] || "Goal not entered"}${i.zip ? ` · ZIP ${i.zip}` : ""} · ${i.county === "Collier County" ? "Collier County" : i.county === "outside" ? "Outside Collier County" : "County unresolved"}`, "finalmap-sub"));
  const list = node("ol", undefined, "finalmap-route"); for (const step of buildMap()) { const li = node("li"), body = node("div"); body.append(node("strong", step.title), node("p", step.status, "summary-status"), node("p", step.sentence)); li.append(node("span", step.status === "Entered fact" ? "✓" : "○", "fm-ico"), body); list.append(li); } wrap.append(list, visualV6());
  if (i.priorities.length) wrap.append(node("p", "Priorities: " + (i.priorityOrder.length ? i.priorityOrder : i.priorities).map(k => PRIORITY_LABELS[k]).join("; ")));
  if (i.doctor) wrap.append(node("p", "Doctor / office to check: " + i.doctor));
  if (state.selected.size) { wrap.append(node("h2", "Saved for comparison, not chosen for enrollment")); for (const plan of state.selected.values()) wrap.append(node("p", `${plan.name} · ${plan.id} · ${CATEGORY_LABELS[plan.category] || plan.category}`)); }
  const ul = node("ul", undefined, "todo-list"); checklistItems().forEach(text => ul.append(node("li", text))); wrap.append(node("h2", "Your next actions"), ul, helpLinks()); return wrap;
}
function stop7(stage) {
  const i = state.intake; stage.append(stageHead(i.jobGoal === "plan" ? "Your work-coverage transition checklist." : "Your coverage map.", "What we know, the checks still open, and your next actions."));
  const doctorNotes = localNotes("doctor", "Doctor or office to verify (optional)", "Name and location; no ID numbers", 240), summary = node("div"); summary.id = "summary-live"; summary.append(summaryContent());
  doctorNotes.querySelector("textarea").addEventListener("input", () => summary.replaceChildren(summaryContent())); stage.append(doctorNotes, summary);
  const row = node("div", undefined, "next-actions"); row.append(secondary(state.plansError ? "Retry my plan search" : "Return to plans", () => goToStop(6)), secondary("Edit medicine needs", () => goToStop(3)), primary("Review printable map", printMap)); stage.append(row);
  stage.append(node("p", "Daylight explains published information. It does not enroll you or establish eligibility, provider participation or personal prices.", "question-note"));
}
function buildPrintContent() { const wrap = node("div"); wrap.append(node("h1", "Your coverage, plain as day.", "print-h1"), node("p", "Daylight Medicare · " + new Date().toLocaleDateString("en-US"), "print-meta"), summaryContent(), node("p", "General information, not a personal recommendation or enrollment. Published-field ordering is not a personal-fit ranking. Unknown items above must be confirmed.", "print-disclaimer")); return wrap; }
function printMap() { const v = el("print-view"); v.replaceChildren(buildPrintContent()); let d = el("print-preview"); if (!d) { d = node("dialog", undefined, "print-preview"); d.id = "print-preview"; d.setAttribute("aria-label", "Printable coverage map"); document.body.append(d); } d.replaceChildren(); const row = node("div", undefined, "preview-actions"); row.append(secondary("Close preview", () => d.close()), primary("Print or save PDF", () => { v.replaceChildren(buildPrintContent()); window.print(); })); d.append(row, buildPrintContent()); d.showModal(); }

const ASK = {
  0: [["What can Daylight help with?", "The guide explains coverage roles, records your questions and can display published 2027 Collier County plan records when the plan service is available. Enrollment and personal fit still require verification."], ["What happens to my answers?", "Guide answers and medicine/doctor notes stay in this tab. If you submit a typed question, that question and recent typed chat are sent to the local server and, when configured, its conversation service. Submitted chat may be logged. Tab notes are not attached automatically."]],
  1: [["What do the A and B letters mean?", "Part A is hospital insurance; Part B is medical insurance, including doctors and outpatient care. Check the card's effective dates to establish what is in place."], ["Is enrollment automatic?", "People already receiving Social Security or Railroad Retirement benefits are usually enrolled automatically at 65. Check the actual notice. Others generally apply through Social Security; special situations can differ."]],
  2: [["What should I ask the benefits office?", "Ask whether coverage is based on current active employment, whether it is a qualifying group plan, employer size, how Medicare coordinates with it, and the exact employment and health-coverage end dates. Ask separately about creditable drug coverage."], ["Why aren't you showing a Part B start date?", "A birthday and current work coverage do not establish when Part B actually starts. Social Security confirms the enrollment route and effective date. Unknown dates stay unknown."]],
  3: [["Does taking no medicines settle the drug-plan decision?", "No. Drug needs can change, and current creditable coverage and enrollment timing affect penalties. Ask your current insurer whether its drug coverage is creditable before changing it."], ["Does my list confirm drug coverage?", "No. The list is a checklist. Verify the exact medicine, strength, plan drug list, restrictions and pharmacy prices. Daylight does not establish personal drug coverage or cost from a name alone."]],
  4: [["Does a dental benefit mean all dental work is covered?", "No. Check the covered services, exclusions, yearly limits, costs and provider requirements for the exact plan. A benefit label is not confirmation for your treatment."], ["Can extras be separate from Medicare?", "Standalone dental and vision coverage exists. Those quotes are not included in this catalog; free local Medicare counseling can help identify what to compare."]],
  5: [["How will my priorities affect results?", "Published plan premiums and medical limits can affect numeric ordering. Doctor participation, travel rules, extras and personal medicine prices are not scored. Those remain verification tasks, even if they are your top priority."], ["When does the Medigap window begin?", "The federal age-65 six-month period depends on both age and having Part B. A birthday alone is insufficient. Special or state protections may also apply; verify rights before dropping other coverage."]],
  6: [["Is the first record the best plan for me?", "No. Records are in source order or ordered by explicit published fields. Eligibility, doctor participation, exact medicines and personal total cost have not been established."], ["What is a special needs plan?", "An Advantage plan restricted to people meeting particular criteria, such as certain Medicaid or clinical circumstances. Listing it does not determine anyone's eligibility."], ["Why might plan records be unavailable?", "The plan service may be disconnected, busy, or waiting for data validation. Retry or use official Medicare comparison. The guide will not substitute unverified records or mark that search complete."]],
  7: [["Who can help me take the next step?", "SHINE offers free, unbiased counseling in Florida at 1-800-963-5337. Medicare is available at 1-800-633-4227. Social Security handles Parts A and B enrollment. Links and phone numbers are included in your map."], ["What remains unresolved?", "The map identifies unanswered coverage facts, unverified doctors and medicines, missing dates and any failed plan search. Saved records are comparison candidates, not enrollment choices."]],
};
function askSource() { return [SOURCES.options, SOURCES.signup, "https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65", "https://www.medicare.gov/health-drug-plans/part-d", SOURCES.costs, SOURCES.medigap, SOURCES.compare, state.intake.county === "Collier County" ? SOURCES.shine : "https://www.shiphelp.org/"][state.journey.stop]; }
function openAsk() { el("ask-panel").hidden = false; el("ask-scrim").hidden = false; el("ask-panel").setAttribute("aria-modal", String(isPhone())); document.body.classList.add("ask-active"); if (isPhone()) [el("main"), el("journey-map"), document.querySelector(".site-header"), document.querySelector(".site-footer")].forEach(n => n.inert = true); renderAskCanned(); requestAnimationFrame(() => el("ask-close").focus()); }
function closeAsk(focus = true) { el("ask-panel").hidden = true; el("ask-scrim").hidden = true; document.body.classList.remove("ask-active"); [el("main"), el("journey-map"), document.querySelector(".site-header"), document.querySelector(".site-footer")].forEach(n => n.inert = false); if (focus && !el("ask-open").hidden) el("ask-open").focus(); }
function renderAskCanned() { const box = el("ask-canned"); box.replaceChildren(node("p", `Questions about ${STOP_NAMES[state.journey.stop].toLowerCase()}`, "ask-canned-head")); for (const [q, answer] of ASK[state.journey.stop]) box.append(secondary(q, () => { addAsk("you", q); addAsk("daylight", answer, askSource()); })); }
function addAsk(who, text, source) { const thread = el("ask-thread"), msg = node("div", undefined, "ask-msg ask-" + who); if (who === "daylight") msg.append(node("p", source ? "Daylight · guide explanation" : "Daylight", "ask-who")); msg.append(node("p", text, "ask-text")); if (source) msg.append(link("Official resource", source)); thread.append(msg); thread.scrollTop = thread.scrollHeight; return msg; }
async function askTyped(message) {
  if (state.busy || !message?.trim()) return; const conversationId = state.conversationId; state.busy = true; el("ask-send").disabled = true; addAsk("you", message); el("ask-status").textContent = "Checking the conversation service…";
  try { await checkConnection(); if (conversationId !== state.conversationId) return; if (!state.live) throw new Error("Typed questions are unavailable right now. The source-linked guide questions above still work. Your question has not been sent to the conversation service."); const result = await requestJSON("/api/live-chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message, history: state.history.slice(-8), conversation_id: conversationId})}); if (conversationId !== state.conversationId) return; addAsk("daylight", result.text || "The service returned no explanation. Try a more specific question."); if (result.question) addAsk("daylight", result.question); state.history.push({role: "user", content: message}, {role: "assistant", content: result.text || ""}); state.history = state.history.slice(-8); }
  catch (e) { if (conversationId === state.conversationId) { const msg = addAsk("daylight", ["AbortError", "TimeoutError"].includes(e.name) ? "The conversation service took too long. You can retry or use the guide questions above." : e.message); msg.append(secondary("Retry this question", () => askTyped(message))); } }
  finally { if (conversationId === state.conversationId) { state.busy = false; el("ask-send").disabled = false; el("ask-status").textContent = ""; } }
}
el("get-started").addEventListener("click", () => beginJourney());
el("fast-start").addEventListener("click", () => beginJourney(true));
el("restart").addEventListener("click", startOver);
el("ask-open").addEventListener("click", openAsk);
el("ask-close").addEventListener("click", () => closeAsk());
el("ask-scrim").addEventListener("click", () => closeAsk());
el("ask-form").addEventListener("submit", e => { e.preventDefault(); const message = el("ask-input").value.trim(); if (message && !state.busy) { el("ask-input").value = ""; askTyped(message); } });
el("ask-input").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); el("ask-form").requestSubmit(); } });
document.addEventListener("keydown", e => { if (el("ask-panel").hidden) return; if (e.key === "Escape") closeAsk(); if (e.key === "Tab" && isPhone()) { const controls = [...el("ask-panel").querySelectorAll("button:not(:disabled),a,textarea")], first = controls[0], last = controls.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); } } });
el("about-answers").addEventListener("toggle", () => document.body.classList.toggle("privacy-expanded", el("about-answers").open));
document.querySelector(".skip-link").addEventListener("click", e => { e.preventDefault(); (el("stage").hidden ? el("landing-title") : el("stage")).focus(); });
checkConnection();
showLanding();
