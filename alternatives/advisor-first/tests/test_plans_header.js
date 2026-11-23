'use strict';
// Execute the real header rendering block, with fictional enrollment and DOM.
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');
const source = readFileSync(__dirname + '/../web-8894/plans-workspace.js', 'utf8');
const start = source.indexOf('    const sticky =');
const end = source.indexOf('    host.append(sticky); headerOffset();', start);
const code = source.slice(start, end) + '\n globalThis.header = sticky;';
function render(view) {
  let steps = 0;
  const context = {view, pathTab: 'advantage', maLocal: null, STEP_VIEW: {}, close() {}, showView() {},
    enroll: () => ({retained: 'A and B dates and plan decisions'}), currentStep: () => 'plan',
    kinds: () => 'Plan tabs', button: text => text, withIcon: value => value,
    el: () => ({children: [], append(...items) {this.children.push(...items);}}),
    window: {DaylightEnrollment: {steps() {steps++; return 'Numbered enrollment decisions';}}}};
  vm.runInNewContext(code, context);
  return {steps, children: Array.from(context.header.children)};
}
test('plan lists go from tabs and Back straight to the plan content', () => {
  for (const view of ['advantage', 'supplement', 'part-d']) {
    assert.deepEqual(render(view), {steps: 0, children: ['Plan tabs', 'Back to my conversation']});
  }
});
test('enrollment decisions remain on enrollment and drug-check steps', () => {
  for (const view of ['ab', 'advantage-drugs']) assert.equal(render(view).steps, 1);
});
