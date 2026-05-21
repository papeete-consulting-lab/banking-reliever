/**
 * api.js — BFF client for BNK.RLVR.CAP.CHN.001.DSH.
 *
 * Wraps `fetch` with:
 *   - JWT bearer token attached on every request
 *   - `If-None-Match` for ETag-driven 304 responses
 *   - Configurable timeout (default 8s)
 *   - A polling loop that fires the callback ONLY on state changes
 *     (200 with a new ETag, 404 transition, or error transition)
 *   - A stub-data fallback when the BFF has been unhealthy for more than
 *     STUB_FALLBACK_AFTER_MS (default 30s)
 *
 * Contract (process/BNK.RLVR.CAP.CHN.001.DSH/api.yaml):
 *   GET /capabilities/chn/001/dsh/cases/{case_id}/dashboard
 *     200 -> DashboardView (PRJ.CHN.001.DSH.DASHBOARD_VIEW)
 *     304 -> no body, ETag matched (poll no-op)
 *     404 -> aggregate not yet materialised  (rendered as empty-state)
 *     401 -> JWT invalid / expired
 *
 * No third-party libraries; vanilla ES module.
 */

import { buildStubDashboardView, buildStubEmptyDashboardView } from './stub-data.js';

// ─── Config ───────────────────────────────────────────────────

export const API_CONFIG = Object.freeze({
  baseUrl: (typeof window !== 'undefined' && window.__BFF_BASE_URL__) || '',
  basePath: '/capabilities/chn/001/dsh',
  pollIntervalMs: 5000, // matches `cache.max_age: PT5S` in api.yaml
  requestTimeoutMs: 8000,
  stubFallbackAfterMs:
    (typeof window !== 'undefined' && window.__STUB_FALLBACK_AFTER_MS__) || 30_000,
});

// ─── JWT resolution ───────────────────────────────────────────

/**
 * Resolves the bearer token in this priority order:
 *   1. `window.__JWT__`      (set by a dev harness or e2e test)
 *   2. `localStorage["jwt"]` (sticky between page reloads)
 *   3. `null`                (the BFF will then 401; we surface a friendly toast)
 *
 * Centralising this in api.js means the rest of the app never has to think
 * about token plumbing.
 */
export function resolveJwt() {
  if (typeof window === 'undefined') return null;
  if (typeof window.__JWT__ === 'string' && window.__JWT__) return window.__JWT__;
  try {
    const stored = window.localStorage && window.localStorage.getItem('jwt');
    if (stored) return stored;
  } catch (_e) {
    // localStorage may be denied (privacy mode) — fall through.
  }
  return null;
}

// ─── Errors ───────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(message, status, cause) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.cause = cause;
  }
}

// ─── Low-level fetch wrapper ──────────────────────────────────

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs || API_CONFIG.requestTimeoutMs,
  );
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Fetches the dashboard view. Returns a tagged-status object:
 *   { status: 200, body: <DashboardView>, etag: <string|null> }
 *   { status: 304 }                                              // unchanged
 *   { status: 404 }                                              // not materialised
 *   { status: <other>, error: <ApiError> }
 *
 * Never throws on HTTP-level failures — the caller decides whether to
 * fall back to stub data or to surface a toast.
 */
export async function fetchDashboard(caseId, etag = null) {
  if (!caseId) throw new ApiError('case_id is required', 400);

  const url =
    API_CONFIG.baseUrl +
    API_CONFIG.basePath +
    `/cases/${encodeURIComponent(caseId)}/dashboard`;

  const headers = {
    Accept: 'application/json',
  };
  const jwt = resolveJwt();
  if (jwt) headers.Authorization = `Bearer ${jwt}`;
  if (etag) headers['If-None-Match'] = etag;

  let res;
  try {
    res = await fetchWithTimeout(url, { method: 'GET', headers });
  } catch (e) {
    return {
      status: 0,
      error: new ApiError('network', 0, e),
    };
  }

  if (res.status === 304) {
    return { status: 304 };
  }
  if (res.status === 404) {
    return { status: 404 };
  }
  if (res.status === 401) {
    return { status: 401, error: new ApiError('auth', 401) };
  }
  if (!res.ok) {
    return { status: res.status, error: new ApiError('server', res.status) };
  }

  let body = null;
  try {
    body = await res.json();
  } catch (e) {
    return { status: 502, error: new ApiError('malformed JSON', 502, e) };
  }
  const newEtag = res.headers.get('ETag');
  return { status: 200, body, etag: newEtag };
}

// ─── Polling loop ─────────────────────────────────────────────

/**
 * Drives a 5 s polling loop. Fires `callback({ kind, ... })` ONLY on state
 * change; identical successive 304s are silent. Returns a `stop()` handle.
 *
 * `kind` values:
 *   - 'data'         — `{ kind: 'data', body, etag }` (200 / new content)
 *   - 'empty'        — `{ kind: 'empty', reason: '404'|'200-null' }`
 *   - 'unchanged'    — `{ kind: 'unchanged' }` (first 304 after a state)
 *   - 'error'        — `{ kind: 'error', error, transient: boolean }`
 *   - 'fallback'     — `{ kind: 'fallback', body }` (stub kicked in)
 *
 * The callback contract is intentionally chatty so the UI can drive a
 * poll-indicator (synced / stale / error / fallback) without polling the
 * client itself.
 */
export function pollDashboard(caseId, callback, opts = {}) {
  const intervalMs = opts.intervalMs || API_CONFIG.pollIntervalMs;
  const stubFallbackAfterMs =
    opts.stubFallbackAfterMs || API_CONFIG.stubFallbackAfterMs;

  let etag = null;
  let lastKind = null;
  let firstFailureAt = null;
  let fallbackActive = false;
  let stopped = false;
  let timer = null;

  function emit(event) {
    // Suppress duplicate consecutive 'unchanged' events to keep the UI quiet.
    if (event.kind === 'unchanged' && lastKind === 'unchanged') return;
    lastKind = event.kind;
    try {
      callback(event);
    } catch (cbErr) {
      // Never let a UI bug kill the polling loop.
      // eslint-disable-next-line no-console
      console.error('[BNK.RLVR.CAP.CHN.001.DSH] poll callback threw', cbErr);
    }
  }

  function isEmptyView(body) {
    if (!body) return true;
    // PRJ.CHN.001.DSH.DASHBOARD_VIEW — empty when all snapshot fields are null
    // and open_envelopes is empty (INV.DSH.006 lazy-materialisation case).
    return (
      body.current_tier_code == null &&
      body.current_score == null &&
      (!Array.isArray(body.open_envelopes) || body.open_envelopes.length === 0)
    );
  }

  async function tick() {
    if (stopped) return;
    const res = await fetchDashboard(caseId, etag);

    if (res.status === 200) {
      etag = res.etag || etag;
      firstFailureAt = null;
      if (fallbackActive) {
        fallbackActive = false;
      }
      if (isEmptyView(res.body)) {
        emit({ kind: 'empty', reason: '200-null', body: res.body });
      } else {
        emit({ kind: 'data', body: res.body, etag });
      }
    } else if (res.status === 304) {
      firstFailureAt = null;
      emit({ kind: 'unchanged' });
    } else if (res.status === 404) {
      // Aggregate not yet materialised — empty state, NOT an error.
      firstFailureAt = null;
      etag = null;
      emit({ kind: 'empty', reason: '404' });
    } else {
      // Some kind of failure (0 = network, 401, 5xx, 502 malformed).
      const now = Date.now();
      if (firstFailureAt == null) firstFailureAt = now;
      const stale = now - firstFailureAt;

      if (stale >= stubFallbackAfterMs && !fallbackActive) {
        fallbackActive = true;
        emit({ kind: 'fallback', body: buildStubDashboardView(caseId) });
      } else {
        emit({
          kind: 'error',
          error: res.error,
          status: res.status,
          transient: !fallbackActive,
        });
      }
    }
  }

  function loop() {
    if (stopped) return;
    tick().finally(() => {
      if (stopped) return;
      timer = setTimeout(loop, intervalMs);
    });
  }

  // Kick off immediately, then on the cadence.
  loop();

  return {
    stop() {
      stopped = true;
      if (timer) clearTimeout(timer);
    },
    /** Exposed for tests — force an immediate refresh. */
    refreshNow() {
      if (timer) clearTimeout(timer);
      loop();
    },
  };
}

// ─── Convenience for the offline demo path ────────────────────

/**
 * Returns a fresh stub DashboardView. Exported so the dev harness and the
 * test agent can populate the DOM without a live BFF.
 */
export function getStubView(caseId, { empty = false } = {}) {
  return empty ? buildStubEmptyDashboardView(caseId) : buildStubDashboardView(caseId);
}

// ─── Global handle (testability contract) ─────────────────────

// The test agent overrides these via Playwright's `addInitScript()`. Keep
// the API minimal — anything not here is an implementation detail.
if (typeof window !== 'undefined') {
  window.BeneficiaryDashboardApi = {
    fetchDashboard,
    pollDashboard,
    resolveJwt,
    getStubView,
    ApiError,
    API_CONFIG,
  };
}
