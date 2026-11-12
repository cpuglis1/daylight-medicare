/* Contextual, text-first diagrams from the server's versioned guide contract. */
(function (root) {
  'use strict';
  const version = 'understanding-20261103-r1';
  function render(guide, options = {}) {
    if (!guide || guide.version !== version || guide.state !== 'educational' ||
        guide.purpose !== 'general_education' || guide.coverage_year !== 2026 ||
        guide.personal_authority !== 'held' || guide.personal_result !== null ||
        !Array.isArray(guide.evidence_refs) || !Array.isArray(guide.blocks) || !guide.blocks.length) return null;
    const doc = options.document || root.document;
    const create = (tag, text, className) => {
      const node = doc.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (className) node.className = className;
      return node;
    };
    const host = create('section', undefined, 'inline-guide understanding-guide');
    host.setAttribute('aria-label', guide.title);
    host.append(create('h3', guide.title, 'guide-title'));
    const blocks = guide.blocks.filter(block => typeof block.id === 'string' && typeof block.label === 'string' &&
      typeof block.text === 'string' && Array.isArray(block.evidence_refs) &&
      block.evidence_refs.length && block.evidence_refs.every(ref => guide.evidence_refs?.includes(ref)));
    if (!blocks.length) return null;
    const blockNode = block => {
      const item = create('div', undefined, 'understanding-block');
      item.append(create('h4', block.label), create('p', block.text));
      return item;
    };
    if (guide.capability === 'coverage_paths') {
      if (!['routes', 'original', 'advantage'].includes(guide.visual)) return null;
      const paths = create('div', undefined, 'understanding-paths');
      for (const [route, label] of [['original', 'Original Medicare'], ['advantage', 'Medicare Advantage']]) {
        const items = blocks.filter(block => block.route === route);
        if (!items.length) continue;
        const path = create('section', undefined, 'understanding-path');
        path.setAttribute('aria-label', label);
        const heading = create('h4');
        if (typeof options.explain === 'function') {
          const explain = create('button', label, 'text-button guide-concept-link');
          explain.type = 'button';explain.setAttribute('aria-label', 'Explain ' + label);
          explain.addEventListener('click', () => options.explain(route));heading.append(explain);
        } else heading.textContent = label;
        path.append(heading);
        for (const block of items) {
          // Base blocks already have the route label as their heading.
          if (block.id.endsWith('_base')) path.append(create('p', block.text));
          else path.append(blockNode(block));
        }
        paths.append(path);
      }
      host.append(paths);
      for (const block of blocks.filter(block => !block.route)) host.append(blockNode(block));
    } else if (guide.capability === 'transition') {
      if (guide.visual !== 'transition') return null;
      if (Array.isArray(guide.reported_dates) && guide.reported_dates.length) {
        host.append(create('p', 'Dates you’ve shared · reported, with precision kept as entered', 'diagram-caption'));
        const dates = create('ol', undefined, 'timeline');
        for (const entry of guide.reported_dates.filter(row => row.state === 'reported')) {
          const row = create('li');
          row.append(create('span', entry.label), create('strong', entry.value));dates.append(row);
        }
        host.append(dates);
      }
      const steps = create('ol', undefined, 'understanding-steps');
      for (const block of blocks) {
        const row = create('li');row.append(blockNode(block));steps.append(row);
      }
      host.append(steps);
      if (Array.isArray(guide.open_checks) && guide.open_checks.length) {
        host.append(create('h4', 'Still to confirm'));
        const checks = create('ul', undefined, 'understanding-checks');
        for (const text of guide.open_checks) checks.append(create('li', text));
        host.append(checks);
      }
      if (typeof options.reviewDates === 'function' && guide.reported_dates?.length) {
        const edit = create('button', 'Review or correct dates', 'text-button');
        edit.type = 'button';edit.addEventListener('click', options.reviewDates);host.append(edit);
      }
    } else if (guide.capability === 'costs') {
      if (guide.visual !== 'costs') return null;
      const layers = create('div', undefined, 'understanding-costs');
      for (const block of blocks) layers.append(blockNode(block));
      host.append(layers);
      const examples = (Array.isArray(guide.fictional_examples) ? guide.fictional_examples : []).filter(example =>
        example.fictional === true && example.receipt?.output_state === 'fictional_fixture_only' &&
        example.receipt?.claim_kind === 'declared_scenario_subtotal' &&
        example.receipt?.complete_total === null && example.receipt?.quote === null &&
        example.receipt?.subtotal?.currency === 'USD' && example.receipt?.subtotal?.period === '2026' &&
        Array.isArray(example.components) && Array.isArray(example.unknown_components));
      if (examples.length) {
        const demonstration = create('details', undefined, 'understanding-example');
        demonstration.append(create('summary', 'See how care use changes a cost example'));
        demonstration.append(create('p', 'Fictional example · invented prices, not Medicare costs or a quote.', 'diagram-caption'));
        const label = create('label', 'Visits in this example');
        const select = create('select');select.setAttribute('aria-label', 'Visits in this fictional example');
        for (const [index, example] of examples.entries()) {
          const visits = example.components.find(component => component.priced_period === 'visit');
          const option = create('option', (visits?.quantity || 'No') + ' visits');
          option.value = String(index);select.append(option);
        }
        label.append(select);demonstration.append(label);
        const result = create('div', undefined, 'understanding-example-result');
        result.setAttribute('aria-live', 'polite');
        const draw = () => {
          const example = examples[Number(select.value) || 0];
          result.replaceChildren();
          const list = create('dl', undefined, 'understanding-amounts');
          for (const component of example.components) {
            const row = create('div');
            row.append(create('dt', component.label), create('dd', '$' + component.amount + ' × ' +
              component.quantity + ' ' + ({month:'months',visit:'visits',fill:'fills'}[component.priced_period] || component.priced_period)));
            list.append(row);
          }
          const subtotal = create('div');subtotal.append(create('dt', 'Subtotal for listed costs in 2026'),
            create('dd', '$' + example.receipt.subtotal.amount));list.append(subtotal);result.append(list);
          result.append(create('p', 'Drug costs and other unpriced services remain unknown. This subtotal is not a total spending limit.'));
        };
        select.addEventListener('change', draw);draw();demonstration.append(result);host.append(demonstration);
      }
    } else return null;
    return host;
  }
  root.DaylightUnderstanding = {render};
  if (typeof module !== 'undefined' && module.exports) module.exports = {render};
})(typeof globalThis !== 'undefined' ? globalThis : this);
