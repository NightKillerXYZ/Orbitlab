/* Node tests for UIUX/OrbitlabUI Main/groundtrack.js (pure math + stub canvas).
   Run: node --test tests/groundtrack.test.cjs */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');

const G = require('../UIUX/OrbitlabUI Main/groundtrack.js');

test('epoch parsing: 01 Jan 2026 12:00:00.000 UTC -> JD 2461042.0', () => {
  const jd = G.parseGmatEpoch('01 Jan 2026 12:00:00.000');
  assert.ok(Math.abs(jd - 2461042.0) < 1e-9, 'got ' + jd);
  assert.equal(G.parseGmatEpoch('not a date'), null);
  assert.equal(G.parseGmatEpoch('32 Foo 2026 12:00:00.000'), null);
  assert.equal(G.parseGmatEpoch(null), null);
});

test('GMST at J2000 is 280.4606 deg', () => {
  assert.ok(Math.abs(G.gmstDeg(2451545.0) - 280.46061837) < 1e-4);
  const g = G.gmstDeg(2461042.0);
  assert.ok(g >= 0 && g < 360, 'normalised: ' + g);
});

test('+X axis at J2000 gives longitude 79.539 deg, latitude 0', () => {
  // lon = atan2(0,6778) - 280.46061837 = -280.46061837 -> +79.53938163
  const ll = G.eciToLatLon(6778, 0, 0, 2451545.0);
  assert.ok(Math.abs(ll.lon - 79.53938163) < 1e-3, 'got ' + ll.lon);
  assert.equal(ll.lat, 0);
  assert.equal(G.eciToLatLon(0, 0, 0, 2451545.0), null);
});

test('+Z axis gives latitude 90', () => {
  const ll = G.eciToLatLon(0, 0, 6778, 2451545.0);
  assert.equal(ll.lat, 90);
});

test('track splits at the +/-180 wrap', () => {
  const segs = G.splitAtWrap([0, 0, 0, 0], [170, 175, -175, -170]);
  assert.equal(segs.length, 2);
  assert.deepEqual(segs[0].lons, [170, 175]);
  assert.deepEqual(segs[1].lons, [-175, -170]);
  assert.deepEqual(G.splitAtWrap([0], [10]), [{ lats: [0], lons: [10] }]);
});

test('decimation keeps first and last within budget', () => {
  const d = G.decimateIndices(5000, 3000);
  assert.ok(d.length <= 3000, 'got ' + d.length);
  assert.equal(d[0], 0);
  assert.equal(d[d.length - 1], 4999);
});

function stubCtx(log) {
  return {
    calls: log,
    set fillStyle(v) { log.push(['fillStyle', v]); },
    set strokeStyle(v) { log.push(['strokeStyle', v]); },
    set font(v) {},
    set textAlign(v) {},
    fillRect(x, y, w, h) { log.push(['fillRect', x, y, w, h]); },
    beginPath() { log.push(['begin']); },
    moveTo(x, y) { log.push(['moveTo', x, y]); },
    lineTo(x, y) { log.push(['lineTo', x, y]); },
    stroke() { log.push(['stroke']); },
    arc(x, y, r, a, b) { log.push(['arc', x, y, r]); },
    fill() { log.push(['fill']); },
    fillText(t, x, y) { log.push(['text', String(t), x, y]); },
  };
}

test('drawGroundTrack draws grid, wrapped track, markers, labels', () => {
  const log = [];
  const canvas = { width: 520, height: 260, getContext: () => stubCtx(log) };
  const ok = G.drawGroundTrack(canvas, [0, 0, 0, 0], [170, 175, -175, -170], {});
  assert.equal(ok, true);
  assert.ok(log.some((c) => c[0] === 'fillRect'), 'background painted');
  assert.ok(log.some((c) => c[0] === 'text' && String(c[1]).includes('°')), 'degree labels');
  const moves = log.filter((c) => c[0] === 'moveTo').length;
  assert.ok(moves >= 2, 'wrap splits into segments, moveTo x' + moves);
  assert.ok(log.filter((c) => c[0] === 'arc').length >= 2, 'start and end markers');
});

test('missing texture and bad canvas never throw', () => {
  const log = [];
  const canvas = { width: 520, height: 260, getContext: () => stubCtx(log) };
  // no global Image in Node: image branch is skipped, grid remains
  assert.equal(G.drawGroundTrack(canvas, [0], [0], { imageUrl: 'assets/textures/earth.jpg' }), true);
  assert.equal(G.drawGroundTrack(null, [0], [0], {}), false);
  assert.equal(G.drawGroundTrack({ getContext: () => null }, [0], [0], {}), false);
  assert.equal(G.drawGroundTrack(canvas, [], [], {}), true);
});
