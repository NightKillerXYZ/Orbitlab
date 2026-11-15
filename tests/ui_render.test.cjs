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
  select() {}
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
doc.execCommand = () => true;
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
add(doc.root, 'span', { id: 'speedMetric', text: '35.0 km/s' });
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
const speedSel = add(doc.root, 'select', { id: 'speedSelect' });
speedSel.value = '0.5';
const speedCustom = add(doc.root, 'input', { id: 'speedCustom' });
speedCustom.value = '0.5'; speedCustom.hidden = true;
add(doc.root, 'span', { id: 'speedReadout' });
add(doc.root, 'div', { id: 'toast' });
add(doc.root, 'button', { id: 'exportBtn' });
add(doc.root, 'button', { id: 'resultsExport' });
const gdate = add(doc.root, 'time', { id: 'globalDate' });
add(gdate, 'span', { text: '' });
add(gdate, 'span', { text: '' });
const topbar = add(doc.root, 'div', { cls: 'topbar' });
const topActions = add(topbar, 'div', { cls: 'top-actions' });
add(topActions, 'span', { cls: 'live-status', text: 'SIMULATION READY' });
// Static singletons mirroring index.html (footer, user card, sim controls).
add(doc.root, 'div', { cls: 'profile' });
add(doc.root, 'div', { cls: 'simulation-controls' });
add(doc.root, 'div', { cls: 'app-footer' });

global.document = doc;
global.window = global;
global.GroundTrack = require('../UIUX/OrbitlabUI Main/groundtrack.js');
global.location = { search: '', href: 'http://localhost/', origin: 'http://localhost' };
global.setInterval = () => 0;
global.clearTimeout = () => {};
global.setTimeout = () => 0;
global.Plots = require('../UIUX/OrbitlabUI Main/plots.js');

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
  assert.ok(trow.innerHTML.includes('ECCENTRICITY'), 'eccentricity cell');
  assert.ok(trow.innerHTML.includes('0.001'), 'stats-derived e=0.001: ' + trow.innerHTML);
  assert.ok(trow.innerHTML.includes('INCLINATION'), 'inclination cell');
  assert.ok(trow.innerHTML.includes('0.01'), 'telemetry-derived i=0.01: ' + trow.innerHTML);
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
  assert.ok(graph.includes('SEMI-MAJOR AXIS vs TIME (computed from telemetry)'));
  assert.ok(graph.includes('ECCENTRICITY vs TIME (computed from telemetry)'));
  assert.equal((graph.match(/<svg/g) || []).length, 4);
  assert.ok(graph.includes('elapsed time'), 'time axis labelled');
  const und = app.liveBody('Understanding');
  assert.ok(und.includes('ElapsedDays 1'));
  assert.ok(und.includes('4x4'));
  const phys = app.liveBody('Physics');
  assert.ok(phys.includes('circular orbit around Earth'));
  app.__test__.setResult(fix.result);
});

test('Results shows a Hohmann maneuver table with analytic estimates', () => {
  const hoh = JSON.parse(JSON.stringify(fix.result));
  hoh.experiment.initialOrbit.elements.semiMajorAxisKm = 7000;
  hoh.experiment.initialOrbit.elements.eccentricity = 0;
  hoh.experiment.maneuvers = [{
    id: 'M1', type: 'TargetedHohmannTransfer',
    trigger: { condition: 'AtPeriapsis' },
    targetObjectives: { targetOrbitRadiusKm: 9000 },
  }];
  app.__test__.setResult(hoh);
  const html = app.liveBody('Results');
  assert.ok(html.includes('MANEUVERS'), 'maneuver section');
  assert.ok(html.includes('M1'), 'maneuver id');
  assert.ok(html.includes('Hohmann transfer'), 'maneuver type');
  assert.ok(html.includes('AtPeriapsis'), 'trigger');
  assert.ok(html.includes('9,000.0 km'), 'target radius');
  assert.ok(html.includes('analytic estimate'), 'estimates labelled analytic');
  assert.ok(/Delta-v 1 \(analytic estimate\)/.test(html), 'dv1 row');
  assert.ok(!html.includes('from simulation'), 'no sim values in this data');
  app.__test__.setResult(fix.result);
});

test('failure banner explains extractor_unavailable in plain words', () => {
  app.__test__.setResult(null);
  app.__test__.setError({
    stage: 'extract',
    code: 'extractor_unavailable',
    message: 'The language model that reads your request is starting up or unreachable. Please try again in a minute.',
    details: { explanation: 'The language model that reads your request is starting up or unreachable. Please try again in a minute.' },
  });
  const chat = app.liveBody('Chat');
  assert.ok(chat.includes('mission reader is unavailable'), 'plain-language banner');
  assert.ok(chat.includes('try again in a minute'), 'retry hint kept');
  assert.ok(chat.includes('spacecraft mass'), 'field hint kept');
  assert.ok(!chat.includes('Run failed at extract'), 'no raw stage banner');
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

test('Graph tab shows an approximate ground track canvas for Earth runs', () => {
  app.__test__.setResult(fix.result);
  const html = app.liveBody('Graph');
  assert.ok(html.includes('<canvas id="groundTrack"'), 'canvas present');
  assert.ok(html.includes('GROUND TRACK (APPROXIMATE)'), 'approx label');
  const calls = [];
  const cv = add(doc.root, 'canvas', { id: 'groundTrack' });
  cv.getContext = () => ({
    set fillStyle(v) {}, set strokeStyle(v) {}, set font(v) {}, set textAlign(v) {},
    set lineWidth(v) {},
    fillRect(x, y, w, h) { calls.push('bg'); },
    beginPath() {}, moveTo(x, y) { calls.push('move'); }, lineTo(x, y) { calls.push('line'); },
    stroke() { calls.push('stroke'); }, arc() { calls.push('arc'); }, fill() {},
    fillText(t) { calls.push('label:' + t); },
  });
  app.__test__.paint();
  assert.ok(calls.includes('bg'), 'map background painted');
  assert.ok(calls.includes('stroke'), 'track stroked');
  assert.ok(calls.some((c) => String(c).startsWith('label:') && c.includes('°')), 'degree labels');
  assert.ok(calls.filter((c) => c === 'arc').length >= 2, 'start and end markers');
  cv.remove();
  app.__test__.setResult(null);
});

test('Graph tab shows the non-Earth message for other bodies', () => {
  const mars = JSON.parse(JSON.stringify(fix.result));
  mars.experiment.centralBody = 'Mars';
  app.__test__.setResult(mars);
  const html = app.liveBody('Graph');
  assert.ok(!html.includes('<canvas id="groundTrack"'), 'no canvas for Mars');
  assert.ok(html.includes('Ground track is available for Earth runs'), 'non-Earth message');
  app.__test__.setResult(null);
});

test('clearRunDrawing removes the overlay for a fresh draw', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  assert.ok(doc.querySelector('#runOrbit'));
  app.__test__.clear();
  assert.equal(doc.querySelectorAll('#runOrbit').length, 0);
});

test('Details tab renders experiment JSON escaped and read-only', () => {
  app.__test__.setResult({ experiment: { centralBody: 'Earth', note: '<b>&"' } });
  app.__test__.setJob(null);
  const html = app.liveBody('Details');
  assert.ok(html.includes('EXPERIMENT JSON'));
  assert.ok(html.includes('centralBody'));
  assert.ok(html.includes('&lt;b&gt;&amp;'), 'escaped, not raw HTML');
  assert.ok(!html.includes('<b>'), 'no raw tags');
  assert.ok(html.includes('data-copy="experiment"'), 'copy button present');
  assert.ok(html.includes('Generated by an AI model'), 'notice present');
  assert.ok(html.includes('No script available for this run'), 'no script without job id');
  app.__test__.setResult(null);
});

test('Details tab script loading, success and failure states', async () => {
  app.__test__.setResult(fix.result);
  app.__test__.setJob('job-1');
  global.fetch = async (url) => {
    assert.ok(String(url).includes('/api/experiments/job-1/script'), 'id in route: ' + url);
    return { ok: true, text: async () => 'GMAT SCRIPT TEXT' };
  };
  try {
    let html = app.liveBody('Details');
    assert.ok(html.includes('Loading GMAT script'), 'loading state first');
    await app.loadScript('job-1');
    html = app.liveBody('Details');
    assert.ok(html.includes('GMAT SCRIPT TEXT'), 'script shown');
    assert.ok(html.includes('data-copy="script"'), 'script copy button present');
  } finally {
    delete global.fetch;
  }
  global.fetch = async () => { throw new Error('down'); };
  try {
    app.__test__.setJob('job-2');
    let html = app.liveBody('Details');
    assert.ok(html.includes('Loading GMAT script'), 'loading state first');
    await app.loadScript('job-2');
    html = app.liveBody('Details');
    assert.ok(html.includes('No script available for this run'), 'error state');
  } finally {
    delete global.fetch;
  }
  app.__test__.setJob(null);
  app.__test__.setResult(null);
  app.__test__.setScript(null, null);
});

test('copy handler copies experiment JSON and script text', () => {
  const seen = [];
  doc.execCommand = (cmd) => { seen.push(cmd); return true; };
  app.__test__.setResult({ experiment: { centralBody: 'Earth' } });
  app.__test__.setScript('job-9', 'GMAT SCRIPT TEXT');
  const evExp = { target: { closest: (s) => (s === '[data-copy]' ? { getAttribute: () => 'experiment' } : null) } };
  assert.equal(app.handleCopyClick(evExp), true);
  assert.deepEqual(seen, ['copy'], 'fallback copy used');
  const evScript = { target: { closest: (s) => (s === '[data-copy]' ? { getAttribute: () => 'script' } : null) } };
  assert.equal(app.handleCopyClick(evScript), true);
  assert.deepEqual(seen, ['copy', 'copy']);
  assert.equal(app.handleCopyClick({ target: { closest: () => null } }), false);
  app.__test__.setResult(null);
  app.__test__.setScript(null, null);
});

test('index page has Details tab and research footer', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'UIUX', 'OrbitlabUI Main', 'index.html'), 'utf-8');
  assert.ok(html.includes('data-tab="Details"'), 'Details tab button');
  assert.ok(html.includes('class="app-footer"'), 'footer element');
  assert.ok(html.includes('research and education tool'), 'footer text');
  assert.ok(html.includes('Not for flight operations'), 'footer warning');
});

test('Open in GMAT button shows only when enabled with a job', () => {
  app.__test__.setResult(fix.result);
  app.__test__.setJob(null);
  app.__test__.setOpenGmat(true);
  assert.ok(!app.liveBody('Results').includes('data-open-gmat'), 'no button without job');
  app.__test__.setJob('job-1');
  assert.ok(app.liveBody('Results').includes('data-open-gmat'), 'button when enabled + job');
  app.__test__.setOpenGmat(false);
  assert.ok(!app.liveBody('Results').includes('data-open-gmat'), 'no button when disabled');
  app.__test__.setJob(null);
  app.__test__.setResult(fix.result);
});

test('openInGmat posts only the job id and reports the outcome', async () => {
  const calls = [];
  global.fetch = async (url, opts) => {
    calls.push([url, opts]);
    return { ok: true, status: 200, json: async () => ({ status: 'started' }) };
  };
  try {
    app.__test__.setJob('job-9');
    assert.equal(await app.openInGmat(), true);
    assert.deepEqual(calls, [['/api/experiments/job-9/open-in-gmat', { method: 'POST' }]]);
  } finally {
    delete global.fetch;
  }
  global.fetch = async () => ({ ok: false, status: 403, json: async () => ({ detail: 'denied' }) });
  try {
    assert.equal(await app.openInGmat(), false);
  } finally {
    delete global.fetch;
  }
  app.__test__.setJob(null);
  assert.equal(await app.openInGmat(), null);
  app.__test__.setResult(fix.result);
});

test('replay pacing is run-relative: whole run in 60 s at 1x', () => {
  assert.equal(app.REPLAY_TICK_MS, 100, '100ms update interval');
  assert.equal(app.REPLAY_FULL_RUN_SECONDS_AT_1X, 60, '60-second full run at 1x');
  assert.deepEqual(app.SPEED_PRESETS, [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20]);
  assert.equal(app.DEFAULT_SPEED, 0.5, 'default is 0.5x');
  const pts = fix.result.trajectory.points;
  const span = pts[pts.length - 1].elapsed_secs - pts[0].elapsed_secs;
  assert.equal(span, 86400, 'fixture spans one day');
  // per-tick progress = span * speed / 600 (600 ticks per full run)
  assert.equal(app.__test__.replay(600, 1), 1, '1 s of a 600 s run per tick at 1x');
  assert.equal(app.__test__.replay(86400, 0.5), 72, '0.5x of a day-long run');
  assert.equal(app.__test__.replay(86400, 20), 2880, '20x of a day-long run');
  assert.equal(app.__test__.replay(0, 1), 0, 'zero span advances nothing');
  assert.equal(app.__test__.replay(100, 0), 0, 'zero speed advances nothing');
  assert.equal(app.__test__.replay(100, -1), 0, 'negative speed advances nothing');
  assert.equal(app.clampSpeed('0.2'), 0.2);
  assert.equal(app.clampSpeed('100'), 100);
  assert.equal(app.clampSpeed('0.01'), 0.01);
  assert.equal(app.clampSpeed(0), null);
  assert.equal(app.clampSpeed(-3), null);
  assert.equal(app.clampSpeed('101'), null);
  assert.equal(app.clampSpeed('fast'), null);
  assert.equal(app.clampSpeed(NaN), null);
  assert.equal(app.clampSpeed(undefined), null);
});

test('epoch overlay shows frame plus advancing epoch; dataset names wired', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  assert.equal(vis.dataset.spacecraftName, 'SC_Put', 'spacecraft name for the 3D label');
  assert.equal(vis.dataset.bodyName, 'Earth', 'body name for the 3D label');
  assert.equal(app.__test__.frame(), 'EarthMJ2000Eq', 'coordinate frame name');
  assert.equal(app.__test__.craftName(), 'SC_Put', 'spacecraft name helper');
  const raw = fix.result.experiment.epoch.value;
  assert.equal(app.__test__.fmtEpoch(GroundTrack.parseGmatEpoch(raw)), raw, 'epoch formats back identically');
  app.__test__.anim(0);
  app.__test__.draw();
  const ov = doc.querySelector('#epochOverlay');
  assert.ok(ov, 'overlay element exists');
  assert.ok(ov.textContent.includes('EarthMJ2000Eq'), 'frame line: ' + ov.textContent);
  assert.ok(ov.textContent.includes('Epoch: 01 Jan 2026 12:00:00.000'), 'start epoch: ' + ov.textContent);
  app.__test__.anim(43200);
  app.__test__.draw();
  assert.ok(ov.textContent.includes('Epoch: 02 Jan 2026 00:00:00.000'), 'epoch advances with replay: ' + ov.textContent);
  assert.ok(String(ov.style.cssText).includes('top:8px'), 'pinned to the top-left, clear of the HUD');
  app.__test__.setResult(fix.result);
});

test('render wires epoch and names for the 3D view', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  assert.equal(vis.dataset.epochValue, '01 Jan 2026 12:00:00.000', 'epoch for the 3D spin');
  assert.equal(vis.dataset.spacecraftName, 'SC_Put');
  assert.equal(vis.dataset.bodyName, 'Earth');
});

test('provenance caption explains live, cached and sample results', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  app.__test__.meta({ origin: 'live', elapsedSecs: 3.2, jobId: 'job-1' });
  app.__test__.prov();
  let cap = doc.querySelector('#runProvenance');
  assert.ok(cap, 'caption element exists');
  assert.equal(cap.textContent, 'Live GMAT run - 3.2 s');
  app.__test__.meta({ origin: 'live', elapsedSecs: null, jobId: null });
  app.__test__.prov();
  assert.equal(doc.querySelector('#runProvenance').textContent, 'Live GMAT run');
  app.__test__.meta({ origin: 'cache', elapsedSecs: 41.7, jobId: 'job-0' });
  app.__test__.prov();
  assert.equal(doc.querySelector('#runProvenance').textContent,
    'Result from cache (same input as an earlier run)');
  app.__test__.meta({ origin: 'sample', elapsedSecs: null, jobId: null });
  app.__test__.prov();
  assert.equal(doc.querySelector('#runProvenance').textContent, 'Sample data (not a run)');
  app.__test__.meta({ origin: 'mock', elapsedSecs: null, jobId: null });
  app.__test__.prov();
  assert.equal(doc.querySelector('#runProvenance').textContent, 'Sample data (not a run)');
  assert.equal(app.__test__.provText(), 'Sample data (not a run)');
  assert.deepEqual(app.__test__.metaFrom({ fromCache: true, elapsedSeconds: 5, jobId: 'j' }),
    { origin: 'cache', elapsedSecs: 5, jobId: 'j' });
  assert.deepEqual(app.__test__.metaFrom({ mock: true }),
    { origin: 'sample', elapsedSecs: null, jobId: null });
  assert.deepEqual(app.__test__.metaFrom({ elapsedSeconds: 2.5 }),
    { origin: 'live', elapsedSecs: 2.5, jobId: null });
  app.__test__.setResult(fix.result);
});

test('repeated renders stay idempotent: one of each element', () => {
  app.__test__.setResult(fix.result);
  const countAll = () => ({
    footer: doc.querySelectorAll('.app-footer').length,
    profile: doc.querySelectorAll('.profile').length,
    simctrl: doc.querySelectorAll('.simulation-controls').length,
    simTime: doc.querySelectorAll('#simTime').length,
    runOrbit: doc.querySelectorAll('#runOrbit').length,
    epoch: doc.querySelectorAll('#epochOverlay').length,
    prov: doc.querySelectorAll('#runProvenance').length,
  });
  app.__test__.render();
  assert.deepEqual(countAll(),
    { footer: 1, profile: 1, simctrl: 1, simTime: 1, runOrbit: 1, epoch: 1, prov: 1 });
  app.__test__.render();
  app.__test__.render();
  assert.deepEqual(countAll(),
    { footer: 1, profile: 1, simctrl: 1, simTime: 1, runOrbit: 1, epoch: 1, prov: 1 },
    'three consecutive renders still singletons');
  const row = doc.querySelector('.telemetry-row');
  assert.equal((row.innerHTML.match(/<div>/g) || []).length, 5, 'stat cells replaced, not appended');
  app.__test__.setResult(fix.result);
});

test('epoch overlay is hidden in 2D and shown in 3D', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  app.__test__.anim(100);
  app.__test__.draw();
  const ov = doc.querySelector('#epochOverlay');
  assert.ok(ov, 'overlay element exists');
  assert.equal(ov.style.display, 'none', 'hidden in 2D mode');
  const origClassList = vis.classList;
  vis.classList = { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => true };
  try {
    app.__test__.draw();
    assert.equal(ov.style.display, '', 'shown in 3D mode');
    assert.ok(ov.textContent.includes('EarthMJ2000Eq'), 'frame line kept');
  } finally {
    vis.classList = origClassList;
  }
  app.__test__.setResult(fix.result);
});

test('missing epoch uses the schema default everywhere', () => {
  const noEpoch = JSON.parse(JSON.stringify(fix.result));
  delete noEpoch.experiment.epoch;
  app.__test__.setResult(noEpoch);
  app.__test__.render();
  app.__test__.anim(0);
  app.__test__.draw();
  const ov = doc.querySelector('#epochOverlay');
  assert.ok(ov.textContent.includes('Epoch: 01 Jan 2026 12:00:00.000'), 'default epoch shown: ' + ov.textContent);
  assert.ok(ov.textContent.includes('(default epoch)'), 'default tagged: ' + ov.textContent);
  assert.deepEqual(app.__test__.epochParts(0),
    { text: 'Epoch: 01 Jan 2026 12:00:00.000', isDefault: true });
  // ground track still paints with the default epoch
  const calls = [];
  const cv = add(doc.root, 'canvas', { id: 'groundTrack' });
  cv.getContext = () => ({
    fillStyle: null, strokeStyle: null, font: null, textAlign: null, lineWidth: null,
    fillRect(x, y, w, h) { calls.push('bg'); },
    beginPath() {}, moveTo(x, y) {}, lineTo(x, y) { calls.push('line'); },
    stroke() { calls.push('stroke'); }, arc() {}, fill() {},
    fillText(t) { calls.push('label:' + t); },
  });
  app.__test__.paint();
  assert.ok(calls.includes('bg'), 'track paints without an experiment epoch');
  cv.remove();
  app.__test__.setResult(fix.result);
});

test('speed presets advance proportionally; mid-replay change does not jump', () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  for (const s of [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20]) {
    assert.ok(app.__test__.applySpeed(s), 'preset applies: ' + s);
    assert.equal(app.__test__.speed(), s, 'current speed ' + s);
    assert.ok(Math.abs(app.__test__.replay(600, s) - s) < 1e-9, 'per-tick progress at ' + s + 'x');
  }
  app.__test__.anim(43200);
  app.__test__.draw();
  const before = doc.querySelector('#simTime').textContent;
  assert.equal(before, 'T+12:00:00');
  assert.ok(app.__test__.applySpeed(0.05), 'slow down mid-replay');
  app.__test__.draw();
  assert.equal(doc.querySelector('#simTime').textContent, before, 'position unchanged by speed change');
  assert.equal(app.__test__.speed(), 0.05);
});

test('custom speed accepts valid values and reverts invalid ones', () => {
  assert.ok(app.__test__.applySpeed(2.5));
  assert.equal(app.__test__.speed(), 2.5);
  assert.equal(doc.querySelector('#speedSelect').value, 'custom', 'Custom selected');
  for (const bad of [0, -3, 101, 'fast', NaN, undefined, '']) {
    assert.equal(app.__test__.applySpeed(bad), false, 'rejected: ' + String(bad));
    assert.equal(app.__test__.speed(), 2.5, 'reverted after: ' + String(bad));
  }
  assert.ok(app.__test__.applySpeed(0.01), 'min custom');
  assert.equal(app.__test__.speed(), 0.01);
  assert.ok(app.__test__.applySpeed(100), 'max custom');
  assert.equal(app.__test__.speed(), 100);
  assert.ok(app.__test__.applySpeed(0.5), 'back to default');
});

test('readout formats simulated time per second across units', () => {
  assert.equal(app.formatSimRate(90, 1), '= 1.5 s of simulation per second');
  assert.equal(app.formatSimRate(30, 1), '= 0.5 s of simulation per second');
  assert.equal(app.formatSimRate(3600, 1), '= 1.0 min of simulation per second');
  assert.equal(app.formatSimRate(86400, 0.5), '= 12 min of simulation per second');
  assert.equal(app.formatSimRate(172800, 1), '= 48 min of simulation per second');
  assert.equal(app.formatSimRate(86400 * 2, 5), '= 4.0 h of simulation per second');
  assert.equal(app.formatSimRate(86400 * 20, 20), '= 6.7 d of simulation per second');
  assert.equal(app.formatSimRate(0, 1), '', 'unknown duration shows nothing');
  assert.equal(app.formatSimRate(86400, 0), '', 'zero speed shows nothing');
  assert.equal(app.formatSimRate(NaN, 1), '', 'bad span shows nothing');
});

test('speed choice persists in localStorage; throwing storage never breaks', () => {
  const kept = [];
  global.localStorage = {
    getItem: (k) => (k === 'orbitlab.speed' ? '2' : null),
    setItem: (k, v) => kept.push([k, v]),
  };
  try {
    assert.equal(app.loadStoredSpeed(), 2, 'stored value loads');
    assert.ok(app.__test__.applySpeed(5), 'applies with storage present');
    assert.deepEqual(kept[kept.length - 1], ['orbitlab.speed', '5'], 'choice persisted');
  } finally {
    delete global.localStorage;
  }
  assert.equal(app.loadStoredSpeed(), null, 'absent storage means default');
  global.localStorage = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  try {
    assert.equal(app.loadStoredSpeed(), null, 'throwing getItem falls back');
    assert.ok(app.__test__.applySpeed(5), 'throwing setItem does not break apply');
    assert.equal(app.__test__.speed(), 5);
  } finally {
    delete global.localStorage;
  }
});

test('speed dropdown exists once and survives repeated renders', () => {
  const fs = require('node:fs');
  const html = fs.readFileSync(require('node:path').join(__dirname, '..', 'UIUX', 'OrbitlabUI Main', 'index.html'), 'utf-8');
  for (const v of ['0.05', '0.1', '0.2', '0.5', '1', '2', '5', '10', '20', 'custom']) {
    assert.ok(html.includes('value="' + v + '"'), 'option ' + v + ' in index.html');
  }
  app.__test__.setResult(fix.result);
  app.__test__.render();
  app.__test__.render();
  app.__test__.render();
  assert.equal(doc.querySelectorAll('#speedSelect').length, 1, 'one dropdown after 3 renders');
  assert.equal(doc.querySelectorAll('#speedCustom').length, 1, 'one custom input after 3 renders');
  assert.equal(doc.querySelectorAll('#speedReadout').length, 1, 'one readout after 3 renders');
});

test('missing fields are translated to plain language with an ask', () => {
  app.__test__.setResult(null);
  app.__test__.setError({
    stage: 'extract', code: 'needs_clarification',
    message: 'Missing required fields: centralBody, dryMassKg, duration.',
    details: { missing: ['centralBody', 'dryMassKg', 'duration'] },
  });
  const chat = app.liveBody('Chat');
  assert.ok(chat.includes('To run this I still need:'), 'plain ask header');
  assert.ok(chat.includes('which body it orbits'), 'centralBody translated');
  assert.ok(chat.includes('the spacecraft mass'), 'dryMassKg translated');
  assert.ok(chat.includes('how long to run it'), 'duration translated');
  assert.ok(chat.includes('Add them to your message'), 'asks the user to add them');
  assert.ok(!chat.includes('centralBody') || chat.includes('which body it orbits'), 'no raw field dump as the message');
  assert.equal(app.__test__.missingText(['centralBody', 'dryMassKg', 'duration', 'orbit']),
    'which body it orbits, the spacecraft mass, how long to run it, the orbit shape or size');
  assert.equal(app.__test__.missingText(['mysteryField']), 'mysteryField', 'unknown fields pass through');
  assert.equal(app.__test__.missingText(['centralBody', 'centralBody']), 'which body it orbits', 'deduped');
  assert.equal(app.__test__.missingText([]), 'a few more mission details', 'empty fallback');
  assert.equal(app.__test__.missingText(null), 'a few more mission details', 'null fallback');
  app.__test__.setError(null);
});

test('verify failures say the AI answer did not match; validate shows its message', () => {
  app.__test__.setResult(null);
  app.__test__.setError({ stage: 'verify', code: 'interpreter_mismatch', message: 'Interpreter returned mismatched values: foo' });
  let chat = app.liveBody('Chat');
  assert.ok(chat.includes('did not match what you asked'), 'verify wording');
  assert.ok(chat.includes('Run stopped'), 'run-stopped header');
  app.__test__.setError({ stage: 'validate', code: 'validation_failed', message: 'Periapsis 50 km is below the 100 km minimum.' });
  chat = app.liveBody('Chat');
  assert.ok(chat.includes('physics check'), 'validate header');
  assert.ok(chat.includes('Periapsis 50 km is below the 100 km minimum.'), 'validator message shown');
  app.__test__.setError({ stage: 'simulate', code: 'gmat_run_error', message: 'GMAT blew up' });
  chat = app.liveBody('Chat');
  assert.ok(chat.includes('Run failed at simulate'), 'other stages keep the stage banner');
  assert.ok(chat.includes('GMAT blew up'), 'other stages keep the message');
  app.__test__.setError(null);
});

test('a failed run clears the previous run everywhere', async () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  assert.equal(doc.querySelectorAll('#runOrbit').length, 1, 'previous run drawn');
  globalThis.OrbitLabAdapter = {
    isMockMode: () => false,
    runExperiment: () => Promise.resolve({ error: { stage: 'simulate', code: 'gmat_run_error', message: 'GMAT blew up' } }),
  };
  try {
    app.__test__.run('doomed prompt');
    for (let k = 0; k < 20; k++) await Promise.resolve();
    assert.equal(app.__test__.getResult(), null, 'no result kept');
    assert.equal(doc.querySelectorAll('#runOrbit').length, 0, 'old track removed');
    const cells = (doc.querySelector('.telemetry-row').innerHTML.match(/<b>(.*?)<\/b>/g) || []).map((c) => c.replace(/<\/?b>/g, ''));
    assert.ok(cells.length === 5 && cells.every((c) => c === 'n/a'), 'stat cards cleared, not stale: ' + cells.join(','));
    assert.equal(doc.querySelector('#captionSpeed').textContent, 'n/a', 'speed cleared');
    assert.equal(doc.querySelector('#speedMetric').innerHTML, 'n/a', 'metric cleared');
    assert.equal(doc.querySelector('#simTime').textContent, 'n/a', 'clock cleared');
    assert.equal(doc.querySelector('#epochOverlay').textContent, '', 'overlay cleared');
    assert.equal(doc.querySelector('#runProvenance').style.display, 'none', 'provenance hidden');
    const chat = app.liveBody('Chat');
    assert.ok(chat.includes('Run failed at simulate'), 'assistant message for the failed run');
    assert.ok(chat.includes('GMAT blew up'), 'failure message kept');
    assert.ok(!chat.includes('Run complete'), 'no stale Run complete card');
  } finally {
    delete globalThis.OrbitLabAdapter;
  }
  app.__test__.setResult(fix.result);
});

test('internal errors show the plain message without raw Python text', () => {
  app.__test__.setResult(null);
  app.__test__.setError({ stage: 'extract', code: 'internal_error',
    message: 'Something went wrong while reading your request (stage: extract). Please try rephrasing.' });
  let chat = app.liveBody('Chat');
  assert.ok(chat.includes('Something went wrong while reading your request'), 'plain extract message shown');
  assert.ok(!chat.includes('Run failed at'), 'no raw banner for internal errors');
  app.__test__.setError({ stage: 'simulate', code: 'internal_error',
    message: 'Something went wrong while running this step (stage: simulate). Please try again or rephrase the request.' });
  chat = app.liveBody('Chat');
  assert.ok(chat.includes('Something went wrong while running this step'), 'plain simulate message shown');
  assert.ok(chat.includes('simulate'), 'stage named');
  app.__test__.setError(null);
});

test('burn-size missing field uses Add it and explains target-altitude limits', () => {
  app.__test__.setResult(null);
  app.__test__.setError({ stage: 'extract', code: 'needs_clarification',
    message: 'Missing required fields: deltaV.',
    details: { missing: ['deltaV'] } });
  const chat = app.liveBody('Chat');
  assert.ok(chat.includes('To run this I still need: the burn size (delta-V in m/s and direction).'), 'burn-size ask');
  assert.ok(chat.includes('Add it to your message'), 'singular Add it');
  assert.ok(chat.includes("aren&#39;t supported"), 'target-altitude note');
  assert.ok(app.__test__.missingText(['deltaV']).indexOf('burn size') >= 0, 'translator covers deltaV');
  app.__test__.setError({ stage: 'extract', code: 'needs_clarification',
    message: 'Missing required fields.',
    details: { missing: ['centralBody', 'deltaV'] } });
  const chat2 = app.liveBody('Chat');
  assert.ok(chat2.includes('Add them to your message'), 'plural Add them for several items');
  assert.ok(chat2.includes("aren&#39;t supported"), 'target-altitude note kept with others');
  app.__test__.setError(null);
});

test('schema errors hide raw pydantic text and keep validator messages intact', () => {
  app.__test__.setResult(null);
  app.__test__.setError({ stage: 'validate', code: 'schema_error',
    message: '1 validation error for OrbitLabExperiment: value is not valid',
    details: {} });
  const chat = app.liveBody('Chat');
  assert.ok(chat.includes("didn&#39;t fit the mission format"), 'friendly schema message');
  assert.ok(chat.indexOf('validation error for') < 0, 'no raw pydantic text');
  assert.ok(chat.indexOf('OrbitLabExperiment') < 0, 'no schema paths');
  app.__test__.setError({ stage: 'validate', code: 'validation_failed',
    message: 'Periapsis 50 km is below the 100 km minimum.' });
  const chat2 = app.liveBody('Chat');
  assert.ok(chat2.includes('Periapsis 50 km is below the 100 km minimum'), 'validator message preserved');
  assert.ok(chat2.includes('physics check'), 'physics header kept');
  app.__test__.setError(null);
});

test('schema failure toast avoids raw pydantic text', async () => {
  app.__test__.setResult(fix.result);
  app.__test__.render();
  globalThis.OrbitLabAdapter = {
    isMockMode: () => false,
    runExperiment: () => Promise.resolve({ error: { stage: 'validate', code: 'schema_error', message: '1 validation error for X' } }),
  };
  try {
    app.__test__.run('doomed prompt');
    for (let k = 0; k < 20; k++) await Promise.resolve();
    const toast = doc.querySelector('#toast');
    assert.ok(toast, 'toast element exists');
    assert.ok(toast.textContent.indexOf('validation error') < 0, 'no raw pydantic in toast');
    assert.ok(toast.textContent.indexOf('mission format') >= 0, 'friendly toast text');
  } finally {
    delete globalThis.OrbitLabAdapter;
  }
  app.__test__.setResult(fix.result);
});
