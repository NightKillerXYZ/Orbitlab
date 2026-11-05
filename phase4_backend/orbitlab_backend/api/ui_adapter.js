/*
 * OrbitLab UI adapter — the ONLY place the UI talks to the backend.
 *
 * STEP 4 — one setting: the API address lives in DEFAULT_API_BASE below.
 * Change that single constant to repoint the whole UI. Without editing code
 * it can be overridden (first set wins) by:
 *   - window.ORBITLAB_API_BASE            (browser, set before this script)
 *   - ORBITLAB_API_BASE env var           (Node / bundled builds)
 *   - VITE_API_BASE env var               (Vite builds)
 *
 * MOCK switch: ORBITLAB_USE_MOCK below (default false). Without editing code
 * it can be overridden by window.ORBITLAB_USE_MOCK, the "?mock=1" URL query
 * parameter, or the ORBITLAB_USE_MOCK / VITE_USE_MOCK env vars ("true").
 * Mock mode behaves exactly as before: createExperiment returns
 * {id: "mock-id"}, getExperiment returns {status:"success",result:{mock:true}},
 * and subscribeExperiment fires one {type:"stage_completed",stage:"mock"} event.
 *
 * Plain script, no modules: load with a normal <script src="...ui_adapter.js">
 * tag (file:// safe) or with require() from Node. Everything is exposed as
 * globalThis.OrbitLabAdapter.
 */
(function () {
  'use strict';

  // ===== THE ONE SETTING: where the backend lives =====
  // Empty means same origin (relative URLs). When this script runs from a
  // page served over http(s) with no explicit override, the page's own
  // origin is used, so no localhost port is ever hard-coded. The
  // localhost fallback below only applies to file:// and Node contexts.
  var DEFAULT_API_BASE = '';
  var LOCALHOST_FALLBACK = 'http://localhost:8000';

  // MOCK switch (kept working; mock output unchanged).
  var ORBITLAB_USE_MOCK = false;

  var STAGES = ['extract', 'interpret', 'verify', 'validate', 'compile', 'simulate', 'parse', 'explain'];

  function readEnv(name) {
    try {
      if (typeof process !== 'undefined' && process && process.env && process.env[name]) {
        return process.env[name];
      }
    } catch (e) {}
    return undefined;
  }

  function detectApiBase() {
    try {
      if (typeof window !== 'undefined' && window && window.ORBITLAB_API_BASE) {
        return window.ORBITLAB_API_BASE;
      }
    } catch (e) {}
    var fromEnv = readEnv('ORBITLAB_API_BASE') || readEnv('VITE_API_BASE');
    if (fromEnv) return fromEnv;
    if (DEFAULT_API_BASE) return DEFAULT_API_BASE;
    // Same origin when served over http(s); localhost fallback otherwise.
    try {
      if (typeof window !== 'undefined' && window && window.location &&
          /^https?:$/.test(window.location.protocol) && window.location.origin) {
        return window.location.origin;
      }
    } catch (e) {}
    return LOCALHOST_FALLBACK;
  }

  function detectMockMode() {
    try {
      if (typeof window !== 'undefined' && window) {
        if (typeof window.ORBITLAB_USE_MOCK !== 'undefined') {
          return window.ORBITLAB_USE_MOCK === true || window.ORBITLAB_USE_MOCK === 'true';
        }
        if (window.location && window.location.search) {
          var m = /[?&]mock=([^&]*)/.exec(window.location.search);
          if (m) return m[1] === '1' || m[1] === 'true';
        }
      }
    } catch (e) {}
    var flag = readEnv('ORBITLAB_USE_MOCK') || readEnv('VITE_USE_MOCK');
    if (typeof flag !== 'undefined') return flag === 'true' || flag === '1';
    return ORBITLAB_USE_MOCK;
  }

  var apiBaseOverride = null;
  var mockOverride = null;

  function getApiBase() {
    if (apiBaseOverride) return apiBaseOverride;
    return detectApiBase();
  }

  function isMockMode() {
    if (mockOverride !== null) return mockOverride;
    return detectMockMode();
  }

  function configure(opts) {
    opts = opts || {};
    if (opts.apiBase) apiBaseOverride = opts.apiBase;
    if (typeof opts.useMock !== 'undefined') mockOverride = !!opts.useMock;
  }

  function wsUrl(path) {
    return getApiBase().replace(/^http/, 'ws') + path;
  }

  function cannotReach() {
    return new Error('cannot reach the server at ' + getApiBase() + ' — is the backend running?');
  }

  function fetchImpl() {
    if (typeof fetch !== 'undefined') return fetch;
    try {
      if (typeof require !== 'undefined') return require('node-fetch');
    } catch (e) {}
    throw cannotReach();
  }

  function WebSocketImpl() {
    if (typeof WebSocket !== 'undefined') return WebSocket;
    try {
      if (typeof require !== 'undefined') return require('ws');
    } catch (e) {}
    return null;
  }

  async function checkHealth() {
    if (isMockMode()) return true;
    try {
      var res = await fetchImpl()(getApiBase() + '/api/health');
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  async function createExperiment(text) {
    if (isMockMode()) {
      return { id: 'mock-id' };
    }
    var res;
    try {
      res = await fetchImpl()(getApiBase() + '/api/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
    } catch (e) {
      throw cannotReach();
    }
    if (!res.ok) throw new Error('create failed ' + res.status);
    return await res.json();
  }

  async function getExperiment(id) {
    if (isMockMode()) return { status: 'success', result: { mock: true } };
    var res;
    try {
      res = await fetchImpl()(getApiBase() + '/api/experiments/' + encodeURIComponent(id));
    } catch (e) {
      throw cannotReach();
    }
    if (!res.ok) throw new Error('get failed ' + res.status);
    return await res.json();
  }

  function subscribeExperiment(id, onEvent, onError) {
    if (isMockMode()) {
      var t = setTimeout(function () {
        try {
          onEvent({ type: 'stage_completed', stage: 'mock' });
        } catch (e) {}
      }, 100);
      return { close: function () { clearTimeout(t); } };
    }
    var WS = WebSocketImpl();
    if (!WS) throw cannotReach();
    var ws;
    try {
      ws = new WS(wsUrl('/ws/experiments/' + encodeURIComponent(id)));
    } catch (e) {
      throw cannotReach();
    }
    ws.onmessage = function (ev) {
      var data = ev && ev.data !== undefined ? ev.data : ev;
      try {
        onEvent(typeof data === 'string' ? JSON.parse(data) : data);
      } catch (e) {}
    };
    ws.onerror = function () {
      if (onError) {
        try { onError(cannotReach()); } catch (e) {}
      }
    };
    return {
      close: function () { try { ws.close(); } catch (e) {} },
      _ws: ws
    };
  }

  // Convenience: create + stream events until the final result/error arrives.
  // Resolves {events, result} or {events, error}. Rejects only when the
  // server cannot be reached at all.
  function runExperiment(text, onEvent) {
    return createExperiment(text).then(function (created) {
      return new Promise(function (resolve, reject) {
        var events = [];
        var sub;
        var settled = false;
        function done(outcome) {
          if (settled) return;
          settled = true;
          try { sub.close(); } catch (e) {}
          resolve(outcome);
        }
        var pollTimer = null;
        function stopPolling() {
          try { if (pollTimer) clearInterval(pollTimer); } catch (e) {}
          pollTimer = null;
        }
        var origDone = done;
        done = function (outcome) {
          stopPolling();
          origDone(outcome);
        };
        function pollOnce(onMissing) {
          getExperiment(created.id).then(function (job) {
            if (job && job.status === 'success' && job.result) {
              done({ events: events, result: job.result });
            } else if (job && job.status === 'failed' && job.error) {
              done({ events: events, error: job.error });
            } else if (onMissing) {
              onMissing();
            }
          }).catch(function () {});
        }
        try {
          sub = subscribeExperiment(created.id, function (ev) {
            events.push(ev);
            try { if (onEvent) onEvent(ev); } catch (e) {}
            if (ev && ev.type === 'final') {
              if (ev.error) done({ events: events, error: ev.error });
              else done({ events: events, result: ev.result });
            }
          }, function () {
            // WS failed: poll immediately, then keep polling below.
            pollOnce();
          });
        } catch (e) {
          reject(e);
          return;
        }
        // If the socket drops or closes early without a final, poll the job
        // record every 2 seconds until it finishes. Safety net: give up and
        // report unreachable after 10 minutes.
        var polls = 0;
        pollTimer = setInterval(function () {
          if (settled) return;
          polls += 1;
          if (polls > 300) {
            try { sub.close(); } catch (e) {}
            stopPolling();
            reject(cannotReach());
            return;
          }
          pollOnce();
        }, 2000);
      });
    });
  }

  var api = {
    STAGES: STAGES,
    getApiBase: getApiBase,
    isMockMode: isMockMode,
    configure: configure,
    checkHealth: checkHealth,
    createExperiment: createExperiment,
    getExperiment: getExperiment,
    subscribeExperiment: subscribeExperiment,
    runExperiment: runExperiment
  };

  try {
    if (typeof globalThis !== 'undefined') globalThis.OrbitLabAdapter = api;
  } catch (e) {}
  try {
    if (typeof window !== 'undefined') window.OrbitLabAdapter = api;
  } catch (e) {}
  try {
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
  } catch (e) {}
})();
