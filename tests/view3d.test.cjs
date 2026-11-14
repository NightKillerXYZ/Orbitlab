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
