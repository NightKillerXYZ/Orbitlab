/* Render-level tests for UIUX/OrbitlabUI Main/app.js using a minimal fake DOM
   (no jsdom available offline). Run: node --test tests/ui_render.test.cjs
   Drives renderRealRun/drawCraft/liveBody with the real fixture result. */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

class El {
  constructor(tag) {    this.tagName = tag;
    this.children = [];
    this.parent = null;
    this.style = {};
    this.dataset = {};
    this.className = '';
    this.attrs = {};
    this._text = '';
    this._html = '';
    this.classList = { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false };
  }
  set textContent(v) { this._text = String(v); }
  get textContent() { return this._text; }
  set id(v) { this.attrs.id = String(v); }
  get id() { return this.attrs.id || ''; }
  set innerHTML(v) { this._html = String(v); }
  get innerHTML() { return this._html; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  addEventListener() {}
  removeEventListener() {}
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  before(n) {
    if (this.parent) {
      const i = this.parent.children.indexOf(this);
      this.parent.children.splice(i < 0 ? this.parent.children.length : i, 0, n);
      n.parent = this.parent;
    }
  }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this);
  }
  closest() { return null; }
  get parentElement() { return this.parent; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100 }; }
  focus() {}
  click() {}
}

function matchPart(el, part) {
  part = part.trim();
  let notCls = null;
  const ni = part.indexOf(':not(');
  if (ni >= 0) {
    const m = part.match(/:not\(([^)]+)\)/);
    if (m) notCls = m[1].replace(/^\./, '');
    part = part.slice(0, ni).trim();
  }
  let ok = false;
  if (part.includes('>')) {
    const [ps, cs] = part.split('>').map((s) => s.trim());
    ok = matchPart(el, cs) && (() => {
      let p = el.parent;
      while (p) { if (matchPart(p, ps)) return true; p = p.parent; }
      return false;
    })();
  } else if (part.includes(' ')) {
    const bits = part.split(/\s+/);
    const last = bits[bits.length - 1];
    const first = bits.slice(0, -1).join(' ');
    ok = matchPart(el, last) && (() => {
      let p = el.parent;
      while (p) { if (matchPart(p, first)) return true; p = p.parent; }
      return false;
    })();
  } else if (part.startsWith('#')) {
    ok = el.attrs.id === part.slice(1);
  } else if (part.startsWith('.')) {
    ok = (' ' + (el.className || '') + ' ').includes(' ' + part.slice(1) + ' ');
  } else if (part) {
    ok = el.tagName === part;
  }
  if (ok && notCls) {
    if ((' ' + (el.className || '') + ' ').includes(' ' + notCls + ' ')) return false;
  }
  return ok;
}

function collect(el, parts, out) {
  for (const c of el.children) {
    if (parts.some((p) => matchPart(c, p))) out.push(c);
    collect(c, parts, out);
  }
  return out;
}

function qsa(root, selector) {
  return collect(root, String(selector).split(',').map((s) => s.trim()).filter(Boolean), []);
}

function wire(el, doc) {
  el.querySelector = (s) => qsa(doc.root, s)[0] || qsa(el, s)[0] || null;
  el.querySelectorAll = (s) => qsa(el, s);
  return el;
}

const doc = { root: new El('root') };
function freshEl() {
  const el = new El('div');
  el.querySelector = (s) => qsa(doc.root, s)[0] || freshEl();
  el.querySelectorAll = (s) => qsa(doc.root, s);
  return el;
}
doc.querySelector = (s) => qsa(doc.root, s)[0] || freshEl();
doc.querySelectorAll = (s) => qsa(doc.root, s);
doc.createElement = (t) => wire(new El(t), doc);
doc.createElementNS = (ns, t) => wire(new El(t), doc);
doc.body = wire(new El('body'), doc);

function add(parent, tag, opts) {
  const el = wire(new El(tag), doc);
  if (opts) {
    if (opts.id) el.setAttribute('id', opts.id);
    if (opts.cls) el.className = opts.cls;
    if (opts.text) el.textContent = opts.text;
  }
  parent.appendChild(el);
  return el;
}

// Minimal page skeleton mirroring index.html structure.
const vis = add(doc.root, 'div', { id: 'orbitVisual', cls: 'orbit-visual' });
add(vis, 'div', { cls: 'space-grid' });
add(vis, 'div', { cls: 'orbit-path path-main' });
add(vis, 'div', { cls: 'orbit-label label-venus', text: 'VENUS' });
add(vis, 'div', { cls: 'label-sun orbit-label', text: 'THE SUN' });
add(vis, 'div', { cls: 'sun-glow' });
add(vis, 'div', { cls: 'sun-core' });
add(vis, 'div', { id: 'venusPlanet', cls: 'planet venus-planet' });
add(vis, 'div', { cls: 'orbit-axis' });
add(vis, 'div', { cls: 'distance-label', text: '0.72 AU' });
add(vis, 'div', { cls: 'scale-label', text: 'NOT TO SCALE' });
const cap = add(vis, 'div', { cls: 'visual-caption' });
add(cap, 'span', { cls: 'caption-dot' });
add(cap, 'span', { text: 'VENUS' });
add(cap, 'b', { id: 'captionSpeed', text: '35.0 km/s' });
const row = add(doc.root, 'div', { cls: 'telemetry-row' });
const crumbs = add(doc.root, 'div', { cls: 'breadcrumbs' });
add(crumbs, 'span', { text: 'My missions' });
const crumbB = add(crumbs, 'b', { text: 'Venus in Motion' });
const welcome = add(doc.root, 'div', { cls: 'welcome-row' });
const h1 = add(welcome, 'h1', { text: 'Venus in Motion' });
add(welcome, 'p', { text: 'Explore gravity.' });
add(doc.root, 'div', { cls: 'card-subtitle', text: 'Observe Venus' });
const topline = add(doc.root, 'div', { cls: 'card-topline' });
add(topline, 'div', { cls: 'view-toggle' });
for (let i = 0; i < 3; i++) add(doc.root, 'button', { cls: 'suggestion', text: 'chip' });
add(doc.root, 'b', { id: 'simTime', text: 'DAY 0.00' });
add(doc.root, 'div', { id: 'timelineFill' });
add(doc.root, 'span', { id: 'timelineKnob' });
add(doc.root, 'button', { id: 'playBtn', text: '▶' });
add(doc.root, 'span', { id: 'runText', text: 'PAUSED' });
add(doc.root, 'button', { id: 'exportBtn' });
add(doc.root, 'button', { id: 'resultsExport' });
const gdate = add(doc.root, 'time', { id: 'globalDate' });
add(gdate, 'span', { text: '' });
add(gdate, 'span', { text: '' });
const topbar = add(doc.root, 'div', { cls: 'topbar' });
const topActions = add(topbar, 'div', { cls: 'top-actions' });
add(topActions, 'span', { cls: 'live-status', text: 'SIMULATION READY' });

global.document = doc;
global.window = global;
global.location = { search: '', href: 'http://localhost/', origin: 'http://localhost' };
global.setInterval = () => 0;
global.clearTimeout = () => {};
global.setTimeout = () => 0;

const app = require('../UIUX/OrbitlabUI Main/app.js');
const fix = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'real_result_earth.json'), 'utf-8'));

test('renderRealRun draws the Earth run and clears sample decor', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  const svg = doc.querySelector('#runOrbit');
  assert.ok(svg, 'overlay svg exists');
  const pl = svg.children.find((c) => c.tagName === 'polyline');
  assert.ok(pl, 'path polyline exists');
  assert.ok(pl.getAttribute('points').split(' ').length > 1000, 'all points drawn');
  const craft = svg.children.find((c) => c.getAttribute('id') === 'runCraft');
  assert.ok(craft, 'spacecraft marker exists');
  assert.equal(doc.querySelectorAll('#noTraj').length, 0);
  assert.equal(doc.querySelector('.label-venus').style.display, 'none');
  assert.equal(doc.querySelector('.distance-label').style.display, 'none');
  assert.equal(doc.querySelector('#venusPlanet').style.display, 'none');
  assert.equal(doc.querySelector('.sun-core').style.display, 'none');
  const badge = doc.querySelector('#runBadge');
  assert.ok(badge && badge.textContent === 'LIVE DATA');
  assert.equal(crumbB.textContent, 'Earth orbit');
  assert.ok(h1.innerHTML.includes('Earth'));
  const trow = doc.querySelector('.telemetry-row');
  assert.ok(trow, 'stat row exists');
  assert.equal((trow.innerHTML.match(/<div>/g) || []).length, 5, 'five stat cells');
  assert.ok(trow.innerHTML.includes('1.54 hours'), 'period cell: ' + trow.innerHTML);
  assert.ok(trow.innerHTML.includes('PERIAPSIS ALT'), 'periapsis cell');
  assert.ok(/3\d\d\.\d km/.test(trow.innerHTML), 'periapsis value ~380s km');
  assert.ok(trow.innerHTML.includes('0.00'), 'inclination cell');
});

test('drawCraft moves the marker and updates live numbers', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  app.__test__.anim(43200);
  app.__test__.draw();
  const craft = doc.querySelector('#runCraft');
  assert.ok(craft.getAttribute('cx') !== null);
  const capEl = doc.querySelector('#captionSpeed');
  assert.ok(/km\/s/.test(capEl.textContent), 'live speed: ' + capEl.textContent);
  assert.equal(doc.querySelector('#simTime').textContent, 'T+12:00:00');
});

test('zero points shows the no-trajectory note, tabs say n/a', () => {
  const empty = JSON.parse(JSON.stringify(fix.result));
  empty.trajectory.points = [];
  app.__test__.setResult(empty);
  app.__test__.render();
  assert.ok(doc.querySelector('#noTraj'), 'note shown');
  assert.equal(doc.querySelectorAll('#runOrbit').length, 0);
  const chat = app.liveBody('Chat');
  assert.ok(chat.includes('n/a'), 'chat shows n/a');
  const graph = app.liveBody('Graph');
  assert.ok(graph.includes('no trajectory returned'));
});

test('tabs carry real data with units', () => {
  app.__test__.setResult(fix.result);
  const results = app.liveBody('Results');
  assert.ok(results.includes('1.54 hours'));
  assert.ok(results.includes('MIN ALTITUDE'));
  assert.ok(results.includes('MAX SPEED'));
  assert.ok(results.includes('Final state'));
  assert.ok(results.includes('interpreter_name_overridden'));
  const graph = app.liveBody('Graph');
  assert.ok(graph.includes('ALTITUDE vs TIME'));
  assert.ok(graph.includes('SPEED vs TIME'));
  assert.equal((graph.match(/<svg/g) || []).length, 2);
  const und = app.liveBody('Understanding');
  assert.ok(und.includes('ElapsedDays 1'));
  assert.ok(und.includes('4x4'));
  const phys = app.liveBody('Physics');
  assert.ok(phys.includes('circular orbit around Earth'));
});

test('failure banner shows the extractor_unavailable message and explanation', () => {
  app.__test__.setResult(null);
  app.__test__.setError({
    stage: 'extract',
    code: 'extractor_unavailable',
    message: 'The language model that reads your request is starting up or unreachable. Please try again in a minute.',
    details: { explanation: 'The language model that reads your request is starting up or unreachable. Please try again in a minute.' },
  });
  const chat = app.liveBody('Chat');
  assert.ok(chat.includes('Run failed at extract'), 'failure banner stage');
  assert.ok(chat.includes('starting up or unreachable'), 'failure message shown');
  assert.ok(chat.includes('Please try again in a minute'), 'explanation shown');
  assert.ok(!chat.includes('More information needed'), 'not the clarification banner');
  app.__test__.setError(null);
});

test('demo badge shows only in demo mode', () => {
  app.updateDemoBadge(false);
  assert.equal(doc.querySelectorAll('#demoBadge').length, 0);
  app.updateDemoBadge(true);
  const badge = doc.querySelector('#demoBadge');
  assert.ok(badge, 'badge added');
  assert.equal(badge.textContent, 'DEMO MODE');
  app.updateDemoBadge(false);
  assert.equal(doc.querySelectorAll('#demoBadge').length, 0, 'badge removed');
  app.__test__.setResult(Object.assign({}, fix.result, { mode: 'demo' }));
  app.updateDemoBadge(!!(app.__test__.getResult() && app.__test__.getResult().mode === 'demo'));
  assert.equal(doc.querySelectorAll('#demoBadge').length, 1, 'result mode drives badge');
  app.updateDemoBadge(false);
  app.__test__.setResult(null);
});

test('clearRunDrawing removes the overlay for a fresh draw', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  assert.ok(doc.querySelector('#runOrbit'));
  app.__test__.clear();
  assert.equal(doc.querySelectorAll('#runOrbit').length, 0);
});
