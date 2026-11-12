'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {render} = require('../web/understanding-view.js');

class Node {
  constructor(tag) {this.tag = tag;this.children = [];this.attributes = {};this.events = {};this._text = '';this.value = '';}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children = nodes;this._text = '';}
  set textContent(value) {this._text = String(value);this.children = [];}
  get textContent() {return this._text + this.children.map(node => node.textContent).join('');}
  setAttribute(key, value) {this.attributes[key] = value;}
  addEventListener(event, handler) {this.events[event] = handler;}
  set innerHTML(value) {throw Error('Unsafe HTML sink');}
}
const document = {createElement: tag => new Node(tag)};
const nodes = node => [node, ...node.children.flatMap(nodes)];
const block = (id, label, text, extra = {}) => ({id, label, text, evidence_refs: ['fixture:source'], ...extra});
const guide = (capability = 'costs', blocks = [block('premium', 'Each month', 'Premiums pay for coverage.')]) => ({
  version: 'understanding-20261103-r1', capability, visual: capability === 'coverage_paths' ? 'routes' : capability,
  title: 'Fictional guide', state: 'educational', purpose: 'general_education', coverage_year: 2026,
  personal_authority: 'held', personal_result: null, evidence_refs: ['fixture:source'], blocks});

test('coverage map preserves route relationships and explicit explain actions', () => {
  const payload = guide('coverage_paths', [
    block('original_base', 'Original Medicare', 'A and B through the federal program.', {route: 'original'}),
    block('advantage_base', 'Medicare Advantage', 'A and B through a private plan.', {route: 'advantage'}),
    block('medigap', 'Where Medigap belongs', 'Original Medicare, not Medicare Advantage.')]);
  const calls = [], original = structuredClone(payload);
  const result = render(payload, {document, explain: value => calls.push(value)});
  const buttons = nodes(result).filter(node => node.tag === 'button');
  assert.deepEqual(buttons.map(button => button.textContent), ['Original Medicare', 'Medicare Advantage']);
  buttons[0].events.click();buttons[1].events.click();
  assert.deepEqual(calls, ['original', 'advantage']);
  assert.ok(result.textContent.includes('Original Medicare, not Medicare Advantage.'));
  assert.deepEqual(payload, original);
});

test('timeline keeps reported precision and uses an explicit correction control', () => {
  const payload = guide('transition', [block('confirm', 'Confirm the start', 'A preference is not an effective date.')]);
  payload.reported_dates = [{label:'65th birthday',value:'November (year not given)',state:'reported'},
    {label:'Insurance end',value:'December 15th',state:'reported'},
    {label:'Stale date',value:'DO_NOT_RENDER',state:'stale'}];
  payload.open_checks = ['Confirm the actual start with Social Security.'];
  let edits = 0;
  const result = render(payload, {document, reviewDates: () => edits++});
  assert.ok(result.textContent.includes('November (year not given)'));
  assert.ok(result.textContent.includes('December 15th'));
  assert.ok(result.textContent.includes('Still to confirm'));
  assert.ok(!result.textContent.includes('DO_NOT_RENDER'));
  nodes(result).find(node => node.tag === 'button').events.click();assert.equal(edits, 1);
});

test('invented cost scenarios change locally and never become a total or quote', () => {
  const payload = guide();
  payload.fictional_examples = ['2', '12'].map((quantity, index) => ({fictional:true,
    components:[{label:'Each month',amount:'100.00',quantity:'12',priced_period:'month'},
      {label:'Visits',amount:'25.00',quantity,priced_period:'visit'}],
    unknown_components:['drug_costs','unpriced_services'],receipt:{
      output_state:'fictional_fixture_only',claim_kind:'declared_scenario_subtotal',
      complete_total:null,quote:null,subtotal:{amount:index ? '1500.00' : '1250.00',currency:'USD',period:'2026'}}}));
  const result = render(payload, {document});
  assert.ok(result.textContent.includes('invented prices, not Medicare costs or a quote'));
  assert.ok(result.textContent.includes('$1250.00'));
  assert.ok(result.textContent.includes('Drug costs and other unpriced services remain unknown'));
  const select = nodes(result).find(node => node.tag === 'select');
  select.value = '1';select.events.change();
  assert.ok(result.textContent.includes('$1500.00'));
  assert.ok(!result.textContent.includes('$1250.00'));
  assert.ok(nodes(result).some(node => node.attributes['aria-live'] === 'polite'));
});

test('unaccepted, inconsistent and malformed guide envelopes fail closed', () => {
  for (const change of [value => value.personal_authority = 'accepted',
    value => value.personal_result = {total:'0'}, value => value.coverage_year = 2027,
    value => value.purpose = 'recommendation', value => value.version = 'other',
    value => value.evidence_refs = {}, value => value.blocks[0].evidence_refs = ['missing'],
    value => value.visual = 'transition']) {
    const payload = guide();change(payload);assert.equal(render(payload, {document}), null);
  }
});

test('source and reported strings are literal text with no executable markup', () => {
  const payload = guide();payload.blocks[0].text = '<img src=x onerror=alert(1)><script>bad()</script>';
  const result = render(payload, {document});
  assert.ok(result.textContent.includes(payload.blocks[0].text));
  assert.ok(!nodes(result).some(node => ['img','script','iframe'].includes(node.tag)));
});

test('the production visual router honors registry suppression before legacy enrichment', () => {
  const source = fs.readFileSync(path.join(__dirname,'../web/advisor.js'),'utf8');
  const start = source.indexOf('  function turnVisual('), end = source.indexOf('  function inlineGuide(',start);
  assert.ok(start > 0 && end > start);
  const route = vm.runInNewContext('(' + source.slice(start,end).trim() + ')');
  const prior = {advisor:{visual:'original',teachingFactIds:['parts']}};
  assert.equal(route({...prior,understanding:{state:'unavailable',visual:null}}),null);
  const limited = guide('coverage_paths',[
    block('original_base','Original Medicare','Parts A and B through the federal program.',{route:'original'})]);
  limited.visual = 'original';
  const visual = route({...prior,understanding:limited});
  assert.equal(visual.kind,'understanding');
  const result = render(visual.guide,{document});
  assert.ok(!result.textContent.includes('Part D'));
  assert.ok(!result.textContent.includes('Medigap'));
});
