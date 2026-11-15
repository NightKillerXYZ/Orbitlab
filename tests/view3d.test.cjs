/* Node tests for UIUX/OrbitlabUI Main/view3d.js (no real GPU: stub WebGL/DOM).
   Run: node --test tests/view3d.test.cjs */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');

const v3 = require('../UIUX/OrbitlabUI Main/view3d.js');

test('radius table uses the specified km values', () => {
  assert.deepEqual(v3.BODY_RADII_KM, {
    Earth: 6378.137, Moon: 1737.4, Mars: 3396.2, Mercury: 2439.7,
    Venus: 6051.8, Jupiter: 71492, Sun: 695700,
  });
  assert.equal(v3.bodyRadiusKm('Earth'), 6378.137);
  assert.equal(v3.bodyRadiusKm('Pluto'), null);
  assert.equal(v3.bodyRadiusKm(null), null);
});

test('texture file names', () => {
  for (const b of ['Earth', 'Moon', 'Mars', 'Mercury', 'Venus', 'Jupiter', 'Sun']) {
    assert.equal(v3.textureFileFor(b), 'assets/textures/' + b.toLowerCase() + '.jpg');
  }
});

test('decimation keeps first and last, stays within budget', () => {
  const pts = [];
  for (let i = 0; i < 10001; i++) pts.push([i, 2 * i, 3 * i]);
  const d = v3.decimatePoints(pts, 5000);
  assert.ok(d.length <= 5000, 'got ' + d.length);
  assert.deepEqual(d[0], [0, 0, 0], 'first kept');
  assert.deepEqual(d[d.length - 1], [10000, 20000, 30000], 'last kept');
  // evenly spaced: index gaps differ by at most one
  const gaps = [];
  let prev = -1;
  const idx = pts.map((p, i) => (d.includes(p) ? i : -1)).filter((i) => i >= 0);
  for (let k = 1; k < idx.length; k++) gaps.push(idx[k] - idx[k - 1]);
  assert.ok(Math.max(...gaps) - Math.min(...gaps) <= 1, 'even: ' + gaps.slice(0, 5));
  const small = [[1, 2, 3], [4, 5, 6]];
  assert.deepEqual(v3.decimatePoints(small, 5000), small);
  assert.deepEqual(v3.decimatePoints([], 5000), []);
  assert.deepEqual(v3.decimatePoints([[1, 1, 1]], 5000), [[1, 1, 1]]);
});

test('progress mapping interpolates elapsed time', () => {
  // hand check: t=2.5 of [0,10] -> quarter point of [0,100] = [25,0,0]
  assert.deepEqual(v3.sampleAtTimes([0, 10], [0, 100], [0, 0], [0, 0], 2.5), [25, 0, 0]);
  assert.deepEqual(v3.sampleAtTimes([0, 10], [0, 100], [0, 0], [0, 0], -5), [0, 0, 0]);
  assert.deepEqual(v3.sampleAtTimes([0, 10], [0, 100], [0, 0], [0, 0], 99), [100, 0, 0]);
  assert.equal(v3.sampleAtTimes([], [], [], [], 5), null);
  assert.equal(v3.countAtOrBefore([0, 5, 10], 5), 2);
  assert.equal(v3.countAtOrBefore([0, 5, 10], -1), 0);
  assert.equal(v3.countAtOrBefore([0, 5, 10], 99), 3);
});

/* ---- createView3D with stubbed THREE + DOM (no WebGL) ---- */
function fakeCtx2d() {
  return {
    font: '', textAlign: '', textBaseline: '', fillStyle: '',
    fillRect() {}, fillText() {}, clearRect() {},
    measureText() { return { width: 10 }; },
  };
}
function fakeCanvas() {
  return {
    width: 0, height: 0, style: {}, id: '',
    getContext() { return fakeCtx2d(); },
    addEventListener() {}, removeEventListener() {},
  };
}
function makeFakeTHREE(log) {
  class V3 {
    constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
    set(x, y, z) { this.x = x; this.y = y; this.z = z; log.pos = [x, y, z]; }
  }
  return {
    Color: function (v) { this.v = v; },
    Scene: function () {
      this.background = null; this.kids = [];
      this.add = (o) => this.kids.push(o);
      this.remove = (o) => { this.kids = this.kids.filter((k) => k !== o); };
    },
    PerspectiveCamera: function () {
      this.position = new V3(0, 0, 0); this.aspect = 1;
      this.updateProjectionMatrix = () => {};
    },
    AmbientLight: function () {},
    DirectionalLight: function () { this.position = new V3(0, 0, 0); },
    WebGLRenderer: function () {
      this.domElement = fakeCanvas();
      this.setPixelRatio = () => {};
      this.setSize = () => {};
      this.render = () => { log.renders++; };
      this.dispose = () => { log.disposed.push('renderer'); };
    },
    BufferGeometry: function () {
      this.attrs = {};
      this.setAttribute = (n, a) => { this.attrs[n] = a; log.geoAttrs.push(a.count); };
      this.setDrawRange = (a, b) => { log.drawRange = b; };
      this.dispose = () => { log.disposed.push('geometry'); };
    },
    Float32BufferAttribute: function (arr, n) { this.array = arr; this.count = arr.length / n; },
    LineBasicMaterial: function (o) { this.o = o; },
    PointsMaterial: function (o) { this.o = o; },
    MeshStandardMaterial: function (o) { this.o = o || {}; log.materials.push(this.o); },
    MeshBasicMaterial: function (o) { this.o = o || {}; },
    SpriteMaterial: function (o) { this.o = o || {}; },
    Line: function (g, m) { this.geometry = g; this.material = m; },
    Points: function (g, m) { this.geometry = g; this.material = m; },
    Mesh: function (g, m) {
      this.geometry = g; this.material = m; this.position = new V3(0, 0, 0);
    },
    SphereGeometry: function () { this.dispose = () => { log.disposed.push('sphere'); }; },
    Group: function () {
      this.kids = [];
      this.add = (o) => this.kids.push(o);
      this.remove = () => {};
      this.traverse = (fn) => this.kids.forEach(fn);
    },
    Sprite: function (m) { this.material = m; this.position = new V3(0, 0, 0); this.scale = new V3(1, 1, 1); },
    CanvasTexture: function () {},
    TextureLoader: function () {
      // missing texture: always fail -> fallback must kick in, never throw
      this.loadAsync = (f) => { log.textureFile = f; return Promise.reject(new Error('missing ' + f)); };
    },
    SRGBColorSpace: 'srgb',
    Vector3: V3,
  };
}
function makeFakeOC(log) {
  return function () {
    this.target = { set() {} };
    this.update = () => {};
    this.dispose = () => { log.disposed.push('controls'); };
    this.addEventListener = () => {};
  };
}
function makeContainer() {
  return {
    clientWidth: 300, clientHeight: 200, style: {}, el: null,
    appendChild(c) { this.el = c; c.parentNode = this; },
    removeChild(c) { if (this.el === c) { this.el = null; c.parentNode = null; } },
    addEventListener() {}, removeEventListener() {},
  };
}
function installDom() {
  global.document = {
    createElement: (t) => (t === 'canvas' ? fakeCanvas() : { style: {}, setAttribute() {} }),
    createElementNS: () => fakeCanvas(),
    querySelector: () => null,
    querySelectorAll: () => [],
  };
}

test('createView3D builds, drives and disposes without real WebGL; missing texture falls back', async () => {
  installDom();
  const log = { renders: 0, disposed: [], geoAttrs: [], materials: [], drawRange: 0, pos: null, textureFile: null };
  const container = makeContainer();
  const h = v3.createView3D(container, { THREE: makeFakeTHREE(log), OrbitControls: makeFakeOC(log) });
  await h.ready;
  assert.ok(container.el, 'canvas attached');
  // 6000 samples -> decimated to <= 5000, first+last kept
  const pts = [];
  for (let i = 0; i < 6000; i++) {
    const a = (i / 5999) * Math.PI * 2;
    pts.push({ x_km: 6778 * Math.cos(a), y_km: 6778 * Math.sin(a), z_km: 0, elapsed_secs: (i / 5999) * 5400 });
  }
  h.setResult(pts, 'Earth');
  await new Promise((r) => setTimeout(r, 20));
  const lineCounts = log.geoAttrs.filter((c) => c > 2);
  assert.ok(lineCounts.length > 0, 'line geometry built');
  assert.ok(lineCounts.every((c) => c <= 5000), 'decimated: ' + lineCounts);
  assert.ok(lineCounts.some((c) => c === 5000 || c === 4999 || c > 4000), 'near budget');
  assert.equal(log.textureFile, 'assets/textures/earth.jpg');
  assert.ok(log.materials.some((m) => m && !m.map && typeof m.color === 'number'), 'fallback plain material, no map');
  h.setProgress(0.5);
  assert.ok(log.drawRange > 0, 'travelled range set');
  assert.ok(log.pos && log.pos.every(Number.isFinite), 'marker positioned');
  h.dispose();
  assert.ok(log.disposed.includes('renderer'), 'renderer disposed');
  assert.ok(log.disposed.includes('controls'), 'controls disposed');
  assert.equal(container.el, null, 'canvas removed');
});

test('createView3D with unknown body uses fallback colour, still no throw', async () => {
  installDom();
  const log = { renders: 0, disposed: [], geoAttrs: [], materials: [], drawRange: 0, pos: null, textureFile: null };
  const h = v3.createView3D(makeContainer(), { THREE: makeFakeTHREE(log), OrbitControls: makeFakeOC(log) });
  await h.ready;
  h.setResult([{ x_km: 7000, y_km: 0, z_km: 0, elapsed_secs: 0 }], 'Pluto');
  await new Promise((r) => setTimeout(r, 20));
  assert.ok(log.materials.some((m) => m && !m.map), 'plain fallback material');
  h.dispose();
});

/* ---- GMAT-look additions: zero-skip, travelled-only reveal, toggle, model fallback ---- */
function makeEl(tag) {
  const el = {
    tag, children: [], parentNode: null, style: {}, dataset: {},
    attrs: {}, handlers: {}, textContent: '', checked: false, type: '',
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; },
    addEventListener(t, fn) { this.handlers[t] = fn; },
    removeEventListener() {},
  };
  Object.defineProperty(el, 'id', {
    get() { return this.attrs.id || ''; },
    set(v) { this.attrs.id = String(v); },
  });
  el.querySelector = (sel) => {
    const m = /^#([\w-]+)$/.exec(sel);
    if (!m) return null;
    const walk = (n) => {
      for (const c of n.children || []) {
        if (c.attrs && c.attrs.id === m[1]) return c;
        const f = walk(c);
        if (f) return f;
      }
      return null;
    };
    return walk(el);
  };
  return el;
}
function makeCanvasStub(log) {
  return {
    width: 0, height: 0, style: {}, id: '', handlers: {},
    getContext() {
      return {
        font: '', textAlign: '', textBaseline: '', fillStyle: '',
        fillRect() {}, fillText() {}, clearRect() {},
        measureText() { return { width: 10 }; },
      };
    },
    setAttribute() {},
    addEventListener(t, fn) { this.handlers[t] = fn; if (log) log.canvasHandlers[t] = fn; },
    removeEventListener() {},
  };
}
function makeRichContainer() {
  const c = makeEl('div');
  c.clientWidth = 300; c.clientHeight = 200;
  return c;
}
function installRichDom(log) {
  global.document = {
    createElement: (t) => (t === 'canvas' ? makeCanvasStub(log) : makeEl(t)),
    createElementNS: () => makeEl('svg'),
    querySelector: () => null,
    querySelectorAll: () => [],
  };
}
function makeRichTHREE(log) {
  class V3 {
    constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
    set(x, y, z) { this.x = x; this.y = y; this.z = z; log.pos = [x, y, z]; return this; }
    copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
  }
  return {
    Color: function (v) { this.v = v; },
    Scene: function () {
      this.background = null; this.kids = [];
      this.add = (o) => this.kids.push(o);
      this.remove = (o) => { this.kids = this.kids.filter((k) => k !== o); };
    },
    PerspectiveCamera: function () {
      this.position = new V3(0, 0, 0); this.up = new V3(0, 1, 0); this.aspect = 1;
      log.camera = this;
      this.updateProjectionMatrix = () => { log.projUpdates = (log.projUpdates || 0) + 1; };
    },
    AmbientLight: function () {},
    DirectionalLight: function () { this.position = new V3(0, 0, 0); },
    WebGLRenderer: function () {
      this.domElement = log.canvas;
      this.setPixelRatio = () => {};
      this.setSize = () => {};
      this.render = () => { log.renders++; };
      this.dispose = () => { log.disposed.push('renderer'); };
    },
    BufferGeometry: function () {
      this.attrs = {}; this.drawStart = 0; this.drawCount = Infinity;
      log.geos.push(this);
      this.setAttribute = (n, a) => { this.attrs[n] = a; };
      this.setDrawRange = (a, b) => { this.drawStart = a; this.drawCount = b; };
      this.dispose = () => {};
    },
    Float32BufferAttribute: function (arr, n) { this.array = arr; this.count = arr.length / n; },
    LineBasicMaterial: function (o) { this.o = o || {}; log.materials.push({ kind: 'line', o: this.o }); },
    PointsMaterial: function (o) { this.o = o || {}; log.materials.push({ kind: 'points', o: this.o }); },
    MeshStandardMaterial: function (o) { this.o = o || {}; log.materials.push({ kind: 'std', o: this.o }); },
    MeshBasicMaterial: function (o) { this.o = o || {}; log.materials.push({ kind: 'basic', o: this.o }); },
    SpriteMaterial: function (o) { this.o = o || {}; log.materials.push({ kind: 'sprite', o: this.o }); },
    Line: function (g, m) { this.geometry = g; this.material = m; this.visible = true; log.lines.push(this); },
    Points: function (g, m) {
      this.geometry = g; this.material = m;
      this.position = new V3(0, 0, 0); this.visible = true; this.frustumCulled = true;
      log.points.push(this);
    },
    Mesh: function (g, m) {
      this.geometry = g; this.material = m;
      const pv = new V3(0, 0, 0);
      pv.set = (x, y, z) => { log.craftPos = [x, y, z]; log.pos = [x, y, z]; pv.x = x; pv.y = y; pv.z = z; return pv; };
      this.position = pv; this.scale = new V3(1, 1, 1); this.visible = true;
      log.meshes.push(this);
    },
    SphereGeometry: function (r) { log.spheres.push(r); this.dispose = () => {}; },
    Group: function () {
      this.kids = []; this.position = new V3(0, 0, 0); this.scale = new V3(1, 1, 1);
      this.add = (o) => this.kids.push(o);
      this.remove = () => {};
      this.traverse = (fn) => this.kids.forEach(fn);
    },
    Sprite: function (m) {
      this.material = m; this.position = new V3(0, 0, 0); this.scale = new V3(1, 1, 1);
      log.sprites.push(this);
    },
    CanvasTexture: function () {},
    TextureLoader: function () {
      this.loadAsync = (f) => { log.textureFile = f; return Promise.reject(new Error('missing ' + f)); };
    },
    SRGBColorSpace: 'srgb',
    Vector3: V3,
    ArrowHelper: function (dir, origin, len, color, hl, hw) {
      log.arrows.push({ color, len }); this.line = {}; this.cone = {};
    },
  };
}
function makeRichOC(log) {
  return function () {
    this.target = { set() {} };
    this.update = () => {};
    this.dispose = () => { log.disposed.push('controls'); };
    this.addEventListener = () => {};
  };
}
function richLog() {
  return {
    renders: 0, disposed: [], geos: [], materials: [], lines: [], points: [],
    meshes: [], sprites: [], arrows: [], spheres: [], pos: null, craftPos: null, textureFile: null,
    camera: null, canvas: null, canvasHandlers: {},
  };
}
function elevenSamples() {
  const pts = [];
  for (let i = 0; i <= 10; i++) pts.push({ x_km: 6778 + i, y_km: 0, z_km: 0, elapsed_secs: i });
  return pts;
}
async function readyScene(opts) {
  const log = richLog();
  log.canvas = makeCanvasStub(log);
  installRichDom(log);
  const THREE = makeRichTHREE(log);
  const deps = { THREE, OrbitControls: makeRichOC(log) };
  if (opts && opts.tds) deps.TDSLoader = opts.tds;
  const container = makeRichContainer();
  if (opts && opts.dataset) Object.assign(container.dataset, opts.dataset);
  const h = v3.createView3D(container, deps);
  await h.ready;
  // The empty init scene is fully replaced by setResult below; scope the logs to it.
  log.sprites.length = 0; log.lines.length = 0; log.arrows.length = 0;
  log.materials.length = 0; log.geos.length = 0; log.points.length = 0;
  h.setResult(opts && opts.tele ? opts.tele : elevenSamples(), (opts && opts.body) || 'Earth');
  await new Promise((r) => setTimeout(r, 50));
  return { log, container, h };
}
const isBright = (l) => l.material && l.material.o && l.material.o.color === 0xff0000 && !l.material.o.transparent;
const isFaint = (l) => l.material && l.material.o && l.material.o.transparent === true;

test('splitRuns drops exact-zero endpoints; near-zero samples are kept', () => {
  assert.equal(v3.modelFileFor(), 'assets/models/spacecraft.3ds');
  const runs = v3.splitRuns([[1, 0, 0], [0, 0, 0], [2, 0, 0], [3, 0, 0]], [0, 1, 2, 3]);
  assert.equal(runs.length, 1, 'lone pre-gap point is not a drawable run');
  assert.deepEqual(runs[0].pts, [[2, 0, 0], [3, 0, 0]]);
  assert.deepEqual(runs[0].times, [2, 3]);
  for (const r of runs) {
    for (const p of [r.pts[0], r.pts[r.pts.length - 1]]) {
      assert.ok(p[0] * p[0] + p[1] * p[1] + p[2] * p[2] > 0, 'no run endpoint at origin');
    }
  }
  const tiny = v3.splitRuns([[1e-12, 0, 0], [2, 0, 0]], [0, 1]);
  assert.equal(tiny.length, 1, 'near-zero is not exact-zero: kept');
});

test('progress 0/0.5/1 draws only the travelled part; red track; marker rests at the end', async () => {
  const { log, h } = await readyScene();
  const bright = log.lines.filter(isBright);
  const faint = log.lines.filter(isFaint);
  assert.equal(bright.length, 1, 'one travelled run');
  assert.equal(faint.length, 1, 'one faint full-path copy');
  assert.equal(bright[0].material.o.color, 0xff0000, 'spacecraft red');
  assert.ok(bright[0].material.o.linewidth >= 2, 'thicker than hairline');
  h.setProgress(0);
  assert.equal(bright[0].geometry.drawCount, 0, 'nothing travelled at 0');
  h.setProgress(0.5);
  assert.equal(bright[0].geometry.drawCount, 6, 'samples at t<=5 of 0..10');
  assert.equal(faint[0].visible, false, 'faint copy hidden by default');
  h.setProgress(1);
  assert.equal(bright[0].geometry.drawCount, 11, 'full trail at the end');
  assert.deepEqual(log.craftPos, [6788, 0, 0], 'marker rests at last point');
  h.dispose();
});

test('axes, screen-fixed stars, Z-up camera at ~3x max radius', async () => {
  const { log, h } = await readyScene();
  assert.deepEqual(log.arrows.slice(-3).map((a) => a.color), [0xff0000, 0x00ff00, 0x4d8dff], 'X/Y/Z arrowheads');
  const maxR = 6788;
  for (const a of log.arrows.slice(-3)) assert.ok(Math.abs(a.len - 1.5 * maxR) < 1e-6, 'axes sized to 1.5x max radius');
  const star = log.materials.find((m) => m.kind === 'points' && m.o.sizeAttenuation === false);
  assert.ok(star, 'stars use constant pixel size (screen-fixed)');
  assert.deepEqual([log.camera.up.x, log.camera.up.y, log.camera.up.z], [0, 0, 1], 'Z-up camera');
  const D = 3 * maxR;
  assert.deepEqual(
    [log.camera.position.x, log.camera.position.y, log.camera.position.z],
    [D * 0.68, -D * 0.68, D * 0.22],
    'default camera at ~3x max radius, slight tilt above the equator');
  assert.ok(log.spheres.includes(6378.137), 'body sphere at true Earth radius');
  assert.ok(log.sprites.length >= 5, 'X/Y/Z + body + spacecraft labels: ' + log.sprites.length);
  h.dispose();
});

test('Show full path checkbox toggles faint copies; Reset view and dblclick restore the camera', async () => {
  const { log, container, h } = await readyScene();
  const ui = container.querySelector('#view3dUI');
  assert.ok(ui, 'in-view controls exist');
  const find = (pred) => {
    const walk = (n) => {
      for (const c of n.children || []) { if (pred(c)) return c; const f = walk(c); if (f) return f; }
      return null;
    };
    return walk(ui);
  };
  const cb = find((c) => c.tag === 'input' && c.type === 'checkbox');
  assert.ok(cb, 'show-full-path checkbox exists');
  assert.equal(cb.checked, false, 'default off');
  const btn = find((c) => c.tag === 'button');
  assert.ok(btn && btn.textContent === 'Reset view', 'reset button exists');
  const faint = log.lines.filter(isFaint);
  assert.ok(faint.length > 0);
  cb.checked = true;
  cb.handlers.change();
  assert.ok(faint.every((f) => f.visible === true), 'faint copies shown');
  cb.checked = false;
  cb.handlers.change();
  assert.ok(faint.every((f) => f.visible === false), 'faint copies hidden again');
  const framed = [log.camera.position.x, log.camera.position.y, log.camera.position.z];
  log.camera.position.set(1, 2, 3);
  btn.handlers.click();
  assert.deepEqual([log.camera.position.x, log.camera.position.y, log.camera.position.z], framed, 'button restores view');
  log.camera.position.set(4, 5, 6);
  assert.ok(log.canvasHandlers.dblclick, 'dblclick handler registered');
  log.canvasHandlers.dblclick();
  assert.deepEqual([log.camera.position.x, log.camera.position.y, log.camera.position.z], framed, 'dblclick restores view');
  h.dispose();
});

test('missing spacecraft.3ds falls back to the marker without throwing', async () => {
  let loadFile = null;
  function TDS() {}
  TDS.prototype.loadAsync = (f) => { loadFile = f; return Promise.reject(new Error('not found')); };
  const { log, h } = await readyScene({ tds: TDS });
  h.setProgress(1);
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(loadFile, 'assets/models/spacecraft.3ds');
  assert.deepEqual(log.craftPos, [6788, 0, 0], 'marker still driven');
  const craft = log.meshes[log.meshes.length - 1];
  assert.ok(craft && craft.visible !== false, 'simple marker kept');
  h.dispose();
});

test('container dataset supplies spacecraft and body label names', async () => {
  const { log, h } = await readyScene({ dataset: { spacecraftName: 'SC_Put', bodyName: 'Earth' } });
  assert.ok(log.sprites.length >= 2, 'name labels created');
  h.dispose();
});

test('name labels keep a constant on-screen size when the camera moves', async () => {
  const { log, h } = await readyScene();
  h.setProgress(0.5);
  const cd = () => {
    const p = log.camera.position;
    return Math.sqrt(p.x * p.x + p.y * p.y + p.z * p.z);
  };
  assert.ok(log.sprites.length > 0, 'labels exist');
  for (const sp of log.sprites) {
    assert.ok(Math.abs(sp.scale.x - cd() * 0.04) / (cd() * 0.04) < 1e-9, 'label width is 4% of camera distance');
    assert.ok(Math.abs(sp.scale.y - cd() * 0.02) / (cd() * 0.02) < 1e-9, 'label kept 2:1');
  }
  const before = log.sprites[0].scale.x;
  log.camera.position.set(log.camera.position.x / 2, log.camera.position.y / 2, log.camera.position.z / 2);
  h.setProgress(0.6);
  assert.ok(Math.abs(log.sprites[0].scale.x - before / 2) / before < 1e-9, 'labels shrink with the camera: ' + log.sprites[0].scale.x);
  h.dispose();
});

test('garbage model data keeps the simple marker', async () => {
  function TDS() {}
  TDS.prototype.loadAsync = () => Promise.resolve({
    updateMatrixWorld() {},
    traverse(fn) { fn({ isMesh: false }); fn({}); },
  });
  const { log, h } = await readyScene({ tds: TDS });
  h.setProgress(1);
  await new Promise((r) => setTimeout(r, 20));
  assert.deepEqual(log.craftPos, [6788, 0, 0], 'marker still driven');
  const craft = log.meshes[log.meshes.length - 1];
  assert.ok(craft && craft.visible !== false, 'simple marker kept');
  h.dispose();
});
