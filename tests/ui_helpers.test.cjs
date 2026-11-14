/* Offline unit tests for the pure helpers at the top of
   UIUX/OrbitlabUI Main/app.js. Run: node --test tests/ui_helpers.test.cjs
   (Node >= 18). No DOM, no network: document/window are stubbed so the
   browser file loads under Node. */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

function makeEl(extra) {
  const el = {
    style: {},
    dataset: {},
    children: [],
    childNodes: [],
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute() {},
    getAttribute() { return null; },
    addEventListener() {},
    removeEventListener() {},
    appendChild() {},
    before() {},
    after() {},
    remove() {},
    closest() { return null; },
    querySelector() { return makeEl(); },
    querySelectorAll() { return []; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 100, height: 100 }; },
    focus() {},
    click() {},
    blur() {},
    set textContent(v) {},
    get textContent() { return ''; },
    set innerHTML(v) {},
    get innerHTML() { return ''; },
  };
  el.parentElement = el;
  return Object.assign(el, extra || {});
}

const globalDateEl = makeEl({ children: [makeEl(), makeEl()] });
global.document = {
  querySelector(sel) {
    if (sel === '#globalDate') return globalDateEl;
    return makeEl();
  },
  querySelectorAll() { return []; },
  createElement() { return makeEl(); },
  body: makeEl(),
};
global.window = global;
global.location = { search: '', href: 'http://localhost/', origin: 'http://localhost' };
global.setInterval = () => 0;
global.clearTimeout = () => {};
global.setTimeout = () => 0;

const app = require('../UIUX/OrbitlabUI Main/app.js');

test('body table mirrors the repo constants', () => {
  assert.equal(app.bodyInfo('Earth').radiusKm, 6378.1363);
  assert.equal(app.bodyInfo('Earth').muKm3S2, 398600.4415);
  assert.equal(app.bodyInfo('Moon').radiusKm, 1737.4);
  assert.equal(app.bodyInfo('Mars').muKm3S2, 42828.375214);
  assert.equal(app.bodyInfo('Mercury').radiusKm, 2440.53);
  assert.equal(app.bodyInfo('Venus').radiusKm, 6051.8);
  assert.equal(app.bodyInfo('Jupiter').radiusKm, 71492);
  assert.equal(app.bodyInfo('Sun').radiusKm, 695700);
  const unk = app.bodyInfo('Pluto');
  assert.equal(unk.radiusKm, null);
  assert.equal(unk.muKm3S2, null);
});

test('period of the 6778.136 km Earth orbit is about 1.54 hours', () => {
  const t = app.keplerPeriodSecs(6778.136, 398600.4415);
  assert.ok(Math.abs(t - 5553.4) < 1.0, 'got ' + t);
  assert.equal(app.periodText(6778.136, 398600.4415), '1.54 hours');
  assert.equal(app.periodText(null, 398600.4415), 'n/a');
  assert.equal(app.periodText(6778.136, null), 'n/a');
});

test('point helpers prefer altitude_km, fall back to r-R', () => {
  const p = { x_km: 6778.136, y_km: 0, z_km: 0, vx_km_s: 0, vy_km_s: 7.6685587, vz_km_s: 0, altitude_km: 399.99984 };
  assert.ok(Math.abs(app.pointRadiusKm(p) - 6778.136) < 1e-6);
  assert.ok(Math.abs(app.pointSpeedKms(p) - 7.6685587) < 1e-6);
  assert.equal(app.pointAltKm(p, 6378.1363), 399.99984);
  const q = { x_km: 7000, y_km: 0, z_km: 0, vx_km_s: 0, vy_km_s: 7, vz_km_s: 0 };
  assert.ok(Math.abs(app.pointAltKm(q, 6378.1363) - 621.8637) < 1e-6);
  assert.equal(app.pointAltKm(q, null), null);
});

test('fitOrbit centers the body and fits the path with margin', () => {
  const pts = [{ x_km: 6778.136, y_km: 0, z_km: 0 }, { x_km: -6778.136, y_km: 0, z_km: 0 }];
  const f = app.fitOrbit(pts, 300, 200, 16);
  assert.ok(f);
  assert.equal(f.cx, 150);
  assert.equal(f.cy, 100);
  assert.equal(f.line.length, 2);
  for (const [x, y] of f.line) {
    assert.ok(x >= 16 && x <= 284, 'x in bounds: ' + x);
    assert.ok(y >= 16 && y <= 184, 'y in bounds: ' + y);
  }
  assert.equal(app.fitOrbit([], 300, 200), null);
  const one = app.fitOrbit([{ x_km: 7000, y_km: 0, z_km: 0 }], 300, 200, 16);
  assert.equal(one.line.length, 1);
});

test('trajectoryStats handles empty, single and multi-point runs', () => {
  const empty = app.trajectoryStats([], 6378.1363);
  assert.equal(empty.n, 0);
  assert.equal(empty.minAlt, null);
  const one = app.trajectoryStats(
    [{ elapsed_secs: 0, x_km: 6778.136, y_km: 0, z_km: 0, vx_km_s: 0, vy_km_s: 7.66, vz_km_s: 0, altitude_km: 400 }], 6378.1363);
  assert.equal(one.n, 1);
  assert.equal(one.minAlt, 400);
  assert.equal(one.maxAlt, 400);
  assert.equal(one.spanSecs, 0);
  const two = app.trajectoryStats([
    { elapsed_secs: 0, x_km: 6778.136, y_km: 0, z_km: 0, vx_km_s: 0, vy_km_s: 7.66, vz_km_s: 0, altitude_km: 400 },
    { elapsed_secs: 86400, x_km: -5415.78, y_km: -4045.75, z_km: 1.5, vx_km_s: 4.6, vy_km_s: -6.16, vz_km_s: 0, altitude_km: 381.95 },
  ], 6378.1363);
  assert.equal(two.minAlt, 381.95);
  assert.equal(two.maxAlt, 400);
  assert.ok(two.minSpeed < two.maxSpeed);
  assert.equal(two.spanSecs, 86400);
  assert.equal(two.finalAlt, 381.95);
});

test('formatters use thousands separators and never invent', () => {
  assert.equal(app.fmtKm(108200.5, 1), '108,200.5');
  assert.equal(app.fmtKm(400, 1), '400.0');
  assert.equal(app.fmtKm(NaN), 'n/a');
  assert.equal(app.fmtKm(undefined), 'n/a');
  assert.equal(app.fmtSecs(86400), 'T+24:00:00');
  assert.equal(app.fmtSecs(200000), 'DAY 2.31');
  assert.equal(app.fmtSecs(45), 'T+00:00:45');
});

test('apoapsis eccentricity from radii', () => {
  // Hohmann 7000 -> 9000 km circular start around Earth (R = 6378.137 km):
  // ra = 9000, rp = 7000  =>  e = (9000-7000)/(9000+7000) = 2000/16000 = 0.125
  const e = app.apoapsisEccentricity(2621.863, 621.863, 6378.137);
  assert.ok(Math.abs(e - 0.125) < 1e-9, 'got ' + e);
  assert.equal(app.apoapsisEccentricity(400, 400, 6378.137), 0);
  assert.equal(app.apoapsisEccentricity(null, 100, 6378.137), null);
  assert.equal(app.apoapsisEccentricity(100, 100, null), null);
  assert.equal(app.apoapsisEccentricity(-9000, 100, 6378.137), null);
});

test('inclination from r x v samples', () => {
  // r=(7000,0,0) km, v=(0,1.7320508,1) km/s:
  // h = r x v = (0,-7000,12124.3556), |h| = 14000,
  // cos i = 12124.3556/14000 = 0.8660254  =>  i = 30 deg
  const pts = [{ x_km: 7000, y_km: 0, z_km: 0, vx_km_s: 0, vy_km_s: 1.7320508, vz_km_s: 1 }];
  const i = app.telemetryInclinationDeg(pts);
  assert.ok(Math.abs(i - 30) < 0.01, 'got ' + i);
  assert.equal(app.telemetryInclinationDeg([]), null);
  assert.equal(app.telemetryInclinationDeg([{ x_km: 1 }]), null);
  assert.equal(app.telemetryInclinationDeg([{ x_km: 0, y_km: 0, z_km: 0, vx_km_s: 0, vy_km_s: 0, vz_km_s: 0 }]), null);
});

test('sma falls back to telemetry mean for Cartesian echoes', () => {
  const exp = { initialOrbit: { type: 'Keplerian', elements: { semiMajorAxisKm: 6778.136 } } };
  assert.equal(app.smaForDisplay(exp, []), 6778.136);
  const cart = { initialOrbit: { type: 'Cartesian', elements: {} } };
  assert.equal(app.smaForDisplay(cart, [{ semi_major_axis_km: 7000 }, { semi_major_axis_km: 7100 }]), 7050);
  assert.equal(app.smaForDisplay({}, []), null);
});

test('chartSVG labels axes with units', () => {
  const svg = app.chartSVG('Altitude vs time', 'km', [0, 43200, 86400], [400, 405, 381.9], '#6faaff');
  assert.ok(svg.includes('<svg'));
  assert.ok(svg.includes('km'));
  assert.ok(svg.includes('elapsed time'));
  assert.ok(svg.includes('<polyline'));
  assert.equal(app.chartSVG('t', 'km', [], [], '#fff'), '<div class="result-note">No data.</div>');
  assert.equal(app.chartSVG('t', 'km', [0], [null], '#fff'), '<div class="result-note">No data.</div>');
});

test('text builders summarize failure-free inputs', () => {
  assert.equal(app.stopText({ stopCondition: { type: 'ElapsedDays', value: 1 } }), 'ElapsedDays 1');
  assert.equal(app.stopText({}), 'n/a');
  assert.equal(app.manText([]), 'none');
  assert.ok(app.manText([{ id: 'M1', type: 'TargetedHohmannTransfer', trigger: { condition: 'AtPeriapsis' }, targetObjectives: { targetOrbitRadiusKm: 9000 } }]).includes('9,000'));
  assert.ok(app.forceText({ gravityDegree: 4, gravityOrder: 4, pointMasses: ['Luna', 'Sun'], atmosphericDrag: { enabled: false }, solarRadiationPressure: true }).includes('4x4'));
  assert.equal(app.forceText(null), 'n/a');
});

test('fixture shape drives the helpers end to end', () => {
  const fix = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'real_result_earth.json'), 'utf-8'));
  const res = fix.result;
  assert.equal(res.status, 'success');
  assert.equal(res.experiment.centralBody, 'Earth');
  assert.ok(Array.isArray(res.trajectory.points) && res.trajectory.points.length > 1000);
  const info = app.bodyInfo(res.experiment.centralBody);
  const stats = app.trajectoryStats(res.trajectory.points, info.radiusKm);
  assert.ok(Math.abs(stats.minAlt - 381.9) < 5, 'min alt near final: ' + stats.minAlt);
  assert.ok(Math.abs(stats.maxAlt - 400.0) < 5, 'max alt near 400: ' + stats.maxAlt);
  assert.equal(app.periodText(app.smaForDisplay(res.experiment, res.trajectory.points), info.muKm3S2), '1.54 hours');
  const fit = app.fitOrbit(res.trajectory.points, 300, 200, 16);
  assert.ok(fit && fit.line.length > 1000);
});
