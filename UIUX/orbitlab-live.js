/*
 * OrbitLab live wiring — connects the (unchanged) mock look to the backend
 * through ../orbitlab_backend/api/ui_adapter.js (window.OrbitLabAdapter).
 *
 * Mock mode (adapter MOCK on, or adapter missing): this script does nothing
 * except the clock/tabs, so the page shows exactly the hardcoded sample data
 * it shows today.
 */
(function () {
  'use strict';

  var STAGES = ['extract', 'interpret', 'verify', 'validate', 'compile', 'simulate', 'parse', 'explain'];

  // ---------- pure helpers (no DOM; also exercised from Node) ----------
  function fmtNum(x, digits) {
    var n = Number(x);
    if (!isFinite(n)) return String(x);
    return n.toLocaleString('en-US', { minimumFractionDigits: digits || 0, maximumFractionDigits: digits || 0 });
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Fold a WS event list into per-stage states for the progress strip (3a).
  function stageStates(events) {
    var states = {};
    STAGES.forEach(function (s) { states[s] = 'pending'; });
    (events || []).forEach(function (ev) {
      if (!ev || !ev.stage || STAGES.indexOf(ev.stage) < 0) return;
      if (ev.type === 'stage_started') states[ev.stage] = 'active';
      else if (ev.type === 'stage_completed') states[ev.stage] = 'done';
      else if (ev.type === 'stage_failed') states[ev.stage] = 'fail';
    });
    return states;
  }

  function hasWarmingEvent(events) {
    return (events || []).some(function (ev) { return ev && ev.type === 'model_warming_up'; });
  }

  function isClarification(error) {
    return !!(error && (error.code === 'needs_clarification' ||
      (error.details && error.details.missing)));
  }

  function missingFromError(error) {
    if (!error) return null;
    if (error.details && error.details.missing) return error.details.missing;
    if (error.missing) return error.missing;
    return null;
  }

  // Explanation text on a failed run, when the backend carries one (3e).
  function errorExplanation(error) {
    if (!error) return null;
    if (error.details && error.details.explanation) return error.details.explanation;
    if (error.explanation) return error.explanation;
    return null;
  }

  function trajPoints(result) {
    if (!result || !result.trajectory || !result.trajectory.points) return [];
    return result.trajectory.points;
  }

  function pointSpeed(p) {
    if (typeof p.speed_km_s === 'number') return p.speed_km_s;
    var vx = +p.vx_km_s || 0, vy = +p.vy_km_s || 0, vz = +p.vz_km_s || 0;
    return Math.sqrt(vx * vx + vy * vy + vz * vz);
  }

  // Scale trajectory x/y into the 900x520 orbit viewBox (pure math).
  function scalePointsToViewBox(pts) {
    pts = pts || [];
    var xs = [], ys = [], i;
    for (i = 0; i < pts.length; i++) {
      if (isFinite(+pts[i].x_km) && isFinite(+pts[i].y_km)) {
        xs.push(+pts[i].x_km); ys.push(+pts[i].y_km);
      }
    }
    if (!xs.length) return { points: '', count: 0, cx: 450, cy: 260 };
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    var span = Math.max(maxX - minX, maxY - minY, 1e-9);
    var scale = 400 / span; // fit longest side into ~400px radius box
    var cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    var out = [];
    for (i = 0; i < pts.length; i++) {
      if (!isFinite(+pts[i].x_km) || !isFinite(+pts[i].y_km)) continue;
      out.push((450 + (+pts[i].x_km - cx) * scale).toFixed(1) + ',' + (260 - (+pts[i].y_km - cy) * scale).toFixed(1));
    }
    return { points: out.join(' '), count: out.length, cx: 450, cy: 260, scale: scale, ox: cx, oy: cy };
  }

  function projectPoint(p, fit) {
    return {
      x: 450 + (+p.x_km - fit.ox) * fit.scale,
      y: 260 - (+p.y_km - fit.oy) * fit.scale
    };
  }

  function elementsOf(result) {
    try { return result.experiment.initialOrbit.elements || {}; } catch (e) { return {}; }
  }

  // Rows for the Understood pane, straight from the returned experiment JSON.
  function understoodRows(result) {
    var exp = (result && result.experiment) || {};
    var rows = [];
    rows.push(['Central body', exp.centralBody || '—']);
    var els = elementsOf(result);
    if (els.semiMajorAxisKm != null) rows.push(['Semi-major axis', fmtNum(els.semiMajorAxisKm, 3) + ' km']);
    if (els.eccentricity != null) rows.push(['Eccentricity', String(els.eccentricity)]);
    if (els.inclinationDeg != null) rows.push(['Inclination', String(els.inclinationDeg) + '°']);
    var sc = exp.spacecraft || {};
    if (sc.dryMassKg != null) rows.push(['Spacecraft dry mass', fmtNum(sc.dryMassKg, 1) + ' kg']);
    var prop = exp.propagation || {};
    if (prop.stopCondition) rows.push(['Stop condition', prop.stopCondition.type + ' ' + prop.stopCondition.value]);
    if (prop.integrator) rows.push(['Integrator', prop.integrator]);
    var mans = exp.maneuvers || [];
    rows.push(['Maneuvers', String(mans.length)]);
    return rows;
  }

  // Rows for the Outcome pane: telemetry + validator warnings (3d).
  function outcomeRows(result) {
    var rows = [];
    var pts = trajPoints(result);
    rows.push(['Trajectory points', fmtNum(pts.length)]);
    var els = elementsOf(result);
    if (els.semiMajorAxisKm != null) rows.push(['Semi-major axis', fmtNum(els.semiMajorAxisKm, 3) + ' km']);
    if (els.eccentricity != null) rows.push(['Eccentricity', String(els.eccentricity)]);
    var warns = (result && result.warnings) || [];
    rows.push(['Validator warnings', String(warns.length)]);
    return rows;
  }

  function formatElapsed(secs) {
    secs = Math.max(0, Math.floor(+secs || 0));
    var d = Math.floor(secs / 86400), h = Math.floor((secs % 86400) / 3600), m = Math.floor((secs % 3600) / 60);
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return d + ' d ' + p(h) + ':' + p(m);
  }

  var helpers = {
    STAGES: STAGES,
    fmtNum: fmtNum,
    escapeHtml: escapeHtml,
    stageStates: stageStates,
    hasWarmingEvent: hasWarmingEvent,
    isClarification: isClarification,
    missingFromError: missingFromError,
    errorExplanation: errorExplanation,
    trajPoints: trajPoints,
    pointSpeed: pointSpeed,
    scalePointsToViewBox: scalePointsToViewBox,
    projectPoint: projectPoint,
    understoodRows: understoodRows,
    outcomeRows: outcomeRows,
    formatElapsed: formatElapsed
  };

  try {
    if (typeof globalThis !== 'undefined') globalThis.OrbitLabLive = helpers;
  } catch (e) {}
  try {
    if (typeof module !== 'undefined' && module.exports) module.exports = helpers;
  } catch (e) {}

  // ---------- DOM wiring (browser only) ----------
  if (typeof document === 'undefined') return;

  function $(id) { return document.getElementById(id); }

  var adapter = (typeof globalThis !== 'undefined' && globalThis.OrbitLabAdapter) ||
    (typeof window !== 'undefined' && window.OrbitLabAdapter) || null;

  // Clock (keeps the header clock live; static text stays if this fails).
  function tickClock() {
    try {
      var now = new Date();
      var d = $('clockDate'), t = $('clockTime');
      if (d) d.textContent = now.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
      if (t) t.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {}
  }

  // Tabs (Chat / Understood / Outcome / Graph / Physics).
  function selectTab(name) {
    var btns = document.querySelectorAll('#tabs button');
    for (var i = 0; i < btns.length; i++) {
      var active = btns[i].getAttribute('data-tab') === name;
      if (active) btns[i].classList.add('active'); else btns[i].classList.remove('active');
    }
    ['chat', 'understood', 'outcome', 'graph', 'physics'].forEach(function (k) {
      var pane = $('pane-' + k);
      if (pane) pane.hidden = (k !== name);
    });
  }

  // ---- run state ----
  var lastTrajectory = [];
  var lastFit = null;
  var replayIdx = 0;
  var replayTimer = null;
  var replaySpeed = 4;
  var originalText = '';
  var threadEl = null;

  function statusPill(mode, text) {
    var pill = $('runStatus'), label = $('runStatusText');
    if (label) label.textContent = text;
    if (!pill) return;
    if (mode === 'fail') {
      pill.style.borderColor = 'rgba(255,122,122,0.6)';
      pill.style.color = '#ff8a8a';
    } else if (mode === 'run') {
      pill.style.borderColor = 'rgba(79,134,255,0.6)';
      pill.style.color = '#9ec1ff';
    } else {
      pill.style.borderColor = '';
      pill.style.color = '';
    }
  }

  function renderStageStrip(states) {
    var strip = $('stageStrip');
    if (!strip) return;
    var html = '';
    STAGES.forEach(function (s) {
      var st = (states && states[s]) || 'pending';
      var mark = st === 'done' ? ' ✓' : st === 'fail' ? ' ✕' : st === 'active' ? ' …' : '';
      html += '<span class="stg ' + st + '">' + escapeHtml(s) + escapeHtml(mark) + '</span>';
    });
    strip.innerHTML = html;
  }

  function addUserMsg(text) {
    if (!threadEl) return;
    var div = document.createElement('div');
    div.className = 'msg-user';
    div.textContent = text;
    threadEl.appendChild(div);
  }

  function addBanner(kind, title, bodyHtml, extraHtml) {
    if (!threadEl) return null;
    var div = document.createElement('div');
    div.className = 'banner' + (kind ? ' ' + kind : '');
    div.innerHTML = '<div class="bt"><span>' + escapeHtml(title) + '</span></div>' +
      '<div class="bb">' + bodyHtml + '</div>' + (extraHtml || '');
    threadEl.appendChild(div);
    try { div.scrollIntoView({ block: 'nearest' }); } catch (e) {}
    return div;
  }

  function ministatsHtml(items) {
    var html = '<div class="ministats">';
    items.forEach(function (it) {
      html += '<div class="ministat"><div class="l">' + escapeHtml(it[0]) + '</div><div class="v">' +
        escapeHtml(it[1]) + '</div></div>';
    });
    return html + '</div>';
  }

  function rowsHtml(rows) {
    var html = '';
    rows.forEach(function (r) {
      html += '<div class="frow"><div><div class="fl">' + escapeHtml(r[0]) + '</div>' +
        '<div class="fv">' + escapeHtml(r[1]) + '</div></div></div>';
    });
    return html;
  }

  // ---- orbit viewer ----
  function renderTrajectory(pts, body) {
    lastTrajectory = pts || [];
    var path = $('trajPath'), ellipse = $('orbitPath');
    if (!path) return;
    if (!lastTrajectory.length) {
      path.setAttribute('opacity', '0');
      if (ellipse) ellipse.setAttribute('opacity', '.8');
      return;
    }
    lastFit = scalePointsToViewBox(lastTrajectory);
    path.setAttribute('points', lastFit.points);
    path.setAttribute('opacity', '.9');
    if (ellipse) ellipse.setAttribute('opacity', '0');
    var tag = $('dataTag');
    if (tag) tag.textContent = 'live data';
    var vk = $('viewKind');
    if (vk) vk.textContent = 'GMAT replay';
    replayIdx = 0;
    drawReplayPoint();
  }

  function drawReplayPoint() {
    var g = $('scDot');
    if (!g || !lastTrajectory.length || !lastFit) return;
    var p = lastTrajectory[replayIdx % lastTrajectory.length];
    if (!isFinite(+p.x_km) || !isFinite(+p.y_km)) return;
    var q = projectPoint(p, lastFit);
    var halo = $('scHalo'), dot = $('scPt');
    if (halo) { halo.setAttribute('cx', q.x.toFixed(1)); halo.setAttribute('cy', q.y.toFixed(1)); }
    if (dot) { dot.setAttribute('cx', q.x.toFixed(1)); dot.setAttribute('cy', q.y.toFixed(1)); }
    var tr = $('cornerTR'), tp = $('tPlus');
    var v = pointSpeed(p);
    if (tr) {
      var alt = (p.altitude_km != null && isFinite(+p.altitude_km))
        ? 'alt ' + fmtNum(+p.altitude_km) + ' km' : 'alt —';
      tr.textContent = alt + ' · v ' + v.toFixed(2) + ' km/s';
    }
    if (tp) tp.textContent = formatElapsed(p.elapsed_secs || 0);
  }

  function stopReplay() {
    if (replayTimer) { clearInterval(replayTimer); replayTimer = null; }
  }

  function startReplay() {
    stopReplay();
    if (!lastTrajectory.length) return;
    replayTimer = setInterval(function () {
      replayIdx = (replayIdx + 1) % lastTrajectory.length;
      drawReplayPoint();
    }, Math.max(30, 400 / replaySpeed));
  }

  // ---- final states ----
  function renderSuccess(result) {
    statusPill('ok', 'Run complete');
    var exp = result.experiment || {};
    var els = elementsOf(result);
    var pts = trajPoints(result);

    var note = $('orbitNote');
    if (note) note.textContent = (exp.centralBody || 'Orbit') + ' · GMAT replay · ' + fmtNum(pts.length) + ' points';

    var bl = $('cornerBL');
    if (bl) {
      var bits = [];
      if (els.eccentricity != null) bits.push('e ' + els.eccentricity);
      if (els.inclinationDeg != null) bits.push('i ' + els.inclinationDeg + '°');
      if (els.semiMajorAxisKm != null) bits.push('a ' + fmtNum(els.semiMajorAxisKm, 1) + ' km');
      bl.textContent = bits.join(' · ') || '—';
    }

    renderTrajectory(pts, exp.centralBody);

    // Chat banner (3d): orbit summary + explanation teaser.
    var mini = [];
    if (els.semiMajorAxisKm != null) mini.push(['Semi-major axis', fmtNum(els.semiMajorAxisKm, 1) + ' km']);
    if (els.eccentricity != null) mini.push(['Eccentricity', String(els.eccentricity)]);
    mini.push(['Trajectory points', fmtNum(pts.length)]);
    mini.push(['Warnings', String((result.warnings || []).length)]);
    addBanner('', 'Run complete',
      escapeHtml('The physics check and the GMAT run finished. Key numbers:') + ministatsHtml(mini),
      '<button class="btn-soft" data-goto="physics">See the physics used</button>');

    // Understood pane: the returned experiment JSON fields.
    var u = $('understoodBody');
    if (u) u.innerHTML = rowsHtml(understoodRows(result));

    // Outcome pane: telemetry + validator warnings.
    var o = $('outcomeBody');
    if (o) {
      var warns = result.warnings || [];
      var wHtml = warns.length
        ? '<div>' + warns.map(function (w) {
          return '<div class="frow"><div><div class="fl">warning</div><div class="fv">' +
            escapeHtml(w) + '</div></div></div>';
        }).join('') + '</div>'
        : '<div class="bb" style="color:#7ee0c0">No warnings.</div>';
      o.innerHTML = rowsHtml(outcomeRows(result)) + wHtml;
    }

    // Graph pane: experiment JSON.
    var g = $('graphBody');
    if (g) {
      g.innerHTML = '<div class="bb" style="color:#9aa7c7;margin-bottom:8px">Experiment JSON · ' +
        fmtNum(pts.length) + ' trajectory points</div>' +
        '<pre class="json">' + escapeHtml(JSON.stringify(result.experiment || {}, null, 2)) + '</pre>';
    }

    // Physics pane: explanation text.
    var ph = $('physicsBody');
    if (ph) {
      ph.innerHTML = '<div class="bb" style="white-space:pre-wrap">' +
        escapeHtml(result.explanation || 'No explanation returned.') + '</div>';
    }
  }

  function showClarification(error) {
    var missing = missingFromError(error) || [];
    statusPill('run', 'Needs input');
    var box = $('clarBox'), txt = $('clarText');
    var line = 'This request needs a few more details before it can run: ' +
      missing.map(function (m) { return String(m); }).join(', ') + '.';
    if (box) box.hidden = false;
    if (txt) txt.textContent = line + ' They will be sent together with your original request.';
    addBanner('warn', 'More information needed', escapeHtml(line));
    selectTab('chat');
  }

  function renderFailure(error) {
    statusPill('fail', 'Run failed');
    var stage = (error && error.stage) || 'unknown';
    var msg = (error && error.message) || 'The run did not finish.';
    var code = (error && error.code) || '';
    var expl = errorExplanation(error);
    var html = escapeHtml(msg);
    if (code) html += '<div class="errtext">' + escapeHtml(stage + ' · ' + code) + '</div>';
    if (expl) {
      html += '<div class="bb" style="white-space:pre-wrap;margin-top:6px">' + escapeHtml(expl) + '</div>';
    } else {
      html += '<div class="bb" style="color:#aebad8;margin-top:6px">No explanation was returned for this failure.</div>';
    }
    addBanner('err', 'Run failed at ' + stage, html);
    // A failed run still leaves the panes readable instead of a crashed page (3e).
    var o = $('outcomeBody');
    if (o) o.innerHTML = '<div class="bb">No result — the run failed at stage <b>' +
      escapeHtml(stage) + '</b>. See the chat panel for details.</div>';
  }

  function renderCannotReach(err) {
    statusPill('fail', 'No connection');
    var msg = (err && err.message) || 'cannot reach the server';
    addBanner('err', 'Cannot reach the server', escapeHtml(msg));
  }

  // ---- run flow ----
  function resetForRun() {
    renderStageStrip(stageStates([]));
    var warm = $('warmNote');
    if (warm) warm.hidden = true;
    var box = $('clarBox');
    if (box) box.hidden = true;
    stopReplay();
  }

  function onStreamEvent(ev, events) {
    if (!ev) return;
    if (ev.type === 'model_warming_up') {
      var warm = $('warmNote');
      if (warm) warm.hidden = false;
    }
    if (ev.stage) renderStageStrip(stageStates(events));
  }

  function runRequest(text) {
    if (!adapter) return;
    originalText = text;
    addUserMsg(text);
    resetForRun();
    statusPill('run', 'Running…');
    var events = [];
    adapter.runExperiment(text, function (ev) {
      events.push(ev);
      onStreamEvent(ev, events);
    }).then(function (outcome) {
      var warm = $('warmNote');
      if (warm) warm.hidden = true;
      renderStageStrip(stageStates(outcome.events || events));
      if (outcome.error) {
        if (isClarification(outcome.error)) showClarification(outcome.error);
        else renderFailure(outcome.error);
      } else if (outcome.result) {
        renderSuccess(outcome.result);
      }
    }).catch(function (err) {
      renderCannotReach(err);
    });
  }

  function init() {
    threadEl = $('thread');
    tickClock();
    setInterval(tickClock, 20000);
    renderStageStrip(stageStates([]));

    document.querySelectorAll('#tabs button').forEach(function (b) {
      b.addEventListener('click', function () { selectTab(b.getAttribute('data-tab')); });
    });
    document.querySelectorAll('[data-goto]').forEach(function (b) {
      b.addEventListener('click', function () { selectTab(b.getAttribute('data-goto')); });
    });

    if (!adapter || adapter.isMockMode()) return; // mock: keep today's sample exactly.

    var input = $('promptInput'), send = $('sendBtn');
    function sendCurrent() {
      var v = input ? input.value.trim() : '';
      if (!v) return;
      if (input) input.value = '';
      runRequest(v);
    }
    if (send) send.addEventListener('click', sendCurrent);
    if (input) input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); sendCurrent(); }
    });
    document.querySelectorAll('.chip').forEach(function (c) {
      c.addEventListener('click', function () {
        if (input) { input.value = c.getAttribute('data-text') || ''; input.focus(); }
      });
    });

    var clarSend = $('clarSend');
    if (clarSend) clarSend.addEventListener('click', function () {
      var extra = $('extraInput');
      var v = extra ? extra.value.trim() : '';
      var box = $('clarBox');
      if (box) box.hidden = true;
      if (extra) extra.value = '';
      runRequest((originalText + ' ' + (v || '')).trim());
    });

    var play = $('playBtn'), reset = $('resetBtn');
    if (play) play.addEventListener('click', function () {
      if (replayTimer) stopReplay(); else startReplay();
    });
    if (reset) reset.addEventListener('click', function () {
      replayIdx = 0; drawReplayPoint();
    });
    document.querySelectorAll('[data-speed]').forEach(function (b) {
      b.addEventListener('click', function () {
        replaySpeed = +b.getAttribute('data-speed') || 1;
        var sv = $('speedVal');
        if (sv) sv.textContent = replaySpeed + '×';
        document.querySelectorAll('[data-speed]').forEach(function (x) {
          if (x === b) x.classList.add('on'); else x.classList.remove('on');
        });
        if (replayTimer) startReplay();
      });
    });

    var csv = $('exportCsv');
    if (csv) csv.addEventListener('click', function () {
      if (!lastTrajectory.length) return;
      var lines = ['elapsed_secs,x_km,y_km,z_km,vx_km_s,vy_km_s,vz_km_s,altitude_km'];
      lastTrajectory.forEach(function (p) {
        lines.push([p.elapsed_secs, p.x_km, p.y_km, p.z_km, p.vx_km_s, p.vy_km_s, p.vz_km_s, p.altitude_km]
          .map(function (v) { return v == null ? '' : v; }).join(','));
      });
      try {
        var blob = new Blob([lines.join('\n')], { type: 'text/csv' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'trajectory.csv';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
      } catch (e) {}
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

