'use strict';

const $ = id => document.getElementById(id);
const api = '/api/drug-estimate-preview';
const dollars = new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'});
const dates = new Intl.DateTimeFormat('en-US', {dateStyle:'long', timeZone:'UTC'});
const holds = {
  quantity_limit_rule_unresolved: 'The plan lists a quantity limit. Its application to this fill still needs review.',
  criteria_unresolved: 'The plan lists coverage requirements that still need to be checked.',
  insulin_negotiated_price_or_unit_unresolved: 'The insulin estimate needs a verified price basis and physical unit.',
  selected_drug_rule_unresolved: 'This drug needs a separate 2026 pricing-rule check.',
  only_in_area_retail_average_available: 'The published averages cover retail fills in the plan’s service area. A mail-order estimate needs separate price evidence.',
  prior_spending_unresolved_or_unsupported: 'A remaining-year estimate needs verified opening spending and deductible balances.',
  assistance_unresolved_or_unsupported: 'This example needs a cost calculation that accounts for assistance.',
  physical_price_unit_unresolved: 'The quantity needs a physical unit that matches the published price.',
  enhanced_troop_threshold_unresolved: 'The plan’s supplemental benefits can change when cost sharing ends. That calculation still needs review.'
};

const cases = new Map();
let revision = 1;
let editing = false;
let confirmedQuantity = 'as_listed';
let expires = 0;

function element(tag, label, parent) {
  const item = document.createElement(tag);
  item.textContent = label;
  parent.append(item);
  return item;
}

function invalidate() {
  revision += 1;
  $('results').hidden = true;
  $('results').replaceChildren();
  $('status').textContent = '';
  $('continue').disabled = !$('case').value || (editing && !$('quantity').value);
}

function facts() {
  const item = cases.get($('case').value);
  const node = $('facts');
  node.replaceChildren();
  $('reports').hidden = !item;
  $('edit').hidden = item?.id !== 'D146-03' || editing;
  if (!item) return;
  const period = item.period.kind === 'full_year' ? 'Full year' : 'Remaining year';
  element('p', `${period} · ${dates.format(new Date(item.period.start))} through December 31, 2026`, node);
  const assistance = item.assistance === 'none' ? 'No assistance' : 'Extra Help reported';
  const balances = item.prior_spending === 'confirmed_zero' ? 'zero opening balances' : 'opening balances unknown';
  element('p', `${assistance} · ${balances}`, node);
  const list = element('ul', '', node);
  item.medicines.forEach((med, index) => {
    let quantity = med.quantity;
    if (item.id === 'D146-03' && index === 0) {
      if (editing) quantity = $('quantity').value || 'Quantity needed';
      else if (confirmedQuantity !== 'as_listed') quantity = confirmedQuantity;
    }
    const unit = quantity === 'Quantity needed' ? '' : ` ${med.unit}${quantity > 1 && med.unit !== 'mL' ? 's' : ''}`;
    element('li', `${med.label} · ${quantity}${unit} per ${med.days_supply}-day fill · ${med.fills.length} planned fills`, list);
  });
  const pharmacies = element('ul', '', node);
  for (const choice of item.choices) {
    element('li', `${choice.label} · ${choice.pharmacy_label} · NPI ${choice.pharmacy.npi}`, pharmacies);
  }
}

function editQuantity(on) {
  editing = on;
  $('quantity-controls').hidden = !on;
  $('quantity').disabled = !on;
  $('quantity').required = on;
  $('back').hidden = !on;
  $('choose').hidden = on;
  $('case').disabled = on;
  $('quantity').value = '';
  invalidate();
  facts();
  $(on ? 'quantity' : 'case').focus();
}

function render(results) {
  const target = $('results');
  target.replaceChildren();
  const heading = element('h2', 'Plan estimates', target);
  heading.tabIndex = -1;
  const grid = element('div', '', target);
  grid.className = 'comparison';
  for (const row of results) {
    const article = element('article', '', grid);
    element('h3', row.label, article);
    if (row.pharmacy && ['preferred', 'standard'].includes(row.pharmacy.status)) {
      const type = row.pharmacy.channel === 'mail' ? 'mail order' : 'retail';
      const status = row.pharmacy.status === 'preferred' ? 'Preferred' : 'Standard';
      element('p', `${status} ${type} pharmacy`, article);
    }
    if (row.state !== 'offline_average_candidate') {
      element('p', holds[row.hold] || 'This estimate is unavailable. Choose another fictional example to continue.', article);
      continue;
    }
    element('p', row.period_kind === 'full_year' ? 'Full-year average-based estimate' : 'Remaining-year average-based estimate', article);
    const table = element('dl', '', article);
    for (const [label, value] of [
      ['Plan premiums', row.plan_premium_cents],
      ['Drug spending', row.drug_spending_cents],
      ['Premiums and drugs', row.plan_premium_plus_drugs_cents]
    ]) {
      const pair = element('div', '', table);
      element('dt', label, pair);
      element('dd', dollars.format(value / 100), pair);
    }
  }
  target.hidden = false;
  heading.focus();
}

$('case').addEventListener('change', () => { invalidate(); facts(); });
$('quantity').addEventListener('change', () => { invalidate(); facts(); });
$('back').addEventListener('click', () => editQuantity(false));
$('edit').addEventListener('click', () => editQuantity(true));
window.addEventListener('pagehide', invalidate);

$('case-form').addEventListener('submit', async event => {
  event.preventDefault();
  invalidate();
  const sentRevision = revision;
  $('continue').disabled = true;
  $('status').textContent = 'Checking the two plans…';
  try {
    const response = await fetch(api, {
      method:'POST', headers:{'Content-Type':'application/json'}, cache:'no-store',
      body:JSON.stringify({case:$('case').value, revision:sentRevision,
        quantity_mode:editing ? $('quantity').value : $('case').value === 'D146-03'
          ? confirmedQuantity : 'as_listed'})
    });
    const payload = await response.json();
    if (sentRevision !== revision) return;
    if (!response.ok || payload.revision !== sentRevision) throw new Error('Preview unavailable');
    if (Date.now() >= expires) {
      $('status').textContent = 'The preview evidence is due for review.';
      return;
    }
    if (editing) confirmedQuantity = $('quantity').value;
    $('status').textContent = '';
    render(payload.results);
  } catch {
    if (sentRevision === revision) $('status').textContent = 'The preview is unavailable. Try Continue again.';
  } finally {
    if (sentRevision === revision) $('continue').disabled = false;
  }
});

async function load() {
  try {
    const response = await fetch(api, {cache:'no-store'});
    if (!response.ok) throw new Error('Preview unavailable');
    const data = await response.json();
    expires = Date.parse(data.expires);
    for (const item of data.cases) {
      cases.set(item.id, item);
      element('option', item.label, $('case')).value = item.id;
    }
    $('case').disabled = false;
    window.setTimeout(() => {
      invalidate();
      $('status').textContent = 'The preview evidence is due for review.';
    }, Math.max(0, expires - Date.now()));
  } catch {
    $('status').textContent = 'The preview is unavailable. Reload this page to try again.';
  }
}
load();
