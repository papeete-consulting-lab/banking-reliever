/**
 * app.js — Boot logic for the BNK.RLVR.CAP.CHN.001.DSH frontend shell.
 *
 * Responsibilities (TASK-002 scope):
 *   - Parse the query string (`?case_id=`, `?beneficiaireId=`, `?consentement=`).
 *   - Show the branch badge (statically injected by build-time placeholder).
 *   - Render the consent gate when `?consentement=refuse` (scaffold only;
 *     enforcement comes in TASK-003).
 *   - Kick off the 5 s polling loop via api.js#pollDashboard.
 *   - Toggle the empty-state placeholder vs. the dashboard body based on
 *     poll events.
 *   - Show a non-blocking error toast on transient failures.
 *
 * The synthesised view itself (tier card, envelope rows) is deferred to
 * TASK-003 — for now the dashboard body is just the two ordered sections.
 */

import { pollDashboard, resolveJwt } from './api.js';
import { t } from './i18n.js';

// ─── DOM helpers ──────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

function show(id) {
  const el = $(id);
  if (el) el.classList.remove('hidden');
}
function hide(id) {
  const el = $(id);
  if (el) el.classList.add('hidden');
}
function setText(id, text) {
  const el = $(id);
  if (el) el.textContent = text;
}

// ─── Query-string parsing ─────────────────────────────────────

function readParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    caseId: p.get('case_id') || p.get('caseId') || null,
    beneficiaireId: p.get('beneficiaireId') || null, // legacy / future use
    consent: p.get('consentement'), // 'refuse' switches on the gate scaffold
    debug: p.get('debug') === '1',
  };
}

// ─── Apply i18n strings into the DOM (data-i18n="dotted.path") ──

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    const value = t(key, el.textContent);
    if (value) el.textContent = value;
  });
}

// ─── Poll indicator (footer) ──────────────────────────────────

function setPollIndicator(state, message) {
  const el = $('poll-indicator');
  if (!el) return;
  el.dataset.state = state;
  el.textContent = message;
}

// ─── Error toast ──────────────────────────────────────────────

let toastTimer = null;

function showError(message) {
  setText('error-toast-message', message);
  show('error-toast');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => hide('error-toast'), 6000);
}

function dismissError() {
  if (toastTimer) clearTimeout(toastTimer);
  hide('error-toast');
}

// ─── Consent gate scaffold ────────────────────────────────────

function showConsentGate(message) {
  hide('loading');
  hide('empty-state');
  hide('dashboard');
  if (message) setText('consent-message', message);
  show('consent-gate');
}

// ─── Render: empty-state placeholder ──────────────────────────

function renderEmptyState() {
  hide('loading');
  hide('dashboard');
  show('empty-state');
}

// ─── Render: dashboard body (shell only for TASK-002) ─────────

function renderDashboardShell(_view) {
  // TASK-002: dashboard body is empty — sections exist but no data is
  // injected. TASK-003 will replace this stub with real synthesis.
  hide('loading');
  hide('empty-state');
  show('dashboard');
}

// ─── Poll event handler ───────────────────────────────────────

function handlePollEvent(event) {
  switch (event.kind) {
    case 'data':
      renderDashboardShell(event.body);
      setPollIndicator('ok', t('poll.ok'));
      break;

    case 'empty':
      // Both `200-with-null-fields` and `404` route here — by design we
      // NEVER surface a raw 404 (DoD criterion).
      renderEmptyState();
      setPollIndicator('ok', t('poll.ok'));
      break;

    case 'unchanged':
      // First 304 after a state — confirms freshness without redrawing.
      setPollIndicator('ok', t('poll.ok'));
      break;

    case 'fallback':
      // 30s+ of failures: render the stub so the shell remains demoable.
      renderDashboardShell(event.body);
      setPollIndicator('stale', t('poll.fallback'));
      showError(t('errors.fallback'));
      break;

    case 'error':
      if (event.status === 401) {
        setPollIndicator('error', t('poll.error'));
        showError(t('errors.auth'));
      } else if (event.status === 0) {
        setPollIndicator('error', t('poll.error'));
        if (event.transient) showError(t('errors.network'));
      } else {
        setPollIndicator('error', t('poll.error'));
        if (event.transient) showError(t('errors.server'));
      }
      break;

    default:
      // Unknown kind — log and keep going.
      // eslint-disable-next-line no-console
      console.warn('[BNK.RLVR.CAP.CHN.001.DSH] unknown poll event', event);
  }
}

// ─── Branch badge (defensive — replaces the build-time placeholder) ──

function applyBranchBadge() {
  // The branch slug is baked into index.html at scaffold time. If the host
  // page exposes `window.__BRANCH_SLUG__`, that takes precedence so a dev
  // harness can override per-iframe.
  const el = $('branch-badge');
  if (!el) return;
  if (typeof window.__BRANCH_SLUG__ === 'string' && window.__BRANCH_SLUG__) {
    el.textContent = window.__BRANCH_SLUG__;
  }
}

// ─── Boot ─────────────────────────────────────────────────────

let pollHandle = null;

async function init() {
  applyI18n();
  applyBranchBadge();

  const { caseId, consent } = readParams();

  // Consent-gate scaffold (DoD requirement #5). Enforcement comes in TASK-003.
  if (consent === 'refuse') {
    showConsentGate(t('consent.refused'));
    return;
  }

  // No case_id? Show the empty-state placeholder and a hint via toast.
  if (!caseId) {
    renderEmptyState();
    setPollIndicator('stale', t('poll.waiting'));
    return;
  }

  // Warn (non-blocking) if no JWT is present — every poll will 401 otherwise.
  if (!resolveJwt()) {
    showError(t('errors.auth'));
  }

  setPollIndicator('stale', t('poll.waiting'));

  // Kick off polling; the callback drives the UI.
  pollHandle = pollDashboard(caseId, handlePollEvent);
}

// ─── Public surface (for inline onclick handlers and tests) ──

window.App = {
  reload() {
    window.location.reload();
  },
  retryConsent() {
    // For now: just reload without the `?consentement=refuse` flag.
    const url = new URL(window.location.href);
    url.searchParams.delete('consentement');
    window.location.href = url.toString();
  },
  dismissError,
  /** Exposed for tests — yields the current poll handle. */
  _pollHandle() {
    return pollHandle;
  },
};

// ─── Startup ──────────────────────────────────────────────────

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
