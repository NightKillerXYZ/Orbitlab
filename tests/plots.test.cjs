/* Node tests for UIUX/OrbitlabUI Main/plots.js (pure functions + stubbed hover).
   Run: node --test tests/plots.test.cjs */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');

const P = require('../UIUX/OrbitlabUI Main/plots.js');

test('mu table uses the specified values', () => {
  assert.deepEqual(P.MU_KM3_S2, {
    Earth: 398600.4418, Moon: 4902.800066, Mars: 42828.37362, Mercury: 22031.78,
    Venus: 324858.592, Jupiter: 126712764.1, Sun: 132712440018,
  });
  assert.equal(P.bodyMu('Earth'), 398600.4418);
  assert.equal(P.bodyMu('Pluto'), null);
});

test('decimation keeps first and last within budget', () => {
  const d = P.decimateIndices(5001, 1500);
  assert.ok(d.length <= 1500, 'got ' + d.length);
  assert.equal(d[0], 0);
  assert.equal(d[d.length - 1], 5000);
  const gaps = [];
  for (let k = 1; k < d.length; k++) gaps.push(d[k] - d[k - 1]);
  assert.ok(Math.max(...gaps) - Math.min(...gaps) <= 1, 'evenly spaced');
  assert.deepEqual(P.decimateIndices(10, 1500), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.deepEqual(P.decimateIndices(0, 1500), []);
});

test('time unit selection', () => {
  assert.equal(P.chooseTimeUnit(45).unit, 's');
  assert.equal(P.chooseTimeUnit(600).unit, 'min');
  assert.equal(P.chooseTimeUnit(5400).unit, 'min');
  assert.equal(P.chooseTimeUnit(9000).unit, 'h');
  assert.equal(P.chooseTimeUnit(200000).unit, 'd');
  assert.equal(P.chooseTimeUnit(9000).fmt(1.5), '1.50');
});

test('circular orbit elements from r and v', () => {
  // r = 7000 km circular, Earth mu = 398600.4418: v = sqrt(mu/r) = 7.5461 km/s.
  // vis-viva: a = 1/(2/7000 - v^2/mu) = 7000; e-vector = 0  =>  e about 0.
  const v = Math.sqrt(398600.4418 / 7000);
  const el = P.orbitalElementsKm(7000, 0, 0, 0, v, 0, 398600.4418);
  assert.ok(Math.abs(el.a - 7000) < 1e-6, 'a=' + el.a);
  assert.ok(el.e < 1e-9, 'e=' + el.e);
  assert.equal(P.orbitalElementsKm(0, 0, 0, 0, 0, 0, 398600.4418), null);
  assert.equal(P.orbitalElementsKm(7000, 0, 0, 0, 7, 0, null), null);
});

test('Hohmann Earth 6678 -> 42164 km analytic values', () => {
  // r1 = 6678, r2 = 42164, mu = 398600.4418, at = 24421.
  // dv1 = sqrt(mu/r1)*(sqrt(2*r2/(r1+r2))-1) = 2.43 km/s
  // dv2 = sqrt(mu/r2)*(1-sqrt(2*r1/(r1+r2))) = 1.47 km/s
  // t = pi*sqrt(at^3/mu) = 18992 s = 5.27 h
  const h = P.hohmannEstimate(6678, 42164, 398600.4418);
  assert.ok(Math.abs(h.dv1 - 2.43) < 0.02, 'dv1=' + h.dv1);
  assert.ok(Math.abs(h.dv2 - 1.47) < 0.02, 'dv2=' + h.dv2);
  assert.ok(Math.abs(h.total - 3.90) < 0.03, 'total=' + h.total);
  assert.ok(Math.abs(h.transferSecs / 3600 - 5.27) < 0.02, 't=' + h.transferSecs / 3600);
  assert.equal(P.hohmannEstimate(0, 42164, 398600.4418), null);
});

test('line chart carries title, units, css vars, hover hook', () => {
  P.__resetForTests();
  const times = [];
  const vals = [];
  for (let i = 0; i < 5000; i++) { times.push(i * 17.28); vals.push(400 + 10 * Math.sin(i / 100)); }
  const svg = P.lineChartSVG({ title: 'Altitude vs time', unit: 'km', times, vals, color: 'var(--blue,#6faaff)' });
  assert.ok(svg.includes('aria-label="Altitude vs time"'), 'title');
  assert.ok(svg.includes('elapsed time'), 'x axis labelled');
  assert.ok(svg.includes('var(--'), 'css variables, not hard-coded colours');
  assert.ok(svg.includes('onmousemove="Plots.hover('), 'hover read-out hook');
  const ids = Object.keys(P.__registry);
  assert.equal(ids.length, 1);
  // 5000 points decimated to <= 1500 but axis span covers the full range
  assert.ok(P.__registry[ids[0]].times.length <= 1500, 'decimated');
  assert.equal(P.__registry[ids[0]].times[0], 0, 'first kept');
  assert.ok(svg.includes('No data') === false);
  assert.ok(P.lineChartSVG({ title: 't', unit: 'km', times: [], vals: [] }).includes('No data'));
});

test('hover resolves nearest sample and writes the readout', () => {
  P.__resetForTests();
  const svg = P.lineChartSVG({ title: 't', unit: 'km', times: [0, 10, 20], vals: [400, 410, 405], color: 'red' });
  const id = Object.keys(P.__registry)[0];
  assert.ok(svg.includes(id + '-ro'), 'readout group present');
  const seen = {};
  const mkEl = () => ({
    setAttribute(k, v) { seen[k] = v; },
    set textContent(v) { seen.text = v; },
    get textContent() { return seen.text; },
  });
  global.document = { querySelector: () => mkEl() };
  try {
    assert.equal(P.hover({ clientX: 200, currentTarget: { getBoundingClientRect: () => ({ left: 0, width: 260 }) } }, id), true);
    assert.ok(String(seen.text).startsWith('t='), 'readout text: ' + seen.text);
    assert.ok(String(seen.text).includes('km'), 'readout units: ' + seen.text);
    assert.equal(P.leave(id), true);
    assert.equal(P.hover({ clientX: 0 }, 'nope'), false);
  } finally {
    delete global.document;
  }
});
