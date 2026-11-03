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

  // ===== THE ONE SETTING (STEP 4): where the backend lives =====
  var DEFAULT_API_BASE = 'http://localhost:8000';

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
    return DEFAULT_API_BASE;
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
        try {
          sub = subscribeExperiment(created.id, function (ev) {
            events.push(ev);
            try { if (onEvent) onEvent(ev); } catch (e) {}
            if (ev && ev.type === 'final') {
              if (ev.error) done({ events: events, error: ev.error });
              else done({ events: events, result: ev.result });
            }
          }, function (err) {
            // Fall back to polling the job record once (covers a WS-only failure).
            getExperiment(created.id).then(function (job) {
              if (job && job.status === 'success' && job.result) {
                done({ events: events, result: job.result });
              } else if (job && job.status === 'failed' && job.error) {
                done({ events: events, error: job.error });
              } else {
                reject(err || cannotReach());
              }
            }).catch(function () { reject(err || cannotReach()); });
          });
        } catch (e) {
          reject(e);
        }
        // Safety net: poll once if no final arrives within 5 minutes.
        setTimeout(function () {
          if (settled) return;
          getExperiment(created.id).then(function (job) {
            if (job && job.status === 'success' && job.result) {
              done({ events: events, result: job.result });
            } else if (job && job.status === 'failed' && job.error) {
              done({ events: events, error: job.error });
            }
          }).catch(function () {});
        }, 300000);
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
